# Prompt Configuration Mapping Table

## Current Mapping (After Standardization)

| Job Type | Email Address | Prompt Name | Status |
|----------|--------------|-------------|--------|
| Daily Progress | `TeamAgent` | `Daily Insights` | ✅ Updated |
| Sprint Goal | `TeamAgent` | `Sprint Goal` | ✅ Updated |
| PI Sync | `PIAgent` | `PISync` | ⚠️ No space in prompt name |
| Team PI Insight | `TeamAgent` | `Team PI Insights` | ✅ Updated (email + prompt) |
| Team Retro Topics | `TeamAgent` | `Team Retro Topics` | ✅ Updated |
| PI Dependencies | `PIAgent` | `PI Dependencies` | - |
| PI Planning Gaps | `PIAgent` | `PI Planning Gaps` | - |
| Group Sprint Flow | `GroupAgent` | `Group Sprint Flow` | - |
| Group Sprint Predictability | `GroupAgent` | `Group Sprint Predictability` | - |

## Changes Made

### Email Address Standardization
- ✅ **DailyAgent** → **TeamAgent** (for Daily Progress and Sprint Goal)
- ✅ **TeamRetroTopicsAgent** → **TeamAgent** (for Team Retro Topics)
- ✅ **PIAgent** → **TeamAgent** (for Team PI Insight)

### Prompt Name Updates
- ✅ **TeamPIInsight** → **Team PI Insights** (added space and plural "Insights")

## Remaining Inconsistencies

### Prompt Name Format
- `"PISync"` still has no space (should be `"PI Sync"`?)
- All other prompts use spaces consistently

## Email Address Pattern Summary
- **TeamAgent**: Used for all team-level jobs (Daily Progress, Sprint Goal, Team PI Insight, Team Retro Topics)
- **PIAgent**: Used for PI-level jobs (PI Sync, PI Dependencies, PI Planning Gaps)
- **GroupAgent**: Used for group-level jobs (Group Sprint Flow, Group Sprint Predictability)

