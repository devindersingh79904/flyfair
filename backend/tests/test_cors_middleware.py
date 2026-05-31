import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.middleware.cors import CORSMiddleware
from app.core.middleware import CorrelationIdMiddleware

def build_test_app(cors_origins):
    app = FastAPI()
    
    app.add_middleware(CorrelationIdMiddleware)
    
    cors_allow_credentials = "*" not in cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.get("/api/v1/airports/search")
    async def dummy_search():
        return {"msg": "ok"}
        
    return app

def test_cors_middleware_wildcard():
    app = build_test_app(["*"])
    client = TestClient(app)
    
    response = client.options(
        "/api/v1/airports/search",
        headers={
            "Origin": "https://flyfair.devinderpanesar.com",
            "Access-Control-Request-Method": "GET"
        }
    )
    
    assert response.status_code in (200, 204)
    assert "access-control-allow-origin" in response.headers
    assert response.headers["access-control-allow-origin"] == "*"
    # Credentials should not be allowed with wildcard
    assert "access-control-allow-credentials" not in response.headers or response.headers["access-control-allow-credentials"] == "false"

def test_cors_middleware_explicit_origin():
    app = build_test_app(["https://flyfair.devinderpanesar.com"])
    client = TestClient(app)
    
    response = client.options(
        "/api/v1/airports/search",
        headers={
            "Origin": "https://flyfair.devinderpanesar.com",
            "Access-Control-Request-Method": "GET"
        }
    )
    
    assert response.status_code in (200, 204)
    assert "access-control-allow-origin" in response.headers
    assert response.headers["access-control-allow-origin"] == "https://flyfair.devinderpanesar.com"
    # Credentials should be allowed with explicit origin
    assert response.headers.get("access-control-allow-credentials") == "true"
