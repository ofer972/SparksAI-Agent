# Group Dependencies Agent - Endpoints and Parameters

## Overview
The **Group Dependencies** agent calls **2 endpoints** to fetch dependency data filtered by group.

## Endpoints Called

### 1. Inbound Dependencies Endpoint (Group Filtered)
- **URL**: `/api/v1/issues/epic-inbound-dependency-load-by-quarter`
- **Method**: `GET`
- **Parameters**:
  - `pi` (query parameter): PI name/identifier (e.g., "Q42025")
  - `team_name` (query parameter): Group name (from `job.group_name`)
  - `is_group` (query parameter): `"true"` (string)
- **Example**:
  ```
  GET /api/v1/issues/epic-inbound-dependency-load-by-quarter?pi=Q42025&team_name=Engineering&is_group=true
  ```
- **Response Structure**:
  ```json
  {
    "success": true,
    "data": [...]
  }
  ```
- **API Client Method**: `client.get_epic_inbound_dependency_load_by_quarter_for_group(pi, group_name)`
- **Location**: `api_client.py` lines 432-449

### 2. Outbound Dependencies Endpoint (Group Filtered)
- **URL**: `/api/v1/issues/epic-outbound-dependency-metrics-by-quarter`
- **Method**: `GET`
- **Parameters**:
  - `pi` (query parameter): PI name/identifier (e.g., "Q42025")
  - `team_name` (query parameter): Group name (from `job.group_name`)
  - `is_group` (query parameter): `"true"` (string)
- **Example**:
  ```
  GET /api/v1/issues/epic-outbound-dependency-metrics-by-quarter?pi=Q42025&team_name=Engineering&is_group=true
  ```
- **Response Structure**:
  ```json
  {
    "success": true,
    "data": [...]
  }
  ```
- **API Client Method**: `client.get_epic_outbound_dependency_metrics_by_quarter_for_group(pi, group_name)`
- **Location**: `api_client.py` lines 451-468

## Code Flow

### Entry Point
- **File**: `job_group_dependencies.py`
- **Function**: `process(job: Dict[str, Any])`
- **Line 108-112**: Calls `get_group_dependencies_for_analysis(client, pi, group_name)`

### Data Fetching Function
- **File**: `utils_data_fetching.py`
- **Function**: `get_group_dependencies_for_analysis(client, pi, group_name)`
- **Line 980**: Calls `client.get_epic_inbound_dependency_load_by_quarter_for_group(pi, group_name)`
- **Line 996**: Calls `client.get_epic_outbound_dependency_metrics_by_quarter_for_group(pi, group_name)`

## Parameter Details

### PI Parameter
- **Source**: Extracted from `job.get("pi")` or `job.get("job_data").get("pi")`
- **Format**: `"Q{quarter}{year}"` (e.g., `"Q42025"` for Q4 2025)
- **Required**: Yes

### Group Name Parameter (as team_name)
- **Source**: Extracted from `job.get("group_name")`
- **Format**: String (e.g., `"Engineering"`, `"Product"`)
- **Required**: Yes
- **Note**: Passed as `team_name` parameter to backend, but represents a group name

### is_group Parameter
- **Value**: Always `"true"` (as string)
- **Purpose**: Tells backend to treat `team_name` as a group name, not a team name
- **Required**: Yes

## Comparison with PI Dependencies

| Aspect | PI Dependencies | Group Dependencies |
|--------|----------------|-------------------|
| **Inbound Endpoint** | `/api/v1/issues/epic-inbound-dependency-load-by-quarter` | Same |
| **Outbound Endpoint** | `/api/v1/issues/epic-outbound-dependency-metrics-by-quarter` | Same |
| **pi Parameter** | ✅ Required | ✅ Required |
| **team_name Parameter** | ❌ Not included | ✅ Required (as group_name) |
| **is_group Parameter** | ❌ Not included | ✅ Required (`"true"`) |

## Full Request Examples

### For Group "Engineering" in PI "Q42025":

**Inbound Dependencies**:
```
GET /api/v1/issues/epic-inbound-dependency-load-by-quarter?pi=Q42025&team_name=Engineering&is_group=true
```

**Outbound Dependencies**:
```
GET /api/v1/issues/epic-outbound-dependency-metrics-by-quarter?pi=Q42025&team_name=Engineering&is_group=true
```

## Summary

**Endpoints**: Same as PI Dependencies (2 endpoints)
**Key Difference**: Group Dependencies adds:
- `team_name` parameter (containing the group name)
- `is_group=true` parameter

This allows the backend to filter dependencies by group instead of returning all dependencies for the PI.

