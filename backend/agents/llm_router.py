"""
DoomsBlerg 4-Cloud Auto-Switching AI Router
===========================================
Routes prompts across Google AI Studio, Groq LPU, OpenRouter, and Kilo AI Gateway
(plus optional OpenCode Zen) with zero local RAM/GPU usage and automatic
SQLite-persisted circuit-breaker failover on HTTP 429 / 503 / timeouts.
"""

import json
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.data_engine.config import PROJECT_ROOT, get_key

ROUTER_DB_PATH = PROJECT_ROOT / "data" / "llm_router.db"
_LOCK = threading.Lock()


# Verified working model targets by provider
DEFAULT_CHAINS: Dict[str, List[Tuple[str, str]]] = {
    "auditor": [
        ("google", "gemini-3.5-flash"),
        ("groq", "openai/gpt-oss-120b"),
        ("openrouter", "nvidia/nemotron-3-ultra-550b-a55b:free"),
        ("kilo", "reflection/beam-free"),
    ],
    "bull": [
        ("groq", "openai/gpt-oss-120b"),
        ("openrouter", "nvidia/nemotron-3.5-lightning:free"),
        ("google", "gemini-2.5-flash"),
        ("kilo", "reflection/beam-free"),
    ],
    "bear": [
        ("google", "gemma-4-31b-it"),
        ("kilo", "reflection/beam-free"),
        ("groq", "qwen/qwen3.8-27b"),
        ("openrouter", "nvidia/nemotron-3.5-lightning:free"),
    ],
    "sentiment": [
        ("groq", "qwen/qwen3.8-27b"),
        ("kilo", "reflection/beam-free"),
        ("google", "gemini-2.5-flash-lite"),
        ("openrouter", "nvidia/nemotron-3.5-lightning:free"),
    ],
    "macro": [
        ("google", "gemini-2.5-flash-lite"),
        ("groq", "qwen/qwen3.8-27b"),
        ("kilo", "reflection/beam-free"),
        ("google", "gemini-2.5-flash"),
    ],
    "judge": [
        ("google", "gemini-3.5-flash"),
        ("groq", "openai/gpt-oss-120b"),
        ("openrouter", "nvidia/nemotron-3-ultra-550b-a55b:free"),
        ("kilo", "reflection/beam-free"),
    ],
}


