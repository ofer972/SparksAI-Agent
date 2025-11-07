import json
from typing import Any, Callable, Dict, List, Tuple

from api_client import APIClient


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
            print(f"📋 Saving {len(parsed_recommendations)} recommendations from JSON to database...")
            
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
                        print(f"⚠️ WARNING: source_ai_summary_id is None when creating recommendation")
                    rsc, rresp = client.create_recommendation(rec_payload)
                    if rsc >= 300:
                        print(f"⚠️ Create recommendation failed: {rsc} {rresp}")
                    else:
                        recommendations_saved += 1
                        print(f"🧩 Recommendation: priority='{priority}' status='Proposed' header='{recommendation_obj['header'][:60]}' text='{recommendation_obj['text'][:120]}'")
                    
                    # Limit to max recommendations
                    if recommendations_saved >= max_count:
                        break
                else:
                    print(f"⚠️ Skipping invalid recommendation object: {recommendation_obj}")
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse recommendations JSON: {e}")
    
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


def process_llm_response_and_save_ai_card(
    client: APIClient,
    llm_answer: str,
    team_name: str | None,
    job_id: int | None,
    card_config: Dict[str, Any],
    card_type: str,  # "PI" or "Team"
    extract_content_fn: Callable[[str], str | None] = extract_pi_sync_review,
) -> Tuple[str, str, str, int]:
    """
    Process LLM response, extract structured content, and save AI cards.
    
    Args:
        client: APIClient instance
        llm_answer: Full LLM response text
        team_name: Team name from job
        job_id: Optional job ID
        card_config: Dict with keys: card_name, card_type, priority, source, pi (if PI card)
        card_type: "PI" for pi-ai-cards, "Team" for team-ai-cards
        extract_content_fn: Function to extract description from LLM response (default: extract_pi_sync_review)
    
    Returns:
        Tuple of (description, full_information, raw_json_string, card_id)
    """
    from datetime import datetime, timezone
    
    # Extract and separate text from JSON
    full_information, dashboard_summary_json, recommendations_json, raw_json_string = extract_text_and_json(llm_answer)
    
    # Extract description using provided function
    extracted_content = extract_content_fn(llm_answer)
    
    # Use extracted section if available, otherwise fallback to full response (truncated)
    description = extracted_content if extracted_content else llm_answer[:2000]
    
    # Truncate full_information if needed (for database storage)
    full_info_truncated = full_information[:2000] if len(full_information) > 2000 else full_information

    # Create card payload
    today = datetime.now(timezone.utc).date().isoformat()
    card_payload = {
        "team_name": team_name,
        "card_name": card_config.get("card_name"),
        "card_type": card_config.get("card_type"),
        "description": description[:2000],  # Truncate description if too long
        "date": today,
        "priority": card_config.get("priority", "Critical"),
        "source": card_config.get("source", "PI"),
        "source_job_id": job_id,
        "full_information": full_info_truncated,
    }
    
    # Add PI if present in config (for PI cards)
    if "pi" in card_config:
        card_payload["pi"] = card_config["pi"]
    
    # Add information_json with raw JSON string from BEGIN_JSON/END_JSON
    if raw_json_string:
        card_payload["information_json"] = raw_json_string
    
    # Upsert card based on type and extract card_id
    upsert_done = False
    card_id = None
    if card_type == "PI":
        sc, cards = client.list_pi_ai_cards()
        if sc == 200 and isinstance(cards, dict):
            items = cards.get("data") or cards
            if isinstance(items, list):
                for c in items:
                    try:
                        same_date = str(c.get("date", ""))[:10] == today
                        if same_date and c.get("team_name") == card_payload["team_name"] and c.get("pi") == card_payload.get("pi") and c.get("card_name") == card_payload["card_name"]:
                            # Patch existing
                            card_id = int(c.get("id"))
                            psc, presp = client.patch_pi_ai_card(card_id, card_payload)
                            if psc >= 300:
                                print(f"⚠️ Patch pi-ai-card failed: {psc} {presp}")
                            upsert_done = psc < 300
                            break
                    except Exception:
                        continue
        if not upsert_done:
            csc, cresp = client.create_pi_ai_card(card_payload)
            if csc < 300 and isinstance(cresp, dict):
                # Extract from response.data.card.id structure
                card_id = cresp.get("data", {}).get("card", {}).get("id")
            elif csc >= 300:
                print(f"⚠️ Create pi-ai-card failed: {csc} {cresp}")
    elif card_type == "Team":
        sc, cards = client.list_team_ai_cards()
        if sc == 200 and isinstance(cards, dict):
            items = cards.get("data") or cards
            if isinstance(items, list):
                for c in items:
                    try:
                        same_date = str(c.get("date", ""))[:10] == today
                        if same_date and c.get("team_name") == card_payload["team_name"] and c.get("card_name") == card_payload["card_name"]:
                            # Patch existing
                            card_id = int(c.get("id"))
                            psc, presp = client.patch_team_ai_card(card_id, card_payload)
                            if psc >= 300:
                                print(f"⚠️ Patch team-ai-card failed: {psc} {presp}")
                            upsert_done = psc < 300
                            break
                    except Exception:
                        continue
        if not upsert_done:
            csc, cresp = client.create_team_ai_card(card_payload)
            if csc < 300 and isinstance(cresp, dict):
                # Extract from response.data.card.id structure
                card_id = cresp.get("data", {}).get("card", {}).get("id")
            elif csc >= 300:
                print(f"⚠️ Create team-ai-card failed: {csc} {cresp}")
    
    # Short log of the created card insight
    desc_preview = (card_payload["description"] or "")[:120]
    print(
        f"🗂️ Card insight: name='{card_payload['card_name']}' type='{card_payload['card_type']}' priority='{card_payload['priority']}' preview='{desc_preview}'"
    )
    
    # Log card_id for debugging
    if card_id is not None:
        print(f"✅ Card ID extracted: {card_id}")
    else:
        print(f"⚠️ WARNING: Card ID is None - source_ai_summary_id will be None in recommendations")
    
    return description, full_info_truncated, raw_json_string, card_id

