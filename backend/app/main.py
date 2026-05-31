import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.core.middleware import CorrelationIdMiddleware
from app.core.errors import AirportSearchException
from app.core.exception_handlers import (
    airport_search_exception_handler,
    validation_exception_handler,
    http_exception_handler,
    general_exception_handler
)
from app.services.index_builder import IndexBuilder
from app.services.airport_search_service import AirportSearchService
from app.api.routes import health_routes, airport_search_routes

# Configure structured JSON logging
setup_logging(log_level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager to load datasets and initialize search engine indexes on boot."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    
    logger.info(f"Initializing database from directory: {data_dir}")
    
    # Instantiating in-memory indexes and binding search coordination service
    index = IndexBuilder(data_dir=data_dir)
    search_service = AirportSearchService(index=index)
    
    # Store reference on FastAPI state for Dependency Injection retrieval
    app.state.search_service = search_service
    logger.info("Search service and in-memory indexes built.")
    logger.info(f"Environment: {settings.APP_ENV}")
    logger.info(f"Allowed CORS Origins: {settings.BACKEND_CORS_ORIGINS}")
    yield
    logger.info("Terminating application state...")

# Initialize App Instance
app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# 1. Register CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Register Correlation ID middleware
app.add_middleware(CorrelationIdMiddleware)

# 3. Register standard API exception handlers
app.add_exception_handler(AirportSearchException, airport_search_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

from app.core.response_builder import build_success_response

# 4. Include API Route Modules
app.include_router(health_routes.router, prefix=settings.API_PREFIX)
app.include_router(airport_search_routes.router, prefix=settings.API_PREFIX)

@app.get("/")
async def root(request: Request):
    correlation_id = getattr(request.state, "correlation_id", "")
    return build_success_response(
        data=None,
        message="app is working",
        correlation_id=correlation_id
    )
