import time
from typing import Any, Dict, List, Optional, Tuple

import requests

import config


class APIClient:
    def __init__(self, base_url: Optional[str] = None, timeout_seconds: int = 60):
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
    def get_transcripts(
        self,
        transcript_type: str | None = None,
        team_name: str | None = None,
        pi_name: str | None = None,
        limit: int = 1,
    ) -> Tuple[int, Any]:
        """Get transcripts using unified endpoint.
        
        Args:
            transcript_type: 'Daily' | 'PI Sync' | None (optional)
            team_name: Team name (required if type='Daily')
            pi_name: PI name (required if type='PI Sync')
            limit: Number of transcripts to retrieve (default: 1, min: 1, max: 100)
            
        Returns:
            Tuple of (status_code, response_data)
        """
        params: Dict[str, Any] = {}
        if transcript_type:
            params["type"] = transcript_type
        if team_name:
            params["team_name"] = team_name
        if pi_name:
            params["pi_name"] = pi_name
        if limit:
            params["limit"] = limit
        
        resp = requests.get(
            self._url("/api/v1/transcripts/getLatest"),
            params=params,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

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

    def get_pi_burndown(self, pi: str, team_name: str | None = None) -> Tuple[int, Any]:
        params: Dict[str, Any] = {"pi": pi}
        if team_name:
            params["team_name"] = team_name
        resp = requests.get(
            self._url("/api/v1/pis/burndown"),
            params=params,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def get_pi_summary_today(self, pi: str, team_name: str | None = None) -> Tuple[int, Any]:
        """Get PI status summary for current date.
        
        Args:
            pi: PI name/identifier
            team_name: Optional team name to filter by
            
        Returns:
            Tuple of (status_code, response_data)
        """
        params: Dict[str, Any] = {"pi": pi}
        if team_name:
            params["team_name"] = team_name
        resp = requests.get(
            self._url("/api/v1/pis/get-pi-status-for-today"),
            params=params,
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

    def get_sprint_predictability(
        self,
        team_name: str | None = None,
        months: int = 3,
    ) -> Tuple[int, Any]:
        """Get sprint predictability data.
        
        Args:
            team_name: Optional team name to filter by
            months: Number of months to look back (default: 3, valid: 1, 2, 3, 4, 6, 9)
            
        Returns:
            Tuple of (status_code, response_data)
        """
        params: Dict[str, Any] = {"months": months}
        if team_name:
            params["team_name"] = team_name
        
        resp = requests.get(
            self._url("/api/v1/sprints/sprint-predictability"),
            params=params,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def get_active_sprint_summary_by_team(self, team_name: str) -> Tuple[int, Any]:
        """Get active sprint summary by team from active_sprint_summary_by_team view.
        
        Args:
            team_name: Team name to get active sprint summary for
            
        Returns:
            Tuple of (status_code, response_data)
        """
        resp = requests.get(
            self._url("/api/v1/sprints/active-sprint-summary-by-team"),
            params={"team_name": team_name},
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def get_active_sprint_summary(self, sprint_id: int) -> Tuple[int, Any]:
        """Get active sprint summary by sprint ID from active_sprint_summary view.
        
        Args:
            sprint_id: Sprint ID to get summary for
            
        Returns:
            Tuple of (status_code, response_data)
        """
        resp = requests.get(
            self._url(f"/api/v1/sprints/active-sprint-summary/{sprint_id}"),
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def get_sprint_issues(self, sprint_id: int, team_name: str, limit: int = 1000) -> Tuple[int, Any]:
        """Get JIRA issues for a sprint.
        
        Args:
            sprint_id: Sprint ID to get issues for
            team_name: Team name to filter issues
            limit: Maximum number of issues to return (default: 1000)
            
        Returns:
            Tuple of (status_code, response_data)
        """
        params = {
            "sprint_id": sprint_id,
            "team_name": team_name,
            "limit": limit
        }
        resp = requests.get(
            self._url("/api/v1/issues"),
            params=params,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def get_sprint_issues_with_epic_for_llm(self, sprint_id: int, team_name: str) -> Tuple[int, Any]:
        """Get sprint issues with epic data formatted for LLM.
        
        Args:
            sprint_id: Sprint ID to get issues for
            team_name: Team name to filter issues
            
        Returns:
            Tuple of (status_code, response_data)
            Response structure: {
                "success": true,
                "data": {
                    "sprint_issues": [...],
                    "count": int,
                    "sprint_id": int
                }
            }
        """
        resp = requests.get(
            self._url("/api/v1/sprints/sprint-issues-with-epic-for-llm"),
            params={"sprint_id": sprint_id, "team_name": team_name},
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

    def post_agent_llm_process(self, body: Dict[str, Any]) -> Tuple[int, Any]:
        resp = requests.post(
            self._url("/api/v1/agent-llm-process"),
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

    def check_health(self) -> Tuple[int, Any]:
        """Check backend health by calling /health endpoint."""
        resp = requests.get(
            self._url("/health"),
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    @staticmethod
    def _safe_json(resp: requests.Response) -> Any:
        try:
            return resp.json()
        except Exception:
            return resp.text


def wait_for_backend(
    api_call_fn,
    operation_name: str = "backend operation",
    initial_delay: float = 2.0,
    max_delay: float | None = None,
) -> Any:
    """
    Generic function to wait/retry backend API calls with exponential backoff.
    
    Args:
        api_call_fn: Callable that performs the API call (can raise RequestException)
        operation_name: Name of operation for logging (e.g., "health check")
        initial_delay: Initial delay in seconds (default: 2.0)
        max_delay: Maximum delay cap in seconds (default: uses config.NETWORK_BACKOFF_CAP_SECONDS)
    
    Returns:
        Result of api_call_fn() when successful
    
    Raises:
        The exception from api_call_fn if all retries are exhausted
    """
    if max_delay is None:
        max_delay = config.NETWORK_BACKOFF_CAP_SECONDS
    
    backoff_delay = initial_delay
    
    while True:
        try:
            result = api_call_fn()
            return result
        except requests.exceptions.RequestException as e:
            print(
                f"🌐 Backend unreachable for {operation_name}, retrying in {backoff_delay}s (error: {e.__class__.__name__})"
            )
            time.sleep(backoff_delay)
            backoff_delay = min(backoff_delay * 2, max_delay)


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


