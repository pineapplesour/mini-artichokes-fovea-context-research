from __future__ import annotations

import html
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import fitz  # type: ignore

from .config import PROJECT_ROOT

CHROMIUM_PRINT_PATH = Path("/usr/local/bin/chromium-headless-playwright")
KORDOC_HELPER_PATH = PROJECT_ROOT / "scripts" / "markdown_to_hwpx.mjs"


def _slugify(text: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z가-힣._-]+", "-", text).strip("-._")
    return slug[:80] or "document"


def _inline_markdown_to_html(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*(.+?)\*", r"<em>\1</em>", escaped)
    escaped = re.sub(r"`(.+?)`", r"<code>\1</code>", escaped)
    return escaped


def markdown_to_legal_html(markdown_text: str, *, title: str, mode: str) -> str:
    lines = markdown_text.replace("\r\n", "\n").split("\n")
    body_parts: list[str] = []
    paragraph_lines: list[str] = []
    list_items: list[str] = []
    list_tag: str | None = None

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        if paragraph_lines:
            text = " ".join(line.strip() for line in paragraph_lines if line.strip())
            if text:
                body_parts.append(f"<p>{_inline_markdown_to_html(text)}</p>")
            paragraph_lines = []

    def flush_list() -> None:
        nonlocal list_items, list_tag
        if list_items and list_tag:
            items = "".join(f"<li>{_inline_markdown_to_html(item)}</li>" for item in list_items)
            body_parts.append(f"<{list_tag}>{items}</{list_tag}>")
        list_items = []
        list_tag = None

    heading_re = re.compile(r"^(#{1,6})\s+(.*)$")
    ordered_re = re.compile(r"^\d+\.\s+(.*)$")
    unordered_re = re.compile(r"^[-*]\s+(.*)$")

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            flush_list()
            continue
        heading_match = heading_re.match(stripped)
        if heading_match:
            flush_paragraph()
            flush_list()
            level = min(len(heading_match.group(1)) + 1, 6)
            body_parts.append(f"<h{level}>{_inline_markdown_to_html(heading_match.group(2).strip())}</h{level}>")
            continue
        ordered_match = ordered_re.match(stripped)
        if ordered_match:
            flush_paragraph()
            if list_tag not in (None, "ol"):
                flush_list()
            list_tag = "ol"
            list_items.append(ordered_match.group(1).strip())
            continue
        unordered_match = unordered_re.match(stripped)
        if unordered_match:
            flush_paragraph()
            if list_tag not in (None, "ul"):
                flush_list()
            list_tag = "ul"
            list_items.append(unordered_match.group(1).strip())
            continue
        flush_list()
        paragraph_lines.append(stripped)

    flush_paragraph()
    flush_list()

    mode_label = "문서 결과" if mode == "document" else "질문 응답"
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <style>
    @page {{
      size: A4;
      margin: 24mm 20mm 24mm 24mm;
    }}
    html, body {{
      background: #f3f4f6;
      color: #111111;
      margin: 0;
      padding: 0;
      font-family: "Malgun Gothic", "Apple SD Gothic Neo", sans-serif;
    }}
    body {{
      padding: 18mm 0;
    }}
    .page {{
      box-sizing: border-box;
      width: 210mm;
      min-height: 297mm;
      margin: 0 auto;
      background: #ffffff;
      border: 1px solid rgba(17, 17, 17, 0.08);
      box-shadow: 0 18px 48px rgba(17, 17, 17, 0.10);
      padding: 24mm 20mm 24mm 24mm;
    }}
    .eyebrow {{
      font-size: 10px;
      letter-spacing: 0.24em;
      text-transform: uppercase;
      color: #667085;
      margin-bottom: 12px;
    }}
    h1, h2, h3, h4, h5, h6 {{
      font-family: "Batang", "Times New Roman", serif;
      color: #111111;
      margin: 0;
    }}
    h1 {{
      font-size: 28px;
      line-height: 1.2;
      margin-bottom: 10px;
    }}
    h2 {{
      font-size: 19px;
      line-height: 1.4;
      margin-top: 20px;
      margin-bottom: 10px;
    }}
    h3, h4, h5, h6 {{
      font-size: 16px;
      line-height: 1.45;
      margin-top: 16px;
      margin-bottom: 8px;
    }}
    p, li {{
      font-size: 13.5px;
      line-height: 1.9;
      letter-spacing: -0.01em;
    }}
    p {{
      margin: 0 0 10px;
      text-align: justify;
    }}
    ul, ol {{
      margin: 0 0 12px 20px;
      padding: 0;
    }}
    li + li {{
      margin-top: 4px;
    }}
    code {{
      font-family: "Consolas", "SFMono-Regular", monospace;
      font-size: 0.92em;
      background: #f3f4f6;
      border-radius: 4px;
      padding: 0.1em 0.35em;
    }}
    .body {{
      margin-top: 18px;
    }}
  </style>
</head>
<body>
  <main class="page">
    <div class="eyebrow">{html.escape(mode_label)}</div>
    <h1>{html.escape(title)}</h1>
    <div class="body">
      {''.join(body_parts)}
    </div>
  </main>
</body>
</html>
"""


def write_markdown_and_html_exports(
    markdown_text: str,
    *,
    exports_dir: Path,
    title: str,
    mode: str,
    stem: str = "final_document",
) -> dict[str, Path]:
    exports_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = exports_dir / f"{stem}.md"
    html_path = exports_dir / f"{stem}.html"
    markdown_path.write_text(markdown_text, encoding="utf-8")
    html_path.write_text(markdown_to_legal_html(markdown_text, title=title, mode=mode), encoding="utf-8")
    return {
        "markdown_path": markdown_path,
        "html_path": html_path,
    }


def export_hwpx_from_markdown(markdown_path: Path, hwpx_path: Path) -> Path:
    hwpx_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["node", str(KORDOC_HELPER_PATH), "--in", str(markdown_path), "--out", str(hwpx_path)],
        check=True,
        cwd=str(PROJECT_ROOT),
    )
    return hwpx_path


def export_pdf_from_html(html_path: Path, pdf_path: Path) -> Path:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            str(CHROMIUM_PRINT_PATH),
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            "--print-to-pdf-no-header",
            f"--print-to-pdf={pdf_path}",
            html_path.as_uri(),
        ],
        check=True,
    )
    return pdf_path


def render_pdf_preview_images(pdf_path: Path, preview_dir: Path, *, max_pages: int = 4) -> list[Path]:
    preview_dir.mkdir(parents=True, exist_ok=True)
    for stale_image in preview_dir.glob("*.png"):
        stale_image.unlink()
    written: list[Path] = []
    document = fitz.open(str(pdf_path))
    try:
        for page_index in range(min(document.page_count, max_pages)):
            page = document.load_page(page_index)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(1.7, 1.7), alpha=False)
            out_path = preview_dir / f"page-{page_index + 1:03d}.png"
            pixmap.save(out_path)
            written.append(out_path)
    finally:
        document.close()
    return written


def build_export_artifacts(
    markdown_text: str,
    *,
    variant_dir: Path,
    title: str,
    mode: str,
    stem: str = "final_document",
) -> dict[str, Any]:
    exports_dir = variant_dir / "exports"
    preview_dir = exports_dir / "preview"
    written = write_markdown_and_html_exports(markdown_text, exports_dir=exports_dir, title=title, mode=mode, stem=stem)

    hwpx_path = exports_dir / f"{stem}.hwpx"
    pdf_path = exports_dir / f"{stem}.pdf"
    preview_paths: list[Path] = []
    errors: list[str] = []

    try:
        export_hwpx_from_markdown(written["markdown_path"], hwpx_path)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"hwpx_export_failed: {type(exc).__name__}: {exc}")

    try:
        export_pdf_from_html(written["html_path"], pdf_path)
        preview_paths = render_pdf_preview_images(pdf_path, preview_dir)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"pdf_export_failed: {type(exc).__name__}: {exc}")

    payload = {
        "markdown_path": str(written["markdown_path"]),
        "html_path": str(written["html_path"]),
        "hwpx_path": str(hwpx_path) if hwpx_path.exists() else "",
        "pdf_path": str(pdf_path) if pdf_path.exists() else "",
        "preview_image_paths": [str(path) for path in preview_paths if path.exists()],
        "errors": errors,
    }
    (exports_dir / "exports.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
