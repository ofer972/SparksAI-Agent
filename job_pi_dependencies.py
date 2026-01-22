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
    get_pi_dependencies_for_analysis,
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




def process(job: Dict[str, Any]) -> Tuple[bool, str]:
    """Process PI Dependencies job type.
    
    Args:
        job: Job payload dictionary
        
    Returns:
        Tuple of (success, result_text)
    """
    start_time = time.time()
    client = APIClient()

    job_id = job.get("job_id") or job.get("id")
    job_type = job.get("job_type", "PI Dependencies")
    
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

    # Fetch current and next PIs to get the current PI and dates
    status_code, current_pis_response = client.get_current_and_next_pis()
    if status_code != 200:
        return False, f"Failed to fetch current PI: HTTP {status_code}"
    
    if not isinstance(current_pis_response, dict) or not current_pis_response.get("success"):
        return False, "Invalid response format from current-and-next PIs endpoint"
    
    data = current_pis_response.get("data", {})
    current_pis = data.get("current_pis", [])
    
    if not current_pis or len(current_pis) == 0:
        return False, "No current PI found"
    
    # Extract current PI information
    current_pi_obj = current_pis[0]
    pi_from_response = current_pi_obj.get("pi_name")
    if not pi_from_response:
        return False, "Current PI object missing pi_name"
    
    # Use PI from job payload if provided, otherwise use current PI from response
    pi = _extract_pi(job)
    if not pi:
        pi = pi_from_response
    
    # Extract PI dates from current PI response
    pi_start_date = current_pi_obj.get("start_date")
    pi_end_date = current_pi_obj.get("end_date")
    
    # Get current date
    current_date = datetime.now(timezone.utc).date().isoformat()

    # Fetch inbound and outbound dependencies
    inbound_formatted, outbound_formatted, inbound_count, outbound_count = get_pi_dependencies_for_analysis(
        client=client,
        pi=pi,
        team_name=team_param,
        is_group=is_group,
    )
    
    # Validate that we have dependencies to analyze
    if inbound_count == 0 or outbound_count == 0:
        error_msg = f"No dependencies found: inbound={inbound_count}, outbound={outbound_count}"
        log(int(job_id) if job_id is not None else None, f"❌ {error_msg}")
        return True, error_msg

    # Build data string (will be reused for both calls)
    data_parts = ["=== PI DEPENDENCIES DATA ==="]
    data_parts.append(f"PI: {pi}")
    if pi_start_date:
        data_parts.append(f"PI Start Date: {pi_start_date}")
    if pi_end_date:
        data_parts.append(f"PI End Date: {pi_end_date}")
    data_parts.append(f"Current Date: {current_date}")
    
    # Add group information if group_name is provided
    if is_group and group_name:
        data_parts.append(f"Data for group: {group_name}")
    data_parts.append("")
    
    # Add inbound dependencies with group context if applicable
    if is_group and group_name:
        # Modify the inbound header to include group info
        inbound_with_group = inbound_formatted.replace(
            "=== INBOUND DEPENDENCIES ===",
            f"=== INBOUND DEPENDENCIES (Data for group: {group_name}) ==="
        )
        data_parts.append(inbound_with_group)
    else:
        data_parts.append(inbound_formatted)
    data_parts.append("")
    
    # Add outbound dependencies with group context if applicable
    if is_group and group_name:
        # Modify the outbound header to include group info
        outbound_with_group = outbound_formatted.replace(
            "=== OUTBOUND DEPENDENCIES ===",
            f"=== OUTBOUND DEPENDENCIES (Data for group: {group_name}) ==="
        )
        data_parts.append(outbound_with_group)
    else:
        data_parts.append(outbound_formatted)
    data_parts.append("")
    
    data_string = "\n".join(data_parts)
    
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
    
    # ===== LLM PROCESSING WITH TWO-STEP FALLBACK =====
    ok, llm_answer, tokens_used, llm_metadata = process_llm_with_two_step_fallback(
        client=client,
        data_string=data_string,
        prompt_base_name="PI Dependencies",
        prompt_email="PIAgent",
        job_type=job_type,
        job_id=int(job_id) if job_id is not None else None,
        job_params=job_params,
        metadata=metadata,
        context_separator="LOCKED DECISION CONTEXT:",
        start_time=start_time,
    )
    
    if not ok:
        # Error already logged and audited by generic function
        error_msg = "LLM processing failed" if not llm_answer else llm_answer
        return False, error_msg
    
    use_two_step_mode = llm_metadata.get("use_two_step_mode", False)
    formatted_first = llm_metadata.get("formatted_first", "")
    formatted_second = llm_metadata.get("formatted_second", "")
    formatted = llm_metadata.get("formatted", "")

    # ===== SHARED RESPONSE PROCESSING (BOTH MODES) =====
    # Extract structured content from LLM response and save card
    log(int(job_id) if job_id is not None else None, "📋 EXTRACTING STRUCTURED CONTENT FROM LLM RESPONSE (Final Response)")
    
    description, full_info_truncated, raw_json_string, card_id = process_llm_response_and_save_ai_card(
        client=client,
        llm_answer=llm_answer,
        team_name=team_name,
        job_id=int(job_id) if job_id is not None else None,
        card_config={
            "pi": pi,
            "card_name": "PI Dependencies Analysis",
            "source": "PI",
        },
        job_type=job_type,
        card_type="PI",
        extract_content_fn=extract_review_section,
        group_name=group_name,
    )
    
    # Extract recommendations_json from LLM response for recommendations saving
    extraction = extract_text_and_json(llm_answer)
    recommendations_json = extraction.recommendations_json

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
    
    if use_two_step_mode:
        # For two-step mode, we don't have llm_answer_first length, but we can show the structure
        result_text = f"""PI Dependencies Analysis Completed (Two-Step Process)

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
        result_text = f"""PI Dependencies Analysis Completed

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
    
    # Call audit service for success (always executed with tokens_used from both modes)
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

