import time
from typing import Any, Dict, List, Optional, Tuple

import requests

import config


class APIClient:
    def __init__(self, base_url: Optional[str] = None, timeout_seconds: int | None = None):
        self.base_url: str = (base_url or config.BASE_URL).rstrip("/")
        self.timeout_seconds: int = timeout_seconds if timeout_seconds is not None else config.API_TIMEOUT_SECONDS

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

    def claim_next_pending_job(self) -> Tuple[int, Any]:
        resp = requests.post(
            self._url("/api/v1/agent-jobs/claim-next"),
            headers=self._headers(),
            json={"claimed_by": "SparksAI-Agent"},
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

    def get_pi_burndown(self, pi: str, team_name: str | None = None, is_group: bool = False) -> Tuple[int, Any]:
        params: Dict[str, Any] = {"pi": pi}
        if team_name:
            params["team_name"] = team_name
        if is_group:
            params["isGroup"] = "true"
        resp = requests.get(
            self._url("/api/v1/pis/burndown"),
            params=params,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def get_pi_summary_today(self, pi: str, team_name: str | None = None, is_group: bool = False) -> Tuple[int, Any]:
        """Get PI status summary for current date.
        
        Args:
            pi: PI name/identifier
            team_name: Optional team name or group name (if is_group=true) to filter by
            is_group: If true, team_name is treated as a group name
            
        Returns:
            Tuple of (status_code, response_data)
        """
        params: Dict[str, Any] = {"pi": pi}
        if team_name:
            params["team_name"] = team_name
        if is_group:
            params["isGroup"] = "true"
        resp = requests.get(
            self._url("/api/v1/pis/get-pi-status-for-today"),
            params=params,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def get_pi_status_for_today_by_team(self, pi: str, team_name: str | None = None, is_group: bool = False) -> Tuple[int, Any]:
        """Get PI status for today by team.
        
        Args:
            pi: PI name/identifier
            team_name: Optional team name or group name (if is_group=true) to filter by
            is_group: If true, team_name is treated as a group name
            
        Returns:
            Tuple of (status_code, response_data)
            Response structure: {
                "success": true,
                "data": {
                    "data": [...],  # List of team status objects
                    "count": int,
                    "team": str | null,
                    "group_name": str | null,
                    "teams_in_group": [...]
                }
            }
        """
        params: Dict[str, Any] = {"pi": pi}
        if team_name:
            params["team_name"] = team_name
        if is_group:
            params["isGroup"] = "true"
        resp = requests.get(
            self._url("/api/v1/pis/get-pi-status-for-today-by-team"),
            params=params,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def get_current_and_next_pis(self) -> Tuple[int, Any]:
        """Get current and next PIs.
        
        Returns:
            Tuple of (status_code, response_data)
            Response structure: {
                "success": true,
                "data": {
                    "current_pis": [
                        {
                            "pi_name": "Q42025",
                            "start_date": "2025-10-05",
                            "end_date": "2025-12-28"
                        }
                    ],
                    "next_pis": [...]
                },
                "count": {
                    "current": 1,
                    "next": 1
                }
            }
        """
        resp = requests.get(
            self._url("/api/v1/pis/current-and-next"),
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def get_average_sprint_velocity_per_team(
        self,
        pi: str | None = None,
        num_sprints: int = 5,
        team_name: str | None = None,
        is_group: bool = False,
    ) -> Tuple[int, Any]:
        """Get average sprint velocity per team.
        
        Args:
            pi: Optional PI name/identifier (if provided, uses teams participating in the PI)
            num_sprints: Number of sprints to average (default: 5, max: 20)
            team_name: Optional team name to filter by
            is_group: Optional flag to treat team_name as a group
            
        Returns:
            Tuple of (status_code, response_data)
            Response structure: {
                "success": true,
                "data": {
                    "velocity_data": [
                        {"team_name": "Team Alpha", "avg_velocity": 12.5},
                        ...
                    ],
                    "num_sprints": 5,
                    "count": 3,
                    "pi": "2025-Q1"
                }
            }
        """
        params: Dict[str, Any] = {}
        if pi:
            params["pi"] = pi
        if num_sprints:
            params["num_sprints"] = num_sprints
        if team_name:
            params["team_name"] = team_name
        if is_group:
            params["isGroup"] = "true"
        
        resp = requests.get(
            self._url("/api/v1/team-metrics/get-average-sprint-velocity-per-team"),
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

    def get_current_sprint_progress(self, team_name: str, is_group: bool = False) -> Tuple[int, Any]:
        """Get current sprint progress for a team or group.
        
        Args:
            team_name: Team name or group name (if is_group=true)
            is_group: If true, team_name is treated as a group name
            
        Returns:
            Tuple of (status_code, response_data)
            Response structure: {
                "success": true,
                "data": {
                    "total_issues": int,
                    "completed_issues": int,
                    "in_progress_issues": int,
                    "todo_issues": int,
                    "percent_completed": float,
                    "percent_completed_status": "green" | "yellow" | "red",
                    "in_progress_issues_status": "green" | "yellow" | "red",
                    "sprint_id": int,
                    "sprint_name": str,
                    "days_left": str,
                    "days_in_sprint": int,
                    "team_name": str
                }
            }
        """
        params: Dict[str, Any] = {"team_name": team_name}
        if is_group:
            params["isGroup"] = "true"
        resp = requests.get(
            self._url("/api/v1/team-metrics/current-sprint-progress"),
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

    def get_closed_sprints(
        self,
        team_name: str | None = None,
        months: int = 3,
        is_group: bool = False,
        issue_type: str | None = None,
    ) -> Tuple[int, Any]:
        """Get closed sprints data.
        
        Args:
            team_name: Optional team name or group name (if is_group=true)
            months: Number of months to look back (default: 3, valid: 1, 2, 3, 4, 6, 9, 12)
            is_group: If true, team_name is treated as a group name
            issue_type: Optional issue type filter (e.g., 'Story', 'Bug', 'Task')
            
        Returns:
            Tuple of (status_code, response_data)
            Response structure: {
                "success": true,
                "data": {
                    "months": int,
                    "closed_sprints_by_team": {
                        "TeamName": [...]
                    }
                }
            }
        """
        params: Dict[str, Any] = {"months": months}
        if team_name:
            params["team_name"] = team_name
        if is_group:
            params["isGroup"] = "true"
        if issue_type:
            params["issue_type"] = issue_type
        
        resp = requests.get(
            self._url("/api/v1/team-metrics/closed-sprints"),
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

    def get_epic_inbound_dependency_load_by_quarter(self, pi: str, team_name: str | None = None, is_group: bool = False) -> Tuple[int, Any]:
        """Get inbound dependency load by quarter for a PI.
        
        Args:
            pi: PI name/identifier (e.g., "Q42025")
            team_name: Optional team name or group name (if is_group=true) to filter by
            is_group: If true, team_name is treated as a group name
            
        Returns:
            Tuple of (status_code, response_data)
            Response structure: {"success": true, "data": [...]}
        """
        params: Dict[str, Any] = {"pi": pi}
        if team_name:
            params["team_name"] = team_name
        if is_group:
            params["isGroup"] = "true"
        resp = requests.get(
            self._url("/api/v1/issues/epic-inbound-dependency-load-by-quarter"),
            params=params,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def get_epic_outbound_dependency_metrics_by_quarter(self, pi: str, team_name: str | None = None, is_group: bool = False) -> Tuple[int, Any]:
        """Get outbound dependency metrics by quarter for a PI.
        
        Args:
            pi: PI name/identifier (e.g., "Q42025")
            team_name: Optional team name or group name (if is_group=true) to filter by
            is_group: If true, team_name is treated as a group name
            
        Returns:
            Tuple of (status_code, response_data)
            Response structure: {"success": true, "data": [...]}
        """
        params: Dict[str, Any] = {"pi": pi}
        if team_name:
            params["team_name"] = team_name
        if is_group:
            params["isGroup"] = "true"
        resp = requests.get(
            self._url("/api/v1/issues/epic-outbound-dependency-metrics-by-quarter"),
            params=params,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def get_epic_inbound_dependency_load_by_quarter_for_group(self, pi: str, group_name: str) -> Tuple[int, Any]:
        """Get inbound dependency load by quarter for a group within a PI.
        
        Args:
            pi: PI name/identifier (e.g., "Q42025")
            group_name: Group name to filter dependencies
            
        Returns:
            Tuple of (status_code, response_data)
            Response structure: {"success": true, "data": [...]}
        """
        resp = requests.get(
            self._url("/api/v1/issues/epic-inbound-dependency-load-by-quarter"),
            params={"pi": pi, "team_name": group_name, "isGroup": "true"},
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def get_epic_outbound_dependency_metrics_by_quarter_for_group(self, pi: str, group_name: str) -> Tuple[int, Any]:
        """Get outbound dependency metrics by quarter for a group within a PI.
        
        Args:
            pi: PI name/identifier (e.g., "Q42025")
            group_name: Group name to filter dependencies
            
        Returns:
            Tuple of (status_code, response_data)
            Response structure: {"success": true, "data": [...]}
        """
        resp = requests.get(
            self._url("/api/v1/issues/epic-outbound-dependency-metrics-by-quarter"),
            params={"pi": pi, "team_name": group_name, "isGroup": "true"},
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def get_active_sprint_epic_dependencies(self, group_name: str) -> Tuple[int, Any]:
        """Get active sprint epic dependencies for a group.
        
        Args:
            group_name: Group name to get active sprint epic dependencies for
            
        Returns:
            Tuple of (status_code, response_data)
            Response structure: {
                "success": true,
                "data": {
                    "dependencies": [...],
                    "count": int,
                    "isGroup": true,
                    "group_name": str,
                    "teams_in_group": [...]
                }
            }
        """
        resp = requests.get(
            self._url("/api/v1/issues/active-sprint-epic-dependencies"),
            params={"team_name": group_name, "isGroup": "true"},
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def get_active_sprint_stories_by_epic(self, group_name: str) -> Tuple[int, Any]:
        """Get active sprint child issues by epic for a group.
        
        Args:
            group_name: Group name to get active sprint child issues by epic for
            
        Returns:
            Tuple of (status_code, response_data)
            Response structure: {
                "success": true,
                "data": [...],
                "count": int,
                "isGroup": false,
                "team_name": null
            }
        """
        resp = requests.get(
            self._url("/api/v1/issues/active-sprint-stories-by-epic"),
            params={"team_name": group_name, "isGroup": "true"},
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def get_epics_by_pi(self, pi: str, team_name: str | None = None, is_group: bool = False) -> Tuple[int, Any]:
        """Get epics by PI with dependency metrics.
        
        Args:
            pi: PI name/identifier (e.g., "Q42025")
            team_name: Optional team name or group name (if is_group=true) to filter by
            is_group: If true, team_name is treated as a group name
            
        Returns:
            Tuple of (status_code, response_data)
            Response structure: {
                "success": true,
                "data": {
                    "epics": [...],
                    "count": int
                }
            }
        """
        params: Dict[str, Any] = {"pi": pi}
        if team_name:
            params["team_name"] = team_name
        if is_group:
            params["isGroup"] = "true"
        resp = requests.get(
            self._url("/api/v1/issues/epics-by-pi"),
            params=params,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def get_epics_average_velocity(
        self,
        pi: str,
        team_name: str | None = None,
        is_group: bool = False,
        num_pis: int = 3,
    ) -> Tuple[int, Any]:
        """Get epics average velocity for a PI.
        
        Args:
            pi: PI name/identifier (e.g., "Q42025")
            team_name: Optional team name or group name (if is_group=true) to filter by
            is_group: If true, team_name is treated as a group name
            num_pis: Number of recent completed PIs to analyze (default: 3, min: 1, max: 20)
            
        Returns:
            Tuple of (status_code, response_data)
            Response structure: {
                "success": true,
                "data": {
                    "num_pis": int,
                    "pis_analyzed": [...],
                    "velocity_by_team": [...],
                    "overall_pi_velocity": {...}
                }
            }
        """
        params: Dict[str, Any] = {"pi": pi, "num_pis": num_pis}
        if team_name:
            params["team_name"] = team_name
        if is_group:
            params["isGroup"] = "true"
        resp = requests.get(
            self._url("/api/v1/pis/epics-average-velocity"),
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

    def post_agent_llm_process(self, body: Dict[str, Any]) -> Tuple[int, Any]:
        resp = requests.post(
            self._url("/api/v1/agent-llm-process"),
            headers=self._headers(),
            json=body,
            timeout=config.LLM_TIMEOUT_SECONDS,
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

    def list_team_ai_cards(self, date: str | None = None, card_name: str | None = None) -> Tuple[int, Any]:
        params = {}
        if date:
            params["date"] = date
        if card_name:
            params["card_name"] = card_name
        resp = requests.get(
            self._url("/api/v1/team-ai-cards"),
            headers=self._headers(),
            params=params if params else None,
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

    # Unified AI Insights methods
    def create_ai_insight(self, body: Dict[str, Any]) -> Tuple[int, Any]:
        """Create AI insight card using unified endpoint.
        
        Args:
            body: Card data (must include insight_type and appropriate identifier fields)
        """
        resp = requests.post(
            self._url("/api/v1/ai-insights"),
            headers=self._headers(),
            json=body,
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def list_ai_insights(self, insight_type: str | None = None, date: str | None = None, 
                        card_name: str | None = None, team_name: str | None = None,
                        group_name: str | None = None, pi: str | None = None,
                        limit: int = 100) -> Tuple[int, Any]:
        """List AI insights with optional filtering using unified endpoint.
        
        Args:
            insight_type: Optional filter by type ('team', 'group', 'pi')
            date: Optional date filter
            card_name: Optional card name filter
            team_name: Optional team name filter
            group_name: Optional group name filter
            pi: Optional PI name filter
            limit: Maximum number of cards to return (default: 100)
        """
        params = {}
        if insight_type:
            params["insight_type"] = insight_type
        if date:
            params["date"] = date
        if card_name:
            params["card_name"] = card_name
        if team_name:
            params["team_name"] = team_name
        if group_name:
            params["group_name"] = group_name
        if pi:
            params["pi"] = pi
        if limit:
            params["limit"] = limit
        
        resp = requests.get(
            self._url("/api/v1/ai-insights"),
            headers=self._headers(),
            params=params if params else None,
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def patch_ai_insight(self, card_id: int, body: Dict[str, Any]) -> Tuple[int, Any]:
        """Update AI insight card using unified endpoint."""
        resp = requests.patch(
            self._url(f"/api/v1/ai-insights/{card_id}"),
            headers=self._headers(),
            json=body,
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def get_teams_in_group_by_name(self, group_name: str) -> Tuple[int, Any]:
        """Get all teams in a group by group name.
        
        Args:
            group_name: The name of the group
            
        Returns:
            Tuple of (status_code, response_data)
            Response structure: {
                "success": true,
                "data": {
                    "teams": [
                        {
                            "team_key": int,
                            "team_name": str,
                            "number_of_team_members": int,
                            "group_key": int
                        },
                        ...
                    ],
                    "count": int,
                    "group_key": int
                }
            }
        """
        resp = requests.get(
            self._url(f"/api/v1/groups/by-name/{group_name}/teams"),
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def get_goals(
        self,
        scope_type: str,
        sprint_id: int | None = None,
        team_name: str | None = None,
    ) -> Tuple[int, Any]:
        """Get goals for a scope (PI, Sprint, or Release).
        
        Args:
            scope_type: 'pi', 'sprint', or 'release'
            sprint_id: Sprint ID (required if scope_type='sprint')
            team_name: Optional team name to filter by
            
        Returns:
            Tuple of (status_code, response_data)
            Response structure: {
                "success": true,
                "data": {
                    "scope_type": "sprint",
                    "team_goals": [...]
                }
            }
        """
        params: Dict[str, Any] = {"scope_type": scope_type}
        if sprint_id:
            params["sprint_id"] = sprint_id
        if team_name:
            params["team_name"] = team_name
        
        resp = requests.get(
            self._url("/api/v1/goals"),
            params=params,
            headers=self._headers(),
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


