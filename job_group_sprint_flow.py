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
    get_group_sprint_burndown_for_analysis,
    process_llm_response_and_save_ai_card,
    save_recommendations_from_json,
)


def process(job: Dict[str, Any]) -> Tuple[bool, str]:
    """Process Group Sprint Flow job type.
    
    Args:
        job: Job payload dictionary
        
    Returns:
        Tuple of (success, result_text)
    """
    client = APIClient()
    job_id = job.get("job_id") or job.get("id")
    job_type = job.get("job_type", "Group Sprint Flow")
    group_name = job.get("group_name")
    if not group_name:
        return False, "Missing group_name in job payload"

    # TODO: Fetch group-level sprint flow data when backend endpoint is ready
    # For now, leave data sections empty as requested
    # sprint_flow_formatted = get_group_sprint_flow_for_analysis(client, group_name)

    # Fetch prompt with error checking
    prompt_text, prompt_error = get_prompt_with_error_check(
        client=client,
        email_address="GroupAgent",
        prompt_name="Group Sprint Flow",
        job_type="Group Sprint Flow",
        job_id=int(job_id) if job_id is not None else None,
    )
    
    if prompt_error:
        return False, prompt_error

    # Get formatted burndown data for all teams in the group
    burndown_formatted = get_group_sprint_burndown_for_analysis(client, group_name)
    
    # Build formatted input by concatenating formatted sections
    parts = ["=== GROUP SPRINT FLOW ==="]
    parts.append(f"Group: {group_name}")
    parts.append("")
    
    # Add formatted burndown data
    parts.append(burndown_formatted)
    parts.append("")
    
    # Add prompt (already includes markers from get_prompt_with_error_check)
    if prompt_text:
        parts.append(prompt_text)
    
    formatted = "\n".join(parts)
    if job_id is not None:
        client.patch_agent_job(int(job_id), {"input_sent": formatted})

    # Call dedicated agent LLM processing endpoint
    print(f"📤 Calling LLM for Group Sprint Flow (input: {len(formatted)} chars)")
    ok, llm_answer, _raw = call_agent_llm_process(
        client=client,
        prompt=formatted,
        job_type="Group Sprint Flow",
        job_id=int(job_id) if job_id is not None else None,
        metadata={"group_name": group_name},
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
        team_name=None,  # Group cards use group_name instead
        job_id=int(job_id) if job_id is not None else None,
        card_config={
            "card_name": "Group Sprint Flow",
            "priority": "High",
            "source": "Group",
        },
        job_type=job_type,
        card_type="Team",  # Use Team AI cards endpoint (which accepts group_name)
        extract_content_fn=extract_review_section,
        group_name=group_name,  # Pass group_name to be included in card payload
    )
    
    # Extract recommendations_json from LLM response for recommendations saving
    _, _, recommendations_json, _ = extract_text_and_json(llm_answer)

    # Extract and create recommendations
    print("📋 EXTRACTING AND SAVING RECOMMENDATIONS")
    
    today = datetime.now(timezone.utc).date().isoformat()
    if recommendations_json:
        # For recommendations, use group_name as team_name_or_pi
        save_recommendations_from_json(
            client=client,
            recommendations_json=recommendations_json,
            team_name_or_pi=group_name,  # Use group_name for recommendations
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
    result_text = f"""Group Sprint Flow Analysis Completed

Group: {group_name}
Job ID: {job_id}
Timestamp: {timestamp}

Data Sent to LLM: {len(formatted)} characters
LLM Response Length: {len(llm_answer)} characters

=== AI ANALYSIS ===
{llm_answer}
"""
    return True, result_text

