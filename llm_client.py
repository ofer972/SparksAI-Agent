from typing import Any, Dict, Tuple

from api_client import APIClient


def call_llm_generic(client: APIClient, formatted_text: str, *, selected_pi: str | None = None) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Call backend LLM chat endpoint. Returns (success, response_text, raw_payload).
    Falls back to a short static string if the call fails or returns unexpected shape.
    """
    body: Dict[str, Any] = {
        "question": formatted_text,
        "selected_pi": selected_pi,
        "chat_type": "PI_dashboard" if selected_pi else None,
    }
    # Remove Nones to keep payload clean
    body = {k: v for k, v in body.items() if v is not None}

    status, data = client.post_ai_chat(body)
    if status == 200 and isinstance(data, dict) and data.get("success") and isinstance(data.get("data"), dict):
        llm_resp = data["data"].get("response")
        if isinstance(llm_resp, str) and llm_resp.strip():
            return True, llm_resp, data
    # Strict behavior: no fallback
    return False, "", data if isinstance(data, dict) else {}


