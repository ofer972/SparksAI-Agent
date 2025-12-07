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


def get_group_sprint_burndown_for_analysis(
    client: APIClient,
    group_name: str,
) -> str:
    """
    Fetch sprint burndown data for all teams in a group and format it for LLM analysis.
    
    Args:
        client: APIClient instance
        group_name: Group name to get burndown for all teams
        
    Returns:
        Formatted string with burndown data for all teams, including headers.
        Returns formatted message if group not found or has no teams.
    """
    try:
        # Get teams in the group
        sc, response = client.get_teams_in_group_by_name(group_name)
        if sc != 200 or not isinstance(response, dict):
            return f"=== BURNDOWN OF ALL TEAMS IN GROUP: {group_name} ===\n⚠️ Failed to fetch teams for group\n"
        
        data = response.get("data") or response
        teams = data.get("teams", [])
        
        if not teams:
            return f"=== BURNDOWN OF ALL TEAMS IN GROUP: {group_name} ===\nNo teams found in group\n"
        
        # Build formatted output
        parts = [f"=== BURNDOWN OF ALL TEAMS IN GROUP: {group_name} ==="]
        parts.append("")
        
        # Get burndown for each team
        for team in teams:
            team_name = team.get("team_name")
            if not team_name:
                continue
            
            parts.append(f"--- Team: {team_name} ---")
            
            # Get burndown for this team
            try:
                team_burndown = get_team_sprint_burndown_for_analysis(client, team_name)
                # Extract content without header using helper function
                burndown_content = _extract_burndown_content_without_header(team_burndown)
                if burndown_content:
                    parts.append(burndown_content)
                else:
                    parts.append("No burndown data available")
                    
            except Exception as e:
                parts.append("No burndown data available")
            
            parts.append("")  # Empty line between teams
        
        return "\n".join(parts)
        
    except Exception as e:
        return f"=== BURNDOWN OF ALL TEAMS IN GROUP: {group_name} ===\n⚠️ Error fetching group burndown data: {str(e)}\n"


def _remove_keys_from_sprint_data(sprint: Dict[str, Any]) -> Dict[str, Any]:
    """Remove issue key fields from sprint data.
    
    Args:
        sprint: Sprint data dictionary
        
    Returns:
        Cleaned sprint dictionary without key fields
    """
    keys_to_remove = [
        "issues_at_start_keys",
        "issues_remaining_keys",
        "issues_added_keys",
        "completed_issue_keys"
    ]
    cleaned = {k: v for k, v in sprint.items() if k not in keys_to_remove}
    return cleaned


def _extract_burndown_content_without_header(burndown_string: str) -> str:
    """Extract burndown content without the header line.
    
    Args:
        burndown_string: Full burndown string with header
        
    Returns:
        Burndown content without header
    """
    header_pattern = "=== BURN DOWN DATA FOR THE ACTIVE SPRINT ==="
    if header_pattern in burndown_string:
        header_index = burndown_string.find(header_pattern)
        if header_index != -1:
            after_header = burndown_string[header_index + len(header_pattern):].lstrip("\n")
            after_header = after_header.rstrip("\n")
            if after_header:
                return after_header
    return burndown_string.strip()


