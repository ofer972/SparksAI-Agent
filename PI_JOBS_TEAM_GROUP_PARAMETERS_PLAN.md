# Plan: Add Team/Group Parameters to PI Jobs

## Overview
This plan outlines the changes needed to add `team_name` and `is_group` parameters to all GET endpoints used in PI-related jobs when the job contains a `team_name` or `group_name` field.

## PI Jobs Affected
1. **job_pi_sync.py** - PI Sync analysis
2. **job_pi_dependencies.py** - PI Dependencies analysis  
3. **job_pi_planning_gaps.py** - PI Planning Gaps analysis

## Current State Analysis

### Job Parameter Detection
- **Current**: All three jobs check for `job.get("team_name")` but:
  - Don't check for `group_name`
  - Don't pass `team_name` to data fetching endpoints (currently pass `None`)
  - Only use `team_name` in metadata and result text

### Endpoints Used in PI Jobs (GET requests only)

#### ✅ Endpoints Already Supporting `team_name` Parameter:
1. **`/api/v1/pis/get-pi-status-for-today`**
   - Used in: `fetch_pi_data_for_analysis()` → `client.get_pi_summary_today()`
   - Current support: `team_name` (optional)
   - Status: ✅ Already supports `team_name`, needs `is_group` support

2. **`/api/v1/pis/burndown`**
   - Used in: `fetch_pi_data_for_analysis()` → `client.get_pi_burndown()`
   - Current support: `team_name` (optional)
   - Status: ✅ Already supports `team_name`, needs `is_group` support

3. **`/api/v1/team-metrics/get-average-sprint-velocity-per-team`**
   - Used in: `get_average_sprint_velocity_per_team_for_analysis()` → `client.get_average_sprint_velocity_per_team()`
   - Current support: `team_name` (optional), `is_group` (optional)
   - Status: ✅ Fully supported

4. **`/api/v1/transcripts/getLatest`**
   - Used in: `get_transcripts_for_analysis()` → `client.get_transcripts()`
   - Current support: `team_name` (for Daily), `pi_name` (for PI Sync)
   - Status: ✅ Already supports `team_name` for Daily transcripts

#### ❌ Endpoints Missing `team_name`/`is_group` Support:
1. **`/api/v1/pis/get-pi-status-for-today-by-team`**
   - Used in: `get_pi_status_for_today_by_team_for_analysis()` → `client.get_pi_status_for_today_by_team()`
   - Current: Only accepts `pi` parameter
   - **Action Required**: Add `team_name` and `is_group` parameters
   - Used in: `job_pi_planning_gaps.py`

2. **`/api/v1/issues/epics-by-pi`**
   - Used in: `get_epics_by_pi_for_analysis()` → `client.get_epics_by_pi()`
   - Current: Only accepts `pi` parameter
   - **Action Required**: Add `team_name` and `is_group` parameters
   - Used in: `job_pi_planning_gaps.py`

3. **`/api/v1/issues/epic-inbound-dependency-load-by-quarter`**
   - Used in: `get_pi_dependencies_for_analysis()` → `client.get_epic_inbound_dependency_load_by_quarter()`
   - Current: Only accepts `pi` parameter (has separate method for groups)
   - **Action Required**: Add `team_name` and `is_group` parameters to main method
   - Used in: `job_pi_dependencies.py`, `job_pi_planning_gaps.py`

4. **`/api/v1/issues/epic-outbound-dependency-metrics-by-quarter`**
   - Used in: `get_pi_dependencies_for_analysis()` → `client.get_epic_outbound_dependency_metrics_by_quarter()`
   - Current: Only accepts `pi` parameter (has separate method for groups)
   - **Action Required**: Add `team_name` and `is_group` parameters to main method
   - Used in: `job_pi_dependencies.py`, `job_pi_planning_gaps.py`

## Detailed Change Plan

### Phase 1: Update Job Files to Extract and Use Team/Group Parameters

#### 1.1 Update `job_pi_sync.py`
**Location**: Lines 38-186

**Changes**:
- Extract `team_name` from `job.get("team_name")`
- Extract `group_name` from `job.get("group_name")`
- Determine which one is present and set `is_group` flag accordingly
- Pass `team_name` and `is_group` to:
  - `fetch_pi_data_for_analysis()` (line 57-62)
  - `get_transcripts_for_analysis()` (line 48-54) - if team_name exists

**Endpoints affected**:
- `fetch_pi_data_for_analysis()` → `/api/v1/pis/get-pi-status-for-today` (needs `is_group` support)
- `fetch_pi_data_for_analysis()` → `/api/v1/pis/burndown` (needs `is_group` support)
- `get_transcripts_for_analysis()` → `/api/v1/transcripts/getLatest` (already supports team_name)

#### 1.2 Update `job_pi_dependencies.py`
**Location**: Lines 74-254

