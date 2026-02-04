"""
Compatibility layer for utils_processing.py

This module re-exports all functions and classes from the split utility modules
to maintain backward compatibility. All existing imports from utils_processing
will continue to work.

The code has been split into:
- utils_formatting.py: Data formatting functions
- utils_data_fetching.py: Data fetching functions (with/without formatting)
- utils_llm_processing_and_extraction.py: LLM extraction, recommendations, and processing
"""

# Import everything from the new split modules
from utils_formatting import (
    filter_columns_excluding_points,
    format_table,
    format_transcript,
    format_burndown_markdown,
    format_pi_status,
    format_pi_analysis_input,
    PROMPT_FORMAT_CONSTANTS,
)

from utils_data_fetching import (
    get_prompt_with_error_check,
    fetch_pi_data_for_analysis,
    get_team_sprint_burndown_for_analysis,
    get_group_sprint_burndown_for_analysis,
    get_daily_transcript_for_analysis,
    get_transcripts_for_analysis,
    get_active_sprint_summary_by_team_for_analysis,
    get_selected_active_sprint_summary,
    format_active_sprint_summary_for_analysis,
    sprint_gate_get_sprint_id_or_stop,
    get_sprint_issues_with_epic_for_analysis,
    get_closed_sprints_for_analysis,
    get_group_closed_sprints_for_analysis,
    get_pi_status_for_today_for_analysis,
    get_pi_status_for_today_by_team_for_analysis,
    get_average_sprint_velocity_per_team_for_analysis,
    get_epics_average_velocity_for_analysis,
    get_epics_by_pi_for_analysis,
    get_pi_burndown_for_analysis,
    get_pi_dependencies_for_analysis,
    get_group_sprint_dependencies_for_analysis,
    get_group_active_sprint_stories_by_epic_for_analysis,
    get_pi_planning_gaps_for_analysis,
    get_goal_progress_for_analysis,
    get_current_sprint_progress_for_analysis,
)

from utils_llm_processing_and_extraction import (
    clean_recommendation_text,
    extract_recommendations,
    save_recommendations_from_json,
    LLM_EXTRACTION_CONSTANTS,
    extract_content_between_markers,
    extract_json_sections,
    extract_text_and_json,
    extract_review_section,
    extract_daily_progress_review,  # Backward compatibility
    extract_pi_sync_review,  # Backward compatibility
    process_llm_response_and_save_ai_card,
    process_llm_with_two_step_fallback,
)

# Re-export everything for backward compatibility
__all__ = [
    # Formatting functions
    "filter_columns_excluding_points",
    "format_table",
    "format_transcript",
    "format_burndown_markdown",
    "format_pi_status",
    "format_pi_analysis_input",
    "PROMPT_FORMAT_CONSTANTS",
    # Data fetching functions
    "get_prompt_with_error_check",
    "fetch_pi_data_for_analysis",
    "get_team_sprint_burndown_for_analysis",
    "get_group_sprint_burndown_for_analysis",
    "get_daily_transcript_for_analysis",
    "get_transcripts_for_analysis",
    "get_active_sprint_summary_by_team_for_analysis",
    "get_selected_active_sprint_summary",
    "format_active_sprint_summary_for_analysis",
    "sprint_gate_get_sprint_id_or_stop",
    "get_sprint_issues_with_epic_for_analysis",
    "get_closed_sprints_for_analysis",
    "get_group_closed_sprints_for_analysis",
    "get_pi_status_for_today_for_analysis",
    "get_pi_status_for_today_by_team_for_analysis",
    "get_average_sprint_velocity_per_team_for_analysis",
    "get_epics_average_velocity_for_analysis",
    "get_epics_by_pi_for_analysis",
    "get_pi_burndown_for_analysis",
    "get_pi_dependencies_for_analysis",
    "get_group_sprint_dependencies_for_analysis",
    "get_group_active_sprint_stories_by_epic_for_analysis",
    "get_pi_planning_gaps_for_analysis",
    "get_goal_progress_for_analysis",
    "get_current_sprint_progress_for_analysis",
    # LLM processing and extraction
    "clean_recommendation_text",
    "extract_recommendations",
    "save_recommendations_from_json",
    "LLM_EXTRACTION_CONSTANTS",
    "extract_content_between_markers",
    "extract_json_sections",
    "extract_text_and_json",
    "extract_review_section",
    "extract_daily_progress_review",  # Backward compatibility
    "extract_pi_sync_review",  # Backward compatibility
    "process_llm_response_and_save_ai_card",
    "process_llm_with_two_step_fallback",
]
