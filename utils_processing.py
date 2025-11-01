import json
from typing import Any, Dict, List, Tuple, Optional

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


def save_recommendations_from_json(
    client: APIClient,
    recommendations_json: str,
    team_name_or_pi: str,
    today: str,
    full_info_truncated: str,
    max_count: int = 2,
    job_id: int | None = None
) -> int:
    """
    Parse and save recommendations from JSON string to database.
    
    Args:
        client: APIClient instance for API calls
        recommendations_json: JSON string containing recommendations array
        team_name_or_pi: Team name (for Daily/Sprint) or PI name (for PI Sync)
        today: Date string in ISO format
        full_info_truncated: Truncated full information text
        max_count: Maximum number of recommendations to save (default: 2)
        job_id: Optional job ID that triggered this recommendation
    
    Returns:
        Number of recommendations successfully saved (0 if none)
    """
    if not recommendations_json:
        return 0
    
    recommendations_saved = 0
    try:
        parsed_recommendations = json.loads(recommendations_json)
        if isinstance(parsed_recommendations, list) and parsed_recommendations:
            print(f"📋 Saving {len(parsed_recommendations)} recommendations from JSON to database...")
            
            # Save each recommendation using the JSON structure
            for recommendation_obj in parsed_recommendations:
                if isinstance(recommendation_obj, dict) and 'header' in recommendation_obj and 'text' in recommendation_obj:
                    rec_payload = {
                        "team_name": team_name_or_pi,
                        "action_text": recommendation_obj['text'],
                        "rational": recommendation_obj['header'],  # Use header as rational
                        "date": today,
                        "priority": "High",
                        "status": "Proposed",
                        "full_information": full_info_truncated,
                        "information_json": json.dumps(recommendation_obj),  # Store individual recommendation JSON
                        "source_job_id": job_id,
                    }
                    rsc, rresp = client.create_recommendation(rec_payload)
                    if rsc >= 300:
                        print(f"⚠️ Create recommendation failed: {rsc} {rresp}")
                    else:
                        recommendations_saved += 1
                        print(f"🧩 Recommendation: priority='High' status='Proposed' header='{recommendation_obj['header'][:60]}' text='{recommendation_obj['text'][:120]}'")
                    
                    # Limit to max recommendations
                    if recommendations_saved >= max_count:
                        break
                else:
                    print(f"⚠️ Skipping invalid recommendation object: {recommendation_obj}")
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse recommendations JSON: {e}")
    
    return recommendations_saved


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


# LLM Response Extraction Constants
class LLM_EXTRACTION_CONSTANTS:
    """Constants for LLM response extraction - shared across all extraction functions"""
    START_MARKER = "dashboard summary"
    END_MARKER = "detailed analysis"
    RECOMMENDATION_MARKER = "recommendation"
    MAX_RECOMMENDATIONS = 2  # Maximum number of recommendations to extract


def extract_content_between_markers(
    llm_response: str, 
    start_marker: str, 
    end_marker: str
) -> str | None:
    """
    Generic function to extract content between two markers (case-insensitive).
    
    Args:
        llm_response: The full LLM response text
        start_marker: Start marker text (case-insensitive)
        end_marker: End marker text (case-insensitive)
    
    Returns:
        str: Extracted content between markers, or None if start marker not found,
             empty string if end marker not found
    """
    try:
        # Split response into lines for better processing
        lines = llm_response.split('\n')
        
        # Look for start marker line (case-insensitive)
        start_line = -1
        for i, line in enumerate(lines):
            if start_marker.lower() in line.lower():
                start_line = i
                break
        
        if start_line == -1:
            print(f"⚠️ '{start_marker}' section not found in LLM response")
            return None
        
        # Look for end marker line (case-insensitive)
        end_line = -1
        for i, line in enumerate(lines):
            if end_marker.lower() in line.lower():
                end_line = i
                break
        
        if end_line == -1:
            print(f"⚠️ '{end_marker}' section not found in LLM response")
            return ""
        
        # Start extracting AFTER start marker
        content_start_line = start_line + 1
        
        # Skip empty lines after start marker until content starts
        while content_start_line < len(lines) and lines[content_start_line].strip() == "":
            content_start_line += 1
        
        if content_start_line >= len(lines):
            print(f"⚠️ No content found after '{start_marker}'")
            return ""
        
        # Extract content between start and end markers
        content_lines = lines[content_start_line:end_line]
        content_text = '\n'.join(content_lines).strip()
        
        if not content_text:
            print(f"⚠️ No content found between '{start_marker}' and '{end_marker}'")
            return ""
        
        print(f"✅ Extracted content between '{start_marker}' and '{end_marker}' ({len(content_text)} characters)")
        return content_text
        
    except Exception as e:
        print(f"❌ Error extracting content between '{start_marker}' and '{end_marker}': {e}")
        return ""


def extract_json_sections(parsed_json: Dict[str, Any] | List[Any]) -> Tuple[str, str]:
    """
    Extract DashboardSummary and Recommendations from parsed JSON
    
    Args:
        parsed_json: Parsed JSON object
    
    Returns:
        tuple: (dashboard_summary_json, recommendations_json) as JSON strings
    """
    try:
        # Handle both dict and list inputs
        if isinstance(parsed_json, list):
            # If it's a list, check if it contains objects with the keys we want
            dashboard_summary = []
            recommendations = []
            for item in parsed_json:
                if isinstance(item, dict):
                    if 'Dashboard_Summary' in item or 'Dashboard Summary' in item or 'DashboardSummary' in item:
                        dashboard_summary.append(item)
                    if 'Recommendations' in item:
                        recommendations.append(item.get('Recommendations', []))
            dashboard_summary_json = json.dumps(dashboard_summary) if dashboard_summary else ""
            recommendations_json = json.dumps(recommendations[0] if recommendations else []) if recommendations else ""
            return dashboard_summary_json, recommendations_json
        
        # Handle dict input
        if not isinstance(parsed_json, dict):
            print(f"⚠️ Unexpected JSON type: {type(parsed_json)}")
            return "", ""
        
        # Debug: Print all available keys
        available_keys = list(parsed_json.keys())
        print(f"🔍 DEBUG: Available JSON keys: {available_keys}")
        
        # Extract DashboardSummary (try multiple variations in order of likelihood)
        dashboard_summary = []
        
        # Try Dashboard_Summary first (most common in your output)
        if 'Dashboard_Summary' in parsed_json:
            dashboard_summary = parsed_json['Dashboard_Summary']
            print(f"✅ Found Dashboard_Summary with {len(dashboard_summary) if isinstance(dashboard_summary, list) else 'unknown'} items")
        elif 'Dashboard Summary' in parsed_json:
            dashboard_summary = parsed_json['Dashboard Summary']
            print(f"✅ Found 'Dashboard Summary' with {len(dashboard_summary) if isinstance(dashboard_summary, list) else 'unknown'} items")
        elif 'DashboardSummary' in parsed_json:
            dashboard_summary = parsed_json['DashboardSummary']
            print(f"✅ Found DashboardSummary with {len(dashboard_summary) if isinstance(dashboard_summary, list) else 'unknown'} items")
        else:
            print(f"⚠️ No Dashboard Summary key found. Available keys: {available_keys}")
        
        dashboard_summary_json = json.dumps(dashboard_summary) if dashboard_summary else ""
        
        # Extract Recommendations
        recommendations = parsed_json.get('Recommendations', [])
        recommendations_json = json.dumps(recommendations) if recommendations else ""
        
        print(f"✅ Extracted sections: DashboardSummary={len(dashboard_summary) if isinstance(dashboard_summary, list) else 0} items, Recommendations={len(recommendations) if isinstance(recommendations, list) else 0} items")
        return dashboard_summary_json, recommendations_json
        
    except Exception as e:
        print(f"❌ Error extracting JSON sections: {e}")
        return "", ""


