# Group Dependencies Agent - Quick Summary

## What We're Building
A new **Group Dependencies** agent that analyzes dependencies at the group level, using the same logic as PI Dependencies but filtered by group.

## Key Points

### Agent Details
- **Job Type**: `"Group Dependencies"`
- **Insight Type**: `"Group Dependencies"`
- **Logic**: Identical to PI Dependencies (inbound/outbound dependencies)

### Key Differences from PI Dependencies
1. **Endpoints**: Include `team_name` (as group_name) and `is_group=true` parameters
2. **Card Type**: Saves as Team AI card with `group_name` (not PI card)
3. **Recommendations**: Uses `group_name` instead of PI name
4. **Prompt**: Uses `GroupAgent` email address

### Files to Create
- `job_group_dependencies.py` (new agent file)

### Files to Modify
1. `api_client.py` - Add 2 new API methods with group filtering
2. `utils_data_fetching.py` - Add `get_group_dependencies_for_analysis()` function
3. `config.py` - Add `"Group Dependencies"` to JOB_TYPES
4. `job_router.py` - Add import and route

### Backend Requirements
- Endpoints must accept `team_name` and `is_group` parameters
- Prompt must exist: `GroupAgent` / `Group Dependencies`

### Pattern to Follow
- **Dependency Logic**: Copy from `job_pi_dependencies.py`
- **Group Card Saving**: Follow `job_group_sprint_predictability.py` pattern
- **Recommendations**: Use `group_name` like Group Sprint Predictability

## Implementation Steps
1. Add API client methods (with group parameters)
2. Add data fetching function
3. Create agent file
4. Update config and router
5. Test end-to-end

