import time
from typing import Any, Dict, Tuple
from datetime import datetime, timezone

import config
from api_client import APIClient
from utils_processing import (
    extract_recommendations,
    extract_text_and_json,
    extract_review_section,
    save_recommendations_from_json,
    get_team_sprint_burndown_for_analysis,
    get_daily_transcript_for_analysis,
    get_active_sprint_summary_by_team_for_analysis,
    process_llm_response_and_save_ai_card,
    process_llm_with_two_step_fallback,
)


def process(job: Dict[str, Any]) -> Tuple[bool, str]:
    client = APIClient()
    job_id = job.get("job_id") or job.get("id")
    job_type = job.get("job_type", "Daily Progress")
    team_name = job.get("team_name")
    if not team_name:
        return False, "Missing team_name in job payload"

    # Get formatted data using helper functions
    # Get active sprint summary first (includes sprint goal and sprint status)
    sprint_summary_formatted, _sprint_id, _sprint_goal = get_active_sprint_summary_by_team_for_analysis(client, team_name)
    transcript_formatted = get_daily_transcript_for_analysis(client, team_name)
    burndown_formatted = get_team_sprint_burndown_for_analysis(client, team_name)

    # Build data string (without prompt)
    parts = ["=== DAILY CONTEXT ==="]
    parts.append(f"Team: {team_name}")
    parts.append("")
    
    # Add active sprint summary at the beginning (includes sprint goal and sprint status)
    parts.append(sprint_summary_formatted)
    
    # Add formatted transcript (includes "=== TRANSCRIPT DATA ===" header)
    parts.append(transcript_formatted)
    
    # Add formatted burndown (includes "=== BURN DOWN DATA FOR THE ACTIVE SPRINT ===" header)
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
    start_time = time.time()
    ok, llm_answer, tokens_used, llm_metadata = process_llm_with_two_step_fallback(
        client=client,
        data_string=data_string,
        prompt_base_name="Daily Insights",
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
        job_type=job_type,
        card_config={
            "card_name": "Daily Progress Review",
            "source": "Daily Progress",
        },
        card_type="Team",
        extract_content_fn=extract_review_section,
    )
    
    # Extract recommendations_json from LLM response for recommendations saving
    _, _, recommendations_json, _, _ = extract_text_and_json(llm_answer)

    # Extract and create recommendations
    print("📋 EXTRACTING AND SAVING RECOMMENDATIONS")
    
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
        print("⚠️ No recommendations from JSON found - falling back to text extraction")
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
        result_text = f"""Daily Progress Analysis Completed (Two-Step Process)

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
        result_text = f"""Daily Progress Analysis Completed

Team: {team_name}
Job ID: {job_id}
Timestamp: {timestamp}

Data Sent to LLM: {len(formatted)} characters
LLM Response Length: {len(llm_answer)} characters
Total Tokens Used: {tokens_used}

=== AI ANALYSIS ===
{llm_answer}
"""
    return True, result_text


