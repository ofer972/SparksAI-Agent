import json
import time
from typing import Any, Dict, Tuple
from datetime import datetime, timezone

import config
from api_client import APIClient
from utils_audit import call_audit_service
from utils_logging import log
from utils_processing import (
    extract_recommendations,
    extract_review_section,
    extract_text_and_json,
    fetch_pi_data_for_analysis,
    get_average_sprint_velocity_per_team_for_analysis,
    get_epics_average_velocity_for_analysis,
    get_epics_by_pi_for_analysis,
    get_pi_status_for_today_by_team_for_analysis,
    process_llm_response_and_save_ai_card,
    process_llm_with_two_step_fallback,
    save_recommendations_from_json,
)


def _extract_pi(job: Dict[str, Any]) -> str | None:
    """Extract PI name from job payload."""
    if isinstance(job.get("pi"), str):
        return job["pi"]
    jd = job.get("job_data")
    try:
        if isinstance(jd, str):
            jd = json.loads(jd)
        if isinstance(jd, dict) and isinstance(jd.get("pi"), str):
            return jd["pi"]
    except Exception:
        pass
    return None


def _extract_pi_dates(pi_status_obj: Dict[str, Any] | None) -> Tuple[str | None, str | None]:
    """Extract PI start and end dates from PI status object.
    
    Args:
        pi_status_obj: PI status data dict (can contain 'data' list or be the list directly)
        
    Returns:
        Tuple of (start_date, end_date) or (None, None) if not found
    """
    if not pi_status_obj:
        return None, None
    
    # Extract the actual data from response structure
    status_list = None
    if isinstance(pi_status_obj, dict):
        # Handle API response format: {"success": true, "data": [...], ...}
        if "data" in pi_status_obj and isinstance(pi_status_obj["data"], list):
            status_list = pi_status_obj["data"]
        else:
            # If it's a dict but no 'data' key, treat it as a single status object
            status_list = [pi_status_obj]
    elif isinstance(pi_status_obj, list):
        status_list = pi_status_obj
    
    if not status_list or len(status_list) == 0:
        return None, None
    
    # Get the first item (should only be one for a specific PI)
    status_obj = status_list[0]
    if isinstance(status_obj, dict):
        # Try common date field names
        start_date = status_obj.get("pi_start_date") or status_obj.get("start_date") or status_obj.get("pi_start")
        end_date = status_obj.get("pi_end_date") or status_obj.get("end_date") or status_obj.get("pi_end")
        return start_date, end_date
    
    return None, None


def _format_pi_status_fields(pi_status_obj: Dict[str, Any] | None) -> str:
    """Format specific PI status fields for LLM input.
    
    Args:
        pi_status_obj: PI status data dict (can contain 'data' list or be the list directly)
        
    Returns:
        Formatted string with specific fields in "field_name = value" format
    """
    if not pi_status_obj:
        return ""
    
    # Extract the actual data from response structure
    status_list = None
    if isinstance(pi_status_obj, dict):
        # Handle API response format: {"success": true, "data": [...], ...}
        if "data" in pi_status_obj and isinstance(pi_status_obj["data"], list):
            status_list = pi_status_obj["data"]
        else:
            # If it's a dict but no 'data' key, treat it as a single status object
            status_list = [pi_status_obj]
    elif isinstance(pi_status_obj, list):
        status_list = pi_status_obj
    
    if not status_list or len(status_list) == 0:
        return ""
    
    # Get the first item (should only be one for a specific PI)
    status_obj = status_list[0]
    if not isinstance(status_obj, dict):
        return ""
    
    # Fields to extract and format
    fields_to_include = [
        "pi_name",
        "pi_start_date",
        "pi_end_date",
        "remaining_epics",
        "ideal_remaining",
        "total_issues",
        "progress_delta_pct_status",
    ]
    
    parts = []
    for field in fields_to_include:
        value = status_obj.get(field)
        if value is not None:
            parts.append(f"{field} = {value}")
    
    return "\n".join(parts) if parts else ""


