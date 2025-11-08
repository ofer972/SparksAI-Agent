from typing import Any, Dict, Tuple

from api_client import APIClient
from utils_formatting import (
    format_burndown_markdown,
    format_pi_status,
    format_table,
    format_transcript,
    PROMPT_FORMAT_CONSTANTS,
)


def get_prompt_with_error_check(
    client: APIClient,
    email_address: str,
    prompt_name: str,
    job_type: str,
    job_id: int | None = None,
) -> Tuple[str | None, str | None]:
    """
    Fetch prompt from backend with error handling and automatic fallback.
    
    Args:
        client: APIClient instance
        email_address: Email address for prompt (e.g., "DailyAgent", "PIAgent")
        prompt_name: Name of prompt (e.g., "Daily Insights", "PI Sync")
        job_type: Job type for error messages (e.g., "Daily Agent")
        job_id: Optional job ID for logging
    
    Returns:
        Tuple of (prompt_text, error_message):
        - If success: (prompt_text, None)
        - If failure: (None, error_message)
    
    Behavior:
        - Tries URL-encoded prompt name first
        - Falls back to space-separated prompt name if 404
        - Logs alert emoji (🚨) if prompt not found
        - Returns error message suitable for job failure
    """
    # Try URL-encoded prompt name first
    url_encoded_name = prompt_name.replace(" ", "%20")
    status_code, response_data = client.get_prompt(email_address, url_encoded_name)
    
    # If 404, try space-separated version
    if status_code == 404:
        status_code, response_data = client.get_prompt(email_address, prompt_name)
    
    # Check for HTTP errors (other than 404 which we already handled)
    if status_code != 200:
        error_msg = f"Failed to fetch prompt '{prompt_name}' for {email_address}: HTTP {status_code}"
        job_context = f" (Job ID: {job_id})" if job_id is not None else ""
        print(f"🚨 ERROR FETCHING PROMPT: {prompt_name} for {email_address} - Status {status_code}{job_context}")
        return None, error_msg
    
    # Check if response is valid dict
    if not isinstance(response_data, dict):
        error_msg = f"Prompt '{prompt_name}' for {email_address} returned invalid response format"
        job_context = f" (Job ID: {job_id})" if job_id is not None else ""
        print(f"🚨 PROMPT RESPONSE INVALID: {prompt_name} for {email_address} - Invalid response format{job_context}")
        return None, error_msg
    
    # Extract prompt_description from nested response structure
    prompt_text = None
    if isinstance(response_data, dict):
        # Try different response structures (API returns data.prompt.prompt_description)
        data = response_data.get("data") or {}
        if isinstance(data, dict):
            # Check for nested prompt object: data.prompt.prompt_description
            prompt_obj = data.get("prompt")
            if isinstance(prompt_obj, dict):
                prompt_text = prompt_obj.get("prompt_description")
            # Fallback: check for direct prompt_description in data
            if not prompt_text:
                prompt_text = data.get("prompt_description")
        # Final fallback: check root level
        if not prompt_text:
            prompt_text = response_data.get("prompt_description")
    
    # Check if prompt_description exists and is not empty
    if not prompt_text or not isinstance(prompt_text, str) or not prompt_text.strip():
        error_msg = f"Prompt '{prompt_name}' not found for {email_address}"
        job_context = f" (Job ID: {job_id})" if job_id is not None else ""
        print(f"🚨 PROMPT NOT FOUND: {prompt_name} for {email_address}{job_context}")
        return None, error_msg
    
    # Success - log and return prompt with markers
    char_count = len(prompt_text)
    job_context = f" (Job ID: {job_id})" if job_id is not None else ""
    print(f"✅ Prompt fetched: {prompt_name} for {email_address} ({char_count} chars){job_context}")
    
    # Format prompt with markers (consistent across all job types)
    formatted_prompt = f"{PROMPT_FORMAT_CONSTANTS.PROMPT_BEGIN}\n{prompt_text}\n{PROMPT_FORMAT_CONSTANTS.PROMPT_END}"
    return formatted_prompt, None


