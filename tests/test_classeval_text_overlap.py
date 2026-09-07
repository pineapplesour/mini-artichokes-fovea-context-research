import pytest

from tools import run_classeval_text_overlap as text


def test_cli_keeps_model_and_disables_execution_tools():
    argv = ["codex", "exec", "--sandbox", "danger-full-access", "--model", "gpt-5.6-luna",
            "--config", "features.shell_tool=true", "--json", "-"]
    changed = text.no_tool_command(argv)
    assert argv[argv.index("--sandbox") + 1] == "danger-full-access"
    assert changed[changed.index("--sandbox") + 1] == "read-only"
    assert "features.shell_tool=false" in changed
    assert "features.code_mode.enabled=false" in changed
    assert changed[changed.index("--model") + 1] == "gpt-5.6-luna"
    assert changed[-1] == "-"


def test_extraction_never_repairs_a_truncated_program():
    assert text.extract_code("```python\nclass X:\n    pass\n```") == "class X:\n    pass\n"
    assert text.extract_code("class X: pass") == "class X: pass\n"
    with pytest.raises((SyntaxError, ValueError)):
        text.extract_code("```python\nclass X:\n")


def test_repair_prompt_does_not_encode_policy_label():
    row = {"skeleton": "class X: pass"}
    p = {"source": "class X: pass", "valid": True, "report": {"passed": False, "cases": {}}}
    assert text.repair_prompt(row, [p, p], p) == text.repair_prompt(row, [p, p], dict(p))
    assert "overlap" not in text.repair_prompt(row, [p, p], p).lower()


def test_common_signature_format_avoids_author_line_based_decorator_trap():
    for prompt in (text.GENERATE, text.REPAIR):
        assert "write every def signature on ONE" in prompt
        assert "with self or cls on that same line" in prompt
    row = {"_dataset": "classeval-pro"}
    single = "class X:\n    def __init__(self, value=3):\n        self.value = value\n"
    multiline = "class X:\n    def __init__(\n        self, value=3\n    ):\n        self.value = value\n"
    namespace = {}
    exec(text.base.evaluation_source(row, single), namespace)
    assert namespace["X"]().value == 3
    # Preserve and expose the author's actual behavior; do not patch scoring.
    assert "@staticmethod" in text.base.evaluation_source(row, multiline)
