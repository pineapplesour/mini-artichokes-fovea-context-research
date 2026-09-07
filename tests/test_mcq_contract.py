import json
from pathlib import Path

import pytest

from tools.run_unified_mcq_benchmark import build_mcq_query, extract_option_ids


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        (
            "2. Which choice is correct?\n① alpha\n② beta\n③ gamma\n④ delta\n⑤ epsilon",
            ["1", "2", "3", "4", "5"],
        ),
        (
            "34. Which choice is correct?\n0) alpha\n@ beta\n6 gamma\n0) delta\n@ epsilon",
            ["1", "2", "3", "4", "5"],
        ),
    ],
)
def test_option_ids_exclude_the_question_number_and_canonicalize_ocr_markers_by_order(prompt, expected):
    assert extract_option_ids(prompt) == expected


def test_mcq_query_explains_order_only_as_a_domain_neutral_format_contract():
    query = build_mcq_query(
        "34. Which choice is correct?\n0) alpha\n@ beta\n6 gamma\n0) delta\n@ epsilon",
        language="ko",
        option_ids=["1", "2", "3", "4", "5"],
    )

    assert "위에서 아래 순서" in query
    lowered = query.lower()
    assert "tcm" not in lowered
    assert "한의" not in lowered
    assert "islam" not in lowered
    assert "기독" not in lowered


def test_checked_in_tcm_unique_manifest_has_five_canonical_option_ids_per_case():
    manifest = json.loads(
        (ROOT / "benchmarks" / "unified" / "mcq_tcm_kuksiwon81_unique92.public.json").read_text(
            encoding="utf-8"
        )
    )

    invalid = {
        str(case.get("id") or ""): extract_option_ids(
            str(case.get("prompt") or ""),
            case.get("options") if isinstance(case.get("options"), list) else None,
        )
        for case in manifest.get("cases", [])
        if extract_option_ids(
            str(case.get("prompt") or ""),
            case.get("options") if isinstance(case.get("options"), list) else None,
        )
        != ["1", "2", "3", "4", "5"]
    }

    assert invalid == {}


def test_every_checked_in_mcq_gold_id_is_in_the_public_option_contract():
    invalid: dict[str, dict[str, object]] = {}
    for public_path in sorted((ROOT / "benchmarks" / "unified").glob("mcq_*.public.json")):
        private_path = public_path.with_name(public_path.name.replace(".public.json", ".private.json"))
        public = json.loads(public_path.read_text(encoding="utf-8"))
        private = json.loads(private_path.read_text(encoding="utf-8"))
        gold_by_case = {
            str(item.get("caseId") or ""): str(item.get("correctOptionId") or "").upper()
            for item in private.get("answers", [])
        }
        for case in public.get("cases", []):
            case_id = str(case.get("id") or "")
            ids = extract_option_ids(
                str(case.get("prompt") or ""),
                case.get("options") if isinstance(case.get("options"), list) else None,
            )
            gold = gold_by_case.get(case_id, "")
            if len(ids) < 2 or not gold or gold not in ids:
                invalid[f"{public_path.name}:{case_id}"] = {"optionIds": ids, "gold": gold}

    assert invalid == {}