def get_closed_sprints_for_analysis(
    client: APIClient,
    team_name: str,
    months: int = 3,
    issue_type: str | None = None,
) -> str:
    """
    Fetch closed sprints data for a team and format it for LLM analysis.
    
    Args:
        client: APIClient instance
        team_name: Team name to get closed sprints for
        months: Number of months to look back (default: 3)
        issue_type: Optional issue type filter
        
    Returns:
        Formatted string with closed sprints data, including header.
        Returns error message if fetch fails or data is empty.
    """
    try:
        sc, data = client.get_closed_sprints(team_name=team_name, months=months, issue_type=issue_type)
        
        if sc != 200 or not isinstance(data, dict):
            return "=== CLOSED SPRINTS DATA ===\nNo closed sprints data found (HTTP error)\n"
        
        # Extract closed sprints data from response structure
        data_obj = data.get("data", {})
        closed_sprints_by_team = data_obj.get("closed_sprints_by_team", {}) if isinstance(data_obj, dict) else {}
        
        if not closed_sprints_by_team or not isinstance(closed_sprints_by_team, dict):
            return "=== CLOSED SPRINTS DATA ===\nNo closed sprints data found\n"
        
        # Get sprints for this team
        team_sprints = closed_sprints_by_team.get(team_name, [])
        
        if not team_sprints or not isinstance(team_sprints, list):
            return "=== CLOSED SPRINTS DATA ===\nNo closed sprints found for team\n"
        
        # Remove keys fields from each sprint
        cleaned_sprints = [_remove_keys_from_sprint_data(sprint) for sprint in team_sprints]
        
        # Format as table
        parts = ["=== CLOSED SPRINTS DATA ==="]
        parts.append("")
        
        table = format_table(cleaned_sprints, max_width=25)
        if table:
            parts.append(table)
        else:
            parts.append("No closed sprints data available")
        
        parts.append("")
        return "\n".join(parts)
        
    except Exception as e:
        return f"=== CLOSED SPRINTS DATA ===\n⚠️ Error fetching closed sprints: {str(e)}\n"


def get_group_closed_sprints_for_analysis(
    client: APIClient,
    group_name: str,
    months: int = 3,
    issue_type: str | None = None,
) -> str:
    """
    Fetch closed sprints data for all teams in a group and format it for LLM analysis.
    
    Args:
        client: APIClient instance
        group_name: Group name to get closed sprints for all teams
        months: Number of months to look back (default: 3)
        issue_type: Optional issue type filter
        
    Returns:
        Formatted string with closed sprints data for all teams, including headers.
        Returns formatted message if group not found or has no teams.
    """
    try:
        # Get teams in the group
        sc, response = client.get_teams_in_group_by_name(group_name)
        if sc != 200 or not isinstance(response, dict):
            return f"=== CLOSED SPRINTS DATA FOR ALL TEAMS IN GROUP: {group_name} ===\n⚠️ Failed to fetch teams for group\n"
        
        data = response.get("data") or response
        teams = data.get("teams", [])
        
        if not teams:
            return f"=== CLOSED SPRINTS DATA FOR ALL TEAMS IN GROUP: {group_name} ===\nNo teams found in group\n"
        
        # Build formatted output
        parts = [f"=== CLOSED SPRINTS DATA FOR ALL TEAMS IN GROUP: {group_name} ==="]
        parts.append("")
        
        # Get closed sprints for each team
        for team in teams:
            team_name = team.get("team_name")
            if not team_name:
                continue
            
            parts.append(f"--- Team: {team_name} ---")
            
            # Get closed sprints for this team
            try:
                team_closed_sprints = get_closed_sprints_for_analysis(client, team_name, months=months, issue_type=issue_type)
                
                # Remove the header line "=== CLOSED SPRINTS DATA ==="
                header_pattern = "=== CLOSED SPRINTS DATA ==="
                if header_pattern in team_closed_sprints:
                    header_index = team_closed_sprints.find(header_pattern)
                    if header_index != -1:
                        after_header = team_closed_sprints[header_index + len(header_pattern):].lstrip("\n")
                        after_header = after_header.rstrip("\n")
                        if after_header:
                            parts.append(after_header)
                        else:
                            parts.append("No closed sprints data available")
                    else:
                        parts.append(team_closed_sprints)
                else:
                    parts.append(team_closed_sprints.strip())
                    
            except Exception as e:
                parts.append("No closed sprints data available")
            
            parts.append("")  # Empty line between teams
        
        return "\n".join(parts)
        
    except Exception as e:
        return f"=== CLOSED SPRINTS DATA FOR ALL TEAMS IN GROUP: {group_name} ===\n⚠️ Error fetching group closed sprints data: {str(e)}\n"


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


