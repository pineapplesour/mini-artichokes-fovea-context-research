#!/usr/bin/env python3
"""Split a large file into deterministic chunks with a manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def split_file(source: Path, output_dir: Path, *, chunk_size: int) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    chunks = []
    total = source.stat().st_size
    source_sha256 = hashlib.sha256()

    with source.open("rb") as reader:
        index = 0
        while True:
            data = reader.read(chunk_size)
            if not data:
                break
            source_sha256.update(data)
            chunk_name = f"{source.name}.part{index:04d}"
            chunk_path = output_dir / chunk_name
            chunk_path.write_bytes(data)
            chunks.append(
                {
                    "index": index,
                    "fileName": chunk_name,
                    "sizeBytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
            index += 1

    manifest = {
        "schemaVersion": 1,
        "sourceFileName": source.name,
        "sourceSizeBytes": total,
        "sourceSha256": source_sha256.hexdigest(),
        "chunkSizeBytes": chunk_size,
        "chunkCount": len(chunks),
        "chunks": chunks,
    }
    (output_dir / f"{source.name}.chunks.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--chunk-size-mib", type=int, default=99)
    args = parser.parse_args()

    if args.chunk_size_mib <= 0:
        parser.error("--chunk-size-mib must be positive")
    if not args.source.exists() or not args.source.is_file():
        parser.error(f"source file does not exist: {args.source}")

    manifest = split_file(args.source, args.output_dir, chunk_size=args.chunk_size_mib * 1024 * 1024)
    print(json.dumps({"outputDir": str(args.output_dir), "chunkCount": manifest["chunkCount"], "sourceSha256": manifest["sourceSha256"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
