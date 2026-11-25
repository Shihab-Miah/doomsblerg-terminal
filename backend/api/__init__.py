"""
DoomsBlerg Terminal Web API Gateway (Phase 4)
=============================================
Unified REST dispatcher and threaded HTTP server (plus optional FastAPI builder).
"""

from .routes import API_CATALOG, dispatch_api_request
from .server import create_fastapi_app, create_http_server, serve_forever

__all__ = [
    "API_CATALOG",
    "dispatch_api_request",
    "create_http_server",
    "serve_forever",
    "create_fastapi_app",
]