def get_pi_status_for_today_by_team_for_analysis(
    client: APIClient,
    pi: str,
) -> str:
    """
    Fetch PI status for today by team and format as markdown table for LLM.
    
    Args:
        client: APIClient instance
        pi: PI name/identifier
        
    Returns:
        Formatted string with PI status by team as markdown table, including header.
        Returns error message if fetch fails or data is empty.
    """
    from utils_formatting import format_table
    
    status_code, response = client.get_pi_status_for_today_by_team(pi)
    
    if status_code != 200:
        return f"=== PI STATUS BY TEAM ===\n⚠️ Failed to fetch: HTTP {status_code}\n"
    
    # Extract data array from response structure
    if isinstance(response, dict) and response.get("success"):
        data_obj = response.get("data", {})
        if isinstance(data_obj, dict):
            # Extract the nested "data" array
            team_status_list = data_obj.get("data", [])
            if team_status_list and isinstance(team_status_list, list):
                # Format as table using generic format_table function
                table = format_table(team_status_list, max_width=50)
                if table:
                    return f"=== PI STATUS BY TEAM ===\n{table}\n"
                else:
                    return "=== PI STATUS BY TEAM ===\nNo team status data available\n"
            else:
                return "=== PI STATUS BY TEAM ===\nNo team status data found\n"
        else:
            return "=== PI STATUS BY TEAM ===\n⚠️ Invalid response format\n"
    else:
        return "=== PI STATUS BY TEAM ===\n⚠️ Invalid response format\n"


def get_average_sprint_velocity_per_team_for_analysis(
    client: APIClient,
    pi: str,
    num_sprints: int = 5,
) -> str:
    """
    Fetch average sprint velocity per team and format as markdown table for LLM.
    
    Args:
        client: APIClient instance
        pi: PI name/identifier (if provided, uses teams participating in the PI)
        num_sprints: Number of sprints to average (default: 5, max: 20)
        
    Returns:
        Formatted string with average sprint velocity by team as markdown table, including header.
        Returns error message if fetch fails or data is empty.
    """
    from utils_formatting import format_table
    
    status_code, response = client.get_average_sprint_velocity_per_team(
        pi=pi,
        num_sprints=num_sprints,
    )
    
    if status_code != 200:
        return f"=== AVERAGE SPRINT VELOCITY BY TEAM ===\n⚠️ Failed to fetch: HTTP {status_code}\n"
    
    # Extract velocity_data array from response structure
    if isinstance(response, dict) and response.get("success"):
        data_obj = response.get("data", {})
        if isinstance(data_obj, dict):
            velocity_data = data_obj.get("velocity_data", [])
            if velocity_data and isinstance(velocity_data, list):
                # Format as table using generic format_table function
                table = format_table(velocity_data, max_width=50)
                if table:
                    num_sprints_used = data_obj.get("num_sprints", num_sprints)
                    return f"=== AVERAGE SPRINT VELOCITY BY TEAM ===\n(Last {num_sprints_used} sprints)\n{table}\n"
                else:
                    return "=== AVERAGE SPRINT VELOCITY BY TEAM ===\nNo velocity data available\n"
            else:
                return "=== AVERAGE SPRINT VELOCITY BY TEAM ===\nNo velocity data found\n"
        else:
            return "=== AVERAGE SPRINT VELOCITY BY TEAM ===\n⚠️ Invalid response format\n"
    else:
        return "=== AVERAGE SPRINT VELOCITY BY TEAM ===\n⚠️ Invalid response format\n"


