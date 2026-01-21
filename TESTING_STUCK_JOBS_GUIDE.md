# User Testing Guide: Stuck Jobs & Mid-Processing Failures

## Overview
This guide helps you test scenarios where jobs get stuck or fail in the middle of processing.

---

## 🔴 Critical Failure Points to Test

### 1. **Agent Crash During Processing**
**Scenario**: Agent process is killed/crashes while processing a job

**How to Test:**
1. Create a job via backend API
2. Wait for agent to claim it (check logs: `🎯 job_id=X`)
3. **Kill the agent process** (Ctrl+C, kill -9, or stop Railway deployment)
4. **Verify**:
   - Job status in database: Should be `claimed` or `pending` (not `completed` or `error`)
   - Check if job can be reclaimed after agent restarts
   - Check if `input_sent` was partially updated

**Expected Behavior:**
- Job should remain in `claimed` state
- After agent restart, backend should allow reclaiming (or have timeout mechanism)
- Partial `input_sent` updates should be visible

---

### 2. **Backend Unavailable During Data Fetching**
**Scenario**: Backend goes down while agent is fetching data (transcripts, PI status, etc.)

**How to Test:**
1. Start agent processing a job
2. **Stop backend server** during data fetching phase
3. **Verify**:
   - Agent retries with exponential backoff (check logs for `🌐 Backend unreachable`)
   - Job remains claimed
   - Agent eventually times out or continues when backend recovers

**Expected Behavior:**
- `wait_for_backend()` should retry with exponential backoff (2s → 4s → 8s → ... up to 300s cap)
- Job should not be marked as error until all retries exhausted
- Agent should continue processing when backend recovers

---

### 3. **LLM Call Failure (Single-Step Mode)**
**Scenario**: LLM endpoint returns error or times out

**How to Test:**
1. Create a job that uses single-step LLM (no `-1` prompt)
2. **Simulate LLM failure**:
   - Stop LLM service
   - Return 500 error from LLM endpoint
   - Timeout LLM call (set `LLM_TIMEOUT_SECONDS` very low)
3. **Verify**:
   - Job marked as `error` status
   - Error message saved in job `error` field
   - Audit service called with failure status
   - `input_sent` contains partial data

**Expected Behavior:**
- Job status: `error`
- Error message logged and saved
- Audit service records failure with tokens=0

---

### 4. **Two-Step LLM: First Step Succeeds, Second Step Fails**
**Scenario**: Two-step mode where first LLM call works but second fails

**How to Test:**
1. Create a job with active `-1` prompt (e.g., "PISync-1")
2. Let first LLM call succeed
3. **Kill LLM service** or return error during second call
4. **Verify**:
   - First call response is logged
   - Second call failure is logged
   - Job marked as `error`
   - `input_sent` contains both first and second prompts
   - Audit service records partial tokens from first call

**Expected Behavior:**
- Job status: `error`
- `input_sent` shows: `[data] + [prompt-1] + [first_response] + [prompt-2]`
- Audit service shows tokens from first call only

---

### 5. **Network Timeout During Job Update**
**Scenario**: Agent successfully processes job but can't update final status

**How to Test:**
1. Process a job successfully
2. **Stop backend** right before `patch_agent_job()` final update (line 139 in `agent.py`)
3. **Verify**:
   - Job processing completed (result generated)
   - Final status update failed (check logs: `⚠️ Final update failed`)
   - Job remains in `claimed` state
   - Result text not saved to database

**Expected Behavior:**
- Job status: `claimed` (not `completed`)
- Result text: Not saved
- Error: Logged but job not marked as error (since processing succeeded)

---

### 6. **Partial Data Collection Failure**
**Scenario**: Some data fetches succeed, others fail (e.g., transcript OK, PI status fails)

**How to Test:**
1. Create a PI Sync job
2. **Make one endpoint fail** (e.g., `/api/v1/pis/get-pi-status-for-today` returns 500)
3. **Verify**:
   - Agent continues with partial data
   - Missing data sections show error messages
   - LLM still called with available data
   - Job may succeed or fail depending on data criticality

**Expected Behavior:**
- Partial data sent to LLM
- Missing sections show: "Failed to fetch PI status: HTTP 500"
- Job may complete with degraded results

---

### 7. **Job Claimed But Never Processed**
**Scenario**: Agent claims job but crashes before calling `route_and_process()`

**How to Test:**
1. Create a job
2. **Kill agent** immediately after claiming (before line 132 in `agent.py`)
3. **Verify**:
   - Job status: `claimed`
   - `input_sent`: May contain initial timestamp or be empty
   - Job not processed

**Expected Behavior:**
- Job stuck in `claimed` state
- Backend should have timeout mechanism to release claimed jobs
- Or manual intervention needed to reset job

---

### 8. **Invalid Job Data**
**Scenario**: Job has missing required fields (e.g., no `pi` for PI Sync)

**How to Test:**
1. Create job with missing required field (e.g., `pi` field missing)
2. **Verify**:
   - Agent processes job
   - Returns early with error: `"Missing PI in job payload"`
   - Job marked as `error`
   - Error message saved

