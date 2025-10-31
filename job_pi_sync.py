import json
from typing import Any, Dict, Tuple
from datetime import datetime, timezone

import config
from api_client import APIClient
from llm_client import call_llm_generic
from utils_processing import format_burndown_markdown, extract_recommendations


def _extract_pi(job: Dict[str, Any]) -> str | None:
    if isinstance(job.get("pi"), str):
        return job["pi"]
    jd = job.get("job_data")
    try:
        if isinstance(jd, str):
            jd = json.loads(jd)
        if isinstance(jd, dict) and isinstance(jd.get("pi"), str):
            return jd["pi"]
    except Exception:
        pass
    return None


def _format_input(transcript: Dict[str, Any] | None, burndown: Dict[str, Any] | None, prompt: str | None) -> str:
    parts: list[str] = []
    parts.append("=== PI SYNC DATA ===")
    if transcript:
        parts.append("-- Latest Transcript --")
        parts.append(f"Date: {transcript.get('transcript_date')}")
        parts.append(f"PI: {transcript.get('team_name')}")
        raw = transcript.get("raw_text")
        if raw:
            parts.append("Transcript Preview:")
            parts.append(str(raw)[:800])
    else:
        parts.append("No transcript found")
    parts.append("")

    parts.append("-- PI Burndown Snapshot --")
    parts.append(format_burndown_markdown(burndown))
    parts.append("")

    if prompt:
        parts.append("-- Prompt --")
        parts.append(prompt)

    return "\n".join(parts)


def process(job: Dict[str, Any]) -> Tuple[bool, str]:
    client = APIClient()

    job_id = job.get("job_id") or job.get("id")
    pi = _extract_pi(job)
    if not pi:
        return False, "Missing PI in job payload"

    # Collect REST data
    transcript_obj = None
    sc, data = client.get_latest_pi_sync_transcript(pi)
    if sc == 200 and isinstance(data, dict):
        transcript_obj = (data.get("data") or {}).get("transcript") or data.get("data") or data

    burndown_obj = None
    sc, data = client.get_pi_burndown(pi)
    if sc == 200 and isinstance(data, dict):
        burndown_obj = data.get("data") or data

    prompt_text = None
    sc, data = client.get_prompt("PIAgent", "PISync")
    if sc == 200 and isinstance(data, dict):
        prompt_text = (data.get("data") or {}).get("prompt_description") or data.get("prompt_description")

    # Build formatted input and update input_sent
    formatted = _format_input(transcript_obj, burndown_obj, prompt_text)
    if job_id is not None:
        client.patch_agent_job(int(job_id), {"input_sent": formatted})

    # Strict LLM call (no fallback)
    ok, llm_answer, _raw = call_llm_generic(client, formatted_text=formatted, selected_pi=pi)
    if not ok:
        return False, "AI chat failed or returned empty response"

    # Create/Upsert PI AI Card (client-side)
    today = datetime.now(timezone.utc).date().isoformat()
    card_payload = {
        "pi": pi,
        "team_name": job.get("team_name"),
        "card_name": "PI Sync Review",
        "card_type": "PI Sync",
        "description": llm_answer[:2000],
        "date": today,
        "priority": "Critical",
        "source": "PI",
        "source_job_id": job_id,
        "full_information": formatted,
    }
    # Try find existing card for (date=today, team_name, pi, card_name)
    sc, cards = client.list_pi_ai_cards()
    upsert_done = False
    if sc == 200 and isinstance(cards, dict):
        items = cards.get("data") or cards
        if isinstance(items, list):
            for c in items:
                try:
                    same_date = str(c.get("date", ""))[:10] == today
                    if same_date and c.get("team_name") == card_payload["team_name"] and c.get("pi") == card_payload["pi"] and c.get("card_name") == card_payload["card_name"]:
                        # Patch existing
                        psc, presp = client.patch_pi_ai_card(int(c.get("id")), card_payload)
                        if psc >= 300:
                            print(f"⚠️ Patch pi-ai-card failed: {psc} {presp}")
                        upsert_done = psc < 300
                        break
                except Exception:
                    continue
    if not upsert_done:
        csc, cresp = client.create_pi_ai_card(card_payload)
        if csc >= 300:
            print(f"⚠️ Create pi-ai-card failed: {csc} {cresp}")
    # Short log of the created card insight
    desc_preview = (card_payload["description"] or "")[:120]
    print(
        f"🗂️ Card insight: name='{card_payload['card_name']}' type='{card_payload['card_type']}' priority='{card_payload['priority']}' preview='{desc_preview}'"
    )

    # Extract and create up to 2 recommendations from LLM text
    recs = extract_recommendations(llm_answer, max_count=2)
    for rec_text in recs:
        # For recommendations, team_name should actually be the quarter (PI)
        rec_payload = {
            "team_name": pi,
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
        f"PI Sync processed for {pi}. Transcript={'yes' if transcript_obj else 'no'}, "
        f"Burndown={'yes' if burndown_obj else 'no'}. Card and recommendation created."
    )
    return True, result


