#!/usr/bin/env python3
"""Verify that product pages keep their declared visual reference contracts."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = Path("/mnt/d/Downloads/레퍼런스")
VIEWPORTS = {
    "mobile": {"width": 360, "height": 740},
    "desktop": {"width": 1280, "height": 720},
}


@dataclass(frozen=True)
class ReferenceSpec:
    product: str
    product_files: tuple[str, ...]
    reference_files: tuple[str, ...]
    reference_design_label: str
    required_reference_markers: tuple[str, ...]
    required_product_markers: tuple[str, ...]


SPECS = (
    ReferenceSpec(
        product="islam",
        product_files=("web/islam.html", "web/islam-chat.html"),
        reference_files=("이슬람 참조.html",),
        reference_design_label="Hikmah · 이슬람 지혜 AI",
        required_reference_markers=("bg-pattern", "query-frame", "Cormorant Garamond", "Amiri", "--gold", "--jade"),
        required_product_markers=("bg-pattern", "query-frame", "Hikmah", "source-band", "corpus"),
    ),
    ReferenceSpec(
        product="tcm",
        product_files=("web/tcm.html", "web/tcm-chat.html"),
        reference_files=("한의학참조1.html", "한의학참조2.html"),
        reference_design_label="醫源 · 의원",
        required_reference_markers=("醫源", "celadon", "terracotta", "Noto Serif KR"),
        required_product_markers=("hanui", "醫源", "hanji-grid", "herb-board", "禁忌"),
    ),
    ReferenceSpec(
        product="simli",
        product_files=("web/simli.html", "web/simli-chat.html"),
        reference_files=("심리참조 이중 B · Therapeutic Aurora 사용.html",),
        reference_design_label="B · Therapeutic Aurora",
        required_reference_markers=("마음결", "Unpacking", "a14a2b"),
        required_product_markers=("aurora-app", "aurora-chat-app", "마음결", "therapy-thread", "clinical-card"),
    ),
)


def _read_text(path: Path, *, max_bytes: int | None = None) -> str:
    data = path.read_bytes() if max_bytes is None else path.read_bytes()[:max_bytes]
    return data.decode("utf-8", errors="ignore")


def _marker_report(markers: tuple[str, ...], text: str) -> dict[str, bool]:
    return {marker: marker in text for marker in markers}


def _all_true(mapping: dict[str, bool]) -> bool:
    return all(mapping.values())


def _product_text(spec: ReferenceSpec) -> tuple[bool, str, list[str]]:
    missing: list[str] = []
    chunks: list[str] = []
    for relative in spec.product_files:
        path = ROOT / relative
        if not path.exists():
            missing.append(relative)
            continue
        chunks.append(path.read_text(encoding="utf-8"))
    return not missing, "\n".join(chunks), missing


def _reference_text(spec: ReferenceSpec) -> tuple[bool, str, list[str]]:
    missing: list[str] = []
    chunks: list[str] = []
    for name in spec.reference_files:
        path = REFERENCE_ROOT / name
        if not path.exists():
            missing.append(name)
            continue
        # Large bundled reference files can be tens of MB. The markers we need
        # are intentionally near the document shell or bundler metadata.
        chunks.append(_read_text(path, max_bytes=2_000_000))
    return not missing, "\n".join(chunks), missing


def product_report(spec: ReferenceSpec, dry_run: bool) -> dict[str, Any]:
    if dry_run:
        return {
            "product": spec.product,
            "passes": True,
            "dryRun": True,
            "productFiles": list(spec.product_files),
            "referenceFiles": list(spec.reference_files),
            "referenceDesignLabel": spec.reference_design_label,
            "requiredReferenceMarkers": list(spec.required_reference_markers),
            "requiredProductMarkers": list(spec.required_product_markers),
            "referenceFilesExist": True,
            "productFilesExist": True,
            "referenceMarkersPresent": {marker: True for marker in spec.required_reference_markers},
            "productMarkersPresent": {marker: True for marker in spec.required_product_markers},
        }

    references_exist, reference_text, missing_references = _reference_text(spec)
    products_exist, product_text, missing_products = _product_text(spec)
    reference_markers = _marker_report(spec.required_reference_markers, reference_text)
    product_markers = _marker_report(spec.required_product_markers, product_text)
    passes = references_exist and products_exist and _all_true(reference_markers) and _all_true(product_markers)
    return {
        "product": spec.product,
        "passes": passes,
        "dryRun": False,
        "productFiles": list(spec.product_files),
        "referenceFiles": list(spec.reference_files),
        "referenceDesignLabel": spec.reference_design_label,
        "requiredReferenceMarkers": list(spec.required_reference_markers),
        "requiredProductMarkers": list(spec.required_product_markers),
        "referenceFilesExist": references_exist,
        "productFilesExist": products_exist,
        "missingReferenceFiles": missing_references,
        "missingProductFiles": missing_products,
        "referenceMarkersPresent": reference_markers,
        "productMarkersPresent": product_markers,
    }


def build_report(dry_run: bool) -> dict[str, Any]:
    products = [product_report(spec, dry_run) for spec in SPECS]
    return {
        "passes": all(item["passes"] for item in products),
        "dryRun": dry_run,
        "referenceRoot": str(REFERENCE_ROOT),
        "viewports": VIEWPORTS,
        "contract": {
            "name": "reference-visual-contract",
            "scope": "static reference file mapping and product visual markers",
            "note": "This is a drift gate, not a pixel-perfect visual diff.",
        },
        "products": products,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="write JSON to stdout")
    parser.add_argument("--dry-run", action="store_true", help="emit contract without reading files")
    parser.add_argument("--output", help="write JSON report to this file")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_report(args.dry_run)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif report["passes"]:
        print("reference visual contract PASS")
    else:
        print("reference visual contract FAIL")
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
