"""Blind, nonbenchmark text-to-image input calibration for Luna.

The source is rendered host-side and attached read-only.  The prompt contains
only a source identifier and output schema, so answer fields require image
reading.  This is an operational smoke, not a benchmark or OCR threshold.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile
from typing import Any

from tools import run_aider_hidden20_arm as isolated
from tools import run_classeval_source_overlap as base
from tools import run_classeval_text_overlap as text_runner
from tools.run_classeval_image_text_smoke import render_text_pages, _events, _observed, _image_args

MODEL, EFFORT, TIMEOUT = "gpt-5.6-luna", "medium", 120
SOURCE_ID = "image-read-blind-smoke-20260906"
FONT = Path("/home/pineapple/.local/share/fonts/NanumGothic-Regular.ttf")
TARGET_LINES = (
    "IMG-READ-ALPHA | 식별자 O(대문자 오) != 0(숫자 영); not 0",
    "line-02: 보존 / 삭제 아님 (NOT-KEEP) | l/1/I are distinct",
    "line-03: x != y | 절대 같지 않음 | C++ -> C--",
    "line-04: [A] -> [B] | 0O Oo O0 | 혼동 금지",
    "line-05: 끝표식: 유지하세요, 지우지 마세요. ID=AB-01-lI1",
)
FILLER_LINES = tuple(
    f"calibration-{n:02d} | neutral filler row; retain this row unchanged."
    for n in range(1, 35)
)
SOURCE_TEXT = "\n".join(TARGET_LINES + FILLER_LINES)
PROMPT = f"""Read the single attached rendered page and return exactly one JSON object.
The page header contains source ID {SOURCE_ID}. After the header, copy the first
five non-header rows into line_1 through line_5 exactly, preserving Unicode,
case, whitespace, punctuation, and symbols. Return this schema only:
{{"source_id": "{SOURCE_ID}", "line_1": string, "line_2": string,
"line_3": string, "line_4": string, "line_5": string,
"negation_1": "yes" or "no", "negation_2": "yes" or "no",
"negation_3": "yes" or "no"}}.
For each negation field, answer yes only when the corresponding copied row
explicitly expresses a negation or rejection. Do not use tools, edit files,
search externally, or return markdown. The neutral rows after the five target
rows are calibration filler and should not be returned.
"""
EXPECTED = {"source_id": SOURCE_ID,
            **{f"line_{n}": line for n, line in enumerate(TARGET_LINES, 1)},
            **{f"negation_{n}": "yes" for n in range(1, 4)}}


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def reconstruct_manifest_text(manifest: dict[str, Any]) -> str:
    """Rebuild source text from renderer rows, including wrapped segments."""
    rows = [row for page in manifest["pages"] for row in page["rows"]]
    rows.sort(key=lambda row: (row["sourceLine"], row["segment"]))
    lines: list[str] = []
    for line_no in range(1, max(row["sourceLine"] for row in rows) + 1):
        lines.append("".join(row["text"] for row in rows if row["sourceLine"] == line_no))
    return "\n".join(lines)


def assert_blind_prompt(prompt: str = PROMPT, source_text: str = SOURCE_TEXT,
                        source_id: str = SOURCE_ID) -> None:
    """Reject accidental answer/source/hash leakage before any model call."""
    if source_id not in prompt:
        raise AssertionError("source ID missing from prompt")
    if _sha_bytes(source_text.encode()) in prompt:
        raise AssertionError("source hash leaked into prompt")
    leaked = [line for line in source_text.splitlines() if line and line in prompt]
    if leaked:
        raise AssertionError(f"source answer leaked into prompt: {leaked[0]!r}")


def _parse_fields(observed: Any) -> dict[str, Any]:
    return observed if isinstance(observed, dict) else {}


def run_smoke(run_root: Path) -> dict[str, Any]:
    run_root = Path(run_root).resolve()
    run_root.mkdir(parents=True, exist_ok=False)
    assert_blind_prompt()
    images = run_root / "images"
    manifest = render_text_pages(SOURCE_TEXT, SOURCE_ID, images, font_path=FONT,
                                 width=1800, rows_per_page=42)
    manifest_text_ok = reconstruct_manifest_text(manifest) == SOURCE_TEXT
    prompt_sha = _sha_bytes(PROMPT.encode())
    code_sha = _sha_bytes(Path(__file__).read_bytes())
    source_sha = _sha_bytes(SOURCE_TEXT.encode())
    image_manifest_sha = _sha_bytes((images / "manifest.json").read_bytes())
    work, artifact = run_root / "work", run_root / "artifact"
    work.mkdir(); artifact.mkdir()
    (run_root / "prompt.txt").write_text(PROMPT, encoding="utf-8")
    (artifact / "prompt.sha256").write_text(prompt_sha + "\n")
    (artifact / "code.sha256").write_text(code_sha + "\n")
    base.write_json(run_root / "contract.json", {
        "kind": "nonbenchmark-blind-image-read-smoke", "model": MODEL,
        "effort": EFFORT, "timeoutSeconds": TIMEOUT, "solverTools": False,
        "sourceId": SOURCE_ID, "sourceSha256": source_sha,
        "promptSha256": prompt_sha, "codeSha256": code_sha,
        "imageManifestSha256": image_manifest_sha, "manifestTextLossless": manifest_text_ok,
        "imagePaths": [p["path"] for p in manifest["pages"]],
    })
    adapter = base.IsolatedCodexAdapter(Path("/home/pineapple/.codex-new-account"),
                                         MODEL, EFFORT, TIMEOUT)
    real_process = isolated.run_process
    try:
        def wrapped(argv, **kwargs):
            transformed = _image_args(argv, [Path(p["path"]) for p in manifest["pages"]])
            redacted = ["<redacted-auth-path>" if "auth.json" in str(x) else x
                        for x in transformed]
            image_args = [redacted[i + 1] for i, value in enumerate(redacted[:-1])
                          if value == "--image"]
            base.write_json(artifact / "injected_argv.json", {
                "argv": redacted, "imageArgs": image_args,
                "imagesReadonly": True, "toolsDisabled": True})
            return real_process(transformed, **kwargs)
        isolated.run_process = wrapped
        result = adapter.run(work, PROMPT, artifact, SOURCE_ID)
    finally:
        isolated.run_process = real_process
    events = _events(result.stdout)
    completed = [item for item in events if item.get("type") == "turn.completed"]
    raw = (artifact / "last_message.txt").read_text(encoding="utf-8") if (
        artifact / "last_message.txt").is_file() else ""
    observed = _parse_fields(_observed(raw))
    field_matches = {key: observed.get(key) == value for key, value in EXPECTED.items()
                     if key in observed or key == "source_id"}
    semantic = {f"negation_{n}": str(observed.get(f"negation_{n}", "")).strip().lower() == "yes"
                for n in range(1, 4)}
    receipt = {
        "model": MODEL, "effort": EFFORT, "timeoutSeconds": TIMEOUT,
        "exit_code": result.exit_code, "timed_out": result.timed_out,
        "duration_seconds": result.duration_seconds,
        "usage": completed[-1].get("usage") if completed else None,
        "turnCompletedCount": len(completed), "sourceSha256": source_sha,
        "promptSha256": prompt_sha, "codeSha256": code_sha,
        "imageManifestSha256": image_manifest_sha, "manifestTextLossless": manifest_text_ok,
        "promptAnswerLeak": False, "solverToolsDisabled": True, "nonbenchmark": True,
        "expectedVsObserved": {"expected": EXPECTED, "observed": observed,
                                "fieldMatches": field_matches,
                                "semanticNegationCorrect": semantic,
                                "allRequiredFieldsMatch": all(field_matches.values()) and
                                len(field_matches) == len(EXPECTED)},
    }
    base.write_json(run_root / "receipt.json", receipt)
    return {"runRoot": str(run_root), "receipt": receipt,
            "imagePaths": [p["path"] for p in manifest["pages"]]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute:
        with tempfile.TemporaryDirectory(prefix="image-text-blind-dry-") as temp:
            manifest = render_text_pages(SOURCE_TEXT, SOURCE_ID, Path(temp) / "images",
                                         font_path=FONT, width=1800, rows_per_page=42)
            assert_blind_prompt()
            print(json.dumps({"mode": "dry-run", "sourceId": SOURCE_ID,
                              "sourceSha256": manifest["textSha256"],
                              "promptHasAnswers": False,
                              "manifestTextLossless": reconstruct_manifest_text(manifest) == SOURCE_TEXT,
                              "pages": len(manifest["pages"]), "rows": len(manifest["pages"][0]["rows"])},
                             ensure_ascii=False))
        return 0
    if args.run_root is None:
        parser.error("--run-root is required with --execute")
    print(json.dumps(run_smoke(args.run_root), ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
