# GET Endpoints Used by Agents

| Endpoint | Purpose |
|----------|---------|
| **Prompts** |
| `/api/v1/prompts/{email_address}/{prompt_name}` | Fetch prompt template |
| **Transcripts** |
| `/api/v1/transcripts/getLatest` | Get latest transcripts (Daily/PI Sync) |
| **PI Data** |
| `/api/v1/pis/get-pi-status-for-today` | Get PI status for today |
| `/api/v1/pis/get-pi-status-for-today-by-team` | Get PI status by team |
| `/api/v1/pis/burndown` | Get PI burndown data |
| **Sprints** |
| `/api/v1/sprints/active-sprint-summary-by-team` | Get active sprint summary |
| `/api/v1/sprints/sprint-predictability` | Get sprint predictability metrics |
| `/api/v1/sprints/sprint-issues-with-epic-for-llm` | Get sprint issues with epic data |
| **Team Metrics** |
| `/api/v1/team-metrics/sprint-burndown` | Get sprint burndown for team |
| `/api/v1/team-metrics/get-average-sprint-velocity-per-team` | Get average sprint velocity |
| **Issues & Epics** |
| `/api/v1/issues` | Get sprint issues |
| `/api/v1/issues/epics-by-pi` | Get epics by PI |
| `/api/v1/issues/epic-inbound-dependency-load-by-quarter` | Get inbound dependencies |
| `/api/v1/issues/epic-outbound-dependency-metrics-by-quarter` | Get outbound dependencies |
| **Groups** |
| `/api/v1/groups/by-name/{group_name}/teams` | Get teams in group |
| **AI Cards** |
| `/api/v1/pi-ai-cards` | List PI AI cards |
| `/api/v1/team-ai-cards` | List Team AI cards |
| **Health** |
| `/health` | Health check |