def _get_conn() -> sqlite3.Connection:
    ROUTER_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(ROUTER_DB_PATH), timeout=10)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS model_cooldowns (
            target_id TEXT PRIMARY KEY,
            cooldown_until REAL NOT NULL,
            last_error TEXT
        )
        """
    )
    return conn


def _is_on_cooldown(provider: str, model: str) -> Optional[str]:
    target = f"{provider}:{model}"
    now = time.time()
    with _LOCK:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT cooldown_until, last_error FROM model_cooldowns WHERE target_id = ?",
                (target,),
            ).fetchone()
            if row and row[0] > now:
                return f"cooldown ({int(row[0] - now)}s left: {row[1]})"
            if row:
                conn.execute("DELETE FROM model_cooldowns WHERE target_id = ?", (target,))
    return None


def _set_cooldown(provider: str, model: str, seconds: int, reason: str) -> None:
    target = f"{provider}:{model}"
    until = time.time() + seconds
    with _LOCK:
        with _get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO model_cooldowns (target_id, cooldown_until, last_error) VALUES (?, ?, ?)",
                (target, until, reason[:200]),
            )


def clear_cooldowns() -> None:
    """Reset all provider/model circuit breakers."""
    with _LOCK:
        with _get_conn() as conn:
            conn.execute("DELETE FROM model_cooldowns")


def _extract_json_object(raw_text: str) -> Dict[str, Any]:
    """Extract a JSON object from raw model output (strips markdown fences or thinking text)."""
    text = (raw_text or "").strip()
    if not text:
        raise ValueError("Empty model response")

    # Strip ```json ... ``` blocks
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))

    # Direct parse or outermost { ... }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        return json.loads(text[start : end + 1])

    raise ValueError(f"No JSON object found in output: {text[:120]}")


def _post_json(url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout: int = 22) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _call_google(model: str, system_prompt: str, user_prompt: str, max_tokens: int, temperature: float) -> str:
    key = get_key("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("Missing GEMINI_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    combined = f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt
    payload = {
        "contents": [{"role": "user", "parts": [{"text": combined}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        },
    }
    data = _post_json(url, {"User-Agent": "DoomsBlergTerminal/1.0"}, payload)
    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"Gemini returned no candidates: {data}")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    if not text:
        text = "".join(p.get("text", "") for p in parts)
    if not text.strip():
        raise RuntimeError("Gemini returned empty text")
    return text.strip()


def _call_openai_compat(
    base_url: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    temperature: float,
    extra_headers: Optional[Dict[str, str]] = None,
) -> str:
    headers = {"User-Agent": "DoomsBlergTerminal/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if extra_headers:
        headers.update(extra_headers)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    data = _post_json(f"{base_url.rstrip('/')}/chat/completions", headers, payload)
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"No choices returned: {data}")
    msg = choices[0].get("message") or {}
    text = msg.get("content") or ""
    if not text.strip():
        # Reasoning models may exhaust tokens in `reasoning` if tight; treat empty content as retryable
        raise RuntimeError("Empty assistant content (reasoning overflow or filtered)")
    return text.strip()


def _dispatch_provider(
    provider: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    temperature: float,
) -> str:
    if provider == "google":
        return _call_google(model, system_prompt, user_prompt, max_tokens, temperature)
    if provider == "groq":
        key = get_key("GROQ_API_KEY")
        if not key:
            raise RuntimeError("Missing GROQ_API_KEY")
        return _call_openai_compat(
            "https://api.groq.com/openai/v1", key, model, system_prompt, user_prompt, max_tokens, temperature
        )
    if provider == "openrouter":
        key = get_key("OPENROUTER_API_KEY")
        if not key:
            raise RuntimeError("Missing OPENROUTER_API_KEY")
        return _call_openai_compat(
            "https://openrouter.ai/api/v1",
            key,
            model,
            system_prompt,
            user_prompt,
            max_tokens,
            temperature,
            extra_headers={
                "HTTP-Referer": "https://github.com/Shihab-Miah/doomsblerg-terminal",
                "X-Title": "DoomsBlerg Terminal",
            },
        )
    if provider == "kilo":
        key = get_key("KILO_API_KEY", "")
        return _call_openai_compat(
            "https://ai-gateway.kilo.ai/api/v1", key, model, system_prompt, user_prompt, max_tokens, temperature
        )
    if provider == "opencode":
        key = get_key("OPENCODE_API_KEY")
        if not key:
            raise RuntimeError("Missing OPENCODE_API_KEY")
        return _call_openai_compat(
            "https://opencode.ai/zen/v1", key, model, system_prompt, user_prompt, max_tokens, temperature
        )
    raise ValueError(f"Unknown AI provider: {provider}")


class MultiCloudLLMRouter:
    """Automatic circuit-breaker router switching across 4 free cloud AI gateways."""

    def generate(
        self,
        role: str,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 800,
        temperature: float = 0.2,
        expect_json: bool = False,
        chain_override: Optional[List[Tuple[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Attempt inference along the role's failover chain until one succeeds.
        Automatically places failing (provider, model) targets on cooldown.
        """
        chain = chain_override or DEFAULT_CHAINS.get(role, DEFAULT_CHAINS["judge"])
        attempts: List[Dict[str, Any]] = []

        for provider, model in chain:
            cd_reason = _is_on_cooldown(provider, model)
            if cd_reason:
                attempts.append({"provider": provider, "model": model, "skipped": cd_reason})
                continue

            t0 = time.time()
            try:
                text = _dispatch_provider(provider, model, system_prompt, user_prompt, max_tokens, temperature)
                parsed = _extract_json_object(text) if expect_json else None
                return {
                    "text": text,
                    "json": parsed,
                    "provider_used": provider,
                    "model_used": model,
                    "latency_ms": int((time.time() - t0) * 1000),
                    "attempts": attempts,
                }
            except urllib.error.HTTPError as exc:
                err_txt = exc.read().decode("utf-8", errors="replace")[:200]
                if exc.code == 429:
                    ttl = 600 if "daily" in err_txt.lower() else 90
                    _set_cooldown(provider, model, ttl, f"HTTP 429: {err_txt}")
                elif exc.code in (401, 403):
                    _set_cooldown(provider, model, 3600, f"HTTP {exc.code}: {err_txt}")
                else:
                    _set_cooldown(provider, model, 60, f"HTTP {exc.code}: {err_txt}")
                attempts.append({"provider": provider, "model": model, "error": f"HTTP {exc.code}"})
            except Exception as exc:
                _set_cooldown(provider, model, 45, str(exc))
                attempts.append({"provider": provider, "model": model, "error": str(exc)[:140]})

        raise RuntimeError(f"All cloud AI gateways failed for role='{role}': {attempts}")

    def gateway_health(self) -> Dict[str, Any]:
        """Run a lightweight check showing configured keys and current circuit-breaker cooldowns."""
        with _LOCK:
            with _get_conn() as conn:
                rows = conn.execute("SELECT target_id, cooldown_until, last_error FROM model_cooldowns").fetchall()
        now = time.time()
        active_cooldowns = [
            {"target": r[0], "seconds_left": int(r[1] - now), "reason": r[2]}
            for r in rows
            if r[1] > now
        ]
        return {
            "gateways": {
                "google_ai_studio": bool(get_key("GEMINI_API_KEY")),
                "groq_lpu": bool(get_key("GROQ_API_KEY")),
                "openrouter": bool(get_key("OPENROUTER_API_KEY")),
                "kilo_gateway": "anonymous_200_per_hr" if not get_key("KILO_API_KEY") else "authenticated",
                "opencode_zen": bool(get_key("OPENCODE_API_KEY")),
            },
            "active_cooldowns": active_cooldowns,
        }


llm_router = MultiCloudLLMRouter()
