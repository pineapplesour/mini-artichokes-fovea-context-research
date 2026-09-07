"""Deterministic text-to-PNG pages and one optional Luna image-read smoke.
The image is a presentation of the exact text, never a replacement for the
plain prompt.  Attached files are bind-mounted read-only into the existing
isolated Codex adapter; the smoke disables solver tools and is nonbenchmark.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile
from typing import Any
from PIL import Image, ImageDraw, ImageFont
from tools import run_aider_hidden20_arm as isolated
from tools import run_classeval_source_overlap as base
from tools import run_classeval_text_overlap as text_runner
MODEL, EFFORT, TIMEOUT = "gpt-5.6-luna", "medium", 120
DEFAULT_FONT = Path("/home/pineapple/.local/share/fonts/NanumGothic-Regular.ttf")
SMOKE_ID = "image-read-smoke-20260906"
SMOKE_TEXT = "\n".join((
    "IMG-READ-ALPHA | 식별자 O(대문자 오) != 0(숫자 영); not 0",
    "line-02: 보존 / 삭제 아님 (NOT-KEEP) | l/1/I are distinct",
    "line-03: x != y | 절대 같지 않음 | C++ -> C--",
    "line-04: [A] -> [B] | 0O Oo O0 | 혼동 금지",
    "line-05: 끝표식: 유지하세요, 지우지 마세요. ID=AB-01-lI1",
))
SMOKE_PROMPT = f"""Read the attached rendered page and return exactly one JSON object.
The plain text below is authoritative and is also rendered in the image.
Schema: {{\"source_id\": string, \"lines\": five exact strings,
\"source_sha256\": string, \"observation\": string}}.
Copy the five displayed lines exactly, including punctuation. Do not use tools,
edit files, search externally, or infer anything beyond the page.
Plain text (authoritative):
{SMOKE_TEXT}
"""
def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")[:80] or "source"
def _font(path: Path, size: int = 24):
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.load_default()
def _segments(line: str, font, max_width: int) -> list[tuple[int, int, str]]:
    if not line:
        return [(0, 0, "")]
    result, start = [], 0
    while start < len(line):
        end = start + 1
        while end <= len(line) and font.getlength(line[start:end]) <= max_width:
            end += 1
        end = max(start + 1, end - 1)
        result.append((start, end, line[start:end]))
        start = end
    return result
def render_text_pages(text: str, source_id: str, output_dir: Path, *, font_path: Path = DEFAULT_FONT,
                      width: int = 1800, rows_per_page: int = 42) -> dict[str, Any]:
    """Render all characters with stable source-line/character mappings."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    source_id = _safe_id(source_id)
    font = _font(Path(font_path))
    margin, header, row_height = 48, 54, 34
    rows: list[dict[str, Any]] = []
    for line_no, raw in enumerate(text.split("\n"), 1):
        display = raw[:-1] if raw.endswith("\r") else raw
        for segment_no, (start, end, chunk) in enumerate(_segments(display, font, width - 2 * margin - 110)):
            rows.append({"sourceLine": line_no, "segment": segment_no,
                         "charStart": start, "charEnd": end, "text": chunk})
    page_count = max(1, (len(rows) + rows_per_page - 1) // rows_per_page)
    pages = []
    for page_no in range(page_count):
        page_rows = rows[page_no * rows_per_page:(page_no + 1) * rows_per_page]
        image = Image.new("RGB", (width, margin + header + row_height * rows_per_page + margin), "white")
        draw = ImageDraw.Draw(image)
        draw.text((margin, margin // 2), f"{source_id} | page {page_no + 1}/{page_count}",
                  fill="black", font=font)
        for row_no, row in enumerate(page_rows):
            y = margin + header + row_no * row_height
            draw.text((margin, y), f"{row['sourceLine']:04d}| {row['text']}", fill="black", font=font)
        path = output_dir / f"{source_id}-p{page_no + 1:03d}.png"
        image.save(path, format="PNG", optimize=False, compress_level=9)
        path.chmod(0o444)
        pages.append({"path": str(path.resolve()), "sha256": _sha_bytes(path.read_bytes()),
                      "rows": page_rows})
    manifest = {"schemaVersion": 1, "sourceId": source_id, "textSha256": _sha_bytes(text.encode()),
                "textChars": len(text), "font": str(Path(font_path)), "width": width,
                "rowsPerPage": rows_per_page, "pages": pages}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return manifest
def _image_args(argv: list[str], image_paths: list[Path]) -> list[str]:
    """Apply the frozen text-runner tool-disable transform and readonly binds."""
    command = text_runner.no_tool_command(list(argv))
    proc = command.index("--proc")
    mounts, attached = ["--dir", "/tmp/image-input"], []
    for index, path in enumerate(image_paths):
        path = Path(path).resolve(strict=True)
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"image must be a non-symlink file: {path}")
        target = f"/tmp/image-input/{index:03d}-{_safe_id(path.name)}"
        mounts += ["--ro-bind", str(path), target]
        attached += ["--image", target]
    command[proc:proc] = mounts
    stdin_index = len(command) - 1 - command[::-1].index("-")
    command[stdin_index:stdin_index] = attached
    return command
def _events(stdout: str) -> list[dict]:
    result = []
    for line in stdout.splitlines():
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                result.append(value)
        except json.JSONDecodeError:
            pass
    return result
def _observed(raw: str) -> Any:
    match = re.search(r"\{.*\}", raw, flags=re.S)
    if not match:
        return {"parseError": "no JSON object", "raw": raw}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        return {"parseError": type(exc).__name__, "raw": raw}
def run_smoke(run_root: Path) -> dict[str, Any]:
    run_root = Path(run_root).resolve()
    run_root.mkdir(parents=True, exist_ok=False)
    images = run_root / "images"
    manifest = render_text_pages(SMOKE_TEXT, SMOKE_ID, images)
    work, artifact = run_root / "work", run_root / "artifact"
    work.mkdir(); artifact.mkdir()
    (run_root / "prompt.txt").write_text(SMOKE_PROMPT, encoding="utf-8")
    base.write_json(run_root / "contract.json", {"kind": "nonbenchmark-image-read-smoke",
        "model": MODEL, "effort": EFFORT, "timeoutSeconds": TIMEOUT,
        "solverTools": False, "sourceId": SMOKE_ID, "imageManifestSha256": _sha_bytes(
            (images / "manifest.json").read_bytes()), "imagePaths": [p["path"] for p in manifest["pages"]]})
    adapter = base.IsolatedCodexAdapter(Path("/home/pineapple/.codex-new-account"), MODEL, EFFORT, TIMEOUT)
    real_process = isolated.run_process
    captured: dict[str, Any] = {}
    try:
        def wrapped(argv, **kwargs):
            transformed = _image_args(argv, [Path(p["path"]) for p in manifest["pages"]])
            captured["argv"] = ["<redacted-auth-path>" if "auth.json" in str(x) else x
                                for x in transformed]
            base.write_json(artifact / "injected_argv.json", {"argv": captured["argv"],
                                                               "imagesReadonly": True, "toolsDisabled": True})
            return real_process(transformed, **kwargs)
        isolated.run_process = wrapped
        result = adapter.run(work, SMOKE_PROMPT, artifact, SMOKE_ID)
    finally:
        isolated.run_process = real_process
    events = _events(result.stdout)
    completed = [item for item in events if item.get("type") == "turn.completed"]
    raw = (artifact / "last_message.txt").read_text(encoding="utf-8") if (artifact / "last_message.txt").is_file() else ""
    expected = {"source_id": SMOKE_ID, "lines": SMOKE_TEXT.split("\n"),
                "source_sha256": _sha_bytes(SMOKE_TEXT.encode())}
    observed = _observed(raw)
    comparison = {"expected": expected, "observed": observed,
                  "match": isinstance(observed, dict) and all(observed.get(k) == v for k, v in expected.items())}
    receipt = {"model": MODEL, "effort": EFFORT, "timeoutSeconds": TIMEOUT,
               "exit_code": result.exit_code, "timed_out": result.timed_out,
               "duration_seconds": result.duration_seconds,
               "usage": completed[-1].get("usage") if completed else None,
               "imageManifestSha256": _sha_bytes((images / "manifest.json").read_bytes()),
               "sourceSha256": expected["source_sha256"], "expectedVsObserved": comparison,
               "solverToolsDisabled": True, "nonbenchmark": True}
    base.write_json(run_root / "receipt.json", receipt)
    return {"runRoot": str(run_root), "receipt": receipt, "comparison": comparison,
            "imagePaths": [p["path"] for p in manifest["pages"]]}
def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--execute", action="store_true", help="make the one nonbenchmark Luna call")
    args = parser.parse_args(argv)
    if not args.execute:
        with tempfile.TemporaryDirectory(prefix="image-text-dry-") as temp:
            manifest = render_text_pages(SMOKE_TEXT, SMOKE_ID, Path(temp) / "images")
            print(json.dumps({"mode": "dry-run", "sourceSha256": manifest["textSha256"],
                              "pages": len(manifest["pages"]), "font": manifest["font"]}, ensure_ascii=False))
        return 0
    if args.run_root is None:
        parser.error("--run-root is required with --execute")
    print(json.dumps(run_smoke(args.run_root), ensure_ascii=False), flush=True)
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
