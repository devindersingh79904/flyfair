import logging
import json
from datetime import datetime, timezone
import contextvars
from typing import Any

# Context variables to hold request correlation and request identifiers
correlation_id_var = contextvars.ContextVar("correlation_id", default=None)
request_id_var = contextvars.ContextVar("request_id", default=None)

class StructuredJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Get correlation and request ids
        correlation_id = correlation_id_var.get()
        request_id = request_id_var.get()

        # Format current ISO timestamp (millisecond precision, e.g. 2026-05-29T10:15:30.123Z)
        now = datetime.now(timezone.utc)
        timestamp_str = now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        log_data = {
            "timestamp": timestamp_str,
            "level": record.levelname,
            "correlationId": correlation_id,
            "requestId": request_id or correlation_id,
            "taskId": getattr(record, "task_id", None),
            "module": record.module,
            "file": record.filename,
            "line": record.lineno,
            "event": getattr(record, "event", "generic_event"),
            "message": record.getMessage()
        }

        # Include explicit search log metrics if available
        search_fields = [
            "query", "normalizedQuery", "resultCount", 
            "topResult", "topScore", "matchReason", "latencyMs"
        ]
        for field in search_fields:
            if hasattr(record, field):
                log_data[field] = getattr(record, field)

        # Support extra custom properties passed via extra argument
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            for k, v in record.extra.items():
                if k not in log_data:
                    log_data[k] = v

        return json.dumps(log_data)

def setup_logging(log_level: str = "INFO"):
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Clear pre-existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Attach the structured JSON stream handler
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(StructuredJsonFormatter())
    logger.addHandler(stream_handler)

    # Silence verbose default logs
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
