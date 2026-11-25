"""
DoomsBlerg Shared HTTP Client & SQLite TTL Cache
=================================================
Lightweight zero-dependency HTTP transport with automatic SQLite caching
so free API quotas are respected and repeated terminal queries load instantly.
"""

import hashlib
import json
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from .config import PROJECT_ROOT, get_key

CACHE_DB_PATH = PROJECT_ROOT / "data" / "cache.db"
_DB_LOCK = threading.Lock()


def _user_agent() -> str:
    """Return compliant User-Agent (required by SEC EDGAR)."""
    email = get_key("USER_EMAIL", "shihabmiah.me@gmail.com")
    return f"DoomsBlergTerminal/1.0 ({email})"


def _get_conn() -> sqlite3.Connection:
    """Open or initialize the SQLite TTL cache database."""
    CACHE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(CACHE_DB_PATH), timeout=10)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS http_cache (
            cache_key TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            expires_at REAL NOT NULL
        )
        """
    )
    return conn


def _make_cache_key(method: str, url: str, body: Optional[bytes]) -> str:
    """Build deterministic cache key excluding raw secret query strings if hashed."""
    raw = f"{method}:{url}:{(body or b'').decode('utf-8', errors='ignore')}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _read_cache(cache_key: str) -> Optional[str]:
    now = time.time()
    with _DB_LOCK:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT payload, expires_at FROM http_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
            if row and row[1] > now:
                return row[0]
            if row:
                conn.execute("DELETE FROM http_cache WHERE cache_key = ?", (cache_key,))
    return None


def _write_cache(cache_key: str, payload: str, ttl_seconds: int) -> None:
    if ttl_seconds <= 0:
        return
    expires_at = time.time() + ttl_seconds
    with _DB_LOCK:
        with _get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO http_cache (cache_key, payload, expires_at) VALUES (?, ?, ?)",
                (cache_key, payload, expires_at),
            )


def clear_expired_cache() -> int:
    """Delete expired cache entries and return count removed."""
    now = time.time()
    with _DB_LOCK:
        with _get_conn() as conn:
            cur = conn.execute("DELETE FROM http_cache WHERE expires_at <= ?", (now,))
            return cur.rowcount


def fetch_text(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    method: str = "GET",
    json_body: Optional[Dict[str, Any]] = None,
    ttl_seconds: int = 0,
    timeout: int = 12,
) -> str:
    """Execute an HTTP request with optional SQLite TTL caching."""
    if params:
        query = urllib.parse.urlencode(params, doseq=True)
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{query}"

    body_bytes = json.dumps(json_body).encode("utf-8") if json_body is not None else None
    cache_key = _make_cache_key(method, url, body_bytes)

    if ttl_seconds > 0:
        cached = _read_cache(cache_key)
        if cached is not None:
            return cached

    req_headers = {
        "User-Agent": _user_agent(),
        "Accept": "application/json, text/csv, text/plain, */*",
    }
    if json_body is not None:
        req_headers["Content-Type"] = "application/json"
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url, data=body_bytes, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"HTTP {exc.code} from {url.split('?')[0]}: {err_body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error calling {url.split('?')[0]}: {exc.reason}") from exc

    if ttl_seconds > 0 and text:
        _write_cache(cache_key, text, ttl_seconds)
    return text


def fetch_json(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    method: str = "GET",
    json_body: Optional[Dict[str, Any]] = None,
    ttl_seconds: int = 0,
    timeout: int = 12,
) -> Any:
    """Execute an HTTP request and parse its JSON body."""
    raw = fetch_text(
        url=url,
        params=params,
        headers=headers,
        method=method,
        json_body=json_body,
        ttl_seconds=ttl_seconds,
        timeout=timeout,
    )
    return json.loads(raw)
