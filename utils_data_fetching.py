import json
from typing import Any, Dict, Tuple

from api_client import APIClient
from utils_formatting import (
    format_burndown_markdown,
    format_pi_status,
    format_table,
    format_transcript,
    PROMPT_FORMAT_CONSTANTS,
)
from utils_logging import log


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
        log(job_id, f"🚨 ERROR FETCHING PROMPT: {prompt_name} for {email_address} - Status {status_code}")
        return None, error_msg
    
    # Check if response is valid dict
    if not isinstance(response_data, dict):
        error_msg = f"Prompt '{prompt_name}' for {email_address} returned invalid response format"
        log(job_id, f"🚨 PROMPT RESPONSE INVALID: {prompt_name} for {email_address} - Invalid response format")
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
        log(job_id, f"🚨 PROMPT NOT FOUND: {prompt_name} for {email_address}")
        return None, error_msg
    
    # Success - log and return prompt with markers
    char_count = len(prompt_text)
    log(job_id, f"✅ Prompt fetched: {prompt_name} for {email_address} ({char_count} chars)")
    
    # Format prompt with markers (consistent across all job types)
    formatted_prompt = f"{PROMPT_FORMAT_CONSTANTS.PROMPT_BEGIN}\n{prompt_text}\n{PROMPT_FORMAT_CONSTANTS.PROMPT_END}"
    return formatted_prompt, None


