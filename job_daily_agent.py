import json
from typing import Any, Dict, Tuple
from datetime import datetime, timezone

import config
from api_client import APIClient
from llm_client import call_agent_llm_process
from utils_processing import (
    format_burndown_markdown,
    format_transcript,
    extract_recommendations,
    extract_text_and_json,
    extract_daily_progress_review,
)


def _format_daily_input(transcript: Dict[str, Any] | None, burndown_records: Any, prompt: str | None, team_name: str) -> str:
    parts: list[str] = []
    parts.append("=== DAILY CONTEXT ===")
    parts.append(f"Team: {team_name}")
    parts.append("")

    # Transcript
    parts.append("=== TRANSCRIPT DATA ===")
    parts.append(format_transcript(transcript, include_label="Raw Transcript:"))
    parts.append("")

    # Burndown
    parts.append("=== BURN DOWN DATA FOR THE ACTIVE SPRINT ===")
    try:
        burndown_formatted = format_burndown_markdown(burndown_records)
        parts.append(burndown_formatted)
    except Exception:
        parts.append("No burndown data available")
    parts.append("")

    # Prompt
    if prompt:
        parts.append("=== PROMPT ===")
        parts.append(prompt)

    return "\n".join(parts)


def process(job: Dict[str, Any]) -> Tuple[bool, str]:
    client = APIClient()
    job_id = job.get("job_id") or job.get("id")
    team_name = job.get("team_name")
    if not team_name:
        return False, "Missing team_name in job payload"

    # Latest Daily transcript via dedicated endpoint
    transcript_obj = None
    sc, data = client.get_latest_daily_transcript(team_name)
    if sc == 200 and isinstance(data, dict):
        transcript_obj = (data.get("data") or {}).get("transcript") or data.get("data") or data

    # Burndown for active sprint (auto-select) via team endpoint
    burndown_obj = None
    try:
        sc, bd = client.get_team_sprint_burndown(team_name)
        if sc == 200 and isinstance(bd, dict):
            burndown_obj = bd.get("data") or bd
    except Exception:
        burndown_obj = None

    # Prompt Daily Insights
    prompt_text = None
    sc, pdata = client.get_prompt("DailyAgent", "Daily%20Insights")
    if sc == 404:
        sc, pdata = client.get_prompt("DailyAgent", "Daily Insights")
    if sc == 200 and isinstance(pdata, dict):
        prompt_text = (pdata.get("data") or {}).get("prompt_description") or pdata.get("prompt_description")

    # Build formatted input and update input_sent
    formatted = _format_daily_input(transcript_obj, burndown_obj, prompt_text, team_name)
    if job_id is not None:
        client.patch_agent_job(int(job_id), {"input_sent": formatted})

    # Call dedicated agent LLM processing endpoint
    ok, llm_answer, _raw = call_agent_llm_process(
        client=client,
        prompt=formatted,
        job_type="Daily Agent",
        job_id=int(job_id) if job_id is not None else None,
        metadata={"team_name": team_name},
    )
    if not ok:
        return False, "AI chat failed or returned empty response"

    # Print first 400 characters of LLM response
    preview = llm_answer[:400] if llm_answer else ""
    print(f"\n📥 LLM Response Preview (first 400 chars):\n{preview}{'...' if len(llm_answer) > 400 else ''}\n")

    # Extract structured content from LLM response
    print("\n" + "="*80)
    print("📋 EXTRACTING STRUCTURED CONTENT FROM LLM RESPONSE")
    print("="*80)
    
    # Extract and separate text from JSON
    full_information, dashboard_summary_json, recommendations_json = extract_text_and_json(llm_answer)
    
    # Extract Daily Progress Review section
    daily_progress_content = extract_daily_progress_review(llm_answer)
    
    # Use extracted section if available, otherwise fallback to full response (truncated)
    description = daily_progress_content if daily_progress_content else llm_answer[:2000]
    
    # Truncate full_information if needed (for database storage)
    full_info_truncated = full_information[:2000] if len(full_information) > 2000 else full_information

    # Create/Upsert Team AI Card
    today = datetime.now(timezone.utc).date().isoformat()
    card_payload = {
        "team_name": team_name,
        "card_name": "Daily Progress Review",
        "card_type": "Daily Progress",
        "description": description[:2000],  # Truncate description if too long
        "date": today,
        "priority": "Critical",
        "source": "Daily Agent",
        "source_job_id": job_id,
        "full_information": full_info_truncated,  # Text before JSON
    }
    
    # Add information_json if we have dashboard summary JSON
    if dashboard_summary_json:
        card_payload["information_json"] = dashboard_summary_json

    # Ensure api_client has list/patch team-ai-cards
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

    # Log insight
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

    # Create detailed result text with full LLM response (like old system)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    result_text = f"""Daily Agent Analysis Completed

Team: {team_name}
Job ID: {job_id}
Timestamp: {timestamp}

Data Collected:
- Transcript: {'Found' if transcript_obj else 'Not found'}
- Burndown: {'Found' if burndown_obj else 'Not found'}
- Prompt: {'Found' if prompt_text else 'Not found'}

Data Sent to LLM: {len(formatted)} characters
LLM Response Length: {len(llm_answer)} characters

=== AI ANALYSIS ===
{llm_answer}
"""
    return True, result_text


