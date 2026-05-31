from fastapi import APIRouter, Request
from app.core.response_builder import build_success_response

router = APIRouter()

@router.get("/health")
async def health(request: Request):
    """Health check endpoint to verify backend operational state."""
    correlation_id = getattr(request.state, "correlation_id", "")
    return build_success_response(
        data={"status": "OK"},
        message="Service is healthy",
        correlation_id=correlation_id
    )
