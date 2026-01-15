import time
from typing import Any, Dict, Tuple
from datetime import datetime, timezone

import config
from api_client import APIClient
from utils_audit import call_audit_service
from utils_processing import (
    extract_recommendations,
    extract_review_section,
    extract_text_and_json,
    get_group_active_sprint_stories_by_epic_for_analysis,
    get_group_sprint_dependencies_for_analysis,
    process_llm_response_and_save_ai_card,
    process_llm_with_two_step_fallback,
    save_recommendations_from_json,
)


def process(job: Dict[str, Any]) -> Tuple[bool, str]:
    """Process Group Sprint Dependency job type.
    
    Args:
        job: Job payload dictionary
        
    Returns:
        Tuple of (success, result_text)
    """
    start_time = time.time()
    client = APIClient()

    job_id = job.get("job_id") or job.get("id")
    job_type = job.get("job_type", "Group Sprint Dependency")
    
    group_name = job.get("group_name")
    if not group_name:
        return False, "Missing group_name in job payload"

    # Fetch current and next PIs to get the current PI
    status_code, current_pis_response = client.get_current_and_next_pis()
    if status_code != 200:
        return False, f"Failed to fetch current PI: HTTP {status_code}"
    
    if not isinstance(current_pis_response, dict) or not current_pis_response.get("success"):
        return False, "Invalid response format from current-and-next PIs endpoint"
    
    data = current_pis_response.get("data", {})
    current_pis = data.get("current_pis", [])
    
    if not current_pis or len(current_pis) == 0:
        return False, "No current PI found"
    
    # Extract current PI information
    current_pi_obj = current_pis[0]
    pi = current_pi_obj.get("pi_name")
    if not pi:
        return False, "Current PI object missing pi_name"
    
    # Extract PI dates from current PI response
    pi_start_date = current_pi_obj.get("start_date")
    pi_end_date = current_pi_obj.get("end_date")
    
    # Fetch sprint dependencies for the group
    dependencies_formatted = get_group_sprint_dependencies_for_analysis(
        client=client,
        group_name=group_name,
    )

    # Fetch active sprint child issues by epic for the group
    stories_by_epic_formatted = get_group_active_sprint_stories_by_epic_for_analysis(
        client=client,
        group_name=group_name,
    )

    # Build data string (without prompt)
    parts = [dependencies_formatted]
    parts.append("")
    
    # Add child issues by epic data
    parts.append(stories_by_epic_formatted)
    parts.append("")
    
    data_string = "\n".join(parts)
    
    # Prepare job_params for audit service
    job_params = {
        "team_name": job.get("team_name"),
        "group_name": group_name,
        "pi": pi,
        "job_id": int(job_id) if job_id is not None else None,
        "job_type": job_type,
    }
    
    # Prepare metadata for LLM calls
    metadata = {"group_name": group_name, "pi_name": pi}
    
    # Call generic LLM processing function (handles prompt fetching and two-step mode)
    ok, llm_answer, tokens_used, llm_metadata = process_llm_with_two_step_fallback(
        client=client,
        data_string=data_string,
        prompt_base_name="Group Sprint Dependency",
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
            "card_name": "Group Sprint Dependency Analysis",
            "source": "Group",
        },
        job_type=job_type,
        card_type="Team",  # Use Team AI cards endpoint (which accepts group_name)
        extract_content_fn=extract_review_section,
        group_name=group_name,  # Pass group_name to be included in card payload
    )
    
    # Extract recommendations_json from LLM response for recommendations saving
    _, _, recommendations_json, _, _ = extract_text_and_json(llm_answer)

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
        result_text = f"""Group Sprint Dependency Analysis Completed (Two-Step Process)

Group: {group_name}
PI: {pi}
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
        result_text = f"""Group Sprint Dependency Analysis Completed

Group: {group_name}
PI: {pi}
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





