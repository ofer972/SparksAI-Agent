# PI Dependencies Agent - Endpoints and Parameters

## Overview
The PI Dependencies agent calls **2 endpoints** to fetch dependency data for analysis.

## Endpoints Called

### 1. Inbound Dependencies Endpoint
- **URL**: `/api/v1/issues/epic-inbound-dependency-load-by-quarter`
- **Method**: `GET`
- **Parameters**:
  - `pi` (query parameter): PI name/identifier
- **Example for Q4 2025**:
  ```
  GET /api/v1/issues/epic-inbound-dependency-load-by-quarter?pi=Q42025
  ```
- **Response Structure**:
  ```json
  {
    "success": true,
    "data": [...]
  }
  ```
- **API Client Method**: `client.get_epic_inbound_dependency_load_by_quarter(pi)`
- **Location**: `api_client.py` lines 396-412

### 2. Outbound Dependencies Endpoint
- **URL**: `/api/v1/issues/epic-outbound-dependency-metrics-by-quarter`
- **Method**: `GET`
- **Parameters**:
  - `pi` (query parameter): PI name/identifier
- **Example for Q4 2025**:
  ```
  GET /api/v1/issues/epic-outbound-dependency-metrics-by-quarter?pi=Q42025
  ```
- **Response Structure**:
  ```json
  {
    "success": true,
    "data": [...]
  }
  ```
- **API Client Method**: `client.get_epic_outbound_dependency_metrics_by_quarter(pi)`
- **Location**: `api_client.py` lines 414-430

## Code Flow

### Entry Point
- **File**: `job_pi_dependencies.py`
- **Function**: `process(job: Dict[str, Any])`
- **Line 104-107**: Calls `get_pi_dependencies_for_analysis(client, pi)`

### Data Fetching Function
- **File**: `utils_data_fetching.py`
- **Function**: `get_pi_dependencies_for_analysis(client, pi)`
- **Lines 926**: Calls `client.get_epic_inbound_dependency_load_by_quarter(pi)`
- **Lines 942**: Calls `client.get_epic_outbound_dependency_metrics_by_quarter(pi)`

## Parameters for Q4 2025

Assuming the Quarter is **Q4 2025**, the PI parameter would be:
- **PI Value**: `"Q42025"`

### Full Request URLs (Example)
```
GET /api/v1/issues/epic-inbound-dependency-load-by-quarter?pi=Q42025
GET /api/v1/issues/epic-outbound-dependency-metrics-by-quarter?pi=Q42025
```

## Additional Endpoints Used (Not for Dependencies)

The PI Dependencies agent also calls these endpoints for other data:

### PI Status Endpoint
- **URL**: `/api/v1/pis/get-pi-status-for-today`
- **Method**: `GET`
- **Parameters**: `pi` (query parameter)
- **Purpose**: Get PI start and end dates
- **Called via**: `fetch_pi_data_for_analysis()` → `client.get_pi_summary_today(pi)`

### Prompt Template Endpoint
- **URL**: `/api/v1/prompts/{email_address}/{prompt_name}`
- **Method**: `GET`
- **Parameters**: 
  - `email_address`: `"PIAgent"`
  - `prompt_name`: `"PI Dependencies"`
- **Purpose**: Get the prompt template for LLM analysis
- **Called via**: `get_prompt_with_error_check()` → `client.get_prompt("PIAgent", "PI Dependencies")`

## Summary

**For Q4 2025 (PI = "Q42025"), the agent calls:**

1. **Inbound Dependencies**:
   - Endpoint: `/api/v1/issues/epic-inbound-dependency-load-by-quarter`
   - Parameter: `pi=Q42025`

2. **Outbound Dependencies**:
   - Endpoint: `/api/v1/issues/epic-outbound-dependency-metrics-by-quarter`
   - Parameter: `pi=Q42025`

Both endpoints use the same parameter format: `pi` as a query parameter with the value in format `"Q{quarter}{year}"` (e.g., `"Q42025"` for Q4 2025).


