# Endpoint Migration Plan: Dedicated Agent LLM Endpoint

## Executive Summary

This plan analyzes how the old DailyAgent system fetched prompts and prepared data for LLM communication, compares it with the current SparksAI-Agent system, and proposes a new dedicated endpoint for agent LLM processing. The goal is to have the agent handle all data preparation client-side, using the new endpoint only for LLM communication.

---

## Analysis of Old DailyAgent System

### 1. Prompt Fetching (Old System)

**Method**: Direct database query
- **Function**: `get_prompt_from_database(engine, prompt_name, email_address, prompt_type)`
- **Query**:
  ```sql
  SELECT prompt_description FROM prompts 
  WHERE prompt_name = :prompt_name 
    AND email_address = :email_address
    AND prompt_type = :prompt_type
    AND prompt_active = true
  ```
- **Examples**:
  - Daily Agent: `prompt_name='Daily Insights'`, `email_address='DailyAgent'`, `prompt_type='Team Dashboard'`
  - PI Sync: `prompt_name='PI Sync'`, `email_address='DailyAgent'`, `prompt_type='PI Dashboard'`
  - Sprint Goal: `prompt_name='Sprint Goal'`, `email_address='DailyAgent'`, `prompt_type='Team Dashboard'`

**Key Characteristics**:
- Direct SQL access to `prompts` table
- Filters by `prompt_active = true` for versioning
- Returns prompt text as string

---

### 2. Data Preparation (Old System)

**Function**: `prepare_data_for_ai(engine, team_name)` or `prepare_data_for_pi_sync(engine, pi_name)`

**Process**:
1. **Fetch Transcript**: Direct SQL query to `transcripts` table
   - Filters by `type` (e.g., 'Daily', 'PI sync')
   - Filters by `team_name` or `pi_name`
   - Orders by `transcript_date DESC LIMIT 1`

2. **Fetch Sprint/Burndown Data**: Direct SQL queries
   - Sprint data from views like `active_sprint_summary_by_team`
   - Burndown data from `sprint_burndown_count` or `pi_burndown_count`

3. **Fetch Prompt**: Uses `get_prompt_from_database()` (see above)

4. **Format for LLM**: `format_data_for_llm(prepared_data)`
   - Combines all data into structured text
   - Sections: `=== TRANSCRIPT DATA ===`, `=== BURN DOWN DATA ===`, `=== PROMPT ===`
   - Creates human-readable markdown/text format

**Key Characteristics**:
- All data fetching happens **client-side**
- Data is formatted into a single string before LLM call
- No backend involvement in data aggregation

---

### 3. LLM Communication (Old System)

**Function**: `call_llm_generic(engine, formatted_data, job_type)`

**Process**:
1. **Get LLM Config from DB**:
   - Reads from `global_settings` table:
     - `ai_provider` (gemini/chatgpt)
     - `ai_model` (e.g., gemini-2.0-flash-exp, gpt-4o)
     - `gemini_api_key` or `chatgpt_api_key`
     - `ai_gemini_temperature` or `ai_chatgpt_temperature`

2. **Direct API Calls**:
   - **Gemini**: Uses `google.genai.Client` directly
   - **ChatGPT**: Uses `openai.OpenAI` directly
   - No backend endpoint involved

**Key Characteristics**:
- LLM config stored in database (client-side)
- Direct API calls to LLM providers
- Client manages API keys and configuration

---

## Analysis of Current SparksAI-Agent System

### 1. Prompt Fetching (Current System)

**Method**: REST API
- **Endpoint**: `GET /api/v1/prompts/{email_address}/{prompt_name}`
- **Usage**:
  ```python
  client.get_prompt("DailyAgent", "Daily Insights")
  # or
  client.get_prompt("PIAgent", "PISync")
  ```
- **Response**: JSON with `prompt_description` field

**Key Characteristics**:
- RESTful API access
- No direct database access
- URL-encoded prompt names (handles spaces with `%20`)

---

### 2. Data Preparation (Current System)

**Function**: `process(job)` in job-specific modules (e.g., `job_daily_agent.py`)

**Process**:
1. **Fetch Transcript**: REST API
   - `GET /api/v1/transcripts/getLatestDaily?team_name={team_name}`
   - `GET /api/v1/transcripts/getLatestPISync?pi_name={pi_name}`

