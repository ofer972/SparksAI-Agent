# Prompt Configuration Verification

## Comparison: Backend Table vs Code

### ✅ Matches Correctly

| Backend Table | Code | Status |
|--------------|------|--------|
| `GroupAgent` - `Group Sprint Flow` | `GroupAgent` - `Group Sprint Flow` | ✅ Match |
| `GroupAgent` - `Group Sprint Predictability` | `GroupAgent` - `Group Sprint Predictability` | ✅ Match |
| `PIAgent` - `PI Planning Gaps` | `PIAgent` - `PI Planning Gaps` | ✅ Match |
| `PIAgent` - `PI Dependencies` | `PIAgent` - `PI Dependencies` | ✅ Match |
| `PIAgent` - `PISync` | `PIAgent` - `PISync` | ✅ Match |
| `TeamAgent` - `Team PI Insights` | `TeamAgent` - `Team PI Insights` | ✅ Match |
| `TeamAgent` - `Team Retro Topics` | `TeamAgent` - `Team Retro Topics` | ✅ Match |
| `TeamAgent` - `Sprint Goal` | `TeamAgent` - `Sprint Goal` | ✅ Match |
| `TeamAgent` - `Daily Insights` | `TeamAgent` - `Daily Insights` | ✅ Match |

### ⚠️ Issue Found

| Backend Table | Code | Status |
|--------------|------|--------|
| `PIAgent` - `TeamPIInsight` | **NOT IN CODE** | ❌ **OLD ENTRY - Should be removed** |

## Summary

**Issue:** The backend table contains an **old/duplicate entry**:
- `PIAgent` - `TeamPIInsight` (old configuration)

This entry should be **removed from the backend** because:
1. We now use `TeamAgent` - `Team PI Insights` instead (which is correctly in the table)
2. The old `TeamPIInsight` prompt name is no longer used in the code
3. The old `PIAgent` email for this job type has been changed to `TeamAgent`

**Action Required:** Remove the duplicate/old entry `PIAgent` - `TeamPIInsight` from the backend prompt table.

## Final Expected Backend Table (9 entries)

1. `GroupAgent` - `Group Sprint Flow`
2. `GroupAgent` - `Group Sprint Predictability`
3. `PIAgent` - `PI Planning Gaps`
4. `PIAgent` - `PI Dependencies`
5. `PIAgent` - `PISync`
6. `TeamAgent` - `Team PI Insights`
7. `TeamAgent` - `Team Retro Topics`
8. `TeamAgent` - `Sprint Goal`
9. `TeamAgent` - `Daily Insights`

