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
    format_burndown_markdown,
    format_pi_status,
    get_transcripts_for_analysis,
    process_llm_response_and_save_ai_card,
    process_llm_with_two_step_fallback,
    save_recommendations_from_json,
)


def _extract_pi(job: Dict[str, Any]) -> str | None:
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
    start_time = time.time()
    client = APIClient()

    job_id = job.get("job_id") or job.get("id")
    job_type = job.get("job_type", "PI Sync")
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

    # Fetch transcript using new unified function
    transcript_formatted = get_transcripts_for_analysis(
        client=client,
        transcript_type="PI Sync",
        pi_name=pi,
        limit=1,
        job_id=int(job_id) if job_id is not None else None,
    )
    
    # Fetch other data using shared function
    _, pi_status_obj, burndown_obj = fetch_pi_data_for_analysis(
        client=client,
        pi=pi,
        team_name=team_param,
        is_group=is_group,
        include_transcript=False,  # Already fetched above
    )

    # Build data string (will be reused for both calls if two-step mode)
    data_parts = ["=== PI SYNC DATA ==="]
    data_parts.append(f"PI: {pi}")
    if team_param:
        if is_group:
            data_parts.append(f"Group: {team_param}")
        else:
            data_parts.append(f"Team: {team_param}")
    data_parts.append("")
    
    # Add transcript section
    data_parts.append("-- Latest Transcript --")
    data_parts.append(transcript_formatted)
    data_parts.append("")
    
    # Add PI status section
    data_parts.append("-- PI status for current date --")
    data_parts.append(format_pi_status(pi_status_obj))
    data_parts.append("")
    
    # Add burndown section
    data_parts.append("-- PI Burndown Snapshot --")
    data_parts.append(format_burndown_markdown(burndown_obj))
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
        prompt_base_name="PISync",
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
    input_sent = llm_metadata.get("input_sent", "")
    
    # Update input_sent in job (use the complete input_sent from metadata)
    if job_id is not None and input_sent:
        client.patch_agent_job(int(job_id), {"input_sent": input_sent})

    # Print first 500 characters of LLM response
    preview = llm_answer[:500] if llm_answer else ""
    log(int(job_id) if job_id is not None else None, f"\n📥 LLM Response Preview (first 500 chars):\n{preview}{'...' if len(llm_answer) > 500 else ''}\n")

    # Extract structured content from LLM response and save card
    log(int(job_id) if job_id is not None else None, "📋 EXTRACTING STRUCTURED CONTENT FROM LLM RESPONSE (Final Response)")
    
    description, full_info_truncated, raw_json_string, card_id = process_llm_response_and_save_ai_card(
        client=client,
        llm_answer=llm_answer,
        team_name=team_name,
        job_id=int(job_id) if job_id is not None else None,
        job_type=job_type,
        card_config={
            "pi": pi,
            "card_name": "PI Sync Review",
            "source": "PI",
        },
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
    
    if use_two_step_mode:
        # For two-step mode, show both calls info
        result_text = f"""PI Sync Analysis Completed (Two-Step Process)

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
        result_text = f"""PI Sync Analysis Completed

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


