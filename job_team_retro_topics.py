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
    get_team_sprint_burndown_for_analysis,
    get_transcripts_for_analysis,
    get_closed_sprints_for_analysis,
    process_llm_response_and_save_ai_card,
    process_llm_with_two_step_fallback,
    save_recommendations_from_json,
)


def process(job: Dict[str, Any]) -> Tuple[bool, str]:
    start_time = time.time()
    client = APIClient()
    job_id = job.get("job_id") or job.get("id")
    job_type = job.get("job_type", "Team Retro Topics")
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
    
    # Get closed sprints (last 3 months)
    closed_sprints_formatted = get_closed_sprints_for_analysis(
        client=client,
        team_name=team_name,
        months=3,
    )

    # Build data string (without prompt)
    parts = ["=== TEAM RETRO TOPICS ==="]
    parts.append(f"Team: {team_name}")
    parts.append("")
    
    # Add formatted transcripts (includes "Begin transcript(s)" / "End transcript(s)" markers)
    parts.append(transcripts_formatted)
    parts.append("")
    
    # Add formatted burndown (includes "=== BURN DOWN DATA FOR THE ACTIVE SPRINT ===" header)
    parts.append(burndown_formatted)
    parts.append("")
    
    # Add formatted closed sprints (includes "=== CLOSED SPRINTS DATA ===" header)
    parts.append(closed_sprints_formatted)
    
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
        prompt_base_name="Team Retro Topics",
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
            "card_name": "Team Retro Topics",
            "source": "Team Retro Topics",
        },
        job_type=job_type,
        card_type="Team",
        extract_content_fn=extract_review_section,
    )
    
    # Extract recommendations_json from LLM response for recommendations saving
    extraction = extract_text_and_json(llm_answer)
    recommendations_json = extraction.recommendations_json

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

    # Create detailed result text with full LLM response
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    use_two_step_mode = llm_metadata.get("use_two_step_mode", False)
    
    if use_two_step_mode:
        formatted_first = llm_metadata.get("formatted_first", "")
        formatted_second = llm_metadata.get("formatted_second", "")
        result_text = f"""Team Retro Topics Analysis Completed (Two-Step Process)

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
        result_text = f"""Team Retro Topics Analysis Completed

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

