# Plan: Generic Prompt Fetching with Error Handling

## Current State Analysis

### Issue 1: No Error Handling
All three job processors silently continue if prompt is not found:
- `job_daily_agent.py`: Sets `prompt_text = None`, continues processing
- `job_pi_sync.py`: Sets `prompt_text = None`, continues processing  
- `job_sprint_goal.py`: Sets `prompt_text = None`, continues processing

### Issue 2: Inconsistent Behavior
- **Daily Agent**: Tries URL-encoded ("Daily%20Insights"), then falls back to space ("Daily Insights")
- **Sprint Goal**: Tries URL-encoded ("Sprint%20Goal"), then falls back to space ("Sprint Goal")
- **PI Sync**: Only tries once ("PISync"), no fallback

### Issue 3: No Logging
- No alert/warning logged when prompt not found
- No clear indication in logs that prompt is missing

### Issue 4: Job Continues Without Prompt
- Jobs process even when prompt is missing
- LLM gets incomplete input (no instructions)

---

## Proposed Solution

### Create Generic Function: `get_prompt_with_error_check()`

**Location**: Add to `utils_processing.py` or create new `prompt_utils.py`

**Function Signature**:
```python
def get_prompt_with_error_check(
    client: APIClient,
    email_address: str,
    prompt_name: str,
    job_type: str,
    job_id: int | None = None
) -> Tuple[str | None, str | None]:
    """
    Fetch prompt from backend with error handling.
    
    Args:
        client: APIClient instance
        email_address: Email address for prompt (e.g., "DailyAgent", "PIAgent")
        prompt_name: Name of prompt (e.g., "Daily Insights", "PI Sync")
        job_type: Job type for error messages (e.g., "Daily Agent")
        job_id: Optional job ID for logging
    
    Returns:
        Tuple of (prompt_text, error_message):
        - If success: (prompt_text, None)
        - If failure: (None, error_message)
    
    Behavior:
        - Tries URL-encoded prompt name first
        - Falls back to space-separated prompt name if 404
        - Logs alert emoji (🚨) if prompt not found
        - Returns error message suitable for job failure
    """
```

### Implementation Details

**Error Handling**:
1. Try URL-encoded prompt name (e.g., "Daily%20Insights")
2. If 404, try space-separated (e.g., "Daily Insights")
3. If still 404 or other error:
   - Log: `🚨 PROMPT NOT FOUND: {prompt_name} for {email_address}`
   - Return: `(None, "Prompt '{prompt_name}' not found for {email_address}")`
4. If status != 200 (other errors):
   - Log: `🚨 ERROR FETCHING PROMPT: {prompt_name} - Status {status_code}`
   - Return: `(None, "Failed to fetch prompt '{prompt_name}': HTTP {status_code}")`
5. If response missing `prompt_description`:
   - Log: `🚨 PROMPT RESPONSE INVALID: {prompt_name} - Missing prompt_description`
   - Return: `(None, "Prompt '{prompt_name}' response missing prompt_description")`

**Success Case**:
- Log: `✅ Prompt fetched: {prompt_name} ({len(prompt_text)} chars)`
- Return: `(prompt_text, None)`

---

## Implementation Steps

### Step 1: Create Generic Function
- [ ] Add `get_prompt_with_error_check()` to `utils_processing.py`
- [ ] Implement URL-encoded fallback logic
- [ ] Add alert emoji logging (🚨)
- [ ] Add success logging (✅)
- [ ] Return proper error messages

### Step 2: Update Daily Agent
- [ ] Replace inline prompt fetching with `get_prompt_with_error_check()`
- [ ] Check for error and fail job early if prompt missing
- [ ] Remove duplicate URL-encoded fallback logic (handled in function)

### Step 3: Update PI Sync
- [ ] Replace inline prompt fetching with `get_prompt_with_error_check()`
- [ ] Check for error and fail job early if prompt missing
- [ ] Add fallback support (function handles it)

### Step 4: Update Sprint Goal
- [ ] Replace inline prompt fetching with `get_prompt_with_error_check()`
- [ ] Check for error and fail job early if prompt missing
- [ ] Remove duplicate URL-encoded fallback logic (handled in function)

### Step 5: Testing
- [ ] Test with valid prompt
- [ ] Test with missing prompt (should fail job with error)
- [ ] Test with invalid email_address (should fail job with error)
- [ ] Verify alert emoji appears in logs
- [ ] Verify job status set to "error" when prompt missing

---

## Code Changes Preview

### Before (Current):
```python
# Prompt Daily Insights
prompt_text = None
sc, pdata = client.get_prompt("DailyAgent", "Daily%20Insights")
if sc == 404:
    sc, pdata = client.get_prompt("DailyAgent", "Daily Insights")
if sc == 200 and isinstance(pdata, dict):
    prompt_text = (pdata.get("data") or {}).get("prompt_description") or pdata.get("prompt_description")

# Build formatted input - continues even if prompt_text is None!
formatted = _format_daily_input(transcript_obj, burndown_obj, prompt_text, team_name)
```

### After (Proposed):
```python
# Fetch prompt with error checking
prompt_text, prompt_error = get_prompt_with_error_check(
    client=client,
    email_address="DailyAgent",
    prompt_name="Daily Insights",
    job_type="Daily Agent",
    job_id=job_id
)

if prompt_error:
    return False, prompt_error

# Build formatted input - prompt_text is guaranteed to be not None
formatted = _format_daily_input(transcript_obj, burndown_obj, prompt_text, team_name)
```

---

## Error Message Examples

### Missing Prompt:
```
🚨 PROMPT NOT FOUND: Daily Insights for DailyAgent
```

Job fails with:
```
"Prompt 'Daily Insights' not found for DailyAgent"
```

### HTTP Error:
```
🚨 ERROR FETCHING PROMPT: Daily Insights - Status 500
```

Job fails with:
```
"Failed to fetch prompt 'Daily Insights': HTTP 500"
```

### Invalid Response:
```
🚨 PROMPT RESPONSE INVALID: Daily Insights - Missing prompt_description
```

Job fails with:
```
"Prompt 'Daily Insights' response missing prompt_description"
```

---

## Benefits

1. **Consistency**: All job processors use same logic
2. **Early Failure**: Jobs fail immediately if prompt missing (no wasted LLM calls)
3. **Clear Logging**: Alert emoji makes missing prompts obvious in logs
4. **Reusable**: Single function handles all prompt fetching
5. **Maintainable**: Change prompt fetching logic in one place
6. **Better Errors**: Clear error messages help debugging

---

## Questions

1. **Should we keep the URL-encoded fallback?**
   - Current: Daily Agent and Sprint Goal try both
   - Option: Keep it for backward compatibility
   - Recommendation: ✅ Yes, keep it in the generic function

2. **Error message format?**
   - Current plan: Simple and clear
   - Should include job_id in error message?
   - Recommendation: Keep simple, job_id already in context

3. **Should we add retry logic?**
   - Current: No retries
   - Option: Retry transient errors (503, 500)
   - Recommendation: ❌ No, keep it simple for now

---

## Files to Modify

1. `utils_processing.py` - Add `get_prompt_with_error_check()` function
2. `job_daily_agent.py` - Replace prompt fetching
3. `job_pi_sync.py` - Replace prompt fetching
4. `job_sprint_goal.py` - Replace prompt fetching

---

## Next Steps

1. Review and approve this plan
2. Implement Step 1 (create function)
3. Implement Steps 2-4 (update job processors)
4. Test and verify
5. Commit changes

