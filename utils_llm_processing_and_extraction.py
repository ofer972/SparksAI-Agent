import json
import time
from typing import Any, Callable, Dict, List, Tuple
from datetime import datetime, timezone
from pydantic import BaseModel

from api_client import APIClient
from llm_client import call_agent_llm_process
from utils_audit import call_audit_service, extract_tokens_from_llm_response
from utils_data_fetching import get_prompt_with_active_check, get_prompt_with_error_check
from utils_logging import log


class JSONExtractionError(Exception):
    """Exception raised when JSON extraction fails (BEGIN_JSON/END_JSON missing or invalid JSON)."""
    pass


class LLMResponseExtraction(BaseModel):
    """Extracted components from LLM response."""
    text_part: str
    dashboard_summary_json: str
    recommendations_json: str
    raw_json_string: str
    criticality_determination: str | None = None
    primary_focus: str | None = None


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
    job_id: int | None = None,
    source_ai_summary_id: int | None = None,
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
        source_ai_summary_id: ID of the AI summary card that generated these recommendations
    
    Returns:
        Number of recommendations successfully saved (0 if none)
    """
    if not recommendations_json:
        return 0
    
    recommendations_saved = 0
    try:
        parsed_recommendations = json.loads(recommendations_json)
        if isinstance(parsed_recommendations, list) and parsed_recommendations:
            log(job_id, f"📋 Saving {len(parsed_recommendations)} recommendations from JSON to database...")
            
            # Save each recommendation using the JSON structure
            for recommendation_obj in parsed_recommendations:
                if isinstance(recommendation_obj, dict) and 'header' in recommendation_obj and 'text' in recommendation_obj:
                    # Get priority from JSON if available, otherwise default to "Important"
                    priority = recommendation_obj.get('priority', 'Important')
                    
                    rec_payload = {
                        "team_name": team_name_or_pi,
                        "action_text": recommendation_obj['text'],
                        "rational": recommendation_obj['header'],  # Use header as rational
                        "date": today,
                        "priority": priority,
                        "status": "Proposed",
                        "full_information": full_info_truncated,
                        "information_json": json.dumps(recommendation_obj),  # Store individual recommendation JSON
                        "source_job_id": job_id,
                        "source_ai_summary_id": source_ai_summary_id,
                    }
                    # Debug: Log the payload being sent
                    if source_ai_summary_id is None:
                        log(job_id, f"⚠️ WARNING: source_ai_summary_id is None when creating recommendation")
                    rsc, rresp = client.create_recommendation(rec_payload)
                    if rsc >= 300:
                        log(job_id, f"⚠️ Create recommendation failed: {rsc} {rresp}")
                    else:
                        recommendations_saved += 1
                        log(job_id, f"🧩 Recommendation: priority='{priority}' status='Proposed' header='{recommendation_obj['header'][:60]}' text='{recommendation_obj['text'][:120]}'")
                    
                    # Limit to max recommendations
                    if recommendations_saved >= max_count:
                        break
                else:
                    log(job_id, f"⚠️ Skipping invalid recommendation object: {recommendation_obj}")
    except json.JSONDecodeError as e:
        log(job_id, f"❌ Failed to parse recommendations JSON: {e}")
    
    return recommendations_saved


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

        return content_text
        
    except Exception as e:
        print(f"❌ Error extracting content between '{start_marker}' and '{end_marker}': {e}")
        return ""


def extract_json_sections(parsed_json: Dict[str, Any] | List[Any]) -> Tuple[str, str, str | None, str | None]:
    """
    Extract DashboardSummary, Recommendations, CriticalityDetermination, and PrimaryFocus from parsed JSON
    
    Args:
        parsed_json: Parsed JSON object
    
    Returns:
        tuple: (dashboard_summary_json, recommendations_json, criticality_determination, primary_focus) where:
            dashboard_summary_json: JSON string of DashboardSummary
            recommendations_json: JSON string of Recommendations
            criticality_determination: CriticalityDetermination value or None
            primary_focus: PrimaryFocus value or None (fallback to first 100 chars of first DashboardSummary item)
    """
    try:
        # Handle both dict and list inputs
        if isinstance(parsed_json, list):
            # If it's a list, check if it contains objects with the keys we want
            dashboard_summary = []
            recommendations = []
            criticality_determination = None
            primary_focus = None
            for item in parsed_json:
                if isinstance(item, dict):
                    if 'Dashboard_Summary' in item or 'Dashboard Summary' in item or 'DashboardSummary' in item:
                        dashboard_summary.append(item)
                    if 'Recommendations' in item:
                        recommendations.append(item.get('Recommendations', []))
                    if 'CriticalityDetermination' in item and criticality_determination is None:
                        criticality_determination = item.get('CriticalityDetermination')
                    # Extract PrimaryFocus (case-insensitive search only)
                    if primary_focus is None:
                        for key in item.keys():
                            if key.lower() == 'primaryfocus':
                                primary_focus = item[key]
                                break
            dashboard_summary_json = json.dumps(dashboard_summary) if dashboard_summary else ""
            recommendations_json = json.dumps(recommendations[0] if recommendations else []) if recommendations else ""
            
            # Fallback: Use first 100 chars of first DashboardSummary item if PrimaryFocus not found
            if primary_focus is None and dashboard_summary and len(dashboard_summary) > 0:
                first_item = dashboard_summary[0]
                if isinstance(first_item, dict):
                    fallback_text = first_item.get('text') or first_item.get('description') or str(first_item)
                else:
                    fallback_text = str(first_item)
                primary_focus = fallback_text[:100] if fallback_text else None
            
            return dashboard_summary_json, recommendations_json, criticality_determination, primary_focus
        
        # Handle dict input
        if not isinstance(parsed_json, dict):
            print(f"⚠️ Unexpected JSON type: {type(parsed_json)}")
            return "", "", None, None

        # Extract DashboardSummary (try multiple variations in order of likelihood)
        dashboard_summary = []
        available_keys = list(parsed_json.keys())

        # Try Dashboard_Summary first (most common in your output)
        if 'Dashboard_Summary' in parsed_json:
            dashboard_summary = parsed_json['Dashboard_Summary']
        elif 'Dashboard Summary' in parsed_json:
            dashboard_summary = parsed_json['Dashboard Summary']
        elif 'DashboardSummary' in parsed_json:
            dashboard_summary = parsed_json['DashboardSummary']
        else:
            print(f"⚠️ No Dashboard Summary key found. Available keys: {available_keys}")
        
        dashboard_summary_json = json.dumps(dashboard_summary) if dashboard_summary else ""
        
        # Extract Recommendations
        recommendations = parsed_json.get('Recommendations', [])
        recommendations_json = json.dumps(recommendations) if recommendations else ""
        
        # Extract CriticalityDetermination
        criticality_determination = parsed_json.get('CriticalityDetermination')

        # Extract PrimaryFocus (case-insensitive search only - no permutations)
        primary_focus = None
        for key in parsed_json.keys():
            if key.lower() == 'primaryfocus':
                primary_focus = parsed_json[key]
                break

        # Fallback: Use first 100 chars of first DashboardSummary item if PrimaryFocus not found
        if primary_focus is None:
            if dashboard_summary and isinstance(dashboard_summary, list) and len(dashboard_summary) > 0:
                first_item = dashboard_summary[0]
                if isinstance(first_item, dict):
                    # Try to get text from common fields
                    fallback_text = first_item.get('text') or first_item.get('description') or str(first_item)
                else:
                    fallback_text = str(first_item)
                primary_focus = fallback_text[:100] if fallback_text else None

        return dashboard_summary_json, recommendations_json, criticality_determination, primary_focus
        
    except Exception as e:
        print(f"❌ Error extracting JSON sections: {e}")
        return "", "", None, None


def extract_text_and_json(llm_response: str) -> LLMResponseExtraction:
    """
    Extract and separate text from JSON in the LLM response.
    Requires BEGIN_JSON/END_JSON markers. Uses relaxed extraction that finds actual JSON boundaries,
    allowing spaces/newlines around markers. Raises JSONExtractionError if markers missing or JSON invalid.
    
    Returns:
        LLMResponseExtraction: Model containing:
            text_part: Text content BEFORE JSON starts (for full_information)
            dashboard_summary_json: JSON array of DashboardSummary (for summary cards)
            recommendations_json: JSON array of Recommendations (for recommendations table)
            raw_json_string: Raw JSON string as extracted (for information_json storage)
            criticality_determination: CriticalityDetermination value or None
            primary_focus: PrimaryFocus value or None (fallback to first 100 chars of first DashboardSummary item)
    
    Raises:
        JSONExtractionError: If BEGIN_JSON marker not found, END_JSON marker not found, or JSON is invalid
    """
    trimmed = llm_response.strip()
    
    # Find BEGIN_JSON marker (allows text before it)
    begin_marker_pos = trimmed.find('BEGIN_JSON')
    if begin_marker_pos == -1:
        raise JSONExtractionError("BEGIN_JSON marker not found in LLM response")
    
    # Find END_JSON marker
    end_marker_pos = trimmed.find('END_JSON')
    if end_marker_pos == -1:
        raise JSONExtractionError("END_JSON marker not found in LLM response")
    
    # Validate marker order
    if end_marker_pos <= begin_marker_pos:
        raise JSONExtractionError("END_JSON must appear after BEGIN_JSON")
    
    # Extract text before BEGIN_JSON (allows spaces/newlines)
    text_before = trimmed[:begin_marker_pos].strip()
    
    # Find the actual start of JSON (first { or [ after BEGIN_JSON)
    # Search in the section between BEGIN_JSON and END_JSON
    search_start = begin_marker_pos + len('BEGIN_JSON')
    search_end = end_marker_pos
    
    # Find first JSON character ({ or [)
    json_start_pos = -1
    for i in range(search_start, search_end):
        char = trimmed[i]
        if char == '{' or char == '[':
            json_start_pos = i
            break
    
    if json_start_pos == -1:
        raise JSONExtractionError("No JSON object or array found after BEGIN_JSON marker")
    
    # Find the actual end of JSON (matching } or ] before END_JSON)
    # Need to find matching closing brace/bracket by counting depth
    start_char = trimmed[json_start_pos]
    end_char = '}' if start_char == '{' else ']'
    
    # Count braces/brackets to find the matching closing one
    depth = 0
    json_end_pos = -1
    for i in range(json_start_pos, search_end):
        char = trimmed[i]
        if char == start_char:
            depth += 1
        elif char == end_char:
            depth -= 1
            if depth == 0:
                json_end_pos = i
                break
    
    if json_end_pos == -1:
        raise JSONExtractionError("JSON structure is incomplete or malformed (unmatched braces/brackets)")
    
    # Extract only the actual JSON content (ignoring whitespace around markers)
    json_content = trimmed[json_start_pos:json_end_pos + 1]
    
    # Validate JSON
    try:
        parsed_json = json.loads(json_content)
    except json.JSONDecodeError as e:
        raise JSONExtractionError(f"Invalid JSON format: {str(e)}")
    
    # Extract sections from parsed JSON
    dashboard_summary, recommendations, criticality_determination, primary_focus = extract_json_sections(parsed_json)
    
    return LLMResponseExtraction(
        text_part=text_before,
        dashboard_summary_json=dashboard_summary,
        recommendations_json=recommendations,
        raw_json_string=json_content,
        criticality_determination=criticality_determination,
        primary_focus=primary_focus
    )
    
    # DISABLED: Method 2 (Markdown code fences) - not used to prevent wrong information in AI cards
    # for marker in ['```json', '```']:
    #     start_pos = trimmed.find(marker)
    #     if start_pos != -1:
    #         end_pos = trimmed.find('```', start_pos + len(marker))
    #         if end_pos != -1:
    #             json_content = trimmed[start_pos + len(marker):end_pos].strip()
    #             text_before = trimmed[:start_pos].strip()
    #             try:
    #                 parsed_json = json.loads(json_content)
    #                 dashboard_summary, recommendations, criticality_determination, primary_focus = extract_json_sections(parsed_json)
    #                 print(f"✅ JSON found in markdown, split at {start_pos}: text={len(text_before)} chars")
    #                 return LLMResponseExtraction(...)
    #             except:
    #                 pass
    
    # DISABLED: Method 3 (Raw JSON detection) - not used to prevent wrong information in AI cards
    # for i, char in enumerate(trimmed):
    #     if char in '{[':
    #         depth = 1
    #         for j in range(i + 1, len(trimmed)):
    #             if trimmed[j] in '{[':
    #                 depth += 1
    #             elif trimmed[j] in '}]':
    #                 depth -= 1
    #                 if depth == 0:
    #                     json_content = trimmed[i:j+1]
    #                     text_before = trimmed[:i].strip()
    #                     try:
    #                         parsed_json = json.loads(json_content)
    #                         dashboard_summary, recommendations, criticality_determination, primary_focus = extract_json_sections(parsed_json)
    #                         return LLMResponseExtraction(...)
    #                     except:
    #                         break
    #         break


def extract_review_section(llm_response: str) -> str | None:
    """
    Extract the review section from LLM response using shared markers.
    This is a shared function used by all job types (Daily Agent, Sprint Goal, PI Sync, etc.)
    
    Args:
        llm_response: The full LLM response text
    
    Returns:
        str: The extracted review section between START_MARKER and END_MARKER,
             or None if start marker not found, empty string if end marker not found
    """
    return extract_content_between_markers(
        llm_response,
        LLM_EXTRACTION_CONSTANTS.START_MARKER,
        LLM_EXTRACTION_CONSTANTS.END_MARKER
    )


# Backward compatibility aliases (deprecated - use extract_review_section instead)
def extract_daily_progress_review(llm_response: str) -> str | None:
    """Deprecated: Use extract_review_section instead"""
    return extract_review_section(llm_response)


def extract_pi_sync_review(llm_response: str) -> str | None:
    """Deprecated: Use extract_review_section instead"""
    return extract_review_section(llm_response)


def process_llm_with_two_step_fallback(
    client: APIClient,
    data_string: str,
    prompt_base_name: str,
    prompt_email: str,
    job_type: str,
    job_id: int | None,
    job_params: Dict[str, Any],
    metadata: Dict[str, Any] | None = None,
    context_separator: str = "LOCKED DECISION CONTEXT:",
    start_time: float | None = None,
) -> Tuple[bool, str, int, Dict[str, Any]]:
    """
    Process LLM with optional two-step mode.
    
    Checks for "{prompt_base_name}-1" prompt with active status. If found and active,
    uses two-step mode (first call with "-1" prompt, second call with "-2" prompt).
    Otherwise, falls back to single-step mode with "{prompt_base_name}" prompt.
    
    Args:
        client: APIClient instance
        data_string: Data string (without prompt) that will be reused for both calls in two-step mode
        prompt_base_name: Base prompt name (e.g., "PI Dependencies")
        prompt_email: Email address for prompt (e.g., "PIAgent")
        job_type: Job type string (e.g., "PI Dependencies")
        job_id: Optional job ID for logging
        job_params: Dict with job parameters for audit service (team_name, group_name, pi, etc.)
        metadata: Optional metadata dict for LLM calls (pi_name, team_name, etc.)
        context_separator: String to separate first response from second prompt (default: "LOCKED DECISION CONTEXT:")
        start_time: Optional start time for duration calculation (if None, uses current time)
    
    Returns:
        Tuple of (success, final_llm_answer, total_tokens, metadata_dict) where:
        - success: True if LLM processing succeeded, False otherwise
        - final_llm_answer: The final LLM response (from second call if two-step, single call if single-step)
        - total_tokens: Total tokens used across all LLM calls
        - metadata_dict: Dict with keys:
            - use_two_step_mode: bool indicating if two-step mode was used
            - input_sent: Complete input_sent string to save to job
            - formatted_first: First call input (if two-step)
            - formatted_second: Second call input (if two-step)
            - formatted: Single call input (if single-step)
    """
    if start_time is None:
        start_time = time.time()
    
    # Try to fetch "{prompt_base_name}-1" with active status check
    prompt_text_first, prompt_error, prompt_active, _ = get_prompt_with_active_check(
        client=client,
        email_address=prompt_email,
        prompt_name=f"{prompt_base_name}-1",
        job_type=job_type,
        job_id=job_id,
    )
    
    use_two_step_mode = False
    prompt_text = None
    
    # Determine if we should use two-step mode or fallback to single-step
    if not prompt_error and prompt_text_first and prompt_active:
        use_two_step_mode = True
        log(job_id, f"✅ Using two-step mode: {prompt_base_name}-1 found and active")
    else:
        # Fallback: fetch "{prompt_base_name}" (original prompt)
        fallback_reason = "not found" if prompt_error else "inactive"
        log(job_id, f"⚠️ FALLBACK MODE: {prompt_base_name}-1 {fallback_reason}, using '{prompt_base_name}'")
        prompt_text, prompt_error_fallback = get_prompt_with_error_check(
            client=client,
            email_address=prompt_email,
            prompt_name=prompt_base_name,
            job_type=job_type,
            job_id=job_id,
        )
        if prompt_error_fallback:
            # Extract tokens (none used yet)
            duration_seconds = time.time() - start_time
            call_audit_service(
                action=job_type,
                duration_seconds=duration_seconds,
                status_code=500,
                action_date=datetime.now(timezone.utc),
                tokens_used=0,
                query_params=job_params,
                body=job_params,
                job_id=job_id,
            )
            return False, "", 0, {"use_two_step_mode": False, "input_sent": "", "formatted": ""}
        use_two_step_mode = False
    
    # Initialize input_sent_parts to build incrementally
    input_sent_parts = []
    
    if use_two_step_mode:
        # ===== TWO-STEP MODE =====
        # Build first input (data + first prompt)
        formatted_first = data_string + "\n" + prompt_text_first if prompt_text_first else data_string
        
        # Add to input_sent (what was sent to first LLM)
        input_sent_parts.append("=== FIRST CALL ===")
        input_sent_parts.append(formatted_first)
        
        # Call first LLM
        log(job_id, f"📤 Calling LLM (First Call) for {job_type} (input: {len(formatted_first)} chars)")
        ok_first, llm_answer_first, _raw_first = call_agent_llm_process(
            client=client,
            prompt=formatted_first,
            job_type=job_type,
            job_id=job_id,
            metadata={**(metadata or {}), "call_number": 1},
        )
        
        if not ok_first:
            # Extract tokens from first call for audit
            tokens_first = extract_tokens_from_llm_response(_raw_first) or 0
            duration_seconds = time.time() - start_time
            call_audit_service(
                action=job_type,
                duration_seconds=duration_seconds,
                status_code=500,
                action_date=datetime.now(timezone.utc),
                tokens_used=tokens_first,
                query_params=job_params,
                body=job_params,
                job_id=job_id,
            )
            return False, "", tokens_first, {
                "use_two_step_mode": True,
                "input_sent": "\n".join(input_sent_parts),
                "formatted_first": formatted_first,
                "formatted_second": "",
            }
        
        # Log first response preview
        preview_first = llm_answer_first[:500] if llm_answer_first else ""
        log(job_id, f"\n📥 First LLM Response Preview (first 500 chars):\n{preview_first}{'...' if len(llm_answer_first) > 500 else ''}\n")
        
        # Add first response to input_sent
        input_sent_parts.append("")
        input_sent_parts.append("=== FIRST CALL RESPONSE ===")
        input_sent_parts.append(llm_answer_first)
        
        # ===== SECOND LLM CALL =====
        # Fetch second prompt with error checking
        prompt_text_second, prompt_error = get_prompt_with_error_check(
            client=client,
            email_address=prompt_email,
            prompt_name=f"{prompt_base_name}-2",
            job_type=job_type,
            job_id=job_id,
        )
        
        if prompt_error:
            # Extract tokens from first call for audit even if second prompt fails
            tokens_first = extract_tokens_from_llm_response(_raw_first) or 0
            duration_seconds = time.time() - start_time
            call_audit_service(
                action=job_type,
                duration_seconds=duration_seconds,
                status_code=500,
                action_date=datetime.now(timezone.utc),
                tokens_used=tokens_first,
                query_params=job_params,
                body=job_params,
                job_id=job_id,
            )
            return False, "", tokens_first, {
                "use_two_step_mode": True,
                "input_sent": "\n".join(input_sent_parts),
                "formatted_first": formatted_first,
                "formatted_second": "",
            }
        
        # Build second input (data + response1 with separator + second prompt)
        formatted_second = data_string + "\n\n" + context_separator + "\n" + llm_answer_first + "\n"
        if prompt_text_second:
            formatted_second += prompt_text_second
        
        # Add to input_sent (what was sent to second LLM)
        input_sent_parts.append("")
        input_sent_parts.append("=== SECOND CALL ===")
        input_sent_parts.append(formatted_second)
        
        # Call second LLM
        log(job_id, f"📤 Calling LLM (Second Call) for {job_type} (input: {len(formatted_second)} chars)")
        ok_second, llm_answer, _raw_second = call_agent_llm_process(
            client=client,
            prompt=formatted_second,
            job_type=job_type,
            job_id=job_id,
            metadata={**(metadata or {}), "call_number": 2},
        )
        
        # Extract tokens from both calls
        tokens_first = extract_tokens_from_llm_response(_raw_first) or 0
        tokens_second = extract_tokens_from_llm_response(_raw_second) or 0
        total_tokens = tokens_first + tokens_second
        
        # Build final input_sent from parts (uses actual variables sent to LLM)
        input_sent = "\n".join(input_sent_parts)
        
        # Save job info after second call (regardless of success/failure)
        if job_id is not None:
            client.patch_agent_job(job_id, {
                "input_sent": input_sent,
                "result": llm_answer if ok_second else ""
            })
        
        if not ok_second:
            # Audit with combined tokens even on failure
            duration_seconds = time.time() - start_time
            call_audit_service(
                action=job_type,
                duration_seconds=duration_seconds,
                status_code=500,
                action_date=datetime.now(timezone.utc),
                tokens_used=total_tokens,
                query_params=job_params,
                body=job_params,
                job_id=job_id,
            )
            return False, "", total_tokens, {
                "use_two_step_mode": True,
                "input_sent": input_sent,
                "formatted_first": formatted_first,
                "formatted_second": formatted_second,
            }
        
        # Log second response preview
        preview_second = llm_answer[:500] if llm_answer else ""
        log(job_id, f"\n📥 Second LLM Response Preview (first 500 chars):\n{preview_second}{'...' if len(llm_answer) > 500 else ''}\n")
        
        return True, llm_answer, total_tokens, {
            "use_two_step_mode": True,
            "input_sent": input_sent,
            "formatted_first": formatted_first,
            "formatted_second": formatted_second,
        }
    
    else:
        # ===== SINGLE-STEP MODE (FALLBACK) =====
        # Build single input (data + prompt) - original format
        formatted = data_string + "\n" + prompt_text if prompt_text else data_string
        
        # Save job info with original format
        if job_id is not None:
            client.patch_agent_job(job_id, {"input_sent": formatted})
        
        # Call LLM once
        log(job_id, f"📤 Calling LLM for {job_type} (input: {len(formatted)} chars)")
        ok, llm_answer, _raw = call_agent_llm_process(
            client=client,
            prompt=formatted,
            job_type=job_type,
            job_id=job_id,
            metadata=metadata,
        )
        
        if not ok:
            # Extract tokens from single call for audit
            tokens_used = extract_tokens_from_llm_response(_raw) or 0
            duration_seconds = time.time() - start_time
            call_audit_service(
                action=job_type,
                duration_seconds=duration_seconds,
                status_code=500,
                action_date=datetime.now(timezone.utc),
                tokens_used=tokens_used,
                query_params=job_params,
                body=job_params,
                job_id=job_id,
            )
            return False, "", tokens_used, {
                "use_two_step_mode": False,
                "input_sent": formatted,
                "formatted": formatted,
            }
        
        # Extract tokens from single call
        tokens_used = extract_tokens_from_llm_response(_raw) or 0
        
        # Log response preview
        preview = llm_answer[:500] if llm_answer else ""
        log(job_id, f"\n📥 LLM Response Preview (first 500 chars):\n{preview}{'...' if len(llm_answer) > 500 else ''}\n")
        
        # Save result to job
        if job_id is not None:
            client.patch_agent_job(job_id, {"result": llm_answer})
        
        return True, llm_answer, tokens_used, {
            "use_two_step_mode": False,
            "input_sent": formatted,
            "formatted": formatted,
        }


def process_llm_response_and_save_ai_card(
    client: APIClient,
    llm_answer: str,
    team_name: str | None,
    job_id: int | None,
    job_type: str,  # The insight_type from job (e.g., "Daily Progress", "PI Sync")
    card_config: Dict[str, Any],
    card_type: str,  # "PI" or "Team" - for determining endpoint
    extract_content_fn: Callable[[str], str | None] = extract_pi_sync_review,
    group_name: str | None = None,  # Optional group_name for Group cards
) -> Tuple[str, str, str, int]:
    """
    Process LLM response, extract structured content, and save AI cards.
    
    Args:
        client: APIClient instance
        llm_answer: Full LLM response text
        team_name: Team name from job (used for Team cards, ignored if group_name is provided)
        job_id: Optional job ID
        job_type: The insight_type from the job payload (e.g., "Daily Progress", "PI Sync")
        card_config: Dict with keys: card_name, source, pi (if PI card) - priority is determined from CriticalityDetermination
        card_type: "PI" for pi-ai-cards, "Team" for team-ai-cards
        extract_content_fn: Function to extract description from LLM response (default: extract_pi_sync_review)
        group_name: Optional group_name for Group cards (if provided, used instead of team_name)
    
    Returns:
        Tuple of (description, full_information, raw_json_string, card_id)
    """
    from datetime import datetime, timezone
    
    # Extract and separate text from JSON
    extraction = extract_text_and_json(llm_answer)
    full_information = extraction.text_part
    dashboard_summary_json = extraction.dashboard_summary_json
    recommendations_json = extraction.recommendations_json
    raw_json_string = extraction.raw_json_string
    criticality_determination = extraction.criticality_determination
    primary_focus = extraction.primary_focus
    
    # Extract description using provided function
    extracted_content = extract_content_fn(llm_answer)
    
    # Use extracted section if available, otherwise fallback to full response (truncated)
    description = extracted_content if extracted_content else llm_answer[:2000]
    
    # Truncate full_information if needed (for database storage)
    full_info_truncated = full_information[:2000] if len(full_information) > 2000 else full_information

    # Truncate primary_focus if needed (max 2000 chars, similar to description)
    short_summary = primary_focus[:2000] if primary_focus and len(primary_focus) > 2000 else primary_focus

    # Create card payload
    today = datetime.now(timezone.utc).date().isoformat()
    
    # Normalize team_name based on card type
    if card_type == "Team":
        # For Team cards: group cards use None (NULL in DB), team cards use actual team_name
        normalized_team_name = None if group_name is not None else team_name
    elif card_type == "PI":
        # PI cards: use "" instead of None for consistency with UNIQUE constraint
        normalized_team_name = team_name if team_name is not None else ""
    else:
        normalized_team_name = team_name
    
    # Determine priority from CriticalityDetermination or default to "Warning"
    priority = criticality_determination if criticality_determination else "Warning"
    
    card_payload = {
        "team_name": normalized_team_name,
        "card_name": card_config.get("card_name"),
        "insight_type": job_type,  # Use job_type parameter - matches insight_types.insight_type
        "description": description[:2000],  # Truncate description if too long
        "date": today,
        "priority": priority,
        "source": card_config.get("source", "PI"),
        "source_job_id": job_id,
        "full_information": full_info_truncated,
        "short_summary": short_summary,  # NEW FIELD (can be None if PrimaryFocus not found and no DashboardSummary)
    }
    
    # Add group_name if provided (for Group cards - backend accepts group_name in Team AI cards endpoint)
    if group_name:
        card_payload["group_name"] = group_name
    
    # Add PI if present in config (for PI cards)
    if "pi" in card_config:
        card_payload["pi"] = card_config["pi"]
    
    # Add information_json with raw JSON string from BEGIN_JSON/END_JSON
    if raw_json_string:
        card_payload["information_json"] = raw_json_string
    
    # Upsert card using unified endpoint
    upsert_done = False
    card_id = None
    
    # Build filter parameters for list query - filter by date, insight_type, and identifiers
    # Aligns with unique index: (date, insight_type, team_name, pi, group_name)
    list_params = {
        "date": today,
        "insight_type": card_payload.get("insight_type")
    }
    
    # Add identifier filters based on what's in the payload
    if "pi" in card_payload and card_payload["pi"]:
        list_params["pi"] = card_payload["pi"]
    if "group_name" in card_payload and card_payload["group_name"]:
        list_params["group_name"] = card_payload["group_name"]
    if "team_name" in card_payload and card_payload["team_name"]:
        list_params["team_name"] = card_payload["team_name"]
    
    sc, cards = client.list_ai_insights(**list_params)
    if sc == 200 and isinstance(cards, dict):
        # Extract cards list from response structure: {"success": true, "data": {"cards": [...]}}
        data = cards.get("data") or {}
        items = data.get("cards") if isinstance(data, dict) else (cards if isinstance(cards, list) else [])
        if isinstance(items, list):
            for c in items:
                try:
                    # Match based on unique index fields: date, insight_type, and identifiers
                    same_date = str(c.get("date", ""))[:10] == today
                    same_insight_type = c.get("insight_type") == card_payload.get("insight_type")
                    
                    if not same_date or not same_insight_type:
                        continue
                    
                    # Match based on identifiers - all must match
                    if c.get("pi") != card_payload.get("pi"):
                        continue
                    if c.get("group_name") != card_payload.get("group_name"):
                        continue
                    existing_team_name = c.get("team_name") or ""
                    payload_team_name = card_payload.get("team_name") or ""
                    if existing_team_name != payload_team_name:
                        continue
                    
                    # All conditions matched - this is the card to update
                    # Extract card ID with validation
                    card_id_raw = c.get("id")
                    if card_id_raw is None:
                        log(job_id, f"⚠️ WARNING: Existing card found but id is None, skipping")
                        continue
                    try:
                        card_id = int(card_id_raw)
                    except (ValueError, TypeError) as e:
                        log(job_id, f"⚠️ WARNING: Cannot convert card id to int: {card_id_raw}, error: {e}")
                        continue
                    
                    # Patch existing using unified endpoint
                    psc, presp = client.patch_ai_insight(card_id, card_payload)
                    if psc < 300:
                        # Patch succeeded, card_id is already set
                        upsert_done = True
                        break
                    else:
                        log(job_id, f"⚠️ Patch ai-insight failed: {psc} {presp}")
                        # Don't set upsert_done, will try to create new
                except Exception as e:
                    # Log exception instead of silently swallowing
                    log(job_id, f"⚠️ WARNING: Exception in card upsert loop: {e}")
                    continue
    
    if not upsert_done:
        # Create new card using unified endpoint
        csc, cresp = client.create_ai_insight(card_payload)
        if csc < 300 and isinstance(cresp, dict):
            # Extract from response.data.card.id structure
            card_id = cresp.get("data", {}).get("card", {}).get("id")
            if card_id is None:
                # Log the actual response structure for debugging
                log(job_id, f"⚠️ WARNING: Card ID not found in response structure")
                log(job_id, f"   Response keys: {list(cresp.keys()) if isinstance(cresp, dict) else 'not a dict'}")
                if isinstance(cresp, dict) and "data" in cresp:
                    log(job_id, f"   Data keys: {list(cresp['data'].keys()) if isinstance(cresp['data'], dict) else 'not a dict'}")
                    if isinstance(cresp['data'], dict) and "card" in cresp['data']:
                        log(job_id, f"   Card keys: {list(cresp['data']['card'].keys()) if isinstance(cresp['data']['card'], dict) else 'not a dict'}")
        elif csc >= 300:
            log(job_id, f"⚠️ Create ai-insight failed: {csc} {cresp}")
    
    # Short log of the created card insight
    desc_preview = (card_payload["description"] or "")[:120]
    log(job_id, f"🗂️ Card insight: name='{card_payload['card_name']}' type='{card_payload.get('insight_type', 'N/A')}' priority='{card_payload['priority']}' preview='{desc_preview}'")
    
    if card_id is not None:
        log(job_id, f"✅ Card ID extracted: {card_id}")
    else:
        log(job_id, f"⚠️ WARNING: Card ID is None - source_ai_summary_id will be None in recommendations")
    
    return description, full_info_truncated, raw_json_string, card_id

