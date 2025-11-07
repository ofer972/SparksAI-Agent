from typing import Any, Dict, List

from api_client import APIClient


def filter_columns_excluding_points(columns: List[str]) -> List[str]:
    return [c for c in columns if 'point' not in c.lower()]


def format_table(records: List[Dict[str, Any]], max_width: int = 20) -> str:
    if not records:
        return ""
    # Build column set from first record
    columns = list(records[0].keys())
    columns = filter_columns_excluding_points(columns)
    if not columns:
        return ""

    # Header
    header = " | ".join([f"{col[:max_width]:<{max_width}}" for col in columns])
    sep = "-" * len(header)
    lines = [header, sep]

    # Rows (skip rows where remaining_issues is null/empty if present)
    remaining_key = None
    for c in columns:
        if 'remaining_issues' in c.lower():
            remaining_key = c
            break

    for rec in records:
        if remaining_key is not None:
            val = rec.get(remaining_key)
            if val is None or str(val).strip().lower() in ('', 'null'):
                continue
        row_values = []
        for col in columns:
            v = rec.get(col)
            row_values.append(f"{str(v)[:max_width] if v is not None else 'NULL':<{max_width}}")
        lines.append(" | ".join(row_values))

    return "\n".join(lines)


def format_transcript(transcript: Dict[str, Any] | None, include_label: str = "Transcript:") -> str:
    """Format transcript data as markdown for LLM and UI display.
    
    Args:
        transcript: Dict containing transcript data (or None)
        include_label: Label to use for the transcript section
        
    Returns:
        Formatted markdown string with transcript information
    """
    if not transcript or not isinstance(transcript, dict):
        return "No transcript found"
    
    parts = []
    # Add metadata fields if available
    if transcript.get("type"):
        parts.append(f"Type: {transcript.get('type')}")
    if transcript.get("team_name"):
        parts.append(f"Team/PI: {transcript.get('team_name')}")
    if transcript.get("file_name"):
        parts.append(f"File: {transcript.get('file_name')}")
    
    # Add the full raw text
    raw = transcript.get("raw_text")
    if raw:
        parts.append(include_label)
        parts.append(str(raw))
    else:
        parts.append("No transcript text found")
    
    return "\n".join(parts)


def format_burndown_markdown(burndown: Dict[str, Any] | List[Dict[str, Any]] | None) -> str:
    """Format burndown data as structured markdown for LLM and UI display.
    
    Handles both:
    - Dict format (e.g., PI burndown with nested burndown_data list)
    - List format (e.g., sprint burndown records)
    """
    # Handle direct list input (sprint burndown)
    if isinstance(burndown, list):
        if not burndown:
            return "No burndown data found"
        table = format_table(burndown)
        return table if table else "No burndown data found"
    
    # Handle dict input (PI burndown)
    if not burndown or not isinstance(burndown, dict):
        return "No burndown data found"
    
    lines = []
    # Group related fields for better readability
    numeric_fields = []
    date_fields = []
    list_fields = []
    other_fields = []
    
    for k, v in burndown.items():
        k_lower = str(k).lower()
        
        # Check if it's a list (especially burndown_data)
        if isinstance(v, list):
            list_fields.append((k, v))
        elif any(x in k_lower for x in ['date', 'time', 'day']):
            date_fields.append((k, v))
        elif isinstance(v, (int, float)) or (isinstance(v, str) and v.replace('.', '').replace('-', '').isdigit()):
            numeric_fields.append((k, v))
        else:
            other_fields.append((k, v))
    
    # Handle lists - especially burndown_data or any list of dicts
    if list_fields:
        for k, v_list in list_fields:
            if isinstance(v_list, list) and len(v_list) > 0 and isinstance(v_list[0], dict):
                # Format as table using existing utility
                lines.append(f"**{k}:**")
                table = format_table(v_list)
                if table:
                    lines.append(table)
                else:
                    # Fallback: show count and sample
                    lines.append(f"- Total records: {len(v_list)}")
                    if len(v_list) > 0:
                        lines.append(f"- Sample record fields: {', '.join(list(v_list[0].keys())[:5])}...")
                lines.append("")
            else:
                # Other lists - show count and truncated preview
                lines.append(f"**{k}:**")
                lines.append(f"- Count: {len(v_list)}")
                preview = str(v_list)[:200]
                if len(str(v_list)) > 200:
                    preview += "..."
                lines.append(f"- Preview: `{preview}`")
                lines.append("")
    
    if date_fields:
        lines.append("**Dates & Timeline:**")
        for k, v in date_fields:
            lines.append(f"- {k}: `{v}`")
        lines.append("")
    
    if numeric_fields:
        lines.append("**Metrics & Numbers:**")
        for k, v in numeric_fields:
            lines.append(f"- {k}: `{v}`")
        lines.append("")
    
    if other_fields:
        lines.append("**Other Information:**")
        for k, v in other_fields:
            # Truncate very long values
            v_str = str(v)
            if len(v_str) > 200:
                v_str = v_str[:200] + "..."
            lines.append(f"- {k}: {v_str}")
    
    return "\n".join(lines) if lines else "No burndown data found"