2. **Fetch Burndown Data**: REST API
   - `GET /api/v1/team-metrics/sprint-burndown?team_name={team_name}`
   - `GET /api/v1/pis/burndown?pi={pi}`

3. **Fetch Prompt**: REST API (see above)

4. **Format for LLM**: Client-side formatting functions
   - `_format_daily_input()` or `_format_input()`
   - Combines data into structured text

**Key Characteristics**:
- All data fetching via REST APIs
- Data formatting happens **client-side**
- Agent prepares complete prompt before LLM call

---

### 3. LLM Communication (Current System)

**Function**: `call_llm_generic(client, formatted_text, selected_pi)`

**Process**:
1. **Prepare Request Body**:
   ```python
   body = {
       "question": formatted_text,  # Complete formatted prompt
       "selected_pi": selected_pi,   # Optional PI name
       "chat_type": "PI_dashboard" if selected_pi else None
   }
   ```

2. **Call Backend Endpoint**:
   - `POST /api/v1/ai-chat`
   - Backend handles LLM provider selection, API keys, configuration

3. **Response**:
   ```json
   {
     "success": true,
     "data": {
       "response": "LLM response text..."
     }
   }
   ```

**Key Characteristics**:
- Backend manages LLM provider and API keys
- Backend handles LLM configuration
- Agent sends fully prepared prompt text
- Backend returns LLM response only

---

## Comparison: Old vs Current vs Proposed

| Aspect | Old System | Current System | **Proposed New System** |
|--------|-----------|----------------|------------------------|
| **Prompt Fetching** | Direct DB query | REST API (`/api/v1/prompts/...`) | ✅ Keep REST API |
| **Data Fetching** | Direct DB queries | REST APIs (transcripts, burndown) | ✅ Keep REST APIs |
| **Data Preparation** | Client-side formatting | Client-side formatting | ✅ Keep client-side |
| **LLM Config** | Stored in DB (client reads) | Managed by backend | ✅ Backend manages |
| **LLM Communication** | Direct API calls (client) | Backend endpoint (`/api/v1/ai-chat`) | ✅ **NEW dedicated endpoint** |

---

## Proposed New Endpoint: `/api/v1/agent-llm-process`

### Rationale

The current `/api/v1/ai-chat` endpoint appears to be designed for user-facing chat interactions (hence `question`, `chat_type` parameters). For agent processing, we need a dedicated endpoint that:

1. **Separates concerns**: Agent processing vs user chat
2. **Simplifies parameters**: Agent already prepares everything, just needs LLM call
3. **Better monitoring**: Can track agent-specific LLM usage separately
4. **Future extensibility**: Can add agent-specific features (rate limiting, job context, etc.)

---

## Recommended Endpoint Specification

### Endpoint: `POST /api/v1/agent-llm-process`

### Purpose
Dedicated endpoint for agent-to-LLM communication. Agent prepares all data and prompts client-side, this endpoint only handles LLM provider communication.

### Request Body

```json
{
  "prompt": "Complete formatted prompt text prepared by agent...",
  "job_type": "Daily Agent" | "Sprint Goal" | "PI Sync",
  "job_id": 123,  // Optional: for logging/tracking
  "model_override": null,  // Optional: override default model for this job type
  "temperature_override": null,  // Optional: override default temperature
  "metadata": {  // Optional: additional context
    "team_name": "Team Alpha",
    "pi_name": "PI-2024-01"
  }
}
```

### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `prompt` | `string` | ✅ Yes | Complete formatted prompt prepared by agent (includes transcript, burndown, prompt template) |
| `job_type` | `string` | ✅ Yes | Type of job: "Daily Agent", "Sprint Goal", or "PI Sync" |
| `job_id` | `integer` | ❌ No | Job ID for logging and tracking |
| `model_override` | `string` | ❌ No | Override default model (e.g., "gemini-2.0-flash-exp") |
| `temperature_override` | `float` | ❌ No | Override default temperature (0.0-2.0) |
| `metadata` | `object` | ❌ No | Additional context (team_name, pi_name, etc.) for logging |

### Response

