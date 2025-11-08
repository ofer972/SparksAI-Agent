from typing import Any, Dict, Tuple
from datetime import datetime, timezone

import config
from api_client import APIClient
from llm_client import call_agent_llm_process
from utils_processing import (
    extract_recommendations,
    extract_text_and_json,
    extract_review_section,
    get_prompt_with_error_check,
    get_team_sprint_burndown_for_analysis,
    get_transcripts_for_analysis,
    get_sprint_predictability_for_analysis,
    process_llm_response_and_save_ai_card,
    save_recommendations_from_json,
)


def process(job: Dict[str, Any]) -> Tuple[bool, str]:
    client = APIClient()
    job_id = job.get("job_id") or job.get("id")
    team_name = job.get("team_name")
    if not team_name:
        return False, "Missing team_name in job payload"

    # Get formatted data using helper functions
    # Get latest 5 transcripts
    transcripts_formatted = get_transcripts_for_analysis(
        client=client,
        transcript_type="Daily",
        team_name=team_name,
        limit=5,
    )
    
    # Get sprint burndown
    burndown_formatted = get_team_sprint_burndown_for_analysis(client, team_name)
    
    # Get sprint predictability (last 3 months)
    sprint_predictability_formatted = get_sprint_predictability_for_analysis(
        client=client,
        team_name=team_name,
        months=3,
    )

    # Fetch prompt with error checking
    prompt_text, prompt_error = get_prompt_with_error_check(
        client=client,
        email_address="TeamRetroTopicsAgent",
        prompt_name="Team Retro Topics",
        job_type="Team Retro Topics",
        job_id=int(job_id) if job_id is not None else None,
    )
    
    if prompt_error:
        return False, prompt_error

    # Build formatted input by concatenating formatted sections
    parts = ["=== TEAM RETRO TOPICS ==="]
    parts.append(f"Team: {team_name}")
    parts.append("")
    
    # Add formatted transcripts (includes "Begin transcript(s)" / "End transcript(s)" markers)
    parts.append(transcripts_formatted)
    parts.append("")
    
    # Add formatted burndown (includes "=== BURN DOWN DATA FOR THE ACTIVE SPRINT ===" header)
    parts.append(burndown_formatted)
    parts.append("")
    
    # Add formatted sprint predictability (includes "=== Previous Sprints metrics and predictability ===" header)
    parts.append(sprint_predictability_formatted)
    
    # Add prompt (already includes markers from get_prompt_with_error_check)
    if prompt_text:
        parts.append(prompt_text)
    
    formatted = "\n".join(parts)
    if job_id is not None:
        client.patch_agent_job(int(job_id), {"input_sent": formatted})

    # Call dedicated agent LLM processing endpoint
    ok, llm_answer, _raw = call_agent_llm_process(
        client=client,
        prompt=formatted,
        job_type="Team Retro Topics",
        job_id=int(job_id) if job_id is not None else None,
        metadata={"team_name": team_name},
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
            "card_name": "Team Retro Topics",
            "card_type": "Team Retro Topics",
            "priority": "High",
            "source": "Team Retro Topics",
        },
        card_type="Team",
        extract_content_fn=extract_review_section,
    )
    
    # Extract recommendations_json from LLM response for recommendations saving
    _, _, recommendations_json, _ = extract_text_and_json(llm_answer)

    # Extract and create recommendations
    print("📋 EXTRACTING AND SAVING RECOMMENDATIONS")
    
    today = datetime.now(timezone.utc).date().isoformat()
    if recommendations_json:
        save_recommendations_from_json(
            client=client,
            recommendations_json=recommendations_json,
            team_name_or_pi=team_name,
            today=today,
            full_info_truncated=full_info_truncated,
            max_count=2,
            job_id=int(job_id) if job_id is not None else None,
            source_ai_summary_id=card_id,
        )
        print("✅ Recommendations saved")
    else:
        print("ℹ️  No recommendations found in LLM response")

    # Create detailed result text with full LLM response (like other jobs)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    result_text = f"""Team Retro Topics Analysis Completed

Team: {team_name}
Job ID: {job_id}
Timestamp: {timestamp}

Data Sent to LLM: {len(formatted)} characters
LLM Response Length: {len(llm_answer)} characters

=== AI ANALYSIS ===
{llm_answer}
"""
    return True, result_text

