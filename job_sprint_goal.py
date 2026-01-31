import time
from typing import Any, Dict, Tuple
from datetime import datetime, timezone

import config
from api_client import APIClient
from utils_audit import call_audit_service
from utils_logging import log
from utils_processing import (
    extract_recommendations,
    extract_text_and_json,
    extract_review_section,
    save_recommendations_from_json,
    get_active_sprint_summary_by_team_for_analysis,
    get_team_sprint_burndown_for_analysis,
    get_goal_progress_for_analysis,
    get_current_sprint_progress_for_analysis,
    process_llm_response_and_save_ai_card,
    process_llm_with_two_step_fallback,
)


def process(job: Dict[str, Any]) -> Tuple[bool, str]:
    start_time = time.time()
    client = APIClient()
    job_id = job.get("job_id") or job.get("id")
    job_type = job.get("job_type", "Sprint Goal")
    team_name = job.get("team_name")
    if not team_name:
        return False, "Missing team_name in job payload"

    # Step 1: Get active sprint ID (we only need sprint_id, not the formatted summary)
    _, sprint_id, _ = get_active_sprint_summary_by_team_for_analysis(client, team_name)
    
    # Check if we got a valid sprint
    if not sprint_id:
        return False, "Failed to get active sprint ID"
    
    log(int(job_id) if job_id is not None else None, f"✅ Sprint ID found: {sprint_id}")
    
    # Step 2: Get goal progress data (formatted)
    goal_progress_formatted = get_goal_progress_for_analysis(client, sprint_id, team_name)
    
    # Check if no goals found - if so, end job without creating AI insights
    if "No goals found" in goal_progress_formatted:
        log(int(job_id) if job_id is not None else None, "❌ No sprint goals found in database")
        return False, "No sprint goal found in the database"
    
    # Step 3: Get current sprint progress data (formatted)
    current_sprint_progress_formatted = get_current_sprint_progress_for_analysis(client, team_name)
    
    # Step 4: Get burndown chart data (formatted)
    burndown_formatted = get_team_sprint_burndown_for_analysis(client, team_name)
    
    # Build data string (without prompt)
    parts = ["SPRINT GOAL ANALYSIS DATA", "=" * 50, ""]
    
    # Add goal progress first
    parts.append(goal_progress_formatted)
    
    # Add current sprint progress second
    parts.append(current_sprint_progress_formatted)
    
    # Add burndown data third
    parts.append(burndown_formatted)
    
    data_string = "\n".join(parts)
    
    # Prepare job_params for audit service
    job_params = {
        "team_name": team_name,
        "group_name": job.get("group_name"),
        "pi": job.get("pi"),
        "job_id": int(job_id) if job_id is not None else None,
        "job_type": job_type,
    }
    
    # Prepare metadata for LLM calls
    metadata = {"team_name": team_name}
    
    # Call generic LLM processing function (handles prompt fetching and two-step mode)
    ok, llm_answer, tokens_used, llm_metadata = process_llm_with_two_step_fallback(
        client=client,
        data_string=data_string,
        prompt_base_name="Sprint Goal",
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
    log(int(job_id) if job_id is not None else None, f"\n📥 LLM Response Preview (first 500 chars):\n{preview}{'...' if len(llm_answer) > 500 else ''}\n")

    # Extract structured content from LLM response and save card
    log(int(job_id) if job_id is not None else None, "📋 EXTRACTING STRUCTURED CONTENT FROM LLM RESPONSE")
    
    description, full_info_truncated, raw_json_string, card_id = process_llm_response_and_save_ai_card(
        client=client,
        llm_answer=llm_answer,
        team_name=team_name,
        job_id=int(job_id) if job_id is not None else None,
        job_type=job_type,
        card_config={
            "card_name": "Sprint Goal Analysis",
            "source": "Sprint Goal",
        },
        card_type="Team",
        extract_content_fn=extract_review_section,
    )
    
    # Extract recommendations_json from LLM response for recommendations saving
    extraction = extract_text_and_json(llm_answer)
    recommendations_json = extraction.recommendations_json

    # Extract and create recommendations
    log(int(job_id) if job_id is not None else None, "📋 EXTRACTING AND SAVING RECOMMENDATIONS")
    
    today = datetime.now(timezone.utc).date().isoformat()
    
    # First try to extract recommendations from JSON if available
    recommendations_saved = save_recommendations_from_json(
        client=client,
        recommendations_json=recommendations_json,
        team_name_or_pi=team_name,
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
            rec_payload = {
                "team_name": team_name,
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
    use_two_step_mode = llm_metadata.get("use_two_step_mode", False)
    
    if use_two_step_mode:
        formatted_first = llm_metadata.get("formatted_first", "")
        formatted_second = llm_metadata.get("formatted_second", "")
        result_text = f"""Sprint Goal Analysis Completed (Two-Step Process)

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
        result_text = f"""Sprint Goal Analysis Completed

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


