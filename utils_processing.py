from typing import Any, Dict, List, Tuple


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


def clean_recommendation_text(text: str) -> str:
    import re
    s = re.sub(r'^\d+\.?\s*', '', text.strip())
    s = s.lstrip('*-•◦').strip()
    return ' '.join(s.split())


def extract_recommendations(llm_text: str, max_count: int = 2) -> List[str]:
    if not llm_text:
        return []
    lines = [ln.strip() for ln in llm_text.split('\n') if ln.strip()]
    items: List[str] = []
    current = ""
    for ln in lines:
        starts = ln.startswith(tuple([f"{i}." for i in range(1, 10)])) or ln.startswith(('*', '-', '•', '◦'))
        if starts:
            if current.strip():
                items.append(current.strip())
            current = ln
        else:
            if current:
                current += " " + ln
            else:
                current = ln
    if current.strip():
        items.append(current.strip())

    cleaned = []
    seen = set()
    for it in items:
        c = clean_recommendation_text(it)
        if c and c not in seen:
            cleaned.append(c)
            seen.add(c)
        if len(cleaned) >= max_count:
            break
    return cleaned


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
    if transcript.get("transcript_date"):
        parts.append(f"Date: {transcript.get('transcript_date')}")
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


