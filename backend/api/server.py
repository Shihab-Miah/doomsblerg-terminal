"""
DoomsBlerg Terminal Web API Server
==================================
Provides a zero-dependency threaded HTTP JSON server (works cleanly on Android
Termux and low-end laptops with Python stdlib alone) plus an optional FastAPI
adapter when `fastapi` is installed.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from typing import Any, Dict, Tuple

from .routes import dispatch_api_request


class DoomsBlergHTTPHandler(BaseHTTPRequestHandler):
    """HTTP handler forwarding GET/POST/OPTIONS requests to dispatch_api_request."""

    server_version = "DoomsBlergHTTP/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        # Keep console output clean unless debugging
        return

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        raw = json.dumps(payload, indent=2, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self) -> None:
        self._send_json(200, {"status": "ok"})

    def do_GET(self) -> None:
        status, payload = dispatch_api_request("GET", self.path)
        self._send_json(status, payload)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body: Dict[str, Any] = {}
        if length > 0:
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            try:
                loaded = json.loads(raw)
                if isinstance(loaded, dict):
                    body = loaded
            except json.JSONDecodeError:
                self._send_json(400, {"error": "Invalid JSON request body."})
                return
        status, payload = dispatch_api_request("POST", self.path, body=body)
        self._send_json(status, payload)


def create_http_server(host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    """Create a bound stdlib ThreadingHTTPServer instance ready to serve."""
    return ThreadingHTTPServer((host, port), DoomsBlergHTTPHandler)


def serve_forever(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start the DoomsBlerg HTTP API gateway blocking until interrupted."""
    server = create_http_server(host=host, port=port)
    actual_host, actual_port = server.server_address[:2]
    print(f"DoomsBlerg Web API listening on http://{actual_host}:{actual_port}")
    try:
        server.serve_forever()
    finally:
        server.server_close()


def create_fastapi_app() -> Any:
    """Optional FastAPI app builder delegating all endpoints to dispatch_api_request."""
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse

    app = FastAPI(title="DoomsBlerg Terminal API", version="0.4.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.api_route("/{full_path:path}", methods=["GET", "POST"])
    async def _catch_all(request: Request, full_path: str) -> JSONResponse:
        body: Dict[str, Any] = {}
        if request.method == "POST":
            try:
                parsed = await request.json()
                if isinstance(parsed, dict):
                    body = parsed
            except Exception:
                body = {}
        raw_url = "/" + full_path
        if request.url.query:
            raw_url = f"{raw_url}?{request.url.query}"
        status, payload = dispatch_api_request(request.method, raw_url, body=body)
        return JSONResponse(status_code=status, content=payload)

    return app
