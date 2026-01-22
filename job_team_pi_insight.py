import json
import time
from typing import Any, Dict, Tuple
from datetime import datetime, timezone

from api_client import APIClient
from utils_audit import call_audit_service
from utils_processing import (
    extract_recommendations,
    extract_review_section,
    extract_text_and_json,
    fetch_pi_data_for_analysis,
    format_burndown_markdown,
    format_pi_status,
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
    """Process Team PI Insight job type.
    
    Args:
        job: Job payload dictionary
        
    Returns:
        Tuple of (success, result_text)
    """
    start_time = time.time()
    client = APIClient()

    job_id = job.get("job_id") or job.get("id")
    job_type = job.get("job_type", "Team PI Insight")
    pi = _extract_pi(job)
    if not pi:
        return False, "Missing PI in job payload"
    
    team_name = job.get("team_name")
    if not team_name:
        return False, "Missing team_name in job payload"

    # Fetch data using shared function (no transcript, with team_name filter)
    transcript_obj, pi_status_obj, burndown_obj = fetch_pi_data_for_analysis(
        client=client,
        pi=pi,
        team_name=team_name,  # Filter by team_name for Team PI Insight
        include_transcript=False,  # Team PI Insight doesn't use transcript
    )

    # Build data string (without prompt) - same structure as format_pi_analysis_input but without prompt
    parts = ["===TEAM PI INSIGHT DATA==="]
    parts.append("-- PI status for current date --")
    parts.append(format_pi_status(pi_status_obj))
    parts.append("")
    parts.append("-- PI Burndown Snapshot --")
    parts.append(format_burndown_markdown(burndown_obj))
    parts.append("")
    
    data_string = "\n".join(parts)
    
    # Prepare job_params for audit service
    job_params = {
        "team_name": team_name,
        "group_name": job.get("group_name"),
        "pi": pi,
        "job_id": int(job_id) if job_id is not None else None,
        "job_type": job_type,
    }
    
    # Prepare metadata for LLM calls
    metadata = {"pi_name": pi, "team_name": team_name}
    
    # Call generic LLM processing function (handles prompt fetching and two-step mode)
    ok, llm_answer, tokens_used, llm_metadata = process_llm_with_two_step_fallback(
        client=client,
        data_string=data_string,
        prompt_base_name="Team PI Insights",
        prompt_email="TeamAgent",
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
    print(f"\n📥 LLM Response Preview (first 500 chars):\n{preview}{'...' if len(llm_answer) > 500 else ''}\n")

    # Extract structured content from LLM response and save card
    print("📋 EXTRACTING STRUCTURED CONTENT FROM LLM RESPONSE")
    
    description, full_info_truncated, raw_json_string, card_id = process_llm_response_and_save_ai_card(
        client=client,
        llm_answer=llm_answer,
        team_name=team_name,
        job_id=int(job_id) if job_id is not None else None,
        card_config={
            "card_name": "Team PI Insight",
            "source": "PI",
            "pi": pi,  # Team PI Insight requires both team_name and pi
        },
        job_type=job_type,
        card_type="Team",  # Use Team AI cards endpoint
        extract_content_fn=extract_review_section,
    )
    
    # Extract recommendations_json from LLM response for recommendations saving
    extraction = extract_text_and_json(llm_answer)
    recommendations_json = extraction.recommendations_json

    # Extract and create recommendations
    print("📋 EXTRACTING AND SAVING RECOMMENDATIONS")
    
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
        print("⚠️ No recommendations from JSON found - falling back to text extraction")
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
                print(f"⚠️ Create recommendation failed: {rsc} {rresp}")
            else:
                recommendations_saved += 1
                print(f"🧩 Recommendation: priority='High' status='Proposed' text='{rec_text[:120]}'")
            
            if recommendations_saved >= 2:
                break

    # Create detailed result text with full LLM response
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    use_two_step_mode = llm_metadata.get("use_two_step_mode", False)
    
    if use_two_step_mode:
        formatted_first = llm_metadata.get("formatted_first", "")
        formatted_second = llm_metadata.get("formatted_second", "")
        result_text = f"""Team PI Insight Analysis Completed (Two-Step Process)

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
        result_text = f"""Team PI Insight Analysis Completed

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

