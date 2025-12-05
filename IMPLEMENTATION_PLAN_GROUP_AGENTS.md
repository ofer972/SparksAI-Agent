# Implementation Plan: Group Sprint Flow & Group Sprint Predictability Agents

## Overview
This plan outlines the implementation of two new Group-level agents:
1. **Group Sprint Flow** - Analyzes sprint flow metrics at the group level
2. **Group Sprint Predictability** - Analyzes sprint predictability metrics at the group level

## Current State Analysis

### Existing Architecture
- **Agent Structure**: Each agent has a `job_*.py` file with a `process()` function
- **Job Routing**: Jobs are routed via `job_router.py` based on `job_type`
- **Configuration**: Job types are defined in `config.py` in the `JOB_TYPES` list
- **Insight Storage**: Insights are saved using `process_llm_response_and_save_ai_card()` which currently supports:
  - `card_type="PI"` → Uses `/api/v1/pi-ai-cards` endpoint
  - `card_type="Team"` → Uses `/api/v1/team-ai-cards` endpoint
- **Database**: User confirmed that `group_name` column exists in:
  - Agent jobs table
  - AI summary/insight table

### Existing Similar Agents
- **Team Retro Topics** (`job_team_retro_topics.py`): Uses sprint predictability data at team level
- **Sprint Goal** (`job_sprint_goal.py`): Uses sprint issues and flow data at team level
- **Team PI Insight** (`job_team_pi_insight.py`): Creates Team-level insights

## Required Changes

### 1. Frontend/Agent Code Changes (This Repository)

#### 1.1 Create New Agent Files
- **File**: `job_group_sprint_flow.py`
  - Similar structure to `job_team_retro_topics.py` or `job_sprint_goal.py`
  - Extract `group_name` from job payload
  - Fetch group-level sprint flow data (needs backend endpoint)
  - Process with LLM
  - Save as Group AI card with `group_name`

- **File**: `job_group_sprint_predictability.py`
  - Similar structure to `job_team_retro_topics.py`
  - Extract `group_name` from job payload
  - Fetch group-level sprint predictability data (may use existing endpoint with `is_group=True`)
  - Process with LLM
  - Save as Group AI card with `group_name`

#### 1.2 Update Configuration
- **File**: `config.py`
  - Add `"Group Sprint Flow"` to `JOB_TYPES` list
  - Add `"Group Sprint Predictability"` to `JOB_TYPES` list

#### 1.3 Update Job Router
- **File**: `job_router.py`
  - Add routing for `"Group Sprint Flow"` → `job_group_sprint_flow.process(job)`
  - Add routing for `"Group Sprint Predictability"` → `job_group_sprint_predictability.process(job)`

#### 1.4 Update LLM Processing Function
- **File**: `utils_llm_processing_and_extraction.py`
  - Modify `process_llm_response_and_save_ai_card()` function to:
    - Accept `group_name` parameter (in addition to `team_name`)
    - Support `card_type="Group"` (new card type)
    - Add `group_name` to card payload when creating/updating cards
    - Use new `/api/v1/group-ai-cards` endpoint (if backend provides it)
    - OR use existing endpoint with `group_name` field

#### 1.5 Update API Client (if needed)
- **File**: `api_client.py`
  - Add `create_group_ai_card()` method (if backend provides separate endpoint)
  - Add `list_group_ai_cards()` method (for upsert logic)
  - Add `patch_group_ai_card()` method (for upsert logic)
  - OR verify existing endpoints accept `group_name` parameter

#### 1.6 Add Group Data Fetching Functions (if needed)
- **File**: `utils_data_fetching.py`
  - Add `get_group_sprint_flow_for_analysis()` function
    - Fetches group-level sprint flow metrics
    - Formats for LLM analysis
  - Add `get_group_sprint_predictability_for_analysis()` function
    - May use existing `get_sprint_predictability()` with `is_group=True` or `group_name` parameter
    - Formats for LLM analysis

### 2. Backend Changes Required

#### 2.1 API Endpoints Verification/Implementation

**CRITICAL - Need Backend Confirmation:**

1. **Group AI Cards Endpoint**
   - **Option A**: New endpoint `/api/v1/group-ai-cards` (similar to `/api/v1/team-ai-cards`)
     - `POST /api/v1/group-ai-cards` - Create group AI card
     - `GET /api/v1/group-ai-cards` - List group AI cards
     - `PATCH /api/v1/group-ai-cards/{id}` - Update group AI card
   - **Option B**: Extend existing `/api/v1/team-ai-cards` to accept `group_name` field
     - Cards with `group_name` set are treated as Group cards
     - Cards with `group_name` null/empty are treated as Team cards

