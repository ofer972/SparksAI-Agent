from typing import Any, Dict, Tuple

from api_client import APIClient


def call_agent_llm_process(
    client: APIClient,
    prompt: str,
    job_type: str,
    job_id: int | None = None,
    metadata: Dict[str, Any] | None = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Call dedicated agent LLM processing endpoint.
    
    Args:
        client: APIClient instance
        prompt: Complete formatted prompt prepared by agent
        job_type: Type of job ("Daily Agent", "Sprint Goal", or "PI Sync")
        job_id: Optional job ID for logging/tracking
        metadata: Optional metadata dict (team_name, pi_name, etc.)
    
    Returns:
        Tuple of (success, response_text, raw_payload)
    """
    body: Dict[str, Any] = {
        "prompt": prompt,
        "job_type": job_type,
    }
    
    # Add optional fields only if provided
    if job_id is not None:
        body["job_id"] = job_id
    if metadata:
        body["metadata"] = metadata
    
    try:
        status, data = client.post_agent_llm_process(body)
    except Exception as e:
        error_payload = {"error": str(e), "exception_type": type(e).__name__}
        print(f"❌ LLM Exception: {str(e)} ({type(e).__name__})")
        print(f"❌ Job Type: {job_type}, Job ID: {job_id}")
        return False, "", error_payload
    
    if status == 200 and isinstance(data, dict) and data.get("success") and isinstance(data.get("data"), dict):
        llm_resp = data["data"].get("response")
        if isinstance(llm_resp, str) and llm_resp.strip():
            return True, llm_resp, data
    
    # Error case: log the error details
    error_payload = data if isinstance(data, dict) else {}
    error_msg = error_payload.get("message") or error_payload.get("error") or f"HTTP {status}" if status != 200 else "Invalid response format"
    print(f"❌ LLM Error: {error_msg}")
    print(f"❌ Job Type: {job_type}, Job ID: {job_id}, Status: {status}")
    print(f"❌ Raw response: {error_payload}")
    
    # Strict behavior: no fallback
    return False, "", error_payload


