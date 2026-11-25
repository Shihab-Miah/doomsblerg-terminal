"""
DoomsBlerg Configuration Loader
===============================
Loads API keys from `.env` and `credentials/keys.env` without third-party dependencies.
"""

from pathlib import Path
import os
from typing import Dict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILES = [
    PROJECT_ROOT / ".env",
    PROJECT_ROOT / "credentials" / "keys.env",
]

_CACHED_ENV: Dict[str, str] | None = None


def _parse_env_file(path: Path) -> Dict[str, str]:
    """Parse key=value pairs from an env file, ignoring comments and blanks."""
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and val:
            values[key] = val
    return values


def load_env(force_reload: bool = False) -> Dict[str, str]:
    """Return merged configuration from OS environment, .env, and credentials vault."""
    global _CACHED_ENV
    if _CACHED_ENV is not None and not force_reload:
        return _CACHED_ENV

    merged: Dict[str, str] = {}
    # Vault first, .env second, explicit process env highest priority
    for env_path in reversed(ENV_FILES):
        merged.update(_parse_env_file(env_path))
    for key, val in os.environ.items():
        if val:
            merged[key] = val

    _CACHED_ENV = merged
    return merged


def get_key(name: str, default: str = "") -> str:
    """Fetch an API key or config value by name."""
    return load_env().get(name, default)


def require_key(name: str) -> str:
    """Fetch a required API key or raise a clear configuration error."""
    value = get_key(name)
    if not value:
        raise RuntimeError(f"Missing required API key: {name}. Check .env or credentials/keys.env.")
    return value
