# Migration Plan: Implementing Old DailyAgent Result Handling Logic

## Executive Summary
The old DailyAgent had sophisticated logic for parsing LLM responses and storing structured data. This plan outlines how to implement the same logic in the new SparksAI-Agent system.

---

## Key Differences Between Old and New Systems

### Old DailyAgent System (Direct DB Access)
- **Structured Extraction**: Extracted specific sections from LLM responses using markers
- **JSON Parsing**: Separated JSON from text, extracted DashboardSummary and Recommendations separately
- **Database Storage**: 
  - Stored `description` (extracted section), `full_information` (text before JSON), `information_json` (parsed JSON)
  - Used UPSERT logic based on date/team_name/card_name
- **Recommendations**: Parsed from JSON structure with `header` and `text` fields

### Current SparksAI-Agent System (REST API)
- **Simple Extraction**: Just uses full LLM response, truncated to 2000 chars
- **No JSON Parsing**: Stores entire response as description
- **Database Storage**: 
  - Only stores description (full response truncated)
  - No separation of text vs JSON
- **Recommendations**: Simple text parsing from unstructured response

---

## Detailed Analysis of Old System Logic

### 1. LLM Response Processing Flow (Old System)

#### Step 1: Extract Text and JSON Separately
**Function**: `extract_text_and_json(llm_response)`
- **Purpose**: Separates text content from JSON in LLM response
- **Logic**:
  1. Looks for `BEGIN_JSON`/`END_JSON` markers
  2. Falls back to markdown code fences (`` ```json`` or ``` ``` ````)
  3. Falls back to detecting JSON starting with `{` or `[`
  4. Returns tuple: `(text_before_json, dashboard_summary_json, recommendations_json)`

#### Step 2: Extract Specific Sections
**Function**: `extract_daily_progress_review(llm_response)`
- **Purpose**: Extract "Daily Progress Review" section between markers
- **Markers**: 
  - Start: `"dashboard summary"` (case-insensitive)
  - End: `"detailed analysis"` (case-insensitive)
- **Logic**: Finds markers, extracts content between them, skips empty lines

#### Step 3: Save Summary Card
**Function**: `save_summary_card()`
- **Fields stored**:
  - `description`: Extracted section content (e.g., "Daily Progress Review")
  - `full_information`: Text content BEFORE JSON (for full context)
  - `information_json`: Dashboard summary JSON array
- **Upsert Logic**: ON CONFLICT (date, team_name, card_name) DO UPDATE

#### Step 4: Extract Recommendations from JSON
**Function**: Processes recommendations_json
- **Structure**: JSON array of objects with `header` and `text` fields
- **Mapping**:
  - `header` → `rational` field in recommendations table
  - `text` → `action_text` field in recommendations table
- **Storage**: Each recommendation stored separately with full_information and information_json

---

## Implementation Plan

### Phase 1: Add Extraction Utilities (utils_processing.py)

#### 1.1 Add `extract_text_and_json()` function
```python
def extract_text_and_json(llm_response: str) -> Tuple[str, str, str]:
    """
    Extract and separate text from JSON in LLM response.
    Returns: (text_part, dashboard_summary_json, recommendations_json)
    """
    # Implementation from old system
```

**Logic to implement**:
- Look for BEGIN_JSON/END_JSON markers
- Try markdown code fences
- Try detecting JSON at start
- Extract Dashboard_Summary (with variations: Dashboard_Summary, Dashboard Summary, DashboardSummary)
- Extract Recommendations array

#### 1.2 Add `extract_content_between_markers()` function
```python
def extract_content_between_markers(
    llm_response: str, 
    start_marker: str, 
    end_marker: str
) -> str | None:
    """
    Extract content between two markers (case-insensitive).
    Returns None if start marker not found, empty string if end marker not found.
    """
```

**Logic**:
- Case-insensitive search for markers
- Extract content AFTER start marker
- Extract until BEFORE end marker
- Handle empty lines

#### 1.3 Add job-type-specific extractors
```python
def extract_daily_progress_review(llm_response: str) -> str | None:
    """Extract Daily Progress Review section"""
    return extract_content_between_markers(
        llm_response, 
        "dashboard summary", 
        "detailed analysis"
    )

def extract_pi_sync_review(llm_response: str) -> str | None:
    """Extract PI Sync Review section"""
    return extract_content_between_markers(
        llm_response, 
        "dashboard summary", 
        "detailed analysis"
    )
```

### Phase 2: Update Job Processors

#### 2.1 Update `job_daily_agent.py`

**Current Flow**:
```python
ok, llm_answer, _raw = call_llm_generic(...)
# Simple upsert with full response as description
card_payload = {"description": llm_answer[:2000], ...}
```

**New Flow**:
```python
ok, llm_answer, _raw = call_llm_generic(...)

# Extract structured content
full_information, dashboard_summary_json, recommendations_json = \
    extract_text_and_json(llm_answer)

# Extract Daily Progress Review section
daily_progress_content = extract_daily_progress_review(llm_answer)

# Save summary card with proper fields
card_payload = {
    "description": daily_progress_content or llm_answer[:2000],  # Fallback if extraction fails
    "full_information": full_information[:2000],  # Text before JSON
    "information_json": dashboard_summary_json,  # Dashboard summary JSON
    # ... other fields
}

# Extract and save recommendations from JSON
if recommendations_json:
    parsed_recs = json.loads(recommendations_json)
    for rec_obj in parsed_recs:
        if isinstance(rec_obj, dict) and 'header' in rec_obj and 'text' in rec_obj:
            rec_payload = {
                "action_text": rec_obj['text'],
                "rational": rec_obj['header'],  # Use header as rational
                "full_information": full_information[:2000],
                "information_json": json.dumps(rec_obj),
                # ... other fields
            }
            client.create_recommendation(rec_payload)
```

#### 2.2 Update `job_pi_sync.py`
- Similar structure to DailyAgent
- Use `extract_pi_sync_review()` for section extraction
- Same JSON parsing logic for recommendations

#### 2.3 Update `job_sprint_goal.py` (if needed)
- Check if it needs similar extraction logic
- May need sprint-goal-specific markers

### Phase 3: Update API Client (if needed)

**Current State**: API client methods exist for:
- `create_team_ai_card()` ✓
- `patch_team_ai_card()` ✓
- `list_team_ai_cards()` ✓
- `create_recommendation()` ✓

**Action**: Verify that these endpoints support:
- `full_information` field (text before JSON)
- `information_json` field (JSON data)

If not, document needed backend changes.

---

## Constants and Configuration

### Extraction Markers (Constants)
```python
# Add to utils_processing.py or config.py
class LLM_EXTRACTION_CONSTANTS:
    START_MARKER = "dashboard summary"
    END_MARKER = "detailed analysis"
    RECOMMENDATION_MARKER = "recommendation"
    MAX_RECOMMENDATIONS = 2
```

---

## Testing Strategy

### Unit Tests
1. Test `extract_text_and_json()` with:
   - BEGIN_JSON/END_JSON markers
   - Markdown code fences
   - JSON at start of response
   - No JSON in response
   - Invalid JSON

2. Test `extract_content_between_markers()` with:
   - Both markers present
   - Only start marker
   - No markers
   - Case-insensitive matching
   - Empty content

3. Test integration with:
   - Real LLM responses
   - Various response formats

### Integration Tests
1. End-to-end job processing
2. Verify database storage format
3. Verify upsert logic works correctly

---

## Migration Steps

### Step 1: Add Utility Functions
- [ ] Add `extract_text_and_json()` to `utils_processing.py`
- [ ] Add `extract_content_between_markers()` to `utils_processing.py`
- [ ] Add job-type-specific extractors

### Step 2: Update DailyAgent Job
- [ ] Update `job_daily_agent.py` to use structured extraction
- [ ] Update recommendation creation to use JSON structure
- [ ] Test with real job

### Step 3: Update PI Sync Job
- [ ] Update `job_pi_sync.py` similarly
- [ ] Test with real job

### Step 4: Verify API Endpoints
- [ ] Check if backend supports `full_information` and `information_json`
- [ ] Update if needed or document requirements

### Step 5: Testing
- [ ] Run unit tests
- [ ] Run integration tests
- [ ] Test with real LLM responses

### Step 6: Documentation
- [ ] Update code comments
- [ ] Document extraction logic
- [ ] Document expected LLM response format

---

## Backward Compatibility

### Fallback Strategy
- If extraction fails (markers not found), fallback to current behavior:
  - Use full response as description
  - Truncate to 2000 chars
  - Still save recommendations using text parsing

### Gradual Migration
- Option 1: Feature flag to enable/disable structured extraction
- Option 2: Try structured extraction first, fallback to simple if fails

---

## Expected Benefits

1. **Better Data Structure**: Separate text and JSON for better querying
2. **Consistent Storage**: Same format as old system
3. **Rich Recommendations**: Structured recommendations with headers
4. **Maintainability**: Clear separation of concerns
5. **Backward Compatible**: Falls back gracefully if extraction fails

---

## Risk Mitigation

1. **LLM Response Format Changes**: 
   - Use flexible marker matching (case-insensitive)
   - Provide fallback to full response

2. **API Endpoint Changes**:
   - Verify endpoints support new fields
   - Document any backend changes needed

3. **Database Schema**:
   - Verify fields exist in database
   - Document schema requirements

---

## Next Steps

1. Review and approve this plan
2. Implement Phase 1 (utility functions)
3. Test extraction logic
4. Implement Phase 2 (job processors)
5. Integration testing
6. Deploy and monitor