**Expected Behavior:**
- Job status: `error`
- Error: `"Missing PI in job payload"`
- No LLM call made

---

### 9. **Backend Returns Invalid Response Format**
**Scenario**: Backend returns unexpected JSON structure

**How to Test:**
1. Mock backend to return malformed response (e.g., `{ "unexpected": "format" }`)
2. **Verify**:
   - Agent handles gracefully
   - Logs warning: `⚠️ Unexpected next-pending response format`
   - Continues polling (doesn't crash)

**Expected Behavior:**
- Agent logs warning
- Skips invalid job
- Continues polling for next job

---

### 10. **Two-Step Mode: Prompt Fetching Fails**
**Scenario**: `-1` prompt exists but fetch fails, or `-2` prompt missing

**How to Test:**
1. Create job expecting two-step mode
2. **Make prompt fetch fail** (500 error or prompt not found)
3. **Verify**:
   - Falls back to single-step mode
   - Logs: `⚠️ FALLBACK MODE: {prompt}-1 not found, using '{prompt}'`
   - Job processes with single-step
   - If base prompt also fails, job marked as error

**Expected Behavior:**
- Falls back gracefully to single-step
- Job completes successfully
- If base prompt fails: job marked as error

---

## 🧪 Testing Tools & Methods

### Manual Testing Steps

1. **Create Test Job**:
   ```bash
   # Via backend API
   POST /api/v1/agent-jobs
   {
     "job_type": "PI Sync",
     "pi": "PI-2024-1",
     "team_name": "TestTeam"
   }
   ```

2. **Monitor Agent Logs**:
   - Watch for `🎯 job_id=X` (job claimed)
   - Watch for `✅ Job X completed` or `❌` errors
   - Check for `⚠️` warnings

3. **Check Job Status**:
   ```bash
   GET /api/v1/agent-jobs/{job_id}
   ```
   - Check `status`: `pending` → `claimed` → `completed`/`error`
   - Check `input_sent`: Should contain full prompt/data
   - Check `result` or `error` fields

4. **Simulate Failures**:
   - **Stop backend**: `docker stop backend` or kill process
   - **Stop LLM service**: Kill LLM endpoint
   - **Kill agent**: `kill -9 <pid>` or stop Railway deployment
   - **Network issues**: Use firewall rules or network throttling

### Automated Testing (Future)

Consider creating test scripts that:
- Create jobs programmatically
- Inject failures at specific points
- Verify job states and recovery
- Check audit service logs

---

## 📊 What to Verify After Each Test

### Job State Verification
- [ ] Job `status` field is correct (`pending`, `claimed`, `completed`, `error`)
- [ ] `input_sent` contains expected data (or is empty if failed early)
- [ ] `result` or `error` field contains appropriate message
- [ ] Timestamps are reasonable

### Agent Behavior Verification
- [ ] Agent logs show appropriate errors/warnings
- [ ] Agent doesn't crash (except when intentionally killed)
- [ ] Agent recovers and continues processing after failures
- [ ] Retry logic works (exponential backoff visible in logs)

### Data Integrity Verification
- [ ] No duplicate job processing
- [ ] Partial data doesn't corrupt results
- [ ] Audit service records match job outcomes
- [ ] Token counts are accurate (or 0 on failure)

---

## 🚨 Critical Scenarios Priority

**High Priority:**
1. Agent crash during processing (#1)
2. Backend unavailable during data fetch (#2)
3. LLM call failure (#3)
4. Final status update failure (#5)

**Medium Priority:**
5. Two-step LLM partial failure (#4)
6. Job claimed but never processed (#7)
7. Invalid job data (#8)

**Low Priority:**
8. Partial data collection (#6)
9. Invalid response format (#9)
10. Prompt fetching fallback (#10)

---

## 📝 Test Checklist Template

For each scenario, document:

```
Test: [Scenario Name]
Date: [Date]
Tester: [Name]

Steps:
1. [Step 1]
2. [Step 2]
3. [Step 3]

Expected:
- [Expected behavior 1]
- [Expected behavior 2]

Actual:
- [Actual behavior 1]
- [Actual behavior 2]

Result: ✅ Pass / ❌ Fail / ⚠️ Partial

Notes:
[Any observations or issues]
```

---

## 🔧 Debugging Tips

1. **Check Agent Logs**: Look for `🎯`, `✅`, `❌`, `⚠️` markers
2. **Check Backend Logs**: Verify API calls and responses
3. **Check Database**: Directly query job table for status
4. **Check Audit Service**: Verify LLM calls were recorded
5. **Use Job ID**: Track specific job through entire lifecycle

---

## ⚠️ Known Limitations

- **No automatic job recovery**: If agent crashes, jobs remain `claimed` until manual intervention or backend timeout
- **No partial result saving**: If final update fails, result is lost even though processing succeeded
- **No retry for final update**: If `patch_agent_job()` fails, agent doesn't retry

---

## 🎯 Success Criteria

A test passes if:
1. Agent handles failure gracefully (doesn't crash unexpectedly)
2. Job state accurately reflects what happened
3. Error messages are clear and actionable
4. Agent recovers and continues processing after transient failures
5. No data corruption or duplicate processing


