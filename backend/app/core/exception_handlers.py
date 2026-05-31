import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.errors import AirportSearchException
from app.core.response_builder import build_error_response
from app.core.constants import LogEvent

logger = logging.getLogger(__name__)

async def airport_search_exception_handler(request: Request, exc: AirportSearchException):
    correlation_id = getattr(request.state, "correlation_id", "")
    errors = [{
        "code": exc.code,
        "message": exc.message,
        "field": exc.field
    }]
    logger.warning(
        f"Application Exception: {exc.message}",
        extra={"event": LogEvent.VALIDATION_ERROR.value, "code": exc.code, "field": exc.field}
    )
    
    content = build_error_response(
        errors=errors,
        message=exc.message,
        correlation_id=correlation_id
    )
    
    # Select HTTP Status Code
    status_code = status.HTTP_400_BAD_REQUEST
    if exc.code in ("INVALID_LIMIT", "INVALID_QUERY"):
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        
    return JSONResponse(status_code=status_code, content=content)

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    correlation_id = getattr(request.state, "correlation_id", "")
    errors = []
    for error in exc.errors():
        loc = error.get("loc", [])
        field = str(loc[-1]) if loc else None
        errors.append({
            "code": "VALIDATION_ERROR",
            "message": error.get("msg", "Invalid value"),
            "field": field
        })
        
    logger.warning(
        f"Validation Error: {str(errors)}",
        extra={"event": LogEvent.VALIDATION_ERROR.value, "errors": errors}
    )
    
    content = build_error_response(
        errors=errors,
        message="Invalid search request",
        correlation_id=correlation_id
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=content
    )

async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    correlation_id = getattr(request.state, "correlation_id", "")
    errors = [{
        "code": "HTTP_EXCEPTION",
        "message": exc.detail,
        "field": None
    }]
    
    content = build_error_response(
        errors=errors,
        message=exc.detail,
        correlation_id=correlation_id
    )
    return JSONResponse(status_code=exc.status_code, content=content)

async def general_exception_handler(request: Request, exc: Exception):
    correlation_id = getattr(request.state, "correlation_id", "")
    errors = [{
        "code": "INTERNAL_SERVER_ERROR",
        "message": "An unexpected error occurred",
        "field": None
    }]
    
    logger.error(
        f"Unhandled exception: {str(exc)}",
        exc_info=True,
        extra={"event": LogEvent.UNHANDLED_EXCEPTION.value}
    )
    
    content = build_error_response(
        errors=errors,
        message="Internal server error",
        correlation_id=correlation_id
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=content
    )
