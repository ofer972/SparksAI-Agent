import json
from typing import Any, Dict, Tuple
from datetime import datetime, timezone

import config
from api_client import APIClient
from llm_client import call_agent_llm_process
from utils_logging import log
from utils_processing import (
    extract_recommendations,
    extract_review_section,
    extract_text_and_json,
    fetch_pi_data_for_analysis,
    get_pi_dependencies_for_analysis,
    get_prompt_with_error_check,
    process_llm_response_and_save_ai_card,
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


def process(job: Dict[str, Any]) -> Tuple[bool, str]:
    """Process PI Dependencies job type.
    
    Args:
        job: Job payload dictionary
        
    Returns:
        Tuple of (success, result_text)
    """
    client = APIClient()

    job_id = job.get("job_id") or job.get("id")
    job_type = job.get("job_type", "PI Dependencies")
    pi = _extract_pi(job)
    if not pi:
        return False, "Missing PI in job payload"

    # Fetch PI status to get dates
    _, pi_status_obj, _ = fetch_pi_data_for_analysis(
        client=client,
        pi=pi,
        team_name=None,  # PI Dependencies doesn't filter by team_name
        include_transcript=False,  # Don't need transcript
    )
    
    # Extract PI dates
    pi_start_date, pi_end_date = _extract_pi_dates(pi_status_obj)
    
    # Get current date
    current_date = datetime.now(timezone.utc).date().isoformat()

    # Fetch inbound and outbound dependencies
    inbound_formatted, outbound_formatted, inbound_count, outbound_count = get_pi_dependencies_for_analysis(
        client=client,
        pi=pi,
    )
    
    # Validate that we have dependencies to analyze
    if inbound_count == 0 or outbound_count == 0:
        error_msg = f"No dependencies found: inbound={inbound_count}, outbound={outbound_count}"
        log(int(job_id) if job_id is not None else None, f"❌ {error_msg}")
        return True, error_msg

    # Fetch prompt with error checking
    prompt_text, prompt_error = get_prompt_with_error_check(
        client=client,
        email_address="PIAgent",
        prompt_name="PI Dependencies",
        job_type="PI Dependencies",
        job_id=int(job_id) if job_id is not None else None,
    )
    
    if prompt_error:
        return False, prompt_error

    # Build formatted input with header (PI, dates, current date)
    parts = ["=== PI DEPENDENCIES DATA ==="]
    parts.append(f"PI: {pi}")
    if pi_start_date:
        parts.append(f"PI Start Date: {pi_start_date}")
    if pi_end_date:
        parts.append(f"PI End Date: {pi_end_date}")
    parts.append(f"Current Date: {current_date}")
    parts.append("")
    
    # Add inbound dependencies
    parts.append(inbound_formatted)
    parts.append("")
    
    # Add outbound dependencies
    parts.append(outbound_formatted)
    parts.append("")
    
    # Add prompt (already includes markers from get_prompt_with_error_check)
    if prompt_text:
        parts.append(prompt_text)
    
    formatted = "\n".join(parts)
    
    if job_id is not None:
        client.patch_agent_job(int(job_id), {"input_sent": formatted})

    # Call dedicated agent LLM processing endpoint
    log(int(job_id) if job_id is not None else None, f"📤 Calling LLM for PI Dependencies (input: {len(formatted)} chars)")
    ok, llm_answer, _raw = call_agent_llm_process(
        client=client,
        prompt=formatted,
        job_type="PI Dependencies",
        job_id=int(job_id) if job_id is not None else None,
        metadata={"pi_name": pi, "team_name": job.get("team_name")},
    )
    if not ok:
        return False, "AI chat failed or returned empty response"

    # Print first 500 characters of LLM response
    preview = llm_answer[:500] if llm_answer else ""
    log(int(job_id) if job_id is not None else None, f"\n📥 LLM Response Preview (first 500 chars):\n{preview}{'...' if len(llm_answer) > 500 else ''}\n")

    # Extract structured content from LLM response and save card
    log(int(job_id) if job_id is not None else None, "📋 EXTRACTING STRUCTURED CONTENT FROM LLM RESPONSE")
    
    description, full_info_truncated, raw_json_string, card_id = process_llm_response_and_save_ai_card(
        client=client,
        llm_answer=llm_answer,
        team_name=job.get("team_name"),
        job_id=int(job_id) if job_id is not None else None,
        card_config={
            "pi": pi,
            "card_name": "PI Dependencies Analysis",
            "priority": "Critical",
            "source": "PI",
        },
        job_type=job_type,
        card_type="PI",
        extract_content_fn=extract_review_section,
    )
    
    # Extract recommendations_json from LLM response for recommendations saving
    _, _, recommendations_json, _ = extract_text_and_json(llm_answer)

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

    # Create detailed result text with full LLM response (like old system)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    team_name = job.get("team_name", "Unknown")
    result_text = f"""PI Dependencies Analysis Completed

PI: {pi}
Team: {team_name}
Job ID: {job_id}
Timestamp: {timestamp}

Data Sent to LLM: {len(formatted)} characters
LLM Response Length: {len(llm_answer)} characters

=== AI ANALYSIS ===
{llm_answer}
"""
    return True, result_text

