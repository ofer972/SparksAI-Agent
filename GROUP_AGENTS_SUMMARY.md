# Group Agents Implementation - Quick Summary

## What We're Building
Two new Group-level agents:
1. **Group Sprint Flow** - Analyzes sprint flow metrics for a group
2. **Group Sprint Predictability** - Analyzes sprint predictability for a group

## Frontend Changes (This Repository)
- ✅ Create 2 new agent files (`job_group_sprint_flow.py`, `job_group_sprint_predictability.py`)
- ✅ Add job types to `config.py`
- ✅ Add routes to `job_router.py`
- ✅ Update `utils_llm_processing_and_extraction.py` to support Group card type with `group_name`
- ⚠️ May need to update `api_client.py` if backend has separate Group card endpoints
- ⚠️ May need group data fetching functions in `utils_data_fetching.py`

## Backend Changes Required ⚠️

### CRITICAL - Must Verify Before Coding:

1. **AI Card Creation**
   - Does backend accept `group_name` when creating AI cards?
   - Is there a `/api/v1/group-ai-cards` endpoint OR does `/api/v1/team-ai-cards` accept `group_name`?

2. **Sprint Flow Data**
   - Does backend have endpoint for group-level sprint flow metrics?
   - Endpoint URL: `/api/v1/sprints/sprint-flow?group_name={group}` OR similar?

3. **Sprint Predictability Data**
   - Does `/api/v1/sprints/sprint-predictability` support `group_name` parameter?
   - Or does it need `is_group=true&group_name={group}`?

4. **Prompts**
   - Are prompts configured for "Group Sprint Flow" and "Group Sprint Predictability"?
   - Email address: `GroupAgent` or similar?

## Database Status ✅
- ✅ `group_name` column exists in agent jobs table (confirmed)
- ✅ `group_name` column exists in AI summary/insight table (confirmed)

## Action Items
1. **Review detailed plan**: `IMPLEMENTATION_PLAN_GROUP_AGENTS.md`
2. **Verify backend endpoints** (see Backend Changes above)
3. **Approve plan** before code changes
4. **Implement** once backend is confirmed

## Estimated Complexity
- **Frontend**: Medium (follows existing patterns)
- **Backend**: Low-Medium (depends on existing endpoint support)