def get_epics_by_pi_for_analysis(
    client: APIClient,
    pi: str,
) -> str:
    """
    Fetch epics by PI and format as markdown table for LLM.
    
    Args:
        client: APIClient instance
        pi: PI name/identifier
        
    Returns:
        Formatted string with epics data as markdown table, including header.
        Returns error message if fetch fails or data is empty.
    """
    from utils_formatting import format_table
    
    status_code, response = client.get_epics_by_pi(pi)
    
    if status_code != 200:
        return f"=== EPICS BY PI ===\n⚠️ Failed to fetch: HTTP {status_code}\n"
    
    # Extract epics array from response structure
    if isinstance(response, dict) and response.get("success"):
        data_obj = response.get("data", {})
        if isinstance(data_obj, dict):
            epics = data_obj.get("epics", [])
            if epics and isinstance(epics, list):
                # Format team_progress_breakdown array as readable string
                formatted_epics = []
                for epic in epics:
                    formatted_epic = epic.copy()
                    # Format team_progress_breakdown array
                    team_breakdown = epic.get("team_progress_breakdown", [])
                    if isinstance(team_breakdown, list) and team_breakdown:
                        # Format as: "Team1: 1/2, Team2: 0/1"
                        breakdown_strs = []
                        for team_data in team_breakdown:
                            if isinstance(team_data, dict):
                                team_name = team_data.get("team_name", "")
                                done = team_data.get("done", 0)
                                total = team_data.get("total", 0)
                                breakdown_strs.append(f"{team_name}: {done}/{total}")
                        formatted_epic["team_progress_breakdown"] = ", ".join(breakdown_strs) if breakdown_strs else "[]"
                    elif not team_breakdown:
                        formatted_epic["team_progress_breakdown"] = "[]"
                    formatted_epics.append(formatted_epic)
                
                # Format as table using generic format_table function
                table = format_table(formatted_epics, max_width=50)
                if table:
                    count = data_obj.get("count", len(epics))
                    return f"=== EPICS BY PI ===\n(Total: {count} epics)\n{table}\n"
                else:
                    return "=== EPICS BY PI ===\nNo epic data available\n"
            else:
                return "=== EPICS BY PI ===\nNo epics found\n"
        else:
            return "=== EPICS BY PI ===\n⚠️ Invalid response format\n"
    else:
        return "=== EPICS BY PI ===\n⚠️ Invalid response format\n"


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


def get_pi_dependencies_for_analysis(
    client: APIClient,
    pi: str,
) -> Tuple[str, str, int, int]:
    """
    Fetch inbound and outbound dependencies and format as tables for LLM.
    
    Args:
        client: APIClient instance
        pi: PI name/identifier (e.g., "Q42025")
        
    Returns:
        Tuple of (inbound_formatted, outbound_formatted, inbound_count, outbound_count)
        Each string includes a header and formatted table
        Counts represent the number of dependency items found
    """
    from utils_formatting import format_table
    
    inbound_count = 0
    outbound_count = 0
    
    # Fetch inbound dependencies
    status_code, inbound_response = client.get_epic_inbound_dependency_load_by_quarter(pi)
    if status_code != 200:
        inbound_formatted = f"=== INBOUND DEPENDENCIES ===\n⚠️ Failed to fetch: HTTP {status_code}\n"
    else:
        # Extract data array from response
        if isinstance(inbound_response, dict) and inbound_response.get("success"):
            data = inbound_response.get("data", [])
            if data and isinstance(data, list):
                inbound_count = len(data)
                table = format_table(data, max_width=50)
                inbound_formatted = f"=== INBOUND DEPENDENCIES ===\n{table}\n"
            else:
                inbound_formatted = "=== INBOUND DEPENDENCIES ===\nNo inbound dependency data found\n"
        else:
            inbound_formatted = "=== INBOUND DEPENDENCIES ===\n⚠️ Invalid response format\n"
    
    # Fetch outbound dependencies
    status_code, outbound_response = client.get_epic_outbound_dependency_metrics_by_quarter(pi)
    if status_code != 200:
        outbound_formatted = f"=== OUTBOUND DEPENDENCIES ===\n⚠️ Failed to fetch: HTTP {status_code}\n"
    else:
        # Extract data array from response
        if isinstance(outbound_response, dict) and outbound_response.get("success"):
            data = outbound_response.get("data", [])
            if data and isinstance(data, list):
                outbound_count = len(data)
                table = format_table(data, max_width=50)
                outbound_formatted = f"=== OUTBOUND DEPENDENCIES ===\n{table}\n"
            else:
                outbound_formatted = "=== OUTBOUND DEPENDENCIES ===\nNo outbound dependency data found\n"
        else:
            outbound_formatted = "=== OUTBOUND DEPENDENCIES ===\n⚠️ Invalid response format\n"
    
    return inbound_formatted, outbound_formatted, inbound_count, outbound_count


