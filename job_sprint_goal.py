from typing import Any, Dict, Tuple
from datetime import datetime, timezone

import config
from api_client import APIClient
from llm_client import call_agent_llm_process
from utils_processing import (
    extract_recommendations,
    extract_text_and_json,
    extract_content_between_markers,
    LLM_EXTRACTION_CONSTANTS,
    get_prompt_with_error_check,
    save_recommendations_from_json,
    get_active_sprint_summary_by_team_for_analysis,
    get_sprint_issues_with_epic_for_analysis,
    process_llm_response_and_save_ai_card,
)


def process(job: Dict[str, Any]) -> Tuple[bool, str]:
    client = APIClient()
    job_id = job.get("job_id") or job.get("id")
    team_name = job.get("team_name")
    if not team_name:
        return False, "Missing team_name in job payload"

    # Step 1: Get active sprint summaries for team (formatted) with sprint_id and sprint_goal
    sprint_summary_formatted, sprint_id, sprint_goal = get_active_sprint_summary_by_team_for_analysis(client, team_name)
    
    # Check if we got a valid sprint
    if not sprint_id:
        # The function already returned an error message in sprint_summary_formatted
        # Check if it's an HTTP error or just no data
        if "HTTP error" in sprint_summary_formatted:
            return False, "Failed to get active sprint summaries"
        return True, "No active sprint summaries found for team"
    
    # Validate sprint_goal
    if not sprint_goal or len(str(sprint_goal).strip()) < 10:
        print("❌ Sprint goal not found")
        return True, "No sprint Goal found"
    
    print(f"✅ Sprint goal found")
    
    # Step 2: Get JIRA issues for the sprint with epic data (formatted)
    jira_issues_formatted = get_sprint_issues_with_epic_for_analysis(client, sprint_id, team_name)
    
    # Step 4: Fetch prompt
    prompt_text, prompt_error = get_prompt_with_error_check(
        client=client,
        email_address="DailyAgent",
        prompt_name="Sprint Goal",
        job_type="Sprint Goal",
        job_id=int(job_id) if job_id is not None else None,
    )
    
    if prompt_error:
        print("❌ Prompt not found")
        return False, prompt_error
    
    if prompt_text:
        print("✅ Prompt found")
    else:
        print("❌ Prompt not found")
    
    # Step 3: Format data using the new helper functions
    parts = ["SPRINT GOAL ANALYSIS DATA", "=" * 50, ""]
    
    # Add formatted sprint summary (includes sprint goal and all sprint data)
    parts.append(sprint_summary_formatted)
    
    # Add formatted JIRA issues
    parts.append(jira_issues_formatted)
    
    # ANALYSIS PROMPT section (already includes markers from get_prompt_with_error_check)
    if prompt_text:
        parts.append(prompt_text)
        parts.append("")
    
    formatted = "\n".join(parts)

    if job_id is not None:
        client.patch_agent_job(int(job_id), {"input_sent": formatted})

    # Call dedicated agent LLM processing endpoint
    ok, llm_answer, _raw = call_agent_llm_process(
        client=client,
        prompt=formatted,
        job_type="Sprint Goal",
        job_id=int(job_id) if job_id is not None else None,
        metadata={"team_name": team_name},
    )
    
    if not ok or not llm_answer:
        return False, "AI chat failed or returned empty response"

    # Print first 500 characters of LLM response
    preview = llm_answer[:500] if llm_answer else ""
    print(f"\n📥 LLM Response Preview (first 500 chars):\n{preview}{'...' if len(llm_answer) > 500 else ''}\n")

    # Extract structured content from LLM response and save card
    print("📋 EXTRACTING STRUCTURED CONTENT FROM LLM RESPONSE")
    
    # Helper function to extract sprint goal content using markers
    def extract_sprint_goal_review(llm_response: str) -> str | None:
        return extract_content_between_markers(
            llm_response,
            LLM_EXTRACTION_CONSTANTS.START_MARKER,
            LLM_EXTRACTION_CONSTANTS.END_MARKER
        )
    
    description, full_info_truncated, raw_json_string, card_id = process_llm_response_and_save_ai_card(
        client=client,
        llm_answer=llm_answer,
        team_name=team_name,
        job_id=int(job_id) if job_id is not None else None,
        card_config={
            "card_name": "Sprint Goal Analysis",
            "card_type": "Sprint Goal",
            "priority": "High",
            "source": "Sprint Goal",
        },
        card_type="Team",
        extract_content_fn=extract_sprint_goal_review,
    )
    
    # Extract recommendations_json from LLM response for recommendations saving
    _, _, recommendations_json, _ = extract_text_and_json(llm_answer)

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

    # Create detailed result text with full LLM response (like old system)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    result_text = f"""Sprint Goal Analysis Completed

Team: {team_name}
Job ID: {job_id}
Timestamp: {timestamp}

Data Sent to LLM: {len(formatted)} characters
LLM Response Length: {len(llm_answer)} characters

=== AI ANALYSIS ===
{llm_answer}
"""
    return True, result_text


