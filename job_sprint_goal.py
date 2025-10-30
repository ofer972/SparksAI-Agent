import json
from typing import Any, Dict, Tuple
from datetime import datetime, timezone

import config
from api_client import APIClient
from llm_client import call_llm_generic
from utils_processing import format_table, extract_recommendations


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
    table = ""
    try:
        if isinstance(burndown_records, list) and burndown_records:
            table = format_table(burndown_records)
    except Exception:
        table = ""
    parts.append(table or "No burndown data")
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

    # Upsert Team AI Card
    today = datetime.now(timezone.utc).date().isoformat()
    card_payload = {
        "team_name": team_name,
        "card_name": "Sprint Goal Analysis",
        "card_type": "Sprint Goal",
        "description": llm_answer[:2000],
        "date": today,
        "priority": "High",
        "source": "Sprint Goal",
        "source_job_id": job_id,
        "full_information": formatted,
    }
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

    # Recommendations from LLM text (cap 2)
    recs = extract_recommendations(llm_answer, max_count=2)
    # Determine quarter/PI for recommendations
    quarter = None
    if isinstance(active, dict):
        quarter = active.get("pi") or active.get("quarter")
    if not quarter:
        quarter = job.get("pi")
    for rec_text in recs:
        rec_payload = {
            "team_name": quarter or "Unknown",
            "action_text": rec_text,
            "priority": "High",
            "status": "Proposed",
            "full_information": llm_answer[:2000],
        }
        rsc, rresp = client.create_recommendation(rec_payload)
        if rsc >= 300:
            print(f"⚠️ Create recommendation failed: {rsc} {rresp}")
        else:
            print(f"🧩 Recommendation: priority='High' status='Proposed' text='{rec_text[:120]}'")

    return True, "Sprint Goal processed"


