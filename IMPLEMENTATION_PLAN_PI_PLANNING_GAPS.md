# Implementation Plan: PI Planning Gaps Agent

## Overview
Add a new agent called "PI Planning Gaps" that follows the same pattern as "PI Dependencies" agent.

## Files to Modify

### 1. `config.py`
**Action**: Add "PI Planning Gaps" to JOB_TYPES list after "PI Dependencies"
```python
JOB_TYPES = [
    "Daily Progress",
    "Sprint Goal",
    "PI Sync",
    "Team PI Insight",
    "Team Retro Topics",
    "PI Dependencies",
    "PI Planning Gaps",  # NEW
]
```

### 2. `job_router.py`
**Action**: 
- Import the new module: `import job_pi_planning_gaps`
- Add routing logic after PI Dependencies:
```python
if job_type == "PI Dependencies":
    return job_pi_dependencies.process(job)
if job_type == "PI Planning Gaps":  # NEW
    return job_pi_planning_gaps.process(job)
```

### 3. `api_client.py` (if new API endpoint needed)
**Action**: Add new method to fetch PI Planning Gaps data (if backend endpoint exists)
```python
def get_pi_planning_gaps(self, pi: str) -> Tuple[int, Any]:
    """Get PI planning gaps data.
    
    Args:
        pi: PI name/identifier (e.g., "Q42025")
        
    Returns:
        Tuple of (status_code, response_data)
    """
    resp = requests.get(
        self._url("/api/v1/pis/planning-gaps"),  # ASSUMED ENDPOINT
        params={"pi": pi},
        headers=self._headers(),
        timeout=self.timeout_seconds,
    )
    return resp.status_code, self._safe_json(resp)
```

### 4. `utils_data_fetching.py` (if new data fetching function needed)
**Action**: Add function to fetch and format PI Planning Gaps data (similar to `get_pi_dependencies_for_analysis`)
```python
def get_pi_planning_gaps_for_analysis(
    client: APIClient,
    pi: str,
) -> str:
    """
    Fetch PI planning gaps and format as table for LLM.
    
    Args:
        client: APIClient instance
        pi: PI name/identifier (e.g., "Q42025")
        
    Returns:
        Formatted string with planning gaps data
    """
    from utils_formatting import format_table
    
    status_code, response = client.get_pi_planning_gaps(pi)
    if status_code != 200:
        return f"=== PI PLANNING GAPS ===\n⚠️ Failed to fetch: HTTP {status_code}\n"
    
    # Extract data array from response
    if isinstance(response, dict) and response.get("success"):
        data = response.get("data", [])
        if data and isinstance(data, list):
            table = format_table(data, max_width=50)
            return f"=== PI PLANNING GAPS ===\n{table}\n"
        else:
            return "=== PI PLANNING GAPS ===\nNo planning gaps data found\n"
    else:
        return "=== PI PLANNING GAPS ===\n⚠️ Invalid response format\n"
```

### 5. `utils_processing.py`
**Action**: Export the new function (if created)
```python
# Add to imports/exports if needed
from utils_data_fetching import (
    # ... existing imports ...
    get_pi_planning_gaps_for_analysis,  # NEW
)
```

## Files to Create

### 6. `job_pi_planning_gaps.py` (NEW FILE)
**Action**: Create new file following the exact pattern of `job_pi_dependencies.py`

**Structure**:
- `_extract_pi()` function (same as PI Dependencies)
- `_extract_pi_dates()` function (same as PI Dependencies)
- `process()` function with:
  - Extract PI from job
  - Fetch PI status for dates
  - Fetch planning gaps data
  - Fetch prompt (email_address="PIAgent", prompt_name="PI Planning Gaps")
  - Format input with header
  - Call LLM
  - Extract and save AI card (card_type="PI Planning Gaps", priority="Critical")
  - Extract and save recommendations
  - Return result text

**Key differences from PI Dependencies**:
- Card name: "PI Planning Gaps Analysis"
- Card type: "PI Planning Gaps"
- Prompt name: "PI Planning Gaps"
- Data section header: "=== PI PLANNING GAPS DATA ==="
- Uses `get_pi_planning_gaps_for_analysis()` instead of `get_pi_dependencies_for_analysis()`

## Implementation Steps

1. ✅ Create this plan document
2. ⏳ Add "PI Planning Gaps" to `config.py` JOB_TYPES
3. ⏳ Create `job_pi_planning_gaps.py` file (copy from `job_pi_dependencies.py` and modify)
4. ⏳ Update `job_router.py` to import and route the new agent
5. ⏳ Add API endpoint method to `api_client.py` (if backend endpoint exists)
6. ⏳ Add data fetching function to `utils_data_fetching.py` (if needed)
7. ⏳ Update `utils_processing.py` exports (if needed)
8. ⏳ Test the implementation

## Open Questions

### Critical Questions (Need Answers Before Implementation):

1. **Backend API Endpoint**: 
   - Does a backend API endpoint exist for fetching PI Planning Gaps data?
   - What is the exact endpoint path? (e.g., `/api/v1/pis/planning-gaps`)
   - What is the response format/structure?
   - What parameters does it accept? (just `pi`, or also `team_name`?)

2. **Data Source**:
   - What data should "PI Planning Gaps" analyze?
   - Should it use the same data as PI Dependencies (inbound/outbound dependencies)?
   - Or does it need different data (e.g., planned vs actual capacity, missing epics, etc.)?

3. **Prompt Configuration**:
   - What email_address should be used? (Following pattern: "PIAgent" like PI Dependencies?)
   - What prompt_name should be used? ("PI Planning Gaps"?)
   - Does the prompt already exist in the backend, or does it need to be created?

4. **Card Configuration**:
   - Should the card priority be "Critical" (same as PI Dependencies)?
   - Should it be a "PI" type card (same as PI Dependencies)?
   - Any other card-specific requirements?

5. **Recommendations**:
   - Should recommendations use PI name as team_name (same as PI Dependencies)?
   - Any different recommendation handling needed?

### Optional Enhancements:

6. **Data Combination**:
   - Should PI Planning Gaps also include dependency data (like PI Dependencies does)?
   - Or should it focus on different metrics (capacity gaps, resource gaps, etc.)?

7. **Team Filtering**:
   - Should PI Planning Gaps filter by team_name (like Team PI Insight)?
   - Or should it be PI-wide (like PI Dependencies)?

## Assumptions Made

Based on following the "PI Dependencies" pattern exactly:

- ✅ Uses same PI extraction logic
- ✅ Uses same date extraction logic
- ✅ Uses same prompt fetching pattern (PIAgent / prompt_name)
- ✅ Uses same LLM processing pattern
- ✅ Uses same card creation pattern (PI type, Critical priority)
- ✅ Uses same recommendations pattern (PI name as team_name)
- ✅ Does NOT filter by team_name (PI-wide analysis)
- ✅ Does NOT include transcript data

## Next Steps

1. **Review this plan** and answer the open questions
2. **Confirm backend API endpoint** exists or needs to be created
3. **Approve the plan** before implementation
4. **Implement** following the approved plan

