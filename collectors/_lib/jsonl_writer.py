"""Append-safe JSONL writer with text_hash dedup."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Iterable


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def text_hash(text: str) -> str:
    n = normalize_text(text)
    return "sha256:" + hashlib.sha256(n.encode("utf-8")).hexdigest()


class JsonlWriter:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seen_hashes: set[str] = set()
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                h = obj.get("text_hash")
                if h:
                    self._seen_hashes.add(h)
        self._fh = open(self.path, "a", encoding="utf-8")

    def write(self, obj: dict) -> bool:
        h = obj.get("text_hash")
        if h and h in self._seen_hashes:
            return False
        if h:
            self._seen_hashes.add(h)
        self._fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self._fh.flush()
        return True

    def write_many(self, objs: Iterable[dict]) -> int:
        n = 0
        for o in objs:
            if self.write(o):
                n += 1
        return n

    def close(self):
        if self._fh:
            self._fh.close()
            self._fh = None

    def __enter__(self): return self
    def __exit__(self, *a): self.close()
