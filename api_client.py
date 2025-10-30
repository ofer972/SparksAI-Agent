import time
from typing import Any, Dict, List, Optional, Tuple

import requests

import config


class APIClient:
    def __init__(self, base_url: Optional[str] = None, timeout_seconds: int = 30):
        self.base_url: str = (base_url or config.BASE_URL).rstrip("/")
        self.timeout_seconds: int = timeout_seconds

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def get_agent_jobs(self) -> Tuple[int, Any]:
        resp = requests.get(
            self._url("/api/v1/agent-jobs"),
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def get_agent_job(self, job_id: int) -> Tuple[int, Any]:
        resp = requests.get(
            self._url(f"/api/v1/agent-jobs/{job_id}"),
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def get_next_pending_job(self) -> Tuple[int, Any]:
        resp = requests.get(
            self._url("/api/v1/agent-jobs/next-pending"),
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def patch_agent_job(self, job_id: int, body: Dict[str, Any]) -> Tuple[int, Any]:
        resp = requests.patch(
            self._url(f"/api/v1/agent-jobs/{job_id}"),
            headers=self._headers(),
            json=body,
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    # ---- PI Sync related endpoints ----
    def get_latest_pi_sync_transcript(self, pi_name: str) -> Tuple[int, Any]:
        resp = requests.get(
            self._url("/api/v1/transcripts/getLatestPISync"),
            params={"pi_name": pi_name},
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def get_latest_daily_transcript(self, team_name: str) -> Tuple[int, Any]:
        resp = requests.get(
            self._url("/api/v1/transcripts/getLatestDaily"),
            params={"team_name": team_name},
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def get_pi_burndown(self, pi: str) -> Tuple[int, Any]:
        resp = requests.get(
            self._url("/api/v1/pis/burndown"),
            params={"pi": pi},
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def get_team_sprint_burndown(self, team_name: str, issue_type: str = "all", sprint_name: str | None = None) -> Tuple[int, Any]:
        params: Dict[str, Any] = {"team_name": team_name, "issue_type": issue_type}
        if sprint_name:
            params["sprint_name"] = sprint_name
        resp = requests.get(
            self._url("/api/v1/team-metrics/sprint-burndown"),
            params=params,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def get_sprints(self, team_name: str, sprint_status: str | None = None) -> Tuple[int, Any]:
        params: Dict[str, Any] = {"team_name": team_name}
        if sprint_status:
            params["sprint_status"] = sprint_status
        resp = requests.get(
            self._url("/api/v1/team-metrics/get-sprints"),
            params=params,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def get_prompt(self, email_address: str, prompt_name: str) -> Tuple[int, Any]:
        resp = requests.get(
            self._url(f"/api/v1/prompts/{email_address}/{prompt_name}"),
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def post_ai_chat(self, body: Dict[str, Any]) -> Tuple[int, Any]:
        resp = requests.post(
            self._url("/api/v1/ai-chat"),
            headers=self._headers(),
            json=body,
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def create_pi_ai_card(self, body: Dict[str, Any]) -> Tuple[int, Any]:
        resp = requests.post(
            self._url("/api/v1/pi-ai-cards"),
            headers=self._headers(),
            json=body,
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def list_pi_ai_cards(self) -> Tuple[int, Any]:
        resp = requests.get(
            self._url("/api/v1/pi-ai-cards"),
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def patch_pi_ai_card(self, card_id: int, body: Dict[str, Any]) -> Tuple[int, Any]:
        resp = requests.patch(
            self._url(f"/api/v1/pi-ai-cards/{card_id}"),
            headers=self._headers(),
            json=body,
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def create_recommendation(self, body: Dict[str, Any]) -> Tuple[int, Any]:
        resp = requests.post(
            self._url("/api/v1/recommendations"),
            headers=self._headers(),
            json=body,
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    # Team AI cards (for Sprint Goal upsert when implemented)
    def create_team_ai_card(self, body: Dict[str, Any]) -> Tuple[int, Any]:
        resp = requests.post(
            self._url("/api/v1/team-ai-cards"),
            headers=self._headers(),
            json=body,
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def list_team_ai_cards(self) -> Tuple[int, Any]:
        resp = requests.get(
            self._url("/api/v1/team-ai-cards"),
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def patch_team_ai_card(self, card_id: int, body: Dict[str, Any]) -> Tuple[int, Any]:
        resp = requests.patch(
            self._url(f"/api/v1/team-ai-cards/{card_id}"),
            headers=self._headers(),
            json=body,
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    @staticmethod
    def _safe_json(resp: requests.Response) -> Any:
        try:
            return resp.json()
        except Exception:
            return resp.text


def retry_call(fn, max_retries: int = 3, base_delay: float = 1.0):
    def wrapper(*args, **kwargs):
        for attempt in range(max_retries + 1):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                if attempt >= max_retries:
                    raise
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
        return None
    return wrapper


