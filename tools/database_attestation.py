from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


MAX_FULL_HASH_BYTES = 64 * 1024 * 1024
SAMPLE_BYTES = 256 * 1024


def database_identity(path: Path) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"database file not found: {resolved}")
    size = resolved.stat().st_size
    if size <= MAX_FULL_HASH_BYTES:
        digest = hashlib.sha256()
        with resolved.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        identity = {"mode": "full_sha256", "sha256": digest.hexdigest()}
    else:
        offsets = sorted({0, max(0, size // 3), max(0, (2 * size) // 3), max(0, size - SAMPLE_BYTES)})
        digest = hashlib.sha256()
        with resolved.open("rb") as handle:
            for offset in offsets:
                handle.seek(offset)
                chunk = handle.read(SAMPLE_BYTES)
                digest.update(str(offset).encode("ascii"))
                digest.update(b"\0")
                digest.update(chunk)
        identity = {
            "mode": "sampled_sha256_v1",
            "sampleBytes": SAMPLE_BYTES,
            "sampleOffsets": offsets,
            "sha256": digest.hexdigest(),
        }
    return {
        "path": str(resolved),
        "sizeBytes": size,
        "identity": identity,
        "fixtureWarning": size < 1024 * 1024,
    }
