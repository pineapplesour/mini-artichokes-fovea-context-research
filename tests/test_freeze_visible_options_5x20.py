from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools/freeze_visible_options_5x20.py"
SPEC = importlib.util.spec_from_file_location("freeze_visible", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_visible_freeze_is_exact_public_5x20_with_separate_single_keys(tmp_path: Path) -> None:
    result = MODULE.freeze(REPO_ROOT, tmp_path, MODULE.DEFAULT_SEED)
    assert result["cases"] == 100
    selection = json.loads((tmp_path / "selection_freeze.json").read_text())
    ids: list[str] = []
    for block in selection["blocks"]:
        public = json.loads(Path(block["publicPayload"]).read_text())
        private_path = tmp_path / "private" / f"{block['blockId']}.json"
        private = json.loads(private_path.read_text())
        assert len(public["cases"]) == len(private["answers"]) == 20
        assert all(set(case) == {"id", "prompt"} for case in public["cases"])
        assert all(set(answer) == {"caseId", "correctOptionId"} for answer in private["answers"])
        public_text = json.dumps(public, ensure_ascii=False).lower()
        assert "correctoptionid" not in public_text
        ids.extend(case["id"] for case in public["cases"])
    assert len(ids) == len(set(ids)) == 100
