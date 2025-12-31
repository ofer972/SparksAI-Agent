# Short Summary: PI Jobs Team/Group Parameters

## ✅ Backend Verification Complete

**All backend endpoints already support `team_name` and `isGroup` parameters!**

Verified by checking actual backend code in `SparksAI-backend/`:
- `pis_service.py` - All PI endpoints support both parameters
- `issues_service.py` - All dependency/epic endpoints support both parameters

## ❌ Client Code Needs Updates

The following client methods in `api_client.py` need to be updated:

1. **`get_pi_summary_today()`** - Add `is_group` parameter
2. **`get_pi_burndown()`** - Add `is_group` parameter  
3. **`get_pi_status_for_today_by_team()`** - Add `team_name` and `is_group` parameters
4. **`get_epics_by_pi()`** - Add `team_name` and `is_group` parameters
5. **`get_epic_inbound_dependency_load_by_quarter()`** - Add `team_name` and `is_group` parameters
6. **`get_epic_outbound_dependency_metrics_by_quarter()`** - Add `team_name` and `is_group` parameters

## 📋 Job Files Need Updates

All three PI job files need to:
1. Extract `team_name` or `group_name` from job payload
2. Determine `is_group` flag (true if `group_name` exists)
3. Pass these parameters to all data fetching functions

**Jobs to update:**
- `job_pi_sync.py`
- `job_pi_dependencies.py`
- `job_pi_planning_gaps.py`

## ✅ No Backend Changes Required

All endpoints are ready - only client code updates needed!

