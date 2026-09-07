"""Focused checks for the canonical information shared by text/image arms."""
from fontTools.ttLib import TTFont
from tools import run_aider_cpp26_image_representation as assay


def test_font_contains_every_official_instruction_character():
    _, _, manifest = assay._load_freeze(assay.DEFAULT_FREEZE)
    chars = set("".join(x["instruction"] for x in manifest["tasks"]))
    cmap = TTFont(assay.FONT).getBestCmap()
    assert not {c for c in chars if not c.isspace() and ord(c) not in cmap}


def test_same_canonical_requirements_and_same_lookup_rules():
    _, task, manifest = assay._load_freeze(assay.DEFAULT_FREEZE)
    text = assay.build_text_prompt(task, manifest)
    image = assay.build_image_prompt(task, manifest)
    shared = assay._protected_rules(task, manifest)
    assert text.startswith(shared) and image.startswith(shared)
    for item in manifest["tasks"]:
        assert item["instruction"] in text
        assert item["instruction"] not in image
    assert "benchmark_manifest.json" in shared
    assert [x["sourceId"] for x in assay._task_index(manifest)] == [
        assay._safe(x["taskId"]) for x in manifest["tasks"]]
