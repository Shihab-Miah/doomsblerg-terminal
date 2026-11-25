"""
DoomsBlerg Terminal Web API Server
==================================
Provides a zero-dependency threaded HTTP JSON server (works cleanly on Android
Termux and low-end laptops with Python stdlib alone) plus an optional FastAPI
adapter when `fastapi` is installed.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import socket
import subprocess
from typing import Any, Dict, List, Tuple

from backend.data_engine.config import PROJECT_ROOT
from .routes import dispatch_api_request


class DoomsBlergHTTPServer(ThreadingHTTPServer):
    """Threaded HTTP server configured cleanly for laptop Chrome & mobile hotspot LAN."""

    daemon_threads = True
    allow_reuse_address = True

FRONTEND_SRC_DIR = (PROJECT_ROOT / "frontend" / "src").resolve()
_STATIC_ASSETS: Dict[str, Tuple[str, str]] = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
}


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
        clean_path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if clean_path == "/favicon.ico":
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if clean_path in _STATIC_ASSETS:
            rel_name, mime = _STATIC_ASSETS[clean_path]
            file_path = (FRONTEND_SRC_DIR / rel_name).resolve()
            if file_path.parent == FRONTEND_SRC_DIR and file_path.is_file():
                content = file_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(content)
                return

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


def detect_lan_urls(port: int = 8000) -> List[Dict[str, str]]:
    """Detect active Hotspot/Wi-Fi IPv4 URLs so another device on the same LAN can connect."""
    found: List[Dict[str, str]] = []
    seen = set()

    for cmd in (["ip", "-4", "addr", "show"], ["ifconfig"]):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            if proc.returncode != 0 or not proc.stdout:
                continue
            cur_iface = ""
            for line in proc.stdout.splitlines():
                m_iface = re.match(r"^(?:\d+:\s+)?([A-Za-z0-9_.-]+?)(?:@\S+)?:\s+", line)
                if m_iface:
                    cur_iface = m_iface.group(1).strip()
                m_ip = re.search(r"\binet\s+(?:addr:)?(\d+\.\d+\.\d+\.\d+)\b", line)
                if m_ip:
                    ip = m_ip.group(1)
                    if ip.startswith("127.") or ip.startswith("192.0.0."):
                        continue
                    if ip in seen:
                        continue
                    seen.add(ip)
                    is_hotspot_or_wifi = cur_iface.startswith(("ap", "wlan", "swlan", "en", "eth", "wl"))
                    found.append(
                        {
                            "interface": cur_iface or "lan",
                            "ip": ip,
                            "url": f"http://{ip}:{port}",
                            "priority": "primary_hotspot_wifi" if is_hotspot_or_wifi else "secondary",
                        }
                    )
            if found:
                break
        except Exception:
            continue

    if not found:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
            s.close()
            if ip and not ip.startswith("127."):
                found.append({"interface": "default", "ip": ip, "url": f"http://{ip}:{port}", "priority": "primary_hotspot_wifi"})
        except Exception:
            pass

    found.sort(key=lambda item: (0 if item["priority"] == "primary_hotspot_wifi" else 1, item["interface"]))
    return found


def create_http_server(host: str = "127.0.0.1", port: int = 8000) -> DoomsBlergHTTPServer:
    """Create a bound stdlib threaded HTTP server instance ready to serve."""
    return DoomsBlergHTTPServer((host, port), DoomsBlergHTTPHandler)


def serve_forever(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start the DoomsBlerg HTTP API gateway blocking until interrupted."""
    if host == "0.0.0.0":
        try:
            subprocess.run(["termux-wake-lock"], capture_output=True, timeout=2)
        except Exception:
            pass

    server = create_http_server(host=host, port=port)
    actual_host, actual_port = server.server_address[:2]
    print(f"DoomsBlerg Terminal Server listening on http://{actual_host}:{actual_port}", flush=True)
    print(f"  Local URL:         http://127.0.0.1:{actual_port}", flush=True)
    if actual_host == "0.0.0.0":
        for entry in detect_lan_urls(actual_port):
            print(f"  Hotspot / LAN URL: {entry['url']}  [{entry['interface']} - {entry['priority']}]", flush=True)
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
