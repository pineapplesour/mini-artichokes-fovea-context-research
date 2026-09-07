#!/usr/bin/env python3
"""Assemble chunks created by split_large_file.py and verify checksums."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def assemble(manifest_path: Path, output_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    base = manifest_path.parent
    output_path.parent.mkdir(parents=True, exist_ok=True)

    source_digest = hashlib.sha256()
    total = 0
    with output_path.open("wb") as writer:
        for chunk in sorted(manifest["chunks"], key=lambda item: item["index"]):
            chunk_path = base / chunk["fileName"]
            data = chunk_path.read_bytes()
            if hashlib.sha256(data).hexdigest() != chunk["sha256"]:
                raise RuntimeError(f"chunk checksum mismatch: {chunk_path}")
            writer.write(data)
            source_digest.update(data)
            total += len(data)

    source_sha256 = source_digest.hexdigest()
    if source_sha256 != manifest["sourceSha256"]:
        raise RuntimeError("assembled source checksum mismatch")
    if total != manifest["sourceSizeBytes"]:
        raise RuntimeError("assembled source size mismatch")
    return {"outputPath": str(output_path), "sizeBytes": total, "sha256": source_sha256}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    result = assemble(args.manifest, args.output)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