def format_pi_status(pi_status: Dict[str, Any] | List[Dict[str, Any]] | None) -> str:
    """Format PI status data for LLM input.
    
    Args:
        pi_status: PI status data dict from API (can contain 'data' list or be the list directly)
        
    Returns:
        Formatted string with "column_name = value" for each field
    """
    if not pi_status:
        return "No PI status data available for current date."

    # Extract the actual data list from response structure
    status_list = None
    if isinstance(pi_status, dict):
        # Handle API response format: {"success": true, "data": [...], ...}
        if "data" in pi_status and isinstance(pi_status["data"], list):
            status_list = pi_status["data"]
        else:
            # If it's a dict but no 'data' key, treat it as a single status object
            status_list = [pi_status]
    elif isinstance(pi_status, list):
        status_list = pi_status
    
    if not status_list or len(status_list) == 0:
        return "No PI status data available for current date."
    
    # Format: "This is the status of the PI as of TODAY" followed by column = value
    lines = ["This is the status of the PI as of TODAY"]
    
    # Get the first item (should only be one for a specific PI)
    status_obj = status_list[0]
    if isinstance(status_obj, dict):
        # Format each column as "column_name = value"
        for key, value in sorted(status_obj.items()):
            lines.append(f"{key} = {value}")
    
    return "\n".join(lines)


class PROMPT_FORMAT_CONSTANTS:
    """Constants for prompt formatting in input_sent - shared across all job types"""
    PROMPT_BEGIN = "===> Prompt:"
    PROMPT_END = "===> End Prompt."


def format_pi_analysis_input(
    transcript: str | Dict[str, Any] | None,
    pi_status: Dict[str, Any] | None,
    burndown: Dict[str, Any] | None,
    prompt: str | None,
    header_title: str = "PI SYNC DATA",
    include_transcript_section: bool = True,
) -> str:
    """
    Format PI analysis input for LLM.
    
    Args:
        transcript: Formatted transcript string (from get_transcripts_for_analysis) or raw transcript dict (or None)
        pi_status: PI status data (or None)
        burndown: Burndown data (or None)
        prompt: Prompt text (or None)
        header_title: Custom header title (default: "PI SYNC DATA")
        include_transcript_section: Whether to include transcript section (default: True)
    
    Returns:
        Formatted string for LLM input
    """
    parts: list[str] = []
    parts.append(f"==={header_title}===")
    
    if include_transcript_section:
        parts.append("-- Latest Transcript --")
        # If transcript is already a formatted string, use it directly
        # Otherwise, format it using the old format_transcript function (backward compatibility)
        if isinstance(transcript, str):
            parts.append(transcript)
        else:
            parts.append(format_transcript(transcript, include_label="Transcript:"))
        parts.append("")

    parts.append("-- PI status for current date --")
    parts.append(format_pi_status(pi_status))
    parts.append("")

    parts.append("-- PI Burndown Snapshot --")
    parts.append(format_burndown_markdown(burndown))
    parts.append("")

    # Add prompt (already includes markers from get_prompt_with_error_check)
    if prompt:
        parts.append(prompt)

    return "\n".join(parts)

