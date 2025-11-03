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
    format_table,
    PROMPT_FORMAT_CONSTANTS,
)


def process(job: Dict[str, Any]) -> Tuple[bool, str]:
    client = APIClient()
    job_id = job.get("job_id") or job.get("id")
    team_name = job.get("team_name")
    if not team_name:
        return False, "Missing team_name in job payload"

    # Step 1: Get active sprint summaries for team
    sc, summaries_response = client.get_active_sprint_summary_by_team(team_name)
    
    if sc != 200:
        error_msg = f"Failed to get active sprint summaries: HTTP {sc}"
        if isinstance(summaries_response, dict) and "detail" in summaries_response:
            error_msg += f" - {summaries_response.get('detail')}"
        return False, error_msg
    
    summaries = summaries_response.get("data", {}).get("summaries", [])
    if not summaries:
        return True, "No active sprint summaries found for team"
    
    # Step 2: Find sprint with HIGHEST issues_at_start
    sprint_with_max_issues = None
    max_issues_at_start = -1
    
    for summary in summaries:
        issues_at_start = summary.get("issues_at_start", 0)
        # Handle different types (int, float, string)
        if isinstance(issues_at_start, str):
            try:
                issues_at_start = int(issues_at_start)
            except (ValueError, TypeError):
                issues_at_start = 0
        elif not isinstance(issues_at_start, (int, float)):
            issues_at_start = 0
        
        if issues_at_start > max_issues_at_start:
            max_issues_at_start = issues_at_start
            sprint_with_max_issues = summary
    
    if not sprint_with_max_issues:
        return True, "No valid sprint found (no issues_at_start data)"
    
    sprint_id = sprint_with_max_issues.get("sprint_id")
    if not sprint_id:
        return True, "No sprint_id found in active sprint summary"
    
    # Use sprint data directly from the selected summary (no second endpoint call)
    sprint_data = sprint_with_max_issues
    
    # Validate sprint_goal
    sprint_goal = sprint_data.get("sprint_goal", "")
    if not sprint_goal or len(str(sprint_goal).strip()) < 10:
        print("❌ Sprint goal not found")
        return True, "No sprint Goal found"
    
    print(f"✅ Sprint goal found")
    
    # Step 3: Get JIRA issues for the sprint with epic data
    sc, issues_response = client.get_sprint_issues_with_epic_for_llm(sprint_id, team_name)
    
    jira_issues = []
    if sc == 200 and issues_response.get("success") and issues_response.get("data", {}).get("sprint_issues"):
        jira_issues = issues_response["data"]["sprint_issues"]
        print(f"✅ Read {len(jira_issues)} issues from sprint")
    else:
        print(f"⚠️ No JIRA issues found for sprint (status: {sc})")
        jira_issues = []
    
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
    
    # Step 5: Format data exactly as old project
    parts = ["SPRINT GOAL ANALYSIS DATA", "=" * 50, ""]
    
    # ACTIVE SPRINT STATUS section
    parts.append("ACTIVE SPRINT STATUS:")
    parts.append("-" * 30)
    
    # Format sprint_goal specially
    sprint_goal_text = sprint_data.get("sprint_goal", "")
    if sprint_goal_text:
        parts.append("**Sprint Goal:**")
        parts.append(str(sprint_goal_text))
        parts.append("")
    
    # Filter out points columns and sprint_goal, format remaining as key: value
    for key, value in sprint_data.items():
        if 'point' not in key.lower() and key != 'sprint_goal':  # Exclude points columns and sprint_goal
            # Format the value
            if value is None:
                formatted_value = ""
            elif hasattr(value, 'isoformat'):  # datetime object
                formatted_value = value.isoformat()
            elif hasattr(value, 'strftime'):  # date object
                formatted_value = value.strftime('%Y-%m-%d %H:%M:%S')
            else:
                formatted_value = str(value)
            parts.append(f"{key}: {formatted_value}")
    
    parts.append("")
    
    # Current Date
    parts.append(f"Current Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    parts.append("")
    
    # JIRA ISSUES section
    if jira_issues:
        parts.append("JIRA ISSUES:")
        parts.append("-" * 20)
        
        # Prepare issues data for table formatting (format arrays as strings)
        formatted_issues = []
        for issue in jira_issues:
            formatted_issue = {}
            
            # Handle each field
            formatted_issue['issue_key'] = issue.get('issue_key', '') or ''
            formatted_issue['issue_summary'] = str(issue.get('issue_summary', '') or '')
            
            issue_description_raw = issue.get('issue_description') or None
            if issue_description_raw:
                if isinstance(issue_description_raw, str):
                    formatted_issue['issue_description'] = issue_description_raw
                else:
                    formatted_issue['issue_description'] = str(issue_description_raw)
            else:
                formatted_issue['issue_description'] = ''
            
            formatted_issue['issue_type'] = issue.get('issue_type', '') or ''
            formatted_issue['status_category'] = issue.get('status_category', '') or ''
            
            # Format flagged: array -> string representation
            flagged_raw = issue.get('flagged', [])
            if isinstance(flagged_raw, list):
                formatted_issue['flagged'] = str(flagged_raw) if flagged_raw else "[]"
            else:
                formatted_issue['flagged'] = str(flagged_raw) if flagged_raw else "[]"
            
            # Format dependency: array -> string representation
            dependency_raw = issue.get('dependency', [])
            if isinstance(dependency_raw, list):
                formatted_issue['dependency'] = str(dependency_raw) if dependency_raw else "[]"
            else:
                formatted_issue['dependency'] = str(dependency_raw) if dependency_raw else "[]"
            
            formatted_issue['epic_summary'] = issue.get('epic_summary', '') or ''
            
            formatted_issues.append(formatted_issue)
        
        # Format as table using the same function as burndown
        table_formatted = format_table(formatted_issues, max_width=100)
        if table_formatted:
            parts.append(table_formatted)
        else:
            parts.append("No issues found")
        
        parts.append("")
    else:
        parts.append("JIRA ISSUES:")
        parts.append("-" * 20)
        parts.append("No issues found")
        parts.append("")
    
    # ANALYSIS PROMPT section
    if prompt_text:
        parts.append(PROMPT_FORMAT_CONSTANTS.PROMPT_BEGIN)
        parts.append(prompt_text)
        parts.append(PROMPT_FORMAT_CONSTANTS.PROMPT_END)
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

    # Extract structured content from LLM response
    print("📋 EXTRACTING STRUCTURED CONTENT FROM LLM RESPONSE")
    
    # Extract and separate text from JSON
    full_information, dashboard_summary_json, recommendations_json, raw_json_string = extract_text_and_json(llm_answer)
    
    # Extract Sprint Goal Analysis section (using same markers as Daily Progress)
    sprint_goal_content = extract_content_between_markers(
        llm_answer, 
        LLM_EXTRACTION_CONSTANTS.START_MARKER, 
        LLM_EXTRACTION_CONSTANTS.END_MARKER
    )
    
    # Use extracted section if available, otherwise fallback to full response (truncated)
    description = sprint_goal_content if sprint_goal_content else llm_answer[:2000]
    
    # Truncate full_information if needed (for database storage)
    full_info_truncated = full_information[:2000] if len(full_information) > 2000 else full_information

    # Upsert Team AI Card
    today = datetime.now(timezone.utc).date().isoformat()
    card_payload = {
        "team_name": team_name,
        "card_name": "Sprint Goal Analysis",
        "card_type": "Sprint Goal",
        "description": description[:2000],  # Truncate description if too long
        "date": today,
        "priority": "High",
        "source": "Sprint Goal",
        "source_job_id": job_id,
        "full_information": full_info_truncated,  # Text before JSON
    }
    
    # Add information_json with raw JSON string from BEGIN_JSON/END_JSON
    if raw_json_string:
        card_payload["information_json"] = raw_json_string
    sc, cards = client.list_team_ai_cards()
    upsert_done = False
    if sc == 200 and isinstance(cards, dict):
        items = cards.get("data") or cards
        if isinstance(items, list):
            for c in items:
                try:
                    same_date = str(c.get("date", ""))[:10] == today
                    if same_date and c.get("team_name") == card_payload["team_name"] and c.get("card_name") == card_payload["card_name"]:
                        psc, presp = client.patch_team_ai_card(int(c.get("id")), card_payload)
                        if psc >= 300:
                            print(f"⚠️ Patch team-ai-card failed: {psc} {presp}")
                        upsert_done = psc < 300
                        break
                except Exception:
                    continue
    if not upsert_done:
        csc, cresp = client.create_team_ai_card(card_payload)
        if csc >= 300:
            print(f"⚠️ Create team-ai-card failed: {csc} {cresp}")

    print(
        f"🗂️ Card insight: name='{card_payload['card_name']}' type='{card_payload['card_type']}' priority='{card_payload['priority']}' preview='{card_payload['description'][:120]}'"
    )

    # Extract and create recommendations
    print("📋 EXTRACTING AND SAVING RECOMMENDATIONS")
    
    # First try to extract recommendations from JSON if available
    recommendations_saved = save_recommendations_from_json(
        client=client,
        recommendations_json=recommendations_json,
        team_name_or_pi=team_name,
        today=today,
        full_info_truncated=full_info_truncated,
        max_count=2,
        job_id=int(job_id) if job_id is not None else None
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


