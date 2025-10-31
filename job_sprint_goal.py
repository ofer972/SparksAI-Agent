import json
from typing import Any, Dict, Tuple
from datetime import datetime, timezone

import config
from api_client import APIClient
from llm_client import call_llm_generic
from utils_processing import (
    format_burndown_markdown,
    extract_recommendations,
    extract_text_and_json,
    extract_content_between_markers,
    LLM_EXTRACTION_CONSTANTS,
)


def process(job: Dict[str, Any]) -> Tuple[bool, str]:
    client = APIClient()
    job_id = job.get("job_id") or job.get("id")
    team_name = job.get("team_name")
    if not team_name:
        return False, "Missing team_name in job payload"

    # Fetch active sprints and validate sprint_goal
    sc, sprints = client.get_sprints(team_name, sprint_status="active")
    active = None
    if sc == 200 and isinstance(sprints, dict):
        items = sprints.get("data") or sprints
        if isinstance(items, list) and items:
            active = items[0]

    sprint_goal = (active or {}).get("sprint_goal") if isinstance(active, dict) else None
    if not sprint_goal or len(str(sprint_goal).strip()) < 10:
        return True, "No sprint Goal found"

    # Burndown for the (auto-selected) active sprint
    burndown_records = None
    sc, bd = client.get_team_sprint_burndown(team_name)
    if sc == 200 and isinstance(bd, dict):
        burndown_records = bd.get("data") or bd
        if isinstance(burndown_records, dict):
            burndown_records = [burndown_records]

    # Prompt
    prompt_text = None
    sc, pdata = client.get_prompt("DailyAgent", "Sprint%20Goal")
    if sc == 404:
        sc, pdata = client.get_prompt("DailyAgent", "Sprint Goal")
    if sc == 200 and isinstance(pdata, dict):
        prompt_text = (pdata.get("data") or {}).get("prompt_description") or pdata.get("prompt_description")

    # Build formatted text
    parts = ["SPRINT GOAL ANALYSIS DATA", "=" * 50, ""]
    if isinstance(active, dict):
        parts.append("ACTIVE SPRINT STATUS:")
        parts.append("-" * 30)
        for k, v in active.items():
            parts.append(f"{k}: {v}")
        parts.append("")
    parts.append(f"Current Date: {datetime.now(timezone.utc).isoformat()}")
    parts.append("")
    parts.append("SPRINT BURNDOWN:")
    parts.append("-" * 20)
    try:
        burndown_formatted = format_burndown_markdown(burndown_records)
        parts.append(burndown_formatted)
    except Exception:
        parts.append("No burndown data")
    parts.append("")
    if prompt_text:
        parts.append("ANALYSIS PROMPT:")
        parts.append("-" * 20)
        parts.append(prompt_text)
        parts.append("")
    formatted = "\n".join(parts)

    if job_id is not None:
        client.patch_agent_job(int(job_id), {"input_sent": formatted})

    # LLM
    ok, llm_answer, _raw = call_llm_generic(client, formatted_text=formatted)
    if not ok or not llm_answer:
        return False, "AI chat failed or returned empty response"

    # Extract structured content from LLM response
    print("\n" + "="*80)
    print("📋 EXTRACTING STRUCTURED CONTENT FROM LLM RESPONSE")
    print("="*80)
    
    # Extract and separate text from JSON
    full_information, dashboard_summary_json, recommendations_json = extract_text_and_json(llm_answer)
    
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
    
    # Add information_json if we have dashboard summary JSON
    if dashboard_summary_json:
        card_payload["information_json"] = dashboard_summary_json
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
    print("\n" + "="*80)
    print("📋 EXTRACTING AND SAVING RECOMMENDATIONS")
    print("="*80)
    
    # First try to extract recommendations from JSON if available
    recommendations_saved = 0
    if recommendations_json:
        try:
            parsed_recommendations = json.loads(recommendations_json)
            if isinstance(parsed_recommendations, list) and parsed_recommendations:
                print(f"📋 Saving {len(parsed_recommendations)} recommendations from JSON to database...")
                
                # Save each recommendation using the JSON structure
                for recommendation_obj in parsed_recommendations:
                    if isinstance(recommendation_obj, dict) and 'header' in recommendation_obj and 'text' in recommendation_obj:
                        rec_payload = {
                            "team_name": team_name,
                            "action_text": recommendation_obj['text'],
                            "rational": recommendation_obj['header'],  # Use header as rational
                            "date": today,
                            "priority": "High",
                            "status": "Proposed",
                            "full_information": full_info_truncated,
                            "information_json": json.dumps(recommendation_obj),  # Store individual recommendation JSON
                        }
                        rsc, rresp = client.create_recommendation(rec_payload)
                        if rsc >= 300:
                            print(f"⚠️ Create recommendation failed: {rsc} {rresp}")
                        else:
                            recommendations_saved += 1
                            print(f"🧩 Recommendation: priority='High' status='Proposed' header='{recommendation_obj['header'][:60]}' text='{recommendation_obj['text'][:120]}'")
                        
                        # Limit to max recommendations
                        if recommendations_saved >= 2:
                            break
                    else:
                        print(f"⚠️ Skipping invalid recommendation object: {recommendation_obj}")
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse recommendations JSON: {e}")
    
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
            }
            rsc, rresp = client.create_recommendation(rec_payload)
            if rsc >= 300:
                print(f"⚠️ Create recommendation failed: {rsc} {rresp}")
            else:
                recommendations_saved += 1
                print(f"🧩 Recommendation: priority='High' status='Proposed' text='{rec_text[:120]}'")
            
            if recommendations_saved >= 2:
                break

    return True, "Sprint Goal processed"