def fetch_pi_data_for_analysis(
    client: APIClient,
    pi: str,
    team_name: str | None = None,
    include_transcript: bool = True,
) -> Tuple[Dict[str, Any] | None, Dict[str, Any] | None, Dict[str, Any] | None]:
    """
    Fetch PI-related data for analysis (transcript, PI status, burndown).
    
    Args:
        client: APIClient instance
        pi: PI name/identifier
        team_name: Optional team name to pass to PI status and burndown endpoints
        include_transcript: Whether to fetch transcript (default: True)
    
    Returns:
        Tuple of (transcript_obj, pi_status_obj, burndown_obj)
    """
    # Fetch transcript only if requested
    transcript_obj = None
    if include_transcript:
        # Use new unified transcript endpoint
        sc, data = client.get_transcripts(
            transcript_type="PI Sync",
            pi_name=pi,
            limit=1,
        )
        if sc == 200 and isinstance(data, dict):
            data_obj = data.get("data", {})
            transcripts = data_obj.get("transcripts", []) if isinstance(data_obj, dict) else []
            if transcripts and isinstance(transcripts, list) and len(transcripts) > 0:
                transcript_obj = transcripts[0]  # Get first transcript

    # Always fetch PI status
    pi_status_obj = None
    sc, data = client.get_pi_summary_today(pi, team_name=team_name)
    if sc == 200 and isinstance(data, dict):
        pi_status_obj = data.get("data") or data

    # Always fetch burndown
    burndown_obj = None
    sc, data = client.get_pi_burndown(pi, team_name=team_name)
    if sc == 200 and isinstance(data, dict):
        burndown_obj = data.get("data") or data

    return transcript_obj, pi_status_obj, burndown_obj


# ============================================================================
# Data Fetching and Formatting Functions for Analysis
# These functions fetch data from backend AND format it, returning formatted
# strings ready to be appended to LLM prompts. This makes it easy to add
# new data sources to job types with minimal code changes.
# ============================================================================

def get_team_sprint_burndown_for_analysis(
    client: APIClient,
    team_name: str,
) -> str:
    """
    Fetch team sprint burndown data and format it for LLM analysis.
    
    Args:
        client: APIClient instance
        team_name: Team name to get burndown for
        
    Returns:
        Formatted string with burndown data, including header.
        Returns "No burndown data available" if fetch fails or data is empty.
    """
    try:
        sc, bd = client.get_team_sprint_burndown(team_name)
        if sc == 200 and isinstance(bd, dict):
            burndown_obj = bd.get("data") or bd
            if burndown_obj:
                parts = ["=== BURN DOWN DATA FOR THE ACTIVE SPRINT ==="]
                formatted = format_burndown_markdown(burndown_obj)
                parts.append(formatted)
                parts.append("")
                return "\n".join(parts)
    except Exception:
        pass
    
    return "=== BURN DOWN DATA FOR THE ACTIVE SPRINT ===\nNo burndown data available\n"


def get_transcripts_for_analysis(
    client: APIClient,
    transcript_type: str | None = None,
    team_name: str | None = None,
    pi_name: str | None = None,
    limit: int = 1,
) -> str:
    """
    Fetch transcripts and format them for LLM analysis.
    
    Args:
        client: APIClient instance
        transcript_type: 'Daily' | 'PI Sync' | None (optional)
        team_name: Team name (required if type='Daily')
        pi_name: PI name (required if type='PI Sync')
        limit: Number of transcripts to retrieve (default: 1, min: 1, max: 100)
        
    Returns:
        Formatted string with transcript(s) data, including begin/end markers.
        Returns "Begin transcript\nNo transcripts found\nEnd transcript" if fetch fails or data is empty.
    """
    sc, data = client.get_transcripts(
        transcript_type=transcript_type,
        team_name=team_name,
        pi_name=pi_name,
        limit=limit,
    )
    
    if sc != 200 or not isinstance(data, dict):
        return "Begin transcript\nNo transcripts found\nEnd transcript"
    
    # Extract transcripts from response structure
    data_obj = data.get("data", {})
    transcripts = data_obj.get("transcripts", []) if isinstance(data_obj, dict) else []
    
    if not transcripts or not isinstance(transcripts, list):
        return "Begin transcript\nNo transcripts found\nEnd transcript"
    
    # Log how many transcripts were found
    transcript_count = len(transcripts)
    print(f"✅ Found {transcript_count} transcript(s)")
    
    # Determine singular vs plural
    is_plural = transcript_count > 1
    begin_marker = "Begin transcripts" if is_plural else "Begin transcript"
    end_marker = "End transcripts" if is_plural else "End transcript"
    
    # Format each transcript
    parts = [begin_marker]
    for index, transcript in enumerate(transcripts, start=1):
        if not isinstance(transcript, dict):
            continue
        
        # Get transcript_date and raw_text
        transcript_date = transcript.get("transcript_date", "")
        raw_text = transcript.get("raw_text", "")
        
        # Add transcript number, date and content
        parts.append(f"Transcript {index}")
        if transcript_date:
            parts.append(f"transcript_date: {transcript_date}")
        if raw_text:
            parts.append(str(raw_text))
        parts.append("")  # Blank line between transcripts
    
    parts.append(end_marker)
    return "\n".join(parts)


