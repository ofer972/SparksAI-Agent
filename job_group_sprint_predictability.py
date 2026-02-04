import time
from typing import Any, Dict, Tuple
from datetime import datetime, timezone

import config
from api_client import APIClient
from utils_audit import call_audit_service
from utils_processing import (
    extract_recommendations,
    extract_text_and_json,
    extract_review_section,
    get_group_closed_sprints_for_analysis,
    get_group_sprint_burndown_for_analysis,
    get_selected_active_sprint_summary,
    process_llm_response_and_save_ai_card,
    process_llm_with_two_step_fallback,
    save_recommendations_from_json,
)


def process(job: Dict[str, Any]) -> Tuple[bool, str]:
    """Process Group Sprint Predictability job type.
    
    Args:
        job: Job payload dictionary
        
    Returns:
        Tuple of (success, result_text)
    """
    start_time = time.time()
    client = APIClient()
    job_id = job.get("job_id") or job.get("id")
    job_type = job.get("job_type", "Group Sprint Predictability")
    group_name = job.get("group_name")
    if not group_name:
        return False, "Missing group_name in job payload"

    # Sprint gate for group: continue if at least one team has an active sprint
    selected, total_issues, _error_msg = get_selected_active_sprint_summary(
        client=client,
        name=group_name,
        is_group=True,
    )
    sprint_id_raw = selected.get("sprint_id") if isinstance(selected, dict) else None
    try:
        sprint_id = int(sprint_id_raw) if sprint_id_raw is not None else None
    except Exception:
        sprint_id = None
    if not sprint_id or (total_issues is not None and total_issues <= 0):
        return True, "No active sprint found. Insight was not created. Job stopped."

    # TODO: Fetch group-level sprint predictability data when backend endpoint is ready
    # For now, leave data sections empty as requested
    # sprint_predictability_formatted = get_group_sprint_predictability_for_analysis(
    #     client=client,
    #     group_name=group_name,
    #     months=3,
    # )

    # Get formatted closed sprints data for all teams in the group
    closed_sprints_formatted = get_group_closed_sprints_for_analysis(client, group_name, months=3)
    
    # Get formatted burndown data for all teams in the group
    burndown_formatted = get_group_sprint_burndown_for_analysis(client, group_name)
    
    # Build data string (without prompt)
    parts = ["=== GROUP SPRINT PREDICTABILITY ==="]
    parts.append(f"Group: {group_name}")
    parts.append("")
    
    # Add formatted closed sprints data
    parts.append(closed_sprints_formatted)
    parts.append("")
    
    # Add formatted burndown data
    parts.append(burndown_formatted)
    parts.append("")
    
    data_string = "\n".join(parts)
    
    # Prepare job_params for audit service
    job_params = {
        "team_name": job.get("team_name"),
        "group_name": group_name,
        "pi": job.get("pi"),
        "job_id": int(job_id) if job_id is not None else None,
        "job_type": job_type,
    }
    
    # Prepare metadata for LLM calls
    metadata = {"group_name": group_name}
    
    # Call generic LLM processing function (handles prompt fetching and two-step mode)
    ok, llm_answer, tokens_used, llm_metadata = process_llm_with_two_step_fallback(
        client=client,
        data_string=data_string,
        prompt_base_name="Group Sprint Predictability",
        prompt_email="GroupAgent",
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
        team_name=None,  # Group cards use group_name instead
        job_id=int(job_id) if job_id is not None else None,
        card_config={
            "card_name": "Group Sprint Predictability",
            "source": "Group",
        },
        job_type=job_type,
        card_type="Team",  # Use Team AI cards endpoint (which accepts group_name)
        extract_content_fn=extract_review_section,
        group_name=group_name,  # Pass group_name to be included in card payload
        sprint_id=sprint_id,
    )
    
    # Extract recommendations_json from LLM response for recommendations saving
    extraction = extract_text_and_json(llm_answer)
    recommendations_json = extraction.recommendations_json

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

    # Create detailed result text with full LLM response
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    use_two_step_mode = llm_metadata.get("use_two_step_mode", False)
    
    if use_two_step_mode:
        formatted_first = llm_metadata.get("formatted_first", "")
        formatted_second = llm_metadata.get("formatted_second", "")
        result_text = f"""Group Sprint Predictability Analysis Completed (Two-Step Process)

Group: {group_name}
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
        result_text = f"""Group Sprint Predictability Analysis Completed

Group: {group_name}
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