2. **Group Sprint Flow Data Endpoint**
   - **Need**: Endpoint to fetch sprint flow metrics aggregated at group level
   - **Possible**: `/api/v1/sprints/sprint-flow?group_name={group_name}`
   - **Or**: `/api/v1/group-metrics/sprint-flow?group_name={group_name}`
   - **Data needed**: Sprint flow metrics (cycle time, lead time, throughput, etc.) for all teams in the group

3. **Group Sprint Predictability Data Endpoint**
   - **May already exist**: `/api/v1/sprints/sprint-predictability` with `group_name` parameter
   - **Or**: `/api/v1/sprints/sprint-predictability?is_group=true&group_name={group_name}`
   - **Verify**: Does existing endpoint support group-level aggregation?

#### 2.2 Database Schema Verification

**Already Confirmed by User:**
- ✅ `group_name` column exists in agent jobs table
- ✅ `group_name` column exists in AI summary/insight table

**Need to Verify:**
- Does the backend API accept `group_name` when creating/updating AI cards?
- Are there any constraints or indexes on `group_name`?
- Is there a separate `group_ai_cards` table or is it the same as `team_ai_cards`?

#### 2.3 Prompt Configuration

**Backend needs to have prompts configured:**
- Prompt for "Group Sprint Flow" agent
  - Email: `GroupAgent` (or similar)
  - Prompt Name: `"Group Sprint Flow"`
- Prompt for "Group Sprint Predictability" agent
  - Email: `GroupAgent` (or similar)
  - Prompt Name: `"Group Sprint Predictability"`

## Implementation Steps

### Phase 1: Backend Verification (REQUIRED BEFORE CODING)
1. ✅ Verify `group_name` column exists in database tables (confirmed by user)
2. ⚠️ **Verify backend API supports group_name in AI card creation**
3. ⚠️ **Verify/implement group-level sprint flow endpoint**
4. ⚠️ **Verify/implement group-level sprint predictability endpoint**
5. ⚠️ **Verify/configure prompts in backend**

### Phase 2: Agent Code Implementation
1. Update `utils_llm_processing_and_extraction.py` to support Group card type
2. Update `api_client.py` with Group card endpoints (if separate endpoint)
3. Create `job_group_sprint_flow.py`
4. Create `job_group_sprint_predictability.py`
5. Update `config.py` with new job types
6. Update `job_router.py` with new routes
7. Add data fetching functions in `utils_data_fetching.py` (if needed)

### Phase 3: Testing
1. Test job creation with `group_name` in payload
2. Test data fetching for group-level metrics
3. Test LLM processing and card creation with `group_name`
4. Verify insights are saved with correct `group_name`

## Backend Action Items

### ⚠️ CRITICAL - Must Verify Before Implementation:

1. **AI Card Creation**
   - [ ] Does `/api/v1/team-ai-cards` endpoint accept `group_name` field?
   - [ ] OR does backend need new `/api/v1/group-ai-cards` endpoint?
   - [ ] What is the expected request/response format?

2. **Sprint Flow Data**
   - [ ] Does backend have endpoint for group-level sprint flow metrics?
   - [ ] What is the endpoint URL and parameters?
   - [ ] What data structure is returned?

3. **Sprint Predictability Data**
   - [ ] Does `/api/v1/sprints/sprint-predictability` support `group_name` parameter?
   - [ ] OR does it support `is_group=true` with `group_name`?
   - [ ] What is the expected response format for group-level data?

4. **Prompts**
   - [ ] Are prompts configured in backend for:
     - "Group Sprint Flow" (email: `GroupAgent` or similar)
     - "Group Sprint Predictability" (email: `GroupAgent` or similar)

## Summary

### Code Changes Required (Frontend)
- ✅ **2 new agent files** (`job_group_sprint_flow.py`, `job_group_sprint_predictability.py`)
- ✅ **1 config update** (`config.py` - add job types)
- ✅ **1 router update** (`job_router.py` - add routes)
- ✅ **1 utility update** (`utils_llm_processing_and_extraction.py` - support Group cards)
- ⚠️ **1 API client update** (`api_client.py` - may need Group card endpoints)
- ⚠️ **1 data fetching update** (`utils_data_fetching.py` - may need group data functions)

### Backend Changes Required
- ⚠️ **AI Card Endpoint**: Verify/implement group AI card creation endpoint
- ⚠️ **Sprint Flow Endpoint**: Verify/implement group-level sprint flow data endpoint
- ⚠️ **Sprint Predictability Endpoint**: Verify group-level support in existing endpoint
- ⚠️ **Prompts**: Configure prompts for both new agents

### Risk Assessment
- **Low Risk**: Database schema already supports `group_name`
- **Medium Risk**: Backend API endpoints may need updates
- **Low Risk**: Agent code structure is well-established pattern

## Next Steps
1. **Review this plan** and approve
2. **Verify backend endpoints** (see Backend Action Items above)
3. **Once backend is confirmed**, proceed with agent code implementation
4. **Test end-to-end** with real group data