def get_daily_transcript_for_analysis(
    client: APIClient,
    team_name: str,
) -> str:
    """
    Fetch daily transcript and format it for LLM analysis.
    
    This is a convenience wrapper around get_transcripts_for_analysis() for backward compatibility.
    
    Args:
        client: APIClient instance
        team_name: Team name to get daily transcript for
        
    Returns:
        Formatted string with transcript data, including header.
        Returns "No transcript found" if fetch fails or data is empty.
    """
    formatted = get_transcripts_for_analysis(
        client=client,
        transcript_type="Daily",
        team_name=team_name,
        limit=1,
    )
    
    # Add the old header format for backward compatibility
    if "No transcripts found" in formatted:
        return "=== TRANSCRIPT DATA ===\nNo transcript found\n"
    
    # Wrap with old header format
    return f"=== TRANSCRIPT DATA ===\n{formatted}\n"


def get_active_sprint_summary_by_team_for_analysis(
    client: APIClient,
    team_name: str,
) -> Tuple[str, int | None, str | None]:
    """
    Fetch active sprint summary by team and format it for LLM analysis.
    
    Args:
        client: APIClient instance
        team_name: Team name to get active sprint summaries for
        
    Returns:
        Tuple of (formatted_string, sprint_id, sprint_goal):
        - formatted_string: Formatted string with active sprint status, including header.
                           Returns error message if fetch fails or data is empty.
        - sprint_id: The sprint_id from the selected sprint (highest issues_at_start),
                    or None if error/no sprint found.
        - sprint_goal: The sprint_goal from the selected sprint, or None if error/no sprint found.
    """
    sc, summaries_response = client.get_active_sprint_summary_by_team(team_name)
    
    if sc != 200:
        error_msg = "=== ACTIVE SPRINT STATUS ===\nNo active sprint summaries found (HTTP error)\n"
        return error_msg, None, None
    
    if not isinstance(summaries_response, dict):
        error_msg = "=== ACTIVE SPRINT STATUS ===\nNo active sprint summaries found\n"
        return error_msg, None, None
    
    summaries = summaries_response.get("data", {}).get("summaries", [])
    if not summaries:
        error_msg = "=== ACTIVE SPRINT STATUS ===\nNo active sprint summaries found\n"
        return error_msg, None, None
    
    # Find sprint with HIGHEST issues_at_start
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
        error_msg = "=== ACTIVE SPRINT STATUS ===\nNo valid sprint found (no issues_at_start data)\n"
        return error_msg, None, None
    
    # Format the selected sprint data
    parts = ["=== ACTIVE SPRINT STATUS ==="]
    parts.append("-" * 30)
    
    # Format sprint_goal specially
    sprint_goal_text = sprint_with_max_issues.get("sprint_goal", "")
    if sprint_goal_text:
        parts.append("**Sprint Goal:**")
        parts.append(str(sprint_goal_text))
        parts.append("")
    
    # Filter out points columns and sprint_goal, format remaining as key: value
    from datetime import datetime, timezone
    for key, value in sprint_with_max_issues.items():
        if 'point' not in key.lower() and key != 'sprint_goal':
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
    parts.append(f"Current Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    parts.append("")
    
    formatted_string = "\n".join(parts)
    
    # Extract sprint_id and sprint_goal from the selected sprint
    sprint_id = sprint_with_max_issues.get("sprint_id")
    sprint_goal = sprint_with_max_issues.get("sprint_goal", "")
    
    return formatted_string, sprint_id, sprint_goal


def get_sprint_predictability_for_analysis(
    client: APIClient,
    team_name: str,
    months: int = 3,
) -> str:
    """
    Fetch sprint predictability data and format it for LLM analysis.
    
    Args:
        client: APIClient instance
        team_name: Team name to get sprint predictability for
        months: Number of months to look back (default: 3)
        
    Returns:
        Formatted string with sprint predictability data, including header.
        Returns error message if fetch fails or data is empty.
    """
    sc, data = client.get_sprint_predictability(team_name=team_name, months=months)
    
    if sc != 200 or not isinstance(data, dict):
        return "=== Previous Sprints metrics and predictability ===\nNo sprint predictability data found (HTTP error)\n"
    
    # Extract sprint predictability data from response structure
    data_obj = data.get("data", {})
    sprint_predictability_list = data_obj.get("sprint_predictability", []) if isinstance(data_obj, dict) else []
    
    if not sprint_predictability_list or not isinstance(sprint_predictability_list, list):
        return "=== Previous Sprints metrics and predictability ===\nNo sprint predictability data found\n"
    
    # Format as table
    parts = ["=== Previous Sprints metrics and predictability ==="]
    parts.append("")
    
    # Use format_table to create a nice table
    table = format_table(sprint_predictability_list, max_width=25)
    if table:
        parts.append(table)
    else:
        parts.append("No sprint predictability data available")
    
    parts.append("")
    return "\n".join(parts)


def get_sprint_issues_with_epic_for_analysis(
    client: APIClient,
    sprint_id: int,
    team_name: str,
) -> str:
    """
    Fetch sprint issues with epic data and format them for LLM analysis.
    
    Args:
        client: APIClient instance
        sprint_id: Sprint ID to get issues for
        team_name: Team name to filter issues
        
    Returns:
        Formatted string with JIRA issues table, including header.
        Returns "No issues found" if fetch fails or data is empty.
    """
    sc, issues_response = client.get_sprint_issues_with_epic_for_llm(sprint_id, team_name)
    
    jira_issues = []
    if sc == 200 and isinstance(issues_response, dict):
        if issues_response.get("success") and issues_response.get("data", {}).get("sprint_issues"):
            jira_issues = issues_response["data"]["sprint_issues"]
    
    parts = ["=== JIRA ISSUES ==="]
    parts.append("-" * 20)
    
    if jira_issues:
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
    else:
        parts.append("No issues found")
    
    parts.append("")
    
    return "\n".join(parts)


def get_pi_status_for_today_for_analysis(
    client: APIClient,
    pi: str,
    team_name: str | None = None,
) -> str:
    """
    Fetch PI status for today and format it for LLM analysis.
    
    Args:
        client: APIClient instance
        pi: PI name/identifier
        team_name: Optional team name to filter by
        
    Returns:
        Formatted string with PI status, including header.
        Returns "No PI status data available" if fetch fails or data is empty.
    """
    sc, data = client.get_pi_summary_today(pi, team_name=team_name)
    
    if sc == 200 and isinstance(data, dict):
        pi_status_obj = data.get("data") or data
        if pi_status_obj:
            parts = ["=== PI status for current date ==="]
            formatted = format_pi_status(pi_status_obj)
            parts.append(formatted)
            parts.append("")
            return "\n".join(parts)
    
    return "=== PI status for current date ===\nNo PI status data available\n"


def get_pi_burndown_for_analysis(
    client: APIClient,
    pi: str,
    team_name: str | None = None,
) -> str:
    """
    Fetch PI burndown data and format it for LLM analysis.
    
    Args:
        client: APIClient instance
        pi: PI name/identifier
        team_name: Optional team name to filter by
        
    Returns:
        Formatted string with PI burndown data, including header.
        Returns "No burndown data available" if fetch fails or data is empty.
    """
    sc, data = client.get_pi_burndown(pi, team_name=team_name)
    
    if sc == 200 and isinstance(data, dict):
        burndown_obj = data.get("data") or data
        if burndown_obj:
            parts = ["=== PI Burndown Snapshot ==="]
            formatted = format_burndown_markdown(burndown_obj)
            parts.append(formatted)
            parts.append("")
            return "\n".join(parts)
    
    return "=== PI Burndown Snapshot ===\nNo burndown data available\n"