def get_prompt_with_active_check(
    client: APIClient,
    email_address: str,
    prompt_name: str,
    job_type: str,
    job_id: int | None = None,
) -> Tuple[str | None, str | None, bool | None, Dict[str, Any] | None]:
    """
    Fetch prompt from backend with error handling and active status check.
    
    Args:
        client: APIClient instance
        email_address: Email address for prompt (e.g., "DailyAgent", "PIAgent")
        prompt_name: Name of prompt (e.g., "Daily Insights", "PI Sync")
        job_type: Job type for error messages (e.g., "Daily Agent")
        job_id: Optional job ID for logging
    
    Returns:
        Tuple of (prompt_text, error_message, prompt_active, raw_response):
        - If success: (prompt_text, None, prompt_active, raw_response)
        - If failure: (None, error_message, None, raw_response)
        - prompt_active: True if active, False if inactive, None if not found
        - raw_response: The raw API response dict
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
        log(job_id, f"🚨 ERROR FETCHING PROMPT: {prompt_name} for {email_address} - Status {status_code}")
        return None, error_msg, None, response_data if isinstance(response_data, dict) else {}
    
    # Check if response is valid dict
    if not isinstance(response_data, dict):
        error_msg = f"Prompt '{prompt_name}' for {email_address} returned invalid response format"
        log(job_id, f"🚨 PROMPT RESPONSE INVALID: {prompt_name} for {email_address} - Invalid response format")
        return None, error_msg, None, {}
    
    # Extract prompt_description and prompt_active from nested response structure
    prompt_text = None
    prompt_active = None
    
    if isinstance(response_data, dict):
        # Try different response structures (API returns data.prompt.prompt_description)
        data = response_data.get("data") or {}
        if isinstance(data, dict):
            # Check for nested prompt object: data.prompt.prompt_description
            prompt_obj = data.get("prompt")
            if isinstance(prompt_obj, dict):
                prompt_text = prompt_obj.get("prompt_description")
                prompt_active = prompt_obj.get("prompt_active")
            # Fallback: check for direct prompt_description in data
            if not prompt_text:
                prompt_text = data.get("prompt_description")
                prompt_active = data.get("prompt_active")
        # Final fallback: check root level
        if not prompt_text:
            prompt_text = response_data.get("prompt_description")
            prompt_active = response_data.get("prompt_active")
    
    # Check if prompt_description exists and is not empty
    if not prompt_text or not isinstance(prompt_text, str) or not prompt_text.strip():
        error_msg = f"Prompt '{prompt_name}' not found for {email_address}"
        log(job_id, f"🚨 PROMPT NOT FOUND: {prompt_name} for {email_address}")
        return None, error_msg, None, response_data
    
    # Success - log and return prompt with markers
    char_count = len(prompt_text)
    active_status = "active" if prompt_active else "inactive"
    log(job_id, f"✅ Prompt fetched: {prompt_name} for {email_address} ({char_count} chars, {active_status})")
    
    # Format prompt with markers (consistent across all job types)
    formatted_prompt = f"{PROMPT_FORMAT_CONSTANTS.PROMPT_BEGIN}\n{prompt_text}\n{PROMPT_FORMAT_CONSTANTS.PROMPT_END}"
    return formatted_prompt, None, prompt_active, response_data


def fetch_pi_data_for_analysis(
    client: APIClient,
    pi: str,
    team_name: str | None = None,
    is_group: bool = False,
    include_transcript: bool = True,
) -> Tuple[Dict[str, Any] | None, Dict[str, Any] | None, Dict[str, Any] | None]:
    """
    Fetch PI-related data for analysis (transcript, PI status, burndown).
    
    Args:
        client: APIClient instance
        pi: PI name/identifier
        team_name: Optional team name or group name (if is_group=true) to pass to PI status and burndown endpoints
        is_group: If true, team_name is treated as a group name
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
    sc, data = client.get_pi_summary_today(pi, team_name=team_name, is_group=is_group)
    if sc == 200 and isinstance(data, dict):
        pi_status_obj = data.get("data") or data

    # Always fetch burndown
    burndown_obj = None
    sc, data = client.get_pi_burndown(pi, team_name=team_name, is_group=is_group)
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
    job_id: int | None = None,
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
    log(job_id, f"✅ Found {transcript_count} transcript(s)")
    
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
        - sprint_id: The sprint_id from the selected sprint (highest total issues: to_do + in_progress + done),
                    or None if error/no sprint found.
        - sprint_goal: The sprint_goal from the selected sprint, or None if error/no sprint found.
    """
    selected, _total_issues, error_msg = get_selected_active_sprint_summary(
        client=client,
        name=team_name,
        is_group=False,
    )
    if error_msg or not selected:
        return error_msg or "=== ACTIVE SPRINT STATUS ===\nNo active sprint summaries found\n", None, None

    formatted_string = format_active_sprint_summary_for_analysis(selected)
    sprint_id = selected.get("sprint_id")
    sprint_goal = selected.get("sprint_goal", "")

    return formatted_string, sprint_id, sprint_goal


def _safe_int(value: Any) -> int:
    """Safely convert value to int, handling strings and nulls."""
    if isinstance(value, str):
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0
    if isinstance(value, (int, float)):
        return int(value)
    return 0


def _calc_total_issues_from_summary(summary: Dict[str, Any]) -> int:
    """Calculate total issues = to_do + in_progress + done from a sprint summary row."""
    total_issues_to_do = _safe_int(summary.get("total_issues_to_do", 0))
    total_issues_in_progress = _safe_int(summary.get("total_issues_in_progress", 0))
    total_issues_done = _safe_int(summary.get("total_issues_done", 0))
    return total_issues_to_do + total_issues_in_progress + total_issues_done


def select_sprint_with_max_total_issues(
    summaries: list[Dict[str, Any]],
) -> tuple[Dict[str, Any] | None, int]:
    """Select the sprint summary row with the maximum total issues."""
    selected: Dict[str, Any] | None = None
    max_total_issues = -1

    for summary in summaries or []:
        if not isinstance(summary, dict):
            continue
        total_issues = _calc_total_issues_from_summary(summary)
        if total_issues > max_total_issues:
            max_total_issues = total_issues
            selected = summary

    return selected, max_total_issues


def get_selected_active_sprint_summary(
    client: APIClient,
    name: str,
    is_group: bool = False,
) -> tuple[Dict[str, Any] | None, int | None, str | None]:
    """
    Fetch active sprint summaries and select the one with max total issues.

    Returns:
        (selected_summary, selected_total_issues, error_msg)
    """
    sc, summaries_response = client.get_active_sprint_summary_by_team(
        team_name=name,
        is_group=is_group,
    )

    if sc != 200:
        error_msg = f"=== ACTIVE SPRINT STATUS ===\nNo active sprint summaries found (HTTP error: {sc})\n"
        return None, None, error_msg

    if not isinstance(summaries_response, dict):
        error_msg = "=== ACTIVE SPRINT STATUS ===\nNo active sprint summaries found\n"
        return None, None, error_msg

    summaries = summaries_response.get("data", {}).get("summaries", [])
    if not summaries or not isinstance(summaries, list):
        error_msg = "=== ACTIVE SPRINT STATUS ===\nNo active sprint summaries found\n"
        return None, None, error_msg

    selected, max_total_issues = select_sprint_with_max_total_issues(summaries)
    if not selected:
        error_msg = "=== ACTIVE SPRINT STATUS ===\nNo valid sprint found (no total issues data)\n"
        return None, None, error_msg

    return selected, max_total_issues, None


def format_active_sprint_summary_for_analysis(selected_summary: Dict[str, Any]) -> str:
    """Format a selected sprint summary row for LLM analysis."""
    parts = ["=== ACTIVE SPRINT STATUS ===", "-" * 30]

    sprint_goal_text = selected_summary.get("sprint_goal", "")
    if sprint_goal_text:
        parts.append("**Sprint Goal:**")
        parts.append(str(sprint_goal_text))
        parts.append("")

    # Filter out points columns and sprint_goal, format remaining as key: value
    from datetime import datetime, timezone

    for key, value in selected_summary.items():
        if "point" in str(key).lower() or key == "sprint_goal":
            continue
        if value is None:
            formatted_value = ""
        elif hasattr(value, "isoformat"):
            formatted_value = value.isoformat()
        elif hasattr(value, "strftime"):
            formatted_value = value.strftime("%Y-%m-%d %H:%M:%S")
        else:
            formatted_value = str(value)
        parts.append(f"{key}: {formatted_value}")

    parts.append("")
    parts.append(f"Current Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    parts.append("")

    return "\n".join(parts)


def sprint_gate_get_sprint_id_or_stop(
    client: APIClient,
    name: str,
    is_group: bool = False,
) -> tuple[int | None, str | None]:
    """
    Determine whether to continue a sprint-scoped job.

    Rules:
    - If no sprint_id (null/missing), stop.
    - If total issues is available/computable and <= 0, stop.
    - On stop, return (None, stop_message). The caller should return success=True with that message.
    """
    selected, total_issues, error_msg = get_selected_active_sprint_summary(
        client=client,
        name=name,
        is_group=is_group,
    )

    if error_msg or not selected:
        return None, "No active sprint found. Insight was not created. Job stopped."

    sprint_id_raw = selected.get("sprint_id")
    sprint_id = _safe_int(sprint_id_raw)
    if sprint_id <= 0:
        return None, "No active sprint found. Insight was not created. Job stopped."

    # total_issues is computed from summary; if it exists and is <= 0, stop
    if total_issues is not None and total_issues <= 0:
        return None, "No active sprint found. Insight was not created. Job stopped."

    return sprint_id, None


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
    team_name: str | None = None,
    is_group: bool = False,
) -> str:
    """
    Fetch PI status for today by team and format as markdown table for LLM.
    
    Args:
        client: APIClient instance
        pi: PI name/identifier
        team_name: Optional team name or group name (if is_group=true) to filter by
        is_group: If true, team_name is treated as a group name
        
    Returns:
        Formatted string with PI status by team as markdown table, including header.
        Returns error message if fetch fails or data is empty.
    """
    from utils_formatting import format_table
    
    status_code, response = client.get_pi_status_for_today_by_team(pi, team_name=team_name, is_group=is_group)
    
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
    team_name: str | None = None,
    is_group: bool = False,
) -> str:
    """
    Fetch average sprint velocity per team and format as markdown table for LLM.
    
    Args:
        client: APIClient instance
        pi: PI name/identifier (if provided, uses teams participating in the PI)
        num_sprints: Number of sprints to average (default: 5, max: 20)
        team_name: Optional team name or group name (if is_group=true) to filter by
        is_group: If true, team_name is treated as a group name
        
    Returns:
        Formatted string with average sprint velocity by team as markdown table, including header.
        Returns error message if fetch fails or data is empty.
    """
    from utils_formatting import format_table
    
    status_code, response = client.get_average_sprint_velocity_per_team(
        pi=pi,
        num_sprints=num_sprints,
        team_name=team_name,
        is_group=is_group,
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
    team_name: str | None = None,
    is_group: bool = False,
) -> str:
    """
    Fetch epics by PI and format as markdown table for LLM.
    
    Args:
        client: APIClient instance
        pi: PI name/identifier
        team_name: Optional team name or group name (if is_group=true) to filter by
        is_group: If true, team_name is treated as a group name
        
    Returns:
        Formatted string with epics data as markdown table, including header.
        Returns error message if fetch fails or data is empty.
    """
    from utils_formatting import format_table
    
    status_code, response = client.get_epics_by_pi(pi, team_name=team_name, is_group=is_group)
    
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


def get_epics_average_velocity_for_analysis(
    client: APIClient,
    pi: str,
    team_name: str | None = None,
    is_group: bool = False,
    num_pis: int = 3,
) -> str:
    """
    Fetch epics average velocity and format for LLM analysis.
    
    Args:
        client: APIClient instance
        pi: PI name/identifier
        team_name: Optional team name or group name (if is_group=true) to filter by
        is_group: If true, team_name is treated as a group name
        num_pis: Number of recent completed PIs to analyze (default: 3, min: 1, max: 20)
        
    Returns:
        Formatted string with epic velocity data, including header.
        Returns error message if fetch fails or data is empty.
    """
    from utils_formatting import format_table
    
    status_code, response = client.get_epics_average_velocity(
        pi=pi,
        team_name=team_name,
        is_group=is_group,
        num_pis=num_pis,
    )
    
    if status_code != 200:
        return f"=== EPICS AVERAGE VELOCITY ===\n⚠️ Failed to fetch: HTTP {status_code}\n"
    
    # Extract data from response structure
    if isinstance(response, dict) and response.get("success"):
        data_obj = response.get("data", {})
        if isinstance(data_obj, dict):
            parts = ["=== EPICS AVERAGE VELOCITY ==="]
            
            # Add PIs analyzed information
            num_pis_analyzed = data_obj.get("num_pis", 0)
            parts.append(f"PIs Analyzed: {num_pis_analyzed}")
            
            pis_analyzed = data_obj.get("pis_analyzed", [])
            if pis_analyzed and isinstance(pis_analyzed, list):
                pi_names = []
                for pi_info in pis_analyzed:
                    if isinstance(pi_info, dict):
                        pi_name = pi_info.get("pi_name", "")
                        end_date = pi_info.get("end_date", "")
                        if pi_name:
                            if end_date:
                                pi_names.append(f"{pi_name} (ended: {end_date})")
                            else:
                                pi_names.append(pi_name)
                if pi_names:
                    parts.append(f"PI Names: {', '.join(pi_names)}")
            parts.append("")
            
            # Add velocity by team table
            velocity_by_team = data_obj.get("velocity_by_team", [])
            if velocity_by_team and isinstance(velocity_by_team, list):
                parts.append("Velocity by Team:")
                table = format_table(velocity_by_team, max_width=50)
                if table:
                    parts.append(table)
                else:
                    parts.append("No team velocity data available")
            else:
                parts.append("Velocity by Team:")
                parts.append("No team velocity data found")
            parts.append("")
            
            # Add overall PI velocity
            overall_velocity = data_obj.get("overall_pi_velocity", {})
            if overall_velocity and isinstance(overall_velocity, dict):
                parts.append("Overall PI Velocity:")
                completed_epics = overall_velocity.get("completed_epics_in_selected_pis")
                avg_velocity = overall_velocity.get("average_velocity")
                
                if completed_epics is not None:
                    parts.append(f"completed_epics_in_selected_pis = {completed_epics}")
                if avg_velocity is not None:
                    parts.append(f"average_velocity = {avg_velocity}")
            else:
                parts.append("Overall PI Velocity:")
                parts.append("No overall velocity data available")
            
            return "\n".join(parts) + "\n"
        else:
            return "=== EPICS AVERAGE VELOCITY ===\n⚠️ Invalid response format\n"
    else:
        return "=== EPICS AVERAGE VELOCITY ===\n⚠️ Invalid response format\n"


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
    team_name: str | None = None,
    is_group: bool = False,
) -> Tuple[str, str, int, int]:
    """
    Fetch inbound and outbound dependencies and format as tables for LLM.
    
    Args:
        client: APIClient instance
        pi: PI name/identifier (e.g., "Q42025")
        team_name: Optional team name or group name (if is_group=true) to filter by
        is_group: If true, team_name is treated as a group name
        
    Returns:
        Tuple of (inbound_formatted, outbound_formatted, inbound_count, outbound_count)
        Each string includes a header and formatted table
        Counts represent the number of dependency items found
    """
    from utils_formatting import format_table
    
    inbound_count = 0
    outbound_count = 0
    
    # Fetch inbound dependencies
    status_code, inbound_response = client.get_epic_inbound_dependency_load_by_quarter(pi, team_name=team_name, is_group=is_group)
    if status_code != 200:
        inbound_formatted = f"=== INBOUND DEPENDENCIES ===\n⚠️ Failed to fetch: HTTP {status_code}\n"
    else:
        # Extract data array from response
        if isinstance(inbound_response, dict) and inbound_response.get("success"):
            data = inbound_response.get("data", [])
            if data and isinstance(data, list):
                inbound_count = len(data)
                table = format_table(data, max_width=50)
                # Extract average_number_of_dependencies_per_team from response root and append after table
                avg_deps = inbound_response.get("average_number_of_dependencies_per_team")
                if avg_deps is not None:
                    inbound_formatted = f"=== INBOUND DEPENDENCIES ===\n{table}\n\naverage_number_of_dependencies_per_team: {avg_deps}\n"
                else:
                    inbound_formatted = f"=== INBOUND DEPENDENCIES ===\n{table}\n"
            else:
                inbound_formatted = "=== INBOUND DEPENDENCIES ===\nNo inbound dependency data found\n"
        else:
            inbound_formatted = "=== INBOUND DEPENDENCIES ===\n⚠️ Invalid response format\n"
    
    # Fetch outbound dependencies
    status_code, outbound_response = client.get_epic_outbound_dependency_metrics_by_quarter(pi, team_name=team_name, is_group=is_group)
    if status_code != 200:
        outbound_formatted = f"=== OUTBOUND DEPENDENCIES ===\n⚠️ Failed to fetch: HTTP {status_code}\n"
    else:
        # Extract data array from response
        if isinstance(outbound_response, dict) and outbound_response.get("success"):
            data = outbound_response.get("data", [])
            if data and isinstance(data, list):
                outbound_count = len(data)
                table = format_table(data, max_width=50)
                # Extract average_number_of_dependencies_per_team from response root and append after table
                avg_deps = outbound_response.get("average_number_of_dependencies_per_team")
                if avg_deps is not None:
                    outbound_formatted = f"=== OUTBOUND DEPENDENCIES ===\n{table}\n\naverage_number_of_dependencies_per_team: {avg_deps}\n"
                else:
                    outbound_formatted = f"=== OUTBOUND DEPENDENCIES ===\n{table}\n"
            else:
                outbound_formatted = "=== OUTBOUND DEPENDENCIES ===\nNo outbound dependency data found\n"
        else:
            outbound_formatted = "=== OUTBOUND DEPENDENCIES ===\n⚠️ Invalid response format\n"
    
    return inbound_formatted, outbound_formatted, inbound_count, outbound_count


def get_group_sprint_dependencies_for_analysis(
    client: APIClient,
    group_name: str,
) -> str:
    """
    Fetch active sprint epic dependencies for a group and format for LLM analysis.
    
    Args:
        client: APIClient instance
        group_name: Group name to get active sprint epic dependencies for
        
    Returns:
        Formatted string with:
        - Group name
        - Teams in group list
        - Description text
        - Formatted table with dependencies data
        Returns error message if fetch fails or data is empty.
    """
    from utils_formatting import format_table
    
    status_code, response = client.get_active_sprint_epic_dependencies(group_name)
    
    if status_code != 200:
        return f"=== GROUP SPRINT DEPENDENCY DATA ===\nGroup: {group_name}\n⚠️ Failed to fetch: HTTP {status_code}\n"
    
    # Extract data from response structure
    if not isinstance(response, dict) or not response.get("success"):
        return f"=== GROUP SPRINT DEPENDENCY DATA ===\nGroup: {group_name}\n⚠️ Invalid response format\n"
    
    data = response.get("data", {})
    if not isinstance(data, dict):
        return f"=== GROUP SPRINT DEPENDENCY DATA ===\nGroup: {group_name}\n⚠️ Invalid response format\n"
    
    # Extract group name and teams from response
    response_group_name = data.get("group_name", group_name)
    teams_in_group = data.get("teams_in_group", [])
    dependencies = data.get("dependencies", [])
    
    # Build formatted output
    parts = [f"=== GROUP SPRINT DEPENDENCY DATA ==="]
    parts.append(f"Group: {response_group_name}")
    parts.append("")
    
    # Add teams in group
    if teams_in_group and isinstance(teams_in_group, list):
        parts.append("Teams in Group:")
        for team in teams_in_group:
            parts.append(f"- {team}")
    else:
        parts.append("Teams in Group: No teams found")
    parts.append("")
    
    # Add description
    parts.append("List of epics owned by the group that have Dependent child issues in the active sprint:")
    parts.append("")
    
    # Add formatted table with dependencies
    if dependencies and isinstance(dependencies, list) and len(dependencies) > 0:
        table = format_table(dependencies, max_width=50)
        if table:
            parts.append(table)
        else:
            parts.append("No dependency data available in table format")
    else:
        parts.append("No dependencies found")
    
    return "\n".join(parts)


def get_group_active_sprint_stories_by_epic_for_analysis(
    client: APIClient,
    group_name: str,
) -> str:
    """
    Fetch active sprint child issues by epic for a group and format for LLM analysis.
    
    Args:
        client: APIClient instance
        group_name: Group name to get active sprint child issues by epic for
        
    Returns:
        Formatted string with:
        - Description text
        - Formatted table with child issues data
        Returns error message if fetch fails or data is empty.
    """
    from utils_formatting import format_table
    
    status_code, response = client.get_active_sprint_stories_by_epic(group_name)
    
    if status_code != 200:
        return f"List of all epics that are in progress that have child issues in the active sprint and the list of child issues in each epic:\n⚠️ Failed to fetch: HTTP {status_code}\n"
    
    # Extract data from response structure
    if not isinstance(response, dict) or not response.get("success"):
        return f"List of all epics that are in progress that have child issues in the active sprint and the list of child issues in each epic:\n⚠️ Invalid response format\n"
    
    data = response.get("data", [])
    
    # Build formatted output
    parts = []
    
    # Add description
    parts.append("List of all epics that are in progress that have child issues in the active sprint and the list of child issues in each epic:")
    parts.append("")
    
    # Add formatted table with child issues
    if data and isinstance(data, list) and len(data) > 0:
        table = format_table(data, max_width=70)
        if table:
            parts.append(table)
        else:
            parts.append("No child issue data available in table format")
    else:
        parts.append("No child issues found")
    
    return "\n".join(parts)


def get_current_sprint_progress_for_analysis(
    client: APIClient,
    team_name: str,
) -> str:
    """
    Fetch current sprint progress data and format it for LLM analysis.
    
    Args:
        client: APIClient instance
        team_name: Team name to get current sprint progress for
        
    Returns:
        Formatted string with current sprint progress data, including header.
        Returns "No sprint progress data available" if fetch fails or data is empty.
    """
    try:
        sc, response = client.get_current_sprint_progress(team_name=team_name, is_group=False)
        
        if sc != 200 or not isinstance(response, dict):
            return "=== CURRENT SPRINT PROGRESS ===\nNo sprint progress data available (HTTP error)\n"
        
        # Extract data from response structure
        data = response.get("data", {})
        if not isinstance(data, dict):
            return "=== CURRENT SPRINT PROGRESS ===\nNo sprint progress data available\n"
        
        # Extract fields from response
        total_issues = data.get("total_issues", 0)
        completed_issues = data.get("completed_issues", 0)
        in_progress_issues = data.get("in_progress_issues", 0)
        todo_issues = data.get("todo_issues", 0)
        percent_completed = data.get("percent_completed", 0.0)
        percent_completed_status = data.get("percent_completed_status", "")
        in_progress_issues_status = data.get("in_progress_issues_status", "")
        sprint_id = data.get("sprint_id")
        sprint_name = data.get("sprint_name", "")
        days_left = data.get("days_left", "")
        days_in_sprint = data.get("days_in_sprint")
        
        # Format the data
        parts = ["=== CURRENT SPRINT PROGRESS ==="]
        parts.append("")
        
        # Sprint information
        if sprint_name:
            parts.append(f"Sprint: {sprint_name}")
        if sprint_id:
            parts.append(f"Sprint ID: {sprint_id}")
        if days_left:
            parts.append(f"Days Left: {days_left}")
        if days_in_sprint is not None:
            parts.append(f"Days in Sprint: {days_in_sprint}")
        parts.append("")
        
        # Issue counts
        parts.append(f"Total Issues: {total_issues}")
        parts.append(f"Completed Issues: {completed_issues} ({percent_completed:.1f}%)")
        parts.append(f"In Progress Issues: {in_progress_issues}")
        parts.append(f"To Do Issues: {todo_issues}")
        parts.append("")
        
        # Status indicators
        if percent_completed_status or in_progress_issues_status:
            parts.append("Status Indicators:")
            if percent_completed_status:
                parts.append(f"  Completion Status: {percent_completed_status}")
            if in_progress_issues_status:
                parts.append(f"  In Progress Status: {in_progress_issues_status}")
        
        parts.append("")
        
        return "\n".join(parts)
        
    except Exception as e:
        return f"=== CURRENT SPRINT PROGRESS ===\n⚠️ Error fetching sprint progress: {str(e)}\n"


def get_goal_progress_for_analysis(
    client: APIClient,
    sprint_id: int,
    team_name: str,
) -> str:
    """
    Fetch goal progress data for a sprint and format it for LLM analysis.
    
    Args:
        client: APIClient instance
        sprint_id: Sprint ID to get goals for
        team_name: Team name to filter goals
        
    Returns:
        Formatted string with goal progress data, including header.
        Returns "No goals found" if fetch fails or data is empty.
    """
    try:
        sc, response = client.get_goals(
            scope_type="sprint",
            sprint_id=sprint_id,
            team_name=team_name,
        )
        
        if sc != 200 or not isinstance(response, dict):
            return "=== GOAL PROGRESS ===\nNo goals found (HTTP error)\n"
        
        # Extract data from response structure
        data = response.get("data", {})
        if not isinstance(data, dict):
            return "=== GOAL PROGRESS ===\nNo goals found\n"
        
        # Extract team_goals array
        team_goals_list = data.get("team_goals", [])
        if not team_goals_list or not isinstance(team_goals_list, list):
            return "=== GOAL PROGRESS ===\nNo goals found for this sprint\n"
        
        # Get goals from first team (should only be one team when filtered by team_name)
        goals = []
        if len(team_goals_list) > 0 and isinstance(team_goals_list[0], dict):
            goals = team_goals_list[0].get("goals", [])
        
        if not goals or not isinstance(goals, list):
            return "=== GOAL PROGRESS ===\nNo goals found for this sprint\n"
        
        # Format goals with connected issues
        parts = ["=== GOAL PROGRESS ==="]
        parts.append("")
        
        # Sort goals by goal_number if available, otherwise by id
        sorted_goals = sorted(
            goals,
            key=lambda g: g.get("goal_number", g.get("id", 0))
        )
        
        for goal_idx, goal in enumerate(sorted_goals, start=1):
            goal_text = goal.get("goal_text", "")
            status = goal.get("status", "")
            progress = goal.get("goal_progress_by_children", 0)
            issue_keys = goal.get("issue_keys", [])
            
            # Format goal header
            parts.append(f"Goal {goal_idx}: {goal_text}")
            parts.append(f"  Status: {status}")
            parts.append(f"  Progress: {progress}%")
            
            # Format connected issues
            if issue_keys and isinstance(issue_keys, list) and len(issue_keys) > 0:
                parts.append("  Connected Issues:")
                for issue in issue_keys:
                    if isinstance(issue, dict):
                        issue_key = issue.get("issue_key", "")
                        summary = issue.get("summary", "")
                        issue_status = issue.get("status", "")
                        status_category = issue.get("status_category", "")
                        
                        issue_line = f"    - {issue_key}: {summary}"
                        if issue_status:
                            issue_line += f" - {issue_status}"
                        if status_category:
                            issue_line += f" ({status_category})"
                        parts.append(issue_line)
            else:
                parts.append("  Connected Issues: None")
            
            parts.append("")  # Empty line between goals
        
        return "\n".join(parts)
        
    except Exception as e:
        return f"=== GOAL PROGRESS ===\n⚠️ Error fetching goal progress: {str(e)}\n"


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