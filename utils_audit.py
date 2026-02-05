import os
import time
from typing import Any, Dict
from datetime import datetime

import requests

from utils_logging import log


def extract_tokens_from_llm_response(raw_response: Dict[str, Any]) -> int | None:
    """
    Extract tokens used from LLM service response.
    
    Args:
        raw_response: The raw response dict from LLM service
        
    Returns:
        Token count or None if not available
    """
    if not isinstance(raw_response, dict):
        return None
    
    # Try various possible paths in the response structure
    # Common patterns:
    # - data.data.tokens_used
    # - data.data.usage.total_tokens
    # - data.tokens_used
    # - data.usage.total_tokens
    # - data.data.usage.tokens_used
    
    data = raw_response.get("data")
    if isinstance(data, dict):
        # Try data.data.tokens_used or data.data.usage
        inner_data = data.get("data")
        if isinstance(inner_data, dict):
            # Try tokens_used directly
            if "tokens_used" in inner_data:
                tokens = inner_data.get("tokens_used")
                if isinstance(tokens, (int, float)):
                    return int(tokens)
            
            # Try usage.total_tokens
            usage = inner_data.get("usage")
            if isinstance(usage, dict):
                total_tokens = usage.get("total_tokens")
                if isinstance(total_tokens, (int, float)):
                    return int(total_tokens)
                tokens_used = usage.get("tokens_used")
                if isinstance(tokens_used, (int, float)):
                    return int(tokens_used)
        
        # Try data.tokens_used
        if "tokens_used" in data:
            tokens = data.get("tokens_used")
            if isinstance(tokens, (int, float)):
                return int(tokens)
        
        # Try data.usage
        usage = data.get("usage")
        if isinstance(usage, dict):
            total_tokens = usage.get("total_tokens")
            if isinstance(total_tokens, (int, float)):
                return int(total_tokens)
            tokens_used = usage.get("tokens_used")
            if isinstance(tokens_used, (int, float)):
                return int(tokens_used)
    
    # Try top-level tokens_used
    if "tokens_used" in raw_response:
        tokens = raw_response.get("tokens_used")
        if isinstance(tokens, (int, float)):
            return int(tokens)
    
    return None


def calculate_severity(status_code: int) -> str:
    """
    Calculate severity based on HTTP status code.
    
    Returns:
        "HIGH" for status_code >= 500
        "WARNING" for status_code > 200 and < 500
        "OK" for status_code == 200
        "NONE" otherwise
    """
    if status_code >= 500:
        return "HIGH"
    elif status_code > 200 and status_code < 500:
        return "WARNING"
    elif status_code == 200:
        return "OK"
    else:
        return "NONE"


def call_audit_service(
    action: str,
    duration_seconds: float,
    status_code: int,
    action_date: datetime,
    tokens_used: int | None = None,
    query_params: Dict[str, Any] | None = None,
    body: Dict[str, Any] | None = None,
    job_id: int | None = None,
) -> None:
    """
    Calls the audit service to log agent job completion (send-and-forget).
    
    Args:
        action: The insight type (e.g., "PI Sync", "Daily Progress")
        duration_seconds: Total processing time in seconds
        status_code: 200 for success, 500 for failure
        action_date: datetime when processing finished
        tokens_used: Optional tokens used from LLM
        query_params: Optional JSON object with agent parameters
        body: Optional JSON object with agent parameters (same as query_params)
        job_id: Optional job ID for logging
    """
    audit_service_url = os.environ.get("AUDIT_SERVICE_URL")
    if not audit_service_url or not audit_service_url.strip():
        log(job_id, "⚠️  WARNING: AUDIT_SERVICE_URL not configured. Audit logging skipped.")
        return
    
    try:
        # Format action_date as ISO string
        action_date_iso = action_date.isoformat()
        
        # Calculate severity from status code
        severity = calculate_severity(status_code)
        
        # Build audit log payload
        audit_log: Dict[str, Any] = {
            "user_id": None,
            "endpoint_path": "sparks-ai-agent",
            "action": action,
            "session_id": None,
            "action_date": action_date_iso,
            "count": 0,
            "http_method": "POST",
            "status_code": status_code,
            "response_time_seconds": duration_seconds,
            "severity": severity,
        }
        
        # Add tokens_used if available
        if tokens_used is not None:
            audit_log["tokens_used"] = tokens_used
        
        # Add query_params if provided
        if query_params is not None:
            audit_log["query_params"] = query_params
        
        # Add body if provided
        if body is not None:
            audit_log["body"] = body
        
        payload = {
            "logs": [audit_log]
        }
        
        url = f"{audit_service_url.rstrip('/')}/api/audit-logs"
        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        
        # Check if request was accepted (202 Accepted)
        if response.status_code == 202:
            # Success - silent (send-and-forget)
            pass
        else:
            # Log warning but don't fail
            log(job_id, f"⚠️  WARNING: Audit service returned status {response.status_code}. Job continues normally.")
    
    except requests.exceptions.Timeout:
        log(job_id, "⚠️  WARNING: Audit service unavailable (timeout after 5s). Job continues normally.")
    except requests.exceptions.RequestException as req_err:
        log(job_id, f"⚠️  WARNING: Audit service unavailable ({req_err}). Job continues normally.")
    except Exception as e:
        # Catch-all for any other errors - log warning and continue
        log(job_id, f"⚠️  WARNING: Audit service call failed ({e}). Job continues normally.")
    # No return needed - send-and-forget

