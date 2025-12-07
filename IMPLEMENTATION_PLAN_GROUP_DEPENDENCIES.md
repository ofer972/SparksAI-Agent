# Implementation Plan: Group Dependencies Agent

## Overview
Create a new **Group Dependencies** agent that analyzes dependencies at the group level, following the same logic as PI Dependencies but filtering by group_name with `is_group=true` parameter.

## Short Summary
- **New Agent Type**: "Group Dependencies"
- **Insight Type**: "Group Dependencies"
- **Logic**: Same as PI Dependencies (inbound/outbound dependencies analysis)
- **Key Difference**: Endpoints include `team_name` (as group_name) and `is_group=true` parameters
- **Card Storage**: Team AI cards with `group_name` (like Group Sprint Predictability)
- **Recommendations**: Use `group_name` as `team_name_or_pi` (like Group Sprint Predictability)

## Detailed Implementation Plan

### 1. API Client Changes (`api_client.py`)

#### 1.1 Add New Methods for Group Dependencies
Add two new methods that mirror the PI dependency endpoints but include group filtering:

**Method 1: `get_epic_inbound_dependency_load_by_quarter_for_group()`**
- **Endpoint**: `/api/v1/issues/epic-inbound-dependency-load-by-quarter`
- **Parameters**:
  - `pi`: PI name/identifier (e.g., "Q42025")
  - `team_name`: Group name (from job.group_name)
  - `is_group`: `"true"` (string, as backend expects)
- **Location**: After `get_epic_outbound_dependency_metrics_by_quarter()` (around line 430)

**Method 2: `get_epic_outbound_dependency_metrics_by_quarter_for_group()`**
- **Endpoint**: `/api/v1/issues/epic-outbound-dependency-metrics-by-quarter`
- **Parameters**:
  - `pi`: PI name/identifier (e.g., "Q42025")
  - `team_name`: Group name (from job.group_name)
  - `is_group`: `"true"` (string, as backend expects)
- **Location**: After the inbound method above

**Implementation Pattern**:
```python
def get_epic_inbound_dependency_load_by_quarter_for_group(
    self, pi: str, group_name: str
) -> Tuple[int, Any]:
    resp = requests.get(
        self._url("/api/v1/issues/epic-inbound-dependency-load-by-quarter"),
        params={"pi": pi, "team_name": group_name, "is_group": "true"},
        headers=self._headers(),
        timeout=self.timeout_seconds,
    )
    return resp.status_code, self._safe_json(resp)
```

### 2. Data Fetching Utility (`utils_data_fetching.py`)

#### 2.1 Add New Function: `get_group_dependencies_for_analysis()`
Create a function similar to `get_pi_dependencies_for_analysis()` but for groups:

**Function Signature**:
```python
def get_group_dependencies_for_analysis(
    client: APIClient,
    pi: str,
    group_name: str,
) -> Tuple[str, str]:
```

**Implementation**:
- Call `client.get_epic_inbound_dependency_load_by_quarter_for_group(pi, group_name)`
- Call `client.get_epic_outbound_dependency_metrics_by_quarter_for_group(pi, group_name)`
- Format responses using `format_table()` (same as PI Dependencies)
- Return `(inbound_formatted, outbound_formatted)` strings

**Location**: After `get_pi_dependencies_for_analysis()` (around line 958)

### 3. New Agent File (`job_group_dependencies.py`)

#### 3.1 File Structure
Create new file following the pattern of:
- `job_pi_dependencies.py` (for dependency logic)
- `job_group_sprint_predictability.py` (for group card saving pattern)

#### 3.2 Key Components

**Extract PI from Job**:
- Use same `_extract_pi()` helper function (copy from `job_pi_dependencies.py`)
- Extract `group_name` from `job.get("group_name")` (like Group Sprint Predictability)

**Extract PI Dates**:
- Use same `_extract_pi_dates()` helper function (copy from `job_pi_dependencies.py`)
- Call `fetch_pi_data_for_analysis()` to get PI status

**Fetch Dependencies**:
- Call `get_group_dependencies_for_analysis(client, pi, group_name)`
- This will use the new API methods with `is_group=true`

**Fetch Prompt**:
- Email address: `"GroupAgent"` (same as Group Sprint Predictability)
- Prompt name: `"Group Dependencies"`
- Job type: `"Group Dependencies"`

