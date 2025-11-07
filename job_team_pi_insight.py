import json
from typing import Any, Dict, Tuple
from datetime import datetime, timezone

from api_client import APIClient
from llm_client import call_agent_llm_process
from utils_processing import (
    extract_recommendations,
    extract_review_section,
    extract_text_and_json,
    fetch_pi_data_for_analysis,
    format_pi_analysis_input,
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


def process(job: Dict[str, Any]) -> Tuple[bool, str]:
    """Process Team PI Insight job type.
    
    Args:
        job: Job payload dictionary
        
    Returns:
        Tuple of (success, result_text)
    """
    client = APIClient()

    job_id = job.get("job_id") or job.get("id")
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

    # Fetch prompt with error checking
    prompt_text, prompt_error = get_prompt_with_error_check(
        client=client,
        email_address="PIAgent",
        prompt_name="TeamPIInsight",
        job_type="Team PI Insight",
        job_id=int(job_id) if job_id is not None else None,
    )
    
    if prompt_error:
        return False, prompt_error

    # Build formatted input and update input_sent
    formatted = format_pi_analysis_input(
        transcript=transcript_obj,
        pi_status=pi_status_obj,
        burndown=burndown_obj,
        prompt=prompt_text,
        header_title="TEAM PI INSIGHT DATA",
        include_transcript_section=False,  # Don't include transcript section
    )
    if job_id is not None:
        client.patch_agent_job(int(job_id), {"input_sent": formatted})

    # Call dedicated agent LLM processing endpoint
    ok, llm_answer, _raw = call_agent_llm_process(
        client=client,
        prompt=formatted,
        job_type="Team PI Insight",
        job_id=int(job_id) if job_id is not None else None,
        metadata={"pi_name": pi, "team_name": team_name},
    )
    if not ok:
        return False, "AI chat failed or returned empty response"

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
            "card_type": "Team PI Insight",
            "priority": "Critical",
            "source": "PI",
            # Note: No "pi" field - team-ai-cards don't have pi field
        },
        card_type="Team",  # Use Team AI cards endpoint
        extract_content_fn=extract_review_section,
    )
    
    # Extract recommendations_json from LLM response for recommendations saving
    _, _, recommendations_json, _ = extract_text_and_json(llm_answer)

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

    # Create detailed result text with full LLM response (like old system)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    result_text = f"""Team PI Insight Analysis Completed

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

