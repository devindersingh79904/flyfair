import uuid
import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.logging_config import correlation_id_var, request_id_var
from app.core.constants import Headers, LogEvent

logger = logging.getLogger(__name__)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Retrieve or generate Correlation ID
        corr_id = request.headers.get(Headers.CORRELATION_ID.value)
        if not corr_id:
            corr_id = str(uuid.uuid4())

        # Bind to Request state for route access
        request.state.correlation_id = corr_id

        # Bind to ContextVars for structured-log access
        token_corr = correlation_id_var.set(corr_id)
        token_req = request_id_var.set(corr_id)

        start_time = time.perf_counter()

        logger.info(
            f"Incoming request: {request.method} {request.url.path}",
            extra={
                "event": LogEvent.API_REQUEST.value,
                "path": request.url.path,
                "method": request.method,
            },
        )

        try:
            try:
                response: Response = await call_next(request)
            except Exception as e:
                latency_ms = int((time.perf_counter() - start_time) * 1000)
                logger.error(
                    f"Unhandled Exception: {str(e)}",
                    extra={
                        "event": LogEvent.UNHANDLED_EXCEPTION.value,
                        "latencyMs": latency_ms,
                    },
                )
                raise

            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Echo Correlation ID in Response headers
            response.headers[Headers.CORRELATION_ID.value] = corr_id

            # Log *before* resetting context so correlationId is present
            logger.info(
                f"Completed request: {request.method} {request.url.path} with status {response.status_code}",
                extra={
                    "event": LogEvent.API_RESPONSE.value,
                    "path": request.url.path,
                    "method": request.method,
                    "statusCode": response.status_code,
                    "latencyMs": latency_ms,
                },
            )

            return response

        finally:
            # Reset ContextVars only after all logging is complete to prevent leaks
            correlation_id_var.reset(token_corr)
            request_id_var.reset(token_req)