**Success Response (200 OK)**:
```json
{
  "success": true,
  "data": {
    "response": "Full LLM response text...",
    "model_used": "gemini-2.0-flash-exp",
    "temperature_used": 0.0,
    "provider": "gemini",
    "tokens_used": 1234,  // Optional: if available
    "processing_time_ms": 2500  // Optional: if available
  }
}
```

**Error Response (400/500)**:
```json
{
  "success": false,
  "error": {
    "code": "INVALID_REQUEST" | "LLM_ERROR" | "RATE_LIMIT",
    "message": "Human-readable error message",
    "details": {}  // Optional: additional error details
  }
}
```

### Backend Responsibilities

1. **LLM Provider Selection**: Based on global settings or job_type defaults
2. **API Key Management**: Retrieve and use appropriate API keys
3. **Model Selection**: Use default model for job_type, or honor `model_override`
4. **Temperature**: Use default for job_type, or honor `temperature_override`
5. **Error Handling**: Handle LLM API errors gracefully
6. **Logging**: Log requests with job_id and metadata for monitoring
7. **Rate Limiting**: Optional agent-specific rate limiting

### Agent Responsibilities (Client-Side)

1. **Fetch Prompt**: Get prompt template from `/api/v1/prompts/...`
2. **Fetch Data**: Get transcript, burndown, sprint data from respective endpoints
3. **Format Prompt**: Combine all data into single formatted prompt string
4. **Call Endpoint**: Send formatted prompt to `/api/v1/agent-llm-process`
5. **Process Response**: Extract structured content from LLM response

---

## Migration Steps

### Phase 1: Backend Implementation
1. ✅ Create new endpoint `/api/v1/agent-llm-process`
2. ✅ Implement LLM provider selection logic
3. ✅ Add job_type-specific defaults for model/temperature
4. ✅ Add logging and monitoring
5. ✅ Add error handling
6. ✅ Test with sample requests

### Phase 2: Agent Implementation
1. ✅ Update `llm_client.py` to add new function:
   ```python
   def call_agent_llm_process(
       client: APIClient, 
       prompt: str, 
       job_type: str,
       job_id: int | None = None,
       metadata: Dict[str, Any] | None = None
   ) -> Tuple[bool, str, Dict[str, Any]]
   ```
2. ✅ Update `job_daily_agent.py` to use new endpoint
3. ✅ Update `job_pi_sync.py` to use new endpoint
4. ✅ Update `job_sprint_goal.py` to use new endpoint

### Phase 3: Testing & Validation
1. ✅ Test with real jobs
2. ✅ Verify LLM responses match expected format
3. ✅ Monitor backend logs for agent requests
4. ✅ Validate error handling

### Phase 4: Cleanup (Optional)
1. ⚠️ Keep `/api/v1/ai-chat` for user-facing chat (if needed)
2. ⚠️ Or deprecate if not used elsewhere
3. ⚠️ Update documentation

---

## Benefits of New Endpoint

### 1. **Separation of Concerns**
- Agent processing vs user chat are different use cases
- Can optimize each independently

### 2. **Simpler API Contract**
- Agent endpoint: Just prompt + job_type
- User chat endpoint: Can have different parameters (conversation history, etc.)

### 3. **Better Monitoring**
- Track agent LLM usage separately
- Job-level logging with `job_id`

### 4. **Future Extensibility**
- Can add agent-specific features:
  - Job context injection
  - Agent-specific rate limiting
  - Batch processing
  - Priority queues

### 5. **Configuration Flexibility**
- Job-type-specific defaults (model, temperature)
- Per-job overrides when needed

---

## Backend Configuration Recommendations

### Job-Type Defaults

**Recommended defaults in backend settings:**

| Job Type | Default Model | Default Temperature | Provider |
|----------|---------------|---------------------|----------|
| Daily Agent | gemini-2.0-flash-exp | 0.0 | gemini |
| Sprint Goal | gemini-2.0-flash-exp | 0.0 | gemini |
| PI Sync | gemini-2.0-flash-exp | 0.0 | gemini |

*Note: These should be configurable in backend settings/global_settings table*

### Error Handling

