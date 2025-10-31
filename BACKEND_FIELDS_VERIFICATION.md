# Backend Fields Verification: `information_json` and `full_information`

## Current Status

### ✅ Client-Side Implementation (COMPLETE)
The agent code is **sending** these fields in API requests:

**For Team AI Cards (`/api/v1/team-ai-cards`):**
- ✅ `description` - Extracted section or full response
- ✅ `full_information` - Text content before JSON (up to 2000 chars)
- ✅ `information_json` - DashboardSummary JSON (if extracted)

**For PI AI Cards (`/api/v1/pi-ai-cards`):**
- ✅ `description` - Extracted section or full response
- ✅ `full_information` - Text content before JSON (up to 2000 chars)
- ✅ `information_json` - DashboardSummary JSON (if extracted)

**For Recommendations (`/api/v1/recommendations`):**
- ✅ `action_text` - Recommendation text
- ✅ `rational` - Recommendation header/rationale (from JSON)
- ✅ `full_information` - Text content before JSON (up to 2000 chars)
- ✅ `information_json` - Individual recommendation JSON object (as string)

### ✅ Old System (PROVEN)
The old DailyAgent system **definitely saved** these fields directly to database:

**Database Schema (from `DailyAgent/database.py`):**

```sql
-- team_ai_summary_cards table
INSERT INTO public.team_ai_summary_cards 
(date, team_name, card_name, card_type, priority, source, 
 description, full_information, source_job_id, information_json, ...)
VALUES 
(..., :description, :full_information, :source_job_id, :information_json, ...)

-- recommendations table
INSERT INTO public.recommendations 
(team_name, date, action_text, rational, priority, status, 
 full_information, information_json, ...)
VALUES 
(..., :action_text, :rational, :priority, :status, :full_information, :information_json, ...)

-- ai_cards table (for PI cards)
INSERT INTO public.ai_cards 
(date, team_name, pi, card_name, card_type, priority, source, 
 description, full_information, source_job_id, information_json, ...)
VALUES 
(..., :description, :full_information, :source_job_id, :information_json, ...)
```

### ❓ Backend API Verification Needed

**We need to verify** that the backend REST API endpoints accept and save these fields:

1. **`POST /api/v1/team-ai-cards`** - Does it accept `full_information` and `information_json`?
2. **`PATCH /api/v1/team-ai-cards/{id}`** - Does it accept `full_information` and `information_json`?
3. **`POST /api/v1/pi-ai-cards`** - Does it accept `full_information` and `information_json`?
4. **`PATCH /api/v1/pi-ai-cards/{id}`** - Does it accept `full_information` and `information_json`?
5. **`POST /api/v1/recommendations`** - Does it accept `full_information` and `information_json`?

## What to Check

### Option 1: Test the API
Send a test request with these fields and check:
1. Does the endpoint return success (200/201)?
2. Does the saved record contain these fields?
3. Check the database directly to verify fields are stored

### Option 2: Check Backend Code
Look at the backend API route handlers for:
- Field validation/schema
- Database save operations
- Whether `full_information` and `information_json` are included in the model/schema

### Option 3: Check Database Schema
Verify the database tables have these columns:
```sql
-- Check team_ai_summary_cards table
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'team_ai_summary_cards' 
  AND column_name IN ('full_information', 'information_json');

-- Check recommendations table
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'recommendations' 
  AND column_name IN ('full_information', 'information_json');

-- Check ai_cards table (for PI cards)
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'ai_cards' 
  AND column_name IN ('full_information', 'information_json');
```

## If Backend Doesn't Support These Fields

If the backend endpoints **don't** accept these fields, you'll need to:

1. **Update Backend API Models/Schemas** to include:
   - `full_information` (text/varchar)
   - `information_json` (text/jsonb)

2. **Update Database Save Operations** to persist these fields

3. **Update API Documentation** to reflect these new fields

## Testing Recommendation

Create a test script to verify:

```python
from api_client import APIClient

client = APIClient()

# Test Team AI Card
test_card = {
    "team_name": "TestTeam",
    "card_name": "Test Card",
    "card_type": "Test",
    "description": "Test description",
    "full_information": "Test full info",
    "information_json": '{"test": "json"}',
    "date": "2024-01-01",
    "priority": "High",
    "source": "Test",
}

sc, resp = client.create_team_ai_card(test_card)
print(f"Status: {sc}, Response: {resp}")

# Then check if the saved record has these fields
sc, cards = client.list_team_ai_cards()
# Look for the test card and verify fields
```

## Summary

- ✅ **Client sends** `full_information` and `information_json`
- ✅ **Database schema supports** these fields (proven by old system)
- ❓ **Backend API** - needs verification
- ⚠️ **If backend doesn't support**: Fields will be silently ignored or cause errors

