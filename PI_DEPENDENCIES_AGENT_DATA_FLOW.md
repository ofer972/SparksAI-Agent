# PI Dependencies Agent - Data Flow and LLM Endpoints

## Overview
The **PI Dependencies Agent** (`job_pi_dependencies.py`) analyzes inbound and outbound dependencies for a Program Increment (PI) using LLM processing.

## Agent Location
- **File**: `job_pi_dependencies.py`
- **Function**: `process(job: Dict[str, Any]) -> Tuple[bool, str]`

## Data Collection Endpoints

The agent uses the following **GET endpoints** to fetch dependency data:

### 1. PI Status Data
- **Endpoint**: `/api/v1/pis/get-pi-status-for-today`
- **Method**: `GET`
- **Parameters**: `pi` (PI name/identifier)
- **Purpose**: Fetches PI status to extract PI start and end dates
- **API Client Method**: `client.get_pi_summary_today(pi)`

### 2. Inbound Dependencies
- **Endpoint**: `/api/v1/issues/epic-inbound-dependency-load-by-quarter`
- **Method**: `GET`
- **Parameters**: `pi` (PI name/identifier, e.g., "Q42025")
- **Purpose**: Fetches inbound dependency load data for epics in the PI
- **API Client Method**: `client.get_epic_inbound_dependency_load_by_quarter(pi)`
- **Response Format**: `{"success": true, "data": [...]}`

### 3. Outbound Dependencies
- **Endpoint**: `/api/v1/issues/epic-outbound-dependency-metrics-by-quarter`
- **Method**: `GET`
- **Parameters**: `pi` (PI name/identifier, e.g., "Q42025")
- **Purpose**: Fetches outbound dependency metrics for epics in the PI
- **API Client Method**: `client.get_epic_outbound_dependency_metrics_by_quarter(pi)`
- **Response Format**: `{"success": true, "data": [...]}`

### 4. Prompt Template
- **Endpoint**: `/api/v1/prompts/{email_address}/{prompt_name}`
- **Method**: `GET`
- **Parameters**: 
  - `email_address`: "PIAgent"
  - `prompt_name`: "PI Dependencies"
- **Purpose**: Fetches the prompt template for LLM analysis
- **API Client Method**: `client.get_prompt("PIAgent", "PI Dependencies")`

## LLM Processing Endpoint

### Main LLM Endpoint
- **Endpoint**: `/api/v1/agent-llm-process`
- **Method**: `POST`
- **API Client Method**: `client.post_agent_llm_process(body)`
- **Location**: `api_client.py` line 464-471

### Request Body Structure
The following data is sent to the LLM endpoint:

```json
{
  "prompt": "<formatted_prompt_string>",
  "job_type": "PI Dependencies",
  "job_id": <optional_job_id>,
  "metadata": {
    "pi_name": "<pi_name>",
    "team_name": "<optional_team_name>"
  }
}
```

### Formatted Prompt Content
The `prompt` field contains a formatted string with:

1. **Header Section**:
   ```
   === PI DEPENDENCIES DATA ===
   PI: <pi_name>
   PI Start Date: <start_date>
   PI End Date: <end_date>
   Current Date: <current_date>
   ```

2. **Inbound Dependencies Section**:
   ```
   === INBOUND DEPENDENCIES ===
   <formatted_table_of_inbound_data>
   ```

3. **Outbound Dependencies Section**:
   ```
   === OUTBOUND DEPENDENCIES ===
   <formatted_table_of_outbound_data>
   ```

4. **Prompt Template**:
   ```
   <prompt_template_from_backend>
   ```

### Data Processing Flow

1. **Fetch PI Status** → Extract dates
2. **Fetch Inbound Dependencies** → Format as table
3. **Fetch Outbound Dependencies** → Format as table
4. **Fetch Prompt Template** → Get analysis instructions
5. **Combine All Data** → Create formatted prompt string
6. **Send to LLM** → POST to `/api/v1/agent-llm-process`
7. **Process Response** → Extract analysis and save AI card + recommendations

## Code Flow

### Entry Point
```python
# job_pi_dependencies.py, line 73
def process(job: Dict[str, Any]) -> Tuple[bool, str]:
```

### Data Fetching
```python
# Lines 90-107
_, pi_status_obj, _ = fetch_pi_data_for_analysis(...)
inbound_formatted, outbound_formatted = get_pi_dependencies_for_analysis(...)
prompt_text, prompt_error = get_prompt_with_error_check(...)
```

### LLM Call
```python
# Lines 148-156
ok, llm_answer, _raw = call_agent_llm_process(
    client=client,
    prompt=formatted,  # Contains all dependency data + prompt
    job_type="PI Dependencies",
    job_id=job_id,
    metadata={"pi_name": pi, "team_name": job.get("team_name")},
)
```

### LLM Client Implementation
```python
# llm_client.py, lines 26-38
body: Dict[str, Any] = {
    "prompt": prompt,      # Full formatted string with all data
    "job_type": job_type,
}
if job_id is not None:
    body["job_id"] = job_id
if metadata:
    body["metadata"] = metadata

status, data = client.post_agent_llm_process(body)  # POST to /api/v1/agent-llm-process
```

## Summary

**Agent**: `job_pi_dependencies.py` - Processes PI dependency analysis jobs

**Data Collection Endpoints**:
- `/api/v1/pis/get-pi-status-for-today` - PI status and dates
- `/api/v1/issues/epic-inbound-dependency-load-by-quarter` - Inbound dependencies
- `/api/v1/issues/epic-outbound-dependency-metrics-by-quarter` - Outbound dependencies
- `/api/v1/prompts/PIAgent/PI Dependencies` - Prompt template

**LLM Endpoint**:
- `/api/v1/agent-llm-process` (POST)
- Receives: Formatted prompt string containing all dependency data + analysis instructions
- Returns: LLM-generated analysis response

**Data Sent to LLM**:
- PI name, start date, end date, current date
- Formatted table of inbound dependencies
- Formatted table of outbound dependencies
- Prompt template with analysis instructions
- Metadata: job_id, job_type, pi_name, team_name

