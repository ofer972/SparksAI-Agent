# Agent Data and Endpoints Summary

## Sprint Daily Agent

| Data Component | Description | Endpoint Called |
|----------------|-------------|-----------------|
| **Daily Transcript** | Latest daily standup transcript for the team | `GET /api/v1/transcripts/getLatest?type=Daily&team_name={team_name}&limit=1` |
| **Sprint Burndown** | Active sprint burndown data (issue counts over time) | `GET /api/v1/team-metrics/sprint-burndown?team_name={team_name}&issue_type=all` |
| **Prompt Template** | "Daily Insights" prompt template | `GET /api/v1/prompts/DailyAgent/Daily%20Insights` |
| **LLM Processing** | Sends formatted data to LLM for analysis | `POST /api/v1/agent-llm-process` |

### Data Sent to LLM:
- Team name
- Formatted daily transcript (with date and raw text)
- Formatted sprint burndown data (markdown table)
- Prompt template text

---

## Sprint Goal Agent

| Data Component | Description | Endpoint Called |
|----------------|-------------|-----------------|
| **Active Sprint Summary** | Active sprint data including sprint goal, sprint_id, dates, issue counts | `GET /api/v1/sprints/active-sprint-summary-by-team?team_name={team_name}` |
| **JIRA Issues with Epic** | All JIRA issues in the sprint with epic information | `GET /api/v1/sprints/sprint-issues-with-epic-for-llm?sprint_id={sprint_id}&team_name={team_name}` |
| **Prompt Template** | "Sprint Goal" prompt template | `GET /api/v1/prompts/DailyAgent/Sprint%20Goal` |
| **LLM Processing** | Sends formatted data to LLM for analysis | `POST /api/v1/agent-llm-process` |

### Data Sent to LLM:
- Sprint goal text
- Active sprint status (all sprint fields except points columns)
- JIRA issues table (issue_key, summary, description, type, status, flagged, dependency, epic_summary)
- Prompt template text

---

## Notes

- Both agents use the same LLM endpoint: `/api/v1/agent-llm-process`
- Both agents fetch prompts from the same endpoint pattern: `/api/v1/prompts/{email_address}/{prompt_name}`
- The Sprint Goal agent selects the sprint with the highest `issues_at_start` if multiple active sprints exist
- All data is formatted client-side before being sent to the LLM endpoint