def process(job: Dict[str, Any]) -> Tuple[bool, str]:
    """Process PI Planning Gaps job type.
    
    Args:
        job: Job payload dictionary
        
    Returns:
        Tuple of (success, result_text)
    """
    start_time = time.time()
    client = APIClient()

    job_id = job.get("job_id") or job.get("id")
    job_type = job.get("job_type", "PI Planning Gaps")
    pi = _extract_pi(job)
    if not pi:
        return False, "Missing PI in job payload"

    # Extract team_name or group_name from job and determine is_group flag
    team_name = job.get("team_name")
    group_name = job.get("group_name")
    
    # Determine which one to use
    if group_name:
        team_param = group_name
        is_group = True
    elif team_name:
        team_param = team_name
        is_group = False
    else:
        team_param = None
        is_group = False

    # Fetch PI status to get dates
    _, pi_status_obj, _ = fetch_pi_data_for_analysis(
        client=client,
        pi=pi,
        team_name=team_param,
        is_group=is_group,
        include_transcript=False,  # Don't need transcript
    )
    
    # Extract PI dates
    pi_start_date, pi_end_date = _extract_pi_dates(pi_status_obj)
    
    # Format PI status fields for LLM
    pi_status_fields_formatted = _format_pi_status_fields(pi_status_obj)
    
    # Get current date
    current_date = datetime.now(timezone.utc).date().isoformat()

    # Fetch PI status by team and format as table
    pi_status_by_team_formatted = get_pi_status_for_today_by_team_for_analysis(
        client=client,
        pi=pi,
        team_name=team_param,
        is_group=is_group,
    )

    # Fetch average sprint velocity per team and format as table
    velocity_formatted = get_average_sprint_velocity_per_team_for_analysis(
        client=client,
        pi=pi,
        num_sprints=5,  # Default: last 5 sprints
        team_name=team_param,
        is_group=is_group,
    )

    # Fetch epics by PI and format as table
    epics_formatted = get_epics_by_pi_for_analysis(
        client=client,
        pi=pi,
        team_name=team_param,
        is_group=is_group,
    )

    # Fetch epics average velocity and format
    epics_velocity_formatted = get_epics_average_velocity_for_analysis(
        client=client,
        pi=pi,
        team_name=team_param,
        is_group=is_group,
        num_pis=3,  # Default: analyze last 3 completed PIs
    )

    # Build data string (without prompt)
    parts = ["=== PI PLANNING GAPS DATA ==="]
    parts.append(f"PI: {pi}")
    if pi_start_date:
        parts.append(f"PI Start Date: {pi_start_date}")
    if pi_end_date:
        parts.append(f"PI End Date: {pi_end_date}")
    parts.append(f"Current Date: {current_date}")
    parts.append("")
    
    # Add PI status fields from get-pi-status-for-today endpoint
    if pi_status_fields_formatted:
        parts.append("=== PI STATUS FOR TODAY ===")
        parts.append(pi_status_fields_formatted)
        parts.append("")
    
    # Add PI status by team (formatted as markdown table)
    parts.append(pi_status_by_team_formatted)
    parts.append("")
    
    # Add average sprint velocity by team (formatted as markdown table)
    parts.append(velocity_formatted)
    parts.append("")
    
    # Add epics by PI (formatted as markdown table)
    parts.append(epics_formatted)
    parts.append("")
    
    # Add epics average velocity
    parts.append(epics_velocity_formatted)
    parts.append("")
    
    data_string = "\n".join(parts)
    
    # Prepare job_params for audit service
    job_params = {
        "team_name": job.get("team_name"),
        "group_name": job.get("group_name"),
        "pi": pi,
        "job_id": int(job_id) if job_id is not None else None,
        "job_type": job_type,
    }
    
    # Prepare metadata for LLM calls
    metadata = {"pi_name": pi, "team_name": job.get("team_name")}
    
    # Call generic LLM processing function (handles prompt fetching and two-step mode)
    ok, llm_answer, tokens_used, llm_metadata = process_llm_with_two_step_fallback(
        client=client,
        data_string=data_string,
        prompt_base_name="PI Planning Gaps",
        prompt_email="PIAgent",
        job_type=job_type,
        job_id=int(job_id) if job_id is not None else None,
        job_params=job_params,
        metadata=metadata,
        start_time=start_time,
    )
    
    if not ok:
        return False, "LLM processing failed"

    # Print first 500 characters of LLM response
    preview = llm_answer[:500] if llm_answer else ""
    log(int(job_id) if job_id is not None else None, f"\n📥 LLM Response Preview (first 500 chars):\n{preview}{'...' if len(llm_answer) > 500 else ''}\n")

    # Extract structured content from LLM response and save card
    log(int(job_id) if job_id is not None else None, "📋 EXTRACTING STRUCTURED CONTENT FROM LLM RESPONSE")
    
    description, full_info_truncated, raw_json_string, card_id = process_llm_response_and_save_ai_card(
        client=client,
        llm_answer=llm_answer,
        team_name=team_name,
        job_id=int(job_id) if job_id is not None else None,
        card_config={
            "pi": pi,
            "card_name": "PI Planning Gaps Analysis",
            "source": "PI",
        },
        job_type=job_type,
        card_type="PI",
        extract_content_fn=extract_review_section,
        group_name=group_name,
    )
    
    # Extract recommendations_json from LLM response for recommendations saving
    _, _, recommendations_json, _, _ = extract_text_and_json(llm_answer)

    # Extract and create recommendations
    log(int(job_id) if job_id is not None else None, "📋 EXTRACTING AND SAVING RECOMMENDATIONS")
    
    today = datetime.now(timezone.utc).date().isoformat()
    
    # First try to extract recommendations from JSON if available
    # For recommendations, team_name should actually be the quarter (PI)
    recommendations_saved = save_recommendations_from_json(
        client=client,
        recommendations_json=recommendations_json,
        team_name_or_pi=pi,  # Use PI name as team_name for recommendations
        today=today,
        full_info_truncated=full_info_truncated,
        max_count=2,
        job_id=int(job_id) if job_id is not None else None,
        source_ai_summary_id=card_id,
    )
    
    # Fallback to text-based extraction if no JSON recommendations found
    if recommendations_saved == 0:
        log(int(job_id) if job_id is not None else None, "⚠️ No recommendations from JSON found - falling back to text extraction")
        recs = extract_recommendations(llm_answer, max_count=2)
        for rec_text in recs:
            # For recommendations, team_name should actually be the quarter (PI)
            rec_payload = {
                "team_name": pi,
                "action_text": rec_text,
                "date": today,
                "priority": "High",
                "status": "Proposed",
                "full_information": full_info_truncated,
                "source_job_id": int(job_id) if job_id is not None else None,
                "source_ai_summary_id": card_id,
            }
            rsc, rresp = client.create_recommendation(rec_payload)
            if rsc >= 300:
                log(int(job_id) if job_id is not None else None, f"⚠️ Create recommendation failed: {rsc} {rresp}")
            else:
                recommendations_saved += 1
                log(int(job_id) if job_id is not None else None, f"🧩 Recommendation: priority='High' status='Proposed' text='{rec_text[:120]}'")
            
            if recommendations_saved >= 2:
                break

    # Create detailed result text with full LLM response
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    team_name = job.get("team_name", "Unknown")
    use_two_step_mode = llm_metadata.get("use_two_step_mode", False)
    
    if use_two_step_mode:
        formatted_first = llm_metadata.get("formatted_first", "")
        formatted_second = llm_metadata.get("formatted_second", "")
        result_text = f"""PI Planning Gaps Analysis Completed (Two-Step Process)

PI: {pi}
Team: {team_name}
Job ID: {job_id}
Timestamp: {timestamp}

First Call Input: {len(formatted_first)} characters
Second Call Input: {len(formatted_second)} characters
Final LLM Response Length: {len(llm_answer)} characters
Total Tokens Used: {tokens_used}

=== AI ANALYSIS (Final Response) ===
{llm_answer}
"""
    else:
        formatted = llm_metadata.get("formatted", "")
        result_text = f"""PI Planning Gaps Analysis Completed

PI: {pi}
Team: {team_name}
Job ID: {job_id}
Timestamp: {timestamp}

Data Sent to LLM: {len(formatted)} characters
LLM Response Length: {len(llm_answer)} characters
Total Tokens Used: {tokens_used}

=== AI ANALYSIS ===
{llm_answer}
"""
    
    # Call audit service for success
    duration_seconds = time.time() - start_time
    status_code = 200
    call_audit_service(
        action=job_type,
        duration_seconds=duration_seconds,
        status_code=status_code,
        action_date=datetime.now(timezone.utc),
        tokens_used=tokens_used,
        query_params=job_params,
        body=job_params,
        job_id=int(job_id) if job_id is not None else None,
    )
    
    return True, result_text


