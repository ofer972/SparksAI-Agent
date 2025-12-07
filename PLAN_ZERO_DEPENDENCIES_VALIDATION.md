# Plan: Zero Dependencies Validation for PI and Group Dependencies

## Overview
Add validation to check if dependencies data is empty before calling LLM. If either inbound or outbound dependencies return zero items, skip LLM processing and fail the job with appropriate logging.

## Short Summary
- **Change**: Add validation after fetching dependencies
- **Check**: If inbound OR outbound dependencies have zero items
- **Action**: Skip LLM call, log warning, fail job
- **Affected Files**: 
  - `job_pi_dependencies.py`
  - `job_group_dependencies.py`
  - `utils_data_fetching.py` (optional - return count info)

## Detailed Plan

### Option 1: Check in Data Fetching Functions (Recommended)
Modify the data fetching functions to return dependency counts along with formatted strings.

#### Changes to `utils_data_fetching.py`:

**1. Modify `get_pi_dependencies_for_analysis()`:**
- Change return type from `Tuple[str, str]` to `Tuple[str, str, int, int]`
- Return: `(inbound_formatted, outbound_formatted, inbound_count, outbound_count)`
- Extract count from response data before formatting

**2. Modify `get_group_dependencies_for_analysis()`:**
- Change return type from `Tuple[str, str]` to `Tuple[str, str, int, int]`
- Return: `(inbound_formatted, outbound_formatted, inbound_count, outbound_count)`
- Extract count from response data before formatting

#### Changes to `job_pi_dependencies.py`:

**After line 107** (after calling `get_pi_dependencies_for_analysis`):
- Unpack 4 values instead of 2: `inbound_formatted, outbound_formatted, inbound_count, outbound_count = ...`
- Add validation:
  ```python
  if inbound_count == 0 or outbound_count == 0:
      error_msg = f"No dependencies found: inbound={inbound_count}, outbound={outbound_count}"
      print(f"❌ {error_msg}")
      return False, error_msg
  ```

#### Changes to `job_group_dependencies.py`:

**After line 67** (after calling `get_group_dependencies_for_analysis`):
- Unpack 4 values instead of 2: `inbound_formatted, outbound_formatted, inbound_count, outbound_count = ...`
- Add validation:
  ```python
  if inbound_count == 0 or outbound_count == 0:
      error_msg = f"No dependencies found: inbound={inbound_count}, outbound={outbound_count}"
      print(f"❌ {error_msg}")
      return False, error_msg
  ```

### Option 2: Check in Agent Files Only (Simpler)
Keep data fetching functions unchanged, check counts in agent files after receiving formatted strings.

#### Changes to `job_pi_dependencies.py`:

**After line 107**:
- Check if formatted strings indicate no data:
  ```python
  if "No inbound dependency data found" in inbound_formatted or "No outbound dependency data found" in outbound_formatted:
      print(f"❌ No dependencies found - skipping LLM call")
      return False, "No dependencies found: cannot analyze empty dependency data"
  ```

#### Changes to `job_group_dependencies.py`:

**After line 67**:
- Same check as above

**Note**: This option is less precise as it relies on string matching.

## Recommended Approach: Option 1

**Advantages:**
- More precise (actual counts)
- Better error messages
- Cleaner separation of concerns
- Easier to test

**Disadvantages:**
- Requires changing function signatures
- Need to update return type in `utils_processing.py` exports

## Implementation Steps (Option 1)

1. **Modify `utils_data_fetching.py`**:
   - Update `get_pi_dependencies_for_analysis()` to return counts
   - Update `get_group_dependencies_for_analysis()` to return counts

2. **Modify `job_pi_dependencies.py`**:
   - Update unpacking to receive 4 values
   - Add validation check after dependencies fetch
   - Return early if zero dependencies

3. **Modify `job_group_dependencies.py`**:
   - Update unpacking to receive 4 values
   - Add validation check after dependencies fetch
   - Return early if zero dependencies

4. **Update `utils_processing.py`** (if needed):
   - Update function signatures in exports if type hints are exported

## Error Message Format

```
❌ No dependencies found: inbound=0, outbound=5
```

or

```
❌ No dependencies found: inbound=3, outbound=0
```

or

```
❌ No dependencies found: inbound=0, outbound=0
```

## Files to Modify

1. `utils_data_fetching.py` - 2 functions (return counts)
2. `job_pi_dependencies.py` - Add validation
3. `job_group_dependencies.py` - Add validation
4. `utils_processing.py` - Update exports if needed

## Testing Considerations

- Test with zero inbound dependencies
- Test with zero outbound dependencies
- Test with both zero
- Test with both non-zero (normal flow)
- Verify job status is set to "error" or "failed"
- Verify LLM is not called when dependencies are zero