def extract_text_and_json(llm_response: str) -> Tuple[str, str, str, str]:
    """
    Extract and separate text from JSON in the LLM response.
    Parses JSON to extract DashboardSummary and Recommendations separately.
    
    Returns:
        tuple: (text_part, dashboard_summary_json, recommendations_json, raw_json_string) where:
            text_part: Text content BEFORE JSON starts (for full_information)
            dashboard_summary_json: JSON array of DashboardSummary (for summary cards)
            recommendations_json: JSON array of Recommendations (for recommendations table)
            raw_json_string: Raw JSON string as extracted (for information_json storage)
    """
    try:
        trimmed = llm_response.strip()
        
        # First try to find BEGIN_JSON/END_JSON markers
        begin_pos = trimmed.find('BEGIN_JSON')
        if begin_pos != -1:
            end_pos = trimmed.find('END_JSON')
            if end_pos != -1:
                json_content = trimmed[begin_pos + len('BEGIN_JSON'):end_pos].strip()
                text_before = trimmed[:begin_pos].strip()
                try:
                    parsed_json = json.loads(json_content)  # Validate JSON
                    dashboard_summary, recommendations = extract_json_sections(parsed_json)
                    print(f"✅ JSON found with BEGIN_JSON/END_JSON markers, split at {begin_pos}: text={len(text_before)} chars")
                    return text_before, dashboard_summary, recommendations, json_content
                except Exception as e:
                    print(f"⚠️ Failed to parse JSON between BEGIN_JSON/END_JSON: {e}")
        
        # Look for JSON markers: ```json or ``` or just start of JSON { or [
        # First try to find markdown code fences
        for marker in ['```json', '```']:
            start_pos = trimmed.find(marker)
            if start_pos != -1:
                # Find closing ```
                end_pos = trimmed.find('```', start_pos + len(marker))
                if end_pos != -1:
                    json_content = trimmed[start_pos + len(marker):end_pos].strip()
                    text_before = trimmed[:start_pos].strip()
                    try:
                        parsed_json = json.loads(json_content)  # Validate JSON
                        dashboard_summary, recommendations = extract_json_sections(parsed_json)
                        print(f"✅ JSON found in markdown, split at {start_pos}: text={len(text_before)} chars")
                        return text_before, dashboard_summary, recommendations, json_content
                    except:
                        pass
        
        # If no markdown, find JSON starting with { or [
        for i, char in enumerate(trimmed):
            if char in '{[':  # JSON starts here
                depth = 1
                for j in range(i + 1, len(trimmed)):
                    if trimmed[j] in '{[':
                        depth += 1
                    elif trimmed[j] in '}]':
                        depth -= 1
                        if depth == 0:  # Found complete JSON
                            json_content = trimmed[i:j+1]
                            text_before = trimmed[:i].strip()  # TEXT STOPS HERE - before JSON starts
                            try:
                                parsed_json = json.loads(json_content)  # Validate JSON
                                dashboard_summary, recommendations = extract_json_sections(parsed_json)
                                print(f"✅ JSON found, split at {i}: text={len(text_before)} chars")
                                return text_before, dashboard_summary, recommendations, json_content
                            except:
                                break
                break
        
        # No JSON found
        print(f"ℹ️ No JSON found in LLM response")
        return trimmed, "", "", ""  # Return everything as text, no JSON
        
    except Exception as e:
        print(f"❌ Error extracting text and JSON: {e}")
        return llm_response, "", "", ""


def extract_daily_progress_review(llm_response: str) -> str | None:
    """
    Extract the "Daily Progress Review" section from LLM response using markers
    
    Args:
        llm_response: The full LLM response text
    
    Returns:
        str: The extracted "Daily Progress Review" section, or None if start marker not found,
             empty string if end marker not found
    """
    return extract_content_between_markers(
        llm_response, 
        LLM_EXTRACTION_CONSTANTS.START_MARKER, 
        LLM_EXTRACTION_CONSTANTS.END_MARKER
    )


def extract_pi_sync_review(llm_response: str) -> str | None:
    """
    Extract the "PI Sync Review" section from LLM response using markers
    
    Args:
        llm_response: The full LLM response text
    
    Returns:
        str: The extracted "PI Sync Review" section, or None if start marker not found,
             empty string if end marker not found
    """
    return extract_content_between_markers(
        llm_response, 
        LLM_EXTRACTION_CONSTANTS.START_MARKER, 
        LLM_EXTRACTION_CONSTANTS.END_MARKER
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
    
    # Success - log and return prompt
    char_count = len(prompt_text)
    job_context = f" (Job ID: {job_id})" if job_id is not None else ""
    print(f"✅ Prompt fetched: {prompt_name} for {email_address} ({char_count} chars){job_context}")
    return prompt_text, None

