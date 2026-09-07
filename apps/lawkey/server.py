from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path


PRODUCT_KEY = "lawkey"
PORT = 8037
ORIGINAL_BACKEND_MODULE = "backend.server"

ROOT = Path(__file__).resolve().parents[2]
LAWKEY_SOURCE_ROOT = Path(os.environ.get("UNIVERSAL_LAWKEY_SOURCE_ROOT", ROOT / "external" / "lawkey-original")).resolve()
LAWKEY_FRONTEND_DIST = (LAWKEY_SOURCE_ROOT / "dist").resolve()
DEFAULT_PRECEDENT_DB = Path(
    "/var/lib/universal-artichoke/lawkey/precedents.sqlite3"
)

if not LAWKEY_SOURCE_ROOT.exists():
    raise RuntimeError(f"Lawkey original source snapshot is missing: {LAWKEY_SOURCE_ROOT}")
if not LAWKEY_FRONTEND_DIST.exists():
    raise RuntimeError(f"Lawkey original frontend dist is missing: {LAWKEY_FRONTEND_DIST}")

if "LAWKEY_PRECEDENT_DB_PATH" not in os.environ:
    os.environ["LAWKEY_PRECEDENT_DB_PATH"] = os.environ.get("RELIGION_LAWKEY_DB_PATH", str(DEFAULT_PRECEDENT_DB))
if "LAWKEY_WORKSPACE_SCRIPTS" not in os.environ:
    os.environ["LAWKEY_WORKSPACE_SCRIPTS"] = str(LAWKEY_SOURCE_ROOT / "scripts")

if str(LAWKEY_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(LAWKEY_SOURCE_ROOT))

_backend = importlib.import_module(ORIGINAL_BACKEND_MODULE)

# Keep the original FastAPI app object and original Expo dist. This adapter only
# supplies a stable Universal Artichoke import path and env alias.
app = _backend.app
