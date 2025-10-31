import json
from typing import Any, Dict, Tuple
from datetime import datetime, timezone

import config
from api_client import APIClient
from llm_client import call_llm_generic
from utils_processing import format_burndown_markdown, extract_recommendations


def _format_daily_input(transcript: Dict[str, Any] | None, burndown_records: Any, prompt: str | None, team_name: str) -> str:
    parts: list[str] = []
    parts.append("=== DAILY CONTEXT ===")
    parts.append(f"Team: {team_name}")
    parts.append("")

    # Transcript
    parts.append("=== TRANSCRIPT DATA ===")
    if transcript:
        parts.append(f"Date: {transcript.get('transcript_date')}")
        parts.append(f"Type: {transcript.get('type')}")
        parts.append(f"File: {transcript.get('file_name')}")
        raw = transcript.get("raw_text")
        if raw:
            parts.append("Raw Transcript Preview:")
            parts.append(str(raw)[:800])
    else:
        parts.append("No transcript found")
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

    # Strict LLM call
    ok, llm_answer, _raw = call_llm_generic(client, formatted_text=formatted, selected_pi=None)
    if not ok:
        return False, "AI chat failed or returned empty response"

    # Create/Upsert Team AI Card
    today = datetime.now(timezone.utc).date().isoformat()
    card_payload = {
        "team_name": team_name,
        "card_name": "Daily Progress Review",
        "card_type": "Daily Progress",
        "description": llm_answer[:2000],
        "date": today,
        "priority": "Critical",
        "source": "Daily Agent",
        "source_job_id": job_id,
        "full_information": formatted,
    }

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

    # Extract and create up to 2 recommendations from LLM text
    recs = extract_recommendations(llm_answer, max_count=2)
    for rec_text in recs:
        rec_payload = {
            "team_name": team_name,
            "action_text": rec_text,
            "date": today,
            "priority": "High",
            "status": "Proposed",
            "full_information": llm_answer[:2000],
        }
        rsc, rresp = client.create_recommendation(rec_payload)
        if rsc >= 300:
            print(f"⚠️ Create recommendation failed: {rsc} {rresp}")
        else:
            print(f"🧩 Recommendation: priority='High' status='Proposed' text='{rec_text[:120]}'")

    result = (
        f"Daily processed for {team_name}. Transcript={'yes' if transcript_obj else 'no'}, "
        f"Burndown={'yes' if burndown_obj else 'no'}. Card upserted."
    )
    return True, result


