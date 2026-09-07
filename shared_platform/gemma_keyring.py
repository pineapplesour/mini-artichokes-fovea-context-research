from __future__ import annotations

import os
import re
import stat
from pathlib import Path
from typing import Any


TEAM1_GEMMA_KEYS_FILE_ENV = "UNIVERSAL_ARTICHOKE_GEMMA_KEYS_FILE"
TEAM1_GEMMA_ALLOW_INSECURE_FILE_ENV = "UNIVERSAL_ARTICHOKE_ALLOW_INSECURE_GEMMA_KEYS_FILE"
TEAM1_GEMMA_KEYS_LOADED_ENV = "UNIVERSAL_ARTICHOKE_GEMMA_KEYS_LOADED"
DEFAULT_TEAM1_GEMMA_KEYS_FILE = Path.home() / ".config" / "universal-artichoke" / "dev1-gemma.keys.env"
ROTATING_KEY_ENV = "GEMINI_API_KEYS"
ROTATING_KEY_ALIASES = ("GEMINI_API_KEYS", "GOOGLE_API_KEYS")
SINGLE_KEY_ENVS = ("RELIGION_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY")
INDEXED_KEY_RE = re.compile(r"^(?:GEMINI|GOOGLE|RELIGION_GEMINI)_API_KEY_(?:\d+|[A-Z0-9_]+)$")


def install_team1_gemma_keys_from_file(*, keys_file: str | Path | None = None, force: bool = False) -> dict[str, Any]:
    """Load Team 1's private Gemma key file into the existing Lawkey key rotation env.

    The real keys must stay outside the repository. This function only injects a
    comma-separated `GEMINI_API_KEYS` value into the current process so the
    existing Lawkey `GeminiKeyScheduler` can keep doing round-robin/rate-limit
    scheduling.
    """
    existing = _existing_key_env_count()
    if existing and not force:
        return {
            "passes": True,
            "source": "environment",
            "path": "",
            "keyCount": existing,
            "installed": False,
            "reason": "existing Gemini key environment preserved",
        }

    path = _resolve_keys_file(keys_file)
    if not path.exists():
        return {
            "passes": False,
            "source": "missing",
            "path": str(path),
            "keyCount": 0,
            "installed": False,
            "reason": "Team 1 Gemma key file does not exist",
        }

    _validate_private_file(path)
    keys = _parse_keys_file(path)
    if not keys:
        return {
            "passes": False,
            "source": "secret_file",
            "path": str(path),
            "keyCount": 0,
            "installed": False,
            "reason": "Team 1 Gemma key file contained no keys",
        }

    os.environ[ROTATING_KEY_ENV] = ",".join(keys)
    os.environ[TEAM1_GEMMA_KEYS_LOADED_ENV] = "1"
    return {
        "passes": True,
        "source": "secret_file",
        "path": str(path),
        "keyCount": len(keys),
        "installed": True,
        "reason": "loaded into GEMINI_API_KEYS for existing Lawkey key rotation",
    }


def first_available_gemini_key() -> str:
    """Return an explicit single Gemini key for direct chat helpers.

    Team 1 key files are installed only for the Lawkey rotation/scheduler path.
    Direct chat helpers must not auto-load or select a key from that rotating
    private pool because those requests bypass scheduler quotas.
    """
    for name in SINGLE_KEY_ENVS:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def team1_gemma_key_source_report() -> dict[str, Any]:
    existing = _existing_key_env_count()
    path = _resolve_keys_file(None)
    return {
        "passes": bool(existing or path.exists()),
        "envKeyCount": existing,
        "secretFilePath": str(path),
        "secretFileExists": path.exists(),
        "secretFilePrivate": _private_file_report(path),
        "policy": "real keys live outside git; Team 1 receives file access, Teams 2/3 do not",
    }


def _resolve_keys_file(keys_file: str | Path | None) -> Path:
    value = keys_file if keys_file is not None else os.getenv(TEAM1_GEMMA_KEYS_FILE_ENV, "").strip()
    if value:
        return Path(value).expanduser().resolve()
    return DEFAULT_TEAM1_GEMMA_KEYS_FILE.expanduser().resolve()


def _existing_key_env_count() -> int:
    values: list[str] = []
    for name in (*ROTATING_KEY_ALIASES, *SINGLE_KEY_ENVS):
        values.extend(_split_values(os.getenv(name, "")))
    return len(list(dict.fromkeys(values)))


def _parse_keys_file(path: Path) -> list[str]:
    keys: list[str] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            env_name = key.strip()
            if env_name in (*ROTATING_KEY_ALIASES, *SINGLE_KEY_ENVS) or INDEXED_KEY_RE.match(env_name):
                keys.extend(_split_values(value))
            continue
        keys.extend(_split_values(line))
    return list(dict.fromkeys(value for value in keys if value))


def _split_values(raw: str) -> list[str]:
    values: list[str] = []
    for part in re.split(r"[\n,]+", str(raw or "")):
        cleaned = part.strip().strip('"').strip("'")
        if cleaned:
            values.append(cleaned)
    return values


def _validate_private_file(path: Path) -> None:
    if os.name == "nt" or os.getenv(TEAM1_GEMMA_ALLOW_INSECURE_FILE_ENV, "").strip().lower() in {"1", "true", "yes", "on"}:
        return
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise PermissionError(f"Team 1 Gemma key file must be owner-only chmod 600/400: {path}")


def _private_file_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"checked": False, "passes": False, "mode": ""}
    if os.name == "nt":
        return {"checked": False, "passes": True, "mode": "windows"}
    mode = stat.S_IMODE(path.stat().st_mode)
    return {
        "checked": True,
        "passes": not bool(mode & 0o077),
        "mode": oct(mode),
    }
