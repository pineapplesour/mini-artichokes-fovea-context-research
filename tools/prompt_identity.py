from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def text_sha256(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def canonical_json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def prompt_identity(
    *,
    manifest: dict[str, Any],
    case: dict[str, Any],
    model_input: str,
    builder_id: str,
    builder_source: Path,
) -> dict[str, str]:
    source = Path(builder_source).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    return {
        "sourceItemId": str(case.get("id") or ""),
        "benchmarkId": str(manifest.get("benchmarkId") or ""),
        "sourceBenchmarkId": str(manifest.get("sourceBenchmarkId") or ""),
        "publicPromptSha256": text_sha256(case.get("prompt")),
        "publicCasePayloadSha256": canonical_json_sha256(case),
        "publicManifestCanonicalSha256": canonical_json_sha256(manifest),
        "modelInputSha256": text_sha256(model_input),
        "builderId": str(builder_id),
        "builderSource": str(source),
        "builderSourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }
