#!/usr/bin/env python3
"""Verify the Lawkey original-app adapter preserves original UI and engine."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "integrations" / "lawkey" / "original-app-contract.json"


def build_report() -> dict[str, Any]:
    contract = _read_json(CONTRACT_PATH)
    source_root = ROOT / str(contract.get("sourceRoot") or "")
    dist = source_root / "dist"
    required_files = [
        source_root / "app/index.tsx",
        source_root / "components/lawkey/workspace.tsx",
        source_root / "components/lawkey/progress-strip.tsx",
        source_root / "lib/use-lawkey-job.ts",
        source_root / "lib/universal-ui-kernel.ts",
        source_root / "backend/server.py",
        source_root / "backend/jobs.py",
        dist / "index.html",
    ]
    forbidden_shells = [
        ROOT / "web/lawkey.html",
        ROOT / "web/lawkey-chat.html",
        ROOT / "web/lawkey-chat.js",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required_files if not path.exists()]
    forbidden_present = [str(path.relative_to(ROOT)) for path in forbidden_shells if path.exists()]
    invariants = contract.get("invariants") if isinstance(contract.get("invariants"), dict) else {}
    passes = (
        contract.get("productKey") == "lawkey"
        and contract.get("mode") == "external-original-app"
        and contract.get("serverModule") == "apps.lawkey.server:app"
        and contract.get("defaultPort") == 8037
        and not missing
        and not forbidden_present
        and invariants.get("preserveOriginalDesign") is True
        and invariants.get("preserveOriginalEngine") is True
        and invariants.get("doNotCreateUniversalHtmlShells") is True
        and contract.get("frontend", {}).get("universalKernelAdapter") == "external/lawkey-original/lib/universal-ui-kernel.ts"
        and contract.get("frontend", {}).get("kernelIntegrationStatus")
        == "hook-level-capability-boundary-not-full-shared-browser-runtime"
    )
    return {
        "passes": passes,
        "productKey": contract.get("productKey"),
        "mode": contract.get("mode"),
        "defaultPort": contract.get("defaultPort"),
        "sourceRoot": str(source_root.relative_to(ROOT)) if source_root.exists() else str(source_root),
        "serverModule": contract.get("serverModule"),
        "distExists": dist.exists(),
        "missingRequiredFiles": missing,
        "forbiddenUniversalShellsPresent": forbidden_present,
        "preservesOriginalDesign": invariants.get("preserveOriginalDesign") is True,
        "preservesOriginalEngine": invariants.get("preserveOriginalEngine") is True,
        "kernelIntegrationStatus": contract.get("frontend", {}).get("kernelIntegrationStatus"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print JSON report.")
    parser.add_argument("--output", default="", help="Write JSON report to this path.")
    args = parser.parse_args(argv)
    report = build_report()
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("PASS Lawkey original contract" if report["passes"] else "FAIL Lawkey original contract")
    return 0 if report["passes"] else 1


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


if __name__ == "__main__":
    raise SystemExit(main())