**Changes**:
- Extract `team_name` from `job.get("team_name")`
- Extract `group_name` from `job.get("group_name")`
- Determine which one is present and set `is_group` flag accordingly
- Pass `team_name` and `is_group` to:
  - `fetch_pi_data_for_analysis()` (line 92-97)
  - `get_pi_dependencies_for_analysis()` (line 106-109)

**Endpoints affected**:
- `fetch_pi_data_for_analysis()` → `/api/v1/pis/get-pi-status-for-today` (needs `is_group` support)
- `fetch_pi_data_for_analysis()` → `/api/v1/pis/burndown` (needs `is_group` support)
- `get_pi_dependencies_for_analysis()` → `/api/v1/issues/epic-inbound-dependency-load-by-quarter` (needs `team_name` + `is_group`)
- `get_pi_dependencies_for_analysis()` → `/api/v1/issues/epic-outbound-dependency-metrics-by-quarter` (needs `team_name` + `is_group`)

#### 1.3 Update `job_pi_planning_gaps.py`
**Location**: Lines 76-267

**Changes**:
- Extract `team_name` from `job.get("team_name")`
- Extract `group_name` from `job.get("group_name")`
- Determine which one is present and set `is_group` flag accordingly
- Pass `team_name` and `is_group` to:
  - `fetch_pi_data_for_analysis()` (line 94-99)
  - `get_pi_status_for_today_by_team_for_analysis()` (line 108-111)
  - `get_average_sprint_velocity_per_team_for_analysis()` (line 114-118)
  - `get_epics_by_pi_for_analysis()` (line 121-124)

**Endpoints affected**:
- `fetch_pi_data_for_analysis()` → `/api/v1/pis/get-pi-status-for-today` (needs `is_group` support)
- `fetch_pi_data_for_analysis()` → `/api/v1/pis/burndown` (needs `is_group` support)
- `get_pi_status_for_today_by_team_for_analysis()` → `/api/v1/pis/get-pi-status-for-today-by-team` (needs `team_name` + `is_group`)
- `get_average_sprint_velocity_per_team_for_analysis()` → `/api/v1/team-metrics/get-average-sprint-velocity-per-team` (✅ already supports)
- `get_epics_by_pi_for_analysis()` → `/api/v1/issues/epics-by-pi` (needs `team_name` + `is_group`)

### Phase 2: Update Utility Functions to Accept and Pass Team/Group Parameters

#### 2.1 Update `utils_data_fetching.py`

**Function: `fetch_pi_data_for_analysis()`**
- **Location**: Lines 94-139
- **Changes**: 
  - Add `is_group: bool = False` parameter
  - Pass `is_group` to `client.get_pi_summary_today()` and `client.get_pi_burndown()`

**Function: `get_pi_status_for_today_by_team_for_analysis()`**
- **Location**: Lines 721-761
- **Changes**:
  - Add `team_name: str | None = None` parameter
  - Add `is_group: bool = False` parameter
  - Pass both to `client.get_pi_status_for_today_by_team()`

**Function: `get_average_sprint_velocity_per_team_for_analysis()`**
- **Location**: Lines 764-809
- **Changes**:
  - Add `team_name: str | None = None` parameter
  - Add `is_group: bool = False` parameter
  - Pass both to `client.get_average_sprint_velocity_per_team()`

**Function: `get_epics_by_pi_for_analysis()`**
- **Location**: Lines 812-872
- **Changes**:
  - Add `team_name: str | None = None` parameter
  - Add `is_group: bool = False` parameter
  - Pass both to `client.get_epics_by_pi()`

**Function: `get_pi_dependencies_for_analysis()`**
- **Location**: Lines 906-961
- **Changes**:
  - Add `team_name: str | None = None` parameter
  - Add `is_group: bool = False` parameter
  - Pass both to:
    - `client.get_epic_inbound_dependency_load_by_quarter()`
    - `client.get_epic_outbound_dependency_metrics_by_quarter()`

### Phase 3: Update API Client Methods

#### 3.1 Update `api_client.py`

**Method: `get_pi_summary_today()`**
- **Location**: Lines 124-143
- **Changes**: Add `is_group: bool = False` parameter and pass as `isGroup` query param

**Method: `get_pi_burndown()`**
- **Location**: Lines 112-122
- **Changes**: Add `is_group: bool = False` parameter and pass as `isGroup` query param

**Method: `get_pi_status_for_today_by_team()`**
- **Location**: Lines 145-170
- **Changes**: 
  - Add `team_name: str | None = None` parameter
  - Add `is_group: bool = False` parameter
  - Pass both as query params

**Method: `get_epics_by_pi()`**
- **Location**: Lines 551-573
- **Changes**:
  - Add `team_name: str | None = None` parameter
  - Add `is_group: bool = False` parameter
  - Pass both as query params

**Method: `get_epic_inbound_dependency_load_by_quarter()`**
- **Location**: Lines 426-442
- **Changes**:
  - Add `team_name: str | None = None` parameter
  - Add `is_group: bool = False` parameter
  - Pass both as query params (can deprecate separate `get_epic_inbound_dependency_load_by_quarter_for_group()` method later)