**Build Formatted Input**:
- Header: `"=== GROUP DEPENDENCIES DATA ==="`
- Include: Group name, PI, PI dates, current date
- Add inbound dependencies section
- Add outbound dependencies section
- Add prompt template

**LLM Processing**:
- Call `call_agent_llm_process()` with:
  - `job_type="Group Dependencies"`
  - `metadata={"group_name": group_name, "pi_name": pi}`

**Save AI Card**:
- Use `process_llm_response_and_save_ai_card()` with:
  - `card_type="Team"` (Team AI cards endpoint accepts group_name)
  - `group_name=group_name` (pass group_name parameter)
  - `team_name=None` (group cards use group_name instead)
  - `card_config`:
    ```python
    {
        "card_name": "Group Dependencies Analysis",
        "card_type": "Group Dependencies",
        "priority": "High",  # Same as Group Sprint Predictability
        "source": "Group",
    }
    ```
  - `extract_content_fn=extract_review_section`

**Save Recommendations**:
- Extract recommendations JSON from LLM response
- Call `save_recommendations_from_json()` with:
  - `team_name_or_pi=group_name` (use group_name, like Group Sprint Predictability)
  - Same parameters as Group Sprint Predictability
- Fallback to text extraction if no JSON (same as PI Dependencies)

**Result Text**:
- Format similar to Group Sprint Predictability
- Include: Group name, PI, Job ID, Timestamp, data/response lengths, full LLM response

### 4. Configuration Changes (`config.py`)

#### 4.1 Add Job Type
Add `"Group Dependencies"` to `JOB_TYPES` list:
```python
JOB_TYPES = [
    ...
    "Group Sprint Flow",
    "Group Sprint Predictability",
    "Group Dependencies",  # NEW
]
```

### 5. Router Changes (`job_router.py`)

#### 5.1 Import New Module
Add import at top:
```python
import job_group_dependencies
```

#### 5.2 Add Route
Add route in `route_and_process()` function:
```python
if job_type == "Group Sprint Predictability":
    return job_group_sprint_predictability.process(job)
if job_type == "Group Dependencies":
    return job_group_dependencies.process(job)
```

### 6. Backend Requirements (Verification Needed)

#### 6.1 Endpoint Support
Verify that these endpoints support the additional parameters:
- `/api/v1/issues/epic-inbound-dependency-load-by-quarter`
  - Must accept: `pi`, `team_name`, `is_group`
  - When `is_group=true`, `team_name` should be treated as a group name

- `/api/v1/issues/epic-outbound-dependency-metrics-by-quarter`
  - Must accept: `pi`, `team_name`, `is_group`
  - When `is_group=true`, `team_name` should be treated as a group name

#### 6.2 Prompt Configuration
Verify that prompt exists:
- Email address: `"GroupAgent"`
- Prompt name: `"Group Dependencies"`

### 7. File Summary

**Files to Create**:
1. `job_group_dependencies.py` (new file)

**Files to Modify**:
1. `api_client.py` - Add 2 new methods
2. `utils_data_fetching.py` - Add 1 new function
3. `config.py` - Add job type
4. `job_router.py` - Add import and route

**Total Changes**: 1 new file, 4 modified files

### 8. Testing Checklist

- [ ] Verify job type is recognized by agent
- [ ] Verify PI extraction works from job payload
- [ ] Verify group_name extraction works
- [ ] Verify API calls include correct parameters (pi, team_name=group_name, is_group=true)
- [ ] Verify dependencies data is fetched correctly
- [ ] Verify prompt is fetched correctly
- [ ] Verify LLM processing works
- [ ] Verify AI card is saved with group_name
- [ ] Verify recommendations are saved with group_name
- [ ] Verify result text format is correct

### 9. Implementation Order

1. **API Client** - Add the two new methods
2. **Data Fetching** - Add `get_group_dependencies_for_analysis()`
3. **Agent File** - Create `job_group_dependencies.py`
4. **Configuration** - Add to `config.py` and `job_router.py`
5. **Testing** - Test end-to-end flow

## Notes

- The agent follows the same data structure and LLM prompt format as PI Dependencies
- The only difference is the endpoint parameters (adding group_name and is_group)
- Card saving follows Group Sprint Predictability pattern (Team cards with group_name)
- Recommendations follow Group Sprint Predictability pattern (using group_name)

