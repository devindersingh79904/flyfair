from datetime import datetime, timezone
from typing import Any, List, Dict, Optional
from app.core.constants import ResponseStatus

def get_current_timestamp() -> str:
    """Return formatted UTC ISO timestamp with millisecond precision."""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

def build_success_response(
    data: Any,
    message: str = "Request completed successfully",
    meta: Optional[Dict[str, Any]] = None,
    correlation_id: str = ""
) -> Dict[str, Any]:
    """Build standardized success API response envelope."""
    return {
        "timestamp": get_current_timestamp(),
        "correlationId": correlation_id,
        "status": ResponseStatus.SUCCESS.value,
        "message": message,
        "data": data,
        "errors": [],
        "meta": meta or {}
    }

def build_error_response(
    errors: List[Dict[str, Any]],
    message: str = "An error occurred",
    correlation_id: str = "",
    latency_ms: Optional[int] = None
) -> Dict[str, Any]:
    """Build standardized error API response envelope."""
    meta = {}
    if latency_ms is not None:
        meta["latencyMs"] = latency_ms
    return {
        "timestamp": get_current_timestamp(),
        "correlationId": correlation_id,
        "status": ResponseStatus.ERROR.value,
        "message": message,
        "data": None,
        "errors": errors,
        "meta": meta
    }