**Method: `get_epic_outbound_dependency_metrics_by_quarter()`**
- **Location**: Lines 444-460
- **Changes**:
  - Add `team_name: str | None = None` parameter
  - Add `is_group: bool = False` parameter
  - Pass both as query params (can deprecate separate `get_epic_outbound_dependency_metrics_by_quarter_for_group()` method later)

## Summary of Endpoint Changes Required

### ✅ Backend Verification Complete - ALL Endpoints Already Support Parameters!

**Backend Code Analysis Results:**

After checking the actual backend endpoint implementations in `SparksAI-backend/`, **ALL endpoints already support both `team_name` and `isGroup` parameters**:

1. **`/api/v1/pis/get-pi-status-for-today`** (`pis_service.py` line 823-923)
   - ✅ Backend supports: `team_name` and `isGroup` parameters
   - Client status: Missing `is_group` parameter

2. **`/api/v1/pis/burndown`** (`pis_service.py` line 631-716)
   - ✅ Backend supports: `team_name` and `isGroup` parameters
   - Client status: Missing `is_group` parameter

3. **`/api/v1/pis/get-pi-status-for-today-by-team`** (`pis_service.py` line 926+)
   - ✅ Backend supports: `team_name` and `isGroup` parameters
   - Client status: Missing both `team_name` and `is_group` parameters

4. **`/api/v1/issues/epics-by-pi`** (`issues_service.py` line 1137+)
   - ✅ Backend supports: `team_name` and `isGroup` parameters
   - Client status: Missing both `team_name` and `is_group` parameters

5. **`/api/v1/issues/epic-inbound-dependency-load-by-quarter`** (`issues_service.py` line 1019+)
   - ✅ Backend supports: `team_name` and `isGroup` parameters
   - Client status: Missing both `team_name` and `is_group` parameters

6. **`/api/v1/issues/epic-outbound-dependency-metrics-by-quarter`** (`issues_service.py` line 1078+)
   - ✅ Backend supports: `team_name` and `isGroup` parameters
   - Client status: Missing both `team_name` and `is_group` parameters

### Conclusion

**✅ No backend changes required!** All endpoints already support the required parameters. We only need to update the **client code** (`api_client.py`) and the **job files** to extract and pass these parameters.

## Implementation Logic

### Team/Group Detection Logic (to be added to each job):
```python
# Extract team_name or group_name from job
team_name = job.get("team_name")
group_name = job.get("group_name")

# Determine which one to use
if group_name:
    team_param = group_name
    is_group = True
elif team_name:
    team_param = team_name
    is_group = False
else:
    team_param = None
    is_group = False
```

## Testing Considerations

1. **Test with team_name only**: Verify endpoints filter by team correctly
2. **Test with group_name only**: Verify endpoints filter by group correctly (is_group=true)
3. **Test with neither**: Verify endpoints return all data (no filtering)
4. **Test backward compatibility**: Ensure jobs without team/group still work

## Quick Reference: Endpoint Mapping Table

| Endpoint | Backend Support | Client Support | Needs Client Update | Used In Jobs |
|----------|----------------|----------------|---------------------|--------------|
| `/api/v1/pis/get-pi-status-for-today` | ✅ `team_name` + `isGroup` | ✅ `team_name` only | ❌ Add `is_group` param | All 3 PI jobs |
| `/api/v1/pis/burndown` | ✅ `team_name` + `isGroup` | ✅ `team_name` only | ❌ Add `is_group` param | All 3 PI jobs |
| `/api/v1/pis/get-pi-status-for-today-by-team` | ✅ `team_name` + `isGroup` | ❌ None | ❌ Add both params | PI Planning Gaps |
| `/api/v1/team-metrics/get-average-sprint-velocity-per-team` | ✅ `team_name` + `isGroup` | ✅ Both ✅ | ✅ None | PI Planning Gaps |
| `/api/v1/issues/epics-by-pi` | ✅ `team_name` + `isGroup` | ❌ None | ❌ Add both params | PI Planning Gaps |
| `/api/v1/issues/epic-inbound-dependency-load-by-quarter` | ✅ `team_name` + `isGroup` | ❌ None | ❌ Add both params | PI Dependencies, PI Planning Gaps |
| `/api/v1/issues/epic-outbound-dependency-metrics-by-quarter` | ✅ `team_name` + `isGroup` | ❌ None | ❌ Add both params | PI Dependencies, PI Planning Gaps |
| `/api/v1/transcripts/getLatest` | ✅ `team_name` (Daily) | ✅ `team_name` | ✅ None | PI Sync (uses `pi_name`) |

## Notes

- The parameter name in query strings should be `isGroup` (camelCase) to match existing API conventions
- When `is_group=True`, the `team_name` parameter should contain the group name
- All changes should maintain backward compatibility (parameters are optional)
- The separate group-specific methods in `api_client.py` can be kept for backward compatibility but should eventually be deprecated