def get_group_dependencies_for_analysis(
    client: APIClient,
    pi: str,
    group_name: str,
) -> Tuple[str, str, int, int]:
    """
    Fetch inbound and outbound dependencies for a group and format as tables for LLM.
    
    Args:
        client: APIClient instance
        pi: PI name/identifier (e.g., "Q42025")
        group_name: Group name to filter dependencies
        
    Returns:
        Tuple of (inbound_formatted, outbound_formatted, inbound_count, outbound_count)
        Each string includes a header and formatted table
        Counts represent the number of dependency items found
    """
    from utils_formatting import format_table
    
    inbound_count = 0
    outbound_count = 0
    
    # Fetch inbound dependencies
    status_code, inbound_response = client.get_epic_inbound_dependency_load_by_quarter_for_group(pi, group_name)
    if status_code != 200:
        inbound_formatted = f"=== INBOUND DEPENDENCIES ===\n⚠️ Failed to fetch: HTTP {status_code}\n"
    else:
        # Extract data array from response
        if isinstance(inbound_response, dict) and inbound_response.get("success"):
            data = inbound_response.get("data", [])
            if data and isinstance(data, list):
                inbound_count = len(data)
                table = format_table(data, max_width=50)
                inbound_formatted = f"=== INBOUND DEPENDENCIES ===\n{table}\n"
            else:
                inbound_formatted = "=== INBOUND DEPENDENCIES ===\nNo inbound dependency data found\n"
        else:
            inbound_formatted = "=== INBOUND DEPENDENCIES ===\n⚠️ Invalid response format\n"
    
    # Fetch outbound dependencies
    status_code, outbound_response = client.get_epic_outbound_dependency_metrics_by_quarter_for_group(pi, group_name)
    if status_code != 200:
        outbound_formatted = f"=== OUTBOUND DEPENDENCIES ===\n⚠️ Failed to fetch: HTTP {status_code}\n"
    else:
        # Extract data array from response
        if isinstance(outbound_response, dict) and outbound_response.get("success"):
            data = outbound_response.get("data", [])
            if data and isinstance(data, list):
                outbound_count = len(data)
                table = format_table(data, max_width=50)
                outbound_formatted = f"=== OUTBOUND DEPENDENCIES ===\n{table}\n"
            else:
                outbound_formatted = "=== OUTBOUND DEPENDENCIES ===\nNo outbound dependency data found\n"
        else:
            outbound_formatted = "=== OUTBOUND DEPENDENCIES ===\n⚠️ Invalid response format\n"
    
    return inbound_formatted, outbound_formatted, inbound_count, outbound_count


def get_pi_planning_gaps_for_analysis(
    client: APIClient,
    pi: str,
) -> Tuple[str, str, int, int]:
    """
    Fetch PI planning gaps data (using dependency endpoints for now).
    Follows same pattern as get_pi_dependencies_for_analysis.
    
    Args:
        client: APIClient instance
        pi: PI name/identifier (e.g., "Q42025")
        
    Returns:
        Tuple of (inbound_formatted, outbound_formatted, inbound_count, outbound_count)
        Each string includes a header and formatted table
        Counts represent the number of dependency items found
        Note: Currently uses dependency endpoints; can be updated when specific planning gaps endpoint is available
    """
    # For now, use the same dependency endpoints as PI Dependencies
    # This allows analysis of gaps in dependencies/planning
    # TODO: Replace with specific planning gaps endpoint when available
    return get_pi_dependencies_for_analysis(client, pi)