**Recommended error codes:**
- `INVALID_REQUEST`: Missing required fields, invalid job_type
- `LLM_ERROR`: LLM API returned error (503, 429, 500, etc.)
- `RATE_LIMIT`: Too many requests from agent
- `CONFIGURATION_ERROR`: Missing API keys or LLM config

### Logging

**Recommended logging fields:**
- `job_id` (if provided)
- `job_type`
- `model_used`
- `provider`
- `prompt_length`
- `response_length`
- `processing_time_ms`
- `success` (boolean)
- `error_code` (if failed)

---

## Example Usage Flow

### 1. Agent Prepares Data (Current Flow)
```python
# Fetch transcript
sc, data = client.get_latest_daily_transcript(team_name)
transcript = data.get("data", {}).get("transcript")

# Fetch burndown
sc, bd = client.get_team_sprint_burndown(team_name)
burndown = bd.get("data")

# Fetch prompt
sc, pdata = client.get_prompt("DailyAgent", "Daily Insights")
prompt_text = pdata.get("data", {}).get("prompt_description")

# Format everything
formatted = _format_daily_input(transcript, burndown, prompt_text, team_name)
```

### 2. Agent Calls New Endpoint
```python
# Call new dedicated endpoint
ok, llm_response, raw = call_agent_llm_process(
    client=client,
    prompt=formatted,
    job_type="Daily Agent",
    job_id=job_id,
    metadata={"team_name": team_name}
)
```

### 3. Agent Processes Response (Current Flow)
```python
# Extract structured content
full_info, dashboard_json, recommendations_json = extract_text_and_json(llm_response)
daily_progress = extract_daily_progress_review(llm_response)

# Save to cards/recommendations
# ... existing logic ...
```

---

## Implementation Checklist

### Backend Tasks
- [ ] Create `/api/v1/agent-llm-process` endpoint
- [ ] Add request validation (prompt, job_type required)
- [ ] Implement LLM provider selection logic
- [ ] Add job-type-specific defaults
- [ ] Add logging with job_id and metadata
- [ ] Add error handling (INVALID_REQUEST, LLM_ERROR, etc.)
- [ ] Add optional model/temperature overrides
- [ ] Test with sample requests
- [ ] Add documentation

### Agent Tasks
- [ ] Add `call_agent_llm_process()` to `llm_client.py`
- [ ] Update `job_daily_agent.py` to use new endpoint
- [ ] Update `job_pi_sync.py` to use new endpoint
- [ ] Update `job_sprint_goal.py` to use new endpoint
- [ ] Test with real jobs
- [ ] Verify response format matches expectations

### Testing Tasks
- [ ] Test with all job types (Daily Agent, Sprint Goal, PI Sync)
- [ ] Test error handling (missing prompt, invalid job_type)
- [ ] Test with model/temperature overrides
- [ ] Verify logging works correctly
- [ ] Monitor backend metrics for agent requests

---

## Questions for Review

1. **Should we keep `/api/v1/ai-chat` for user-facing chat?**
   - If yes, we maintain both endpoints
   - If no, we can deprecate it

2. **Do we need job-type-specific model defaults?**
   - Current proposal: All use same default (configurable)
   - Alternative: Different models per job type

3. **Should metadata be required or optional?**
   - Current proposal: Optional
   - Alternative: Make team_name/pi_name required for logging

4. **Do we need response metadata (tokens_used, processing_time_ms)?**
   - Useful for monitoring
   - Depends on LLM provider capabilities

5. **Should we support batch processing?**
   - Future enhancement: Process multiple prompts in one request
   - Not needed for initial implementation

---

## Next Steps

1. **Review and approve this plan**
2. **Backend team**: Implement `/api/v1/agent-llm-process` endpoint
3. **Agent team**: Update client code to use new endpoint
4. **Testing**: Validate end-to-end flow
5. **Deploy**: Roll out incrementally (feature flag optional)
6. **Monitor**: Track usage and errors
7. **Documentation**: Update API docs

---

## Summary

The new `/api/v1/agent-llm-process` endpoint separates agent LLM processing from user-facing chat, simplifies the API contract (agent prepares everything client-side), and enables better monitoring and future extensibility. The agent continues to handle all data preparation (fetching prompts, transcripts, burndown data and formatting them), while the backend focuses solely on LLM provider communication.

