from pathlib import Path

import pytest

from tools.codex_home_failover import CodexHomeFailoverClient, load_unique_homes, resolve_codex_home_paths


def _home(tmp_path: Path, name: str, auth: str) -> Path:
    path = tmp_path / name
    path.mkdir()
    (path / "auth.json").write_text(auth, encoding="utf-8")
    return path


def test_client_rotates_only_for_quota_and_persists_nonsensitive_state(tmp_path):
    homes = load_unique_homes([
        _home(tmp_path, ".codex-7", "auth-seven"),
        _home(tmp_path, ".codex-6", "auth-six"),
    ])
    calls = []

    class FakeClient:
        def __init__(self, **kwargs):
            self.home = Path(__import__("os").environ["CODEX_HOME"]).name

        def complete(self, messages, *, model):
            calls.append(self.home)
            if self.home == ".codex-7":
                raise RuntimeError("weekly usage limit reached")
            return '{"ok":true}'

        def consume_last_call_trace(self):
            return {"tokenUsage": {"totalTokens": 5}}

    state_path = tmp_path / "state.json"
    client = CodexHomeFailoverClient(
        homes=homes,
        state_path=state_path,
        client_factory=FakeClient,
    )

    assert client.complete([{"role": "user", "content": "x"}], model="gpt-5.6-luna") == '{"ok":true}'
    assert calls == [".codex-7", ".codex-6"]
    state_text = state_path.read_text(encoding="utf-8")
    assert "auth-seven" not in state_text
    assert "auth-six" not in state_text
    assert '"quotaFailovers": 1' in state_text
    assert client.consume_last_call_trace()["codexHomeAlias"] == "codex-6"


def test_client_does_not_rotate_for_nonquota_error(tmp_path):
    homes = load_unique_homes([
        _home(tmp_path, ".codex-7", "auth-seven"),
        _home(tmp_path, ".codex-6", "auth-six"),
    ])
    calls = []

    class FakeClient:
        def __init__(self, **kwargs):
            self.home = Path(__import__("os").environ["CODEX_HOME"]).name

        def complete(self, messages, *, model):
            calls.append(self.home)
            raise RuntimeError("invalid response schema")

        def consume_last_call_trace(self):
            return {}

    client = CodexHomeFailoverClient(homes=homes, client_factory=FakeClient)
    with pytest.raises(RuntimeError, match="invalid response schema"):
        client.complete([{"role": "user", "content": "x"}], model="gpt-5.6-luna")
    assert calls == [".codex-7"]
    assert client.state["currentHomeIndex"] == 0


def test_shallow_discovery_prefers_requested_account_order(tmp_path):
    for name in (".codex-2", ".codex-new-account", ".codex-6", ".codex-7", ".codex-profile"):
        _home(tmp_path, name, name)
    (tmp_path / ".codex-no-auth").mkdir()
    explicit = tmp_path / ".codex-2"

    paths = resolve_codex_home_paths([explicit], tmp_path)

    assert [path.name for path in paths] == [
        ".codex-2",
        ".codex-7",
        ".codex-6",
        ".codex-new-account",
        ".codex-profile",
    ]


def test_client_forwards_tool_enabled_agent_configuration(tmp_path):
    homes = load_unique_homes([_home(tmp_path, ".codex-7", "auth-seven")])
    skill = tmp_path / "skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("---\nname: skill\ndescription: fixture\n---\n", encoding="utf-8")
    seen = {}

    class FakeClient:
        def __init__(self, **kwargs):
            seen.update(kwargs)

        def complete(self, messages, *, model):
            return '{"ok":true}'

        def consume_last_call_trace(self):
            return {"status": "completed"}

    client = CodexHomeFailoverClient(
        homes=homes,
        web_search_enabled=True,
        calculation_tools_enabled=True,
        domain_evidence_mcp_enabled=True,
        domain_beta6_frontier_enabled=False,
        domain_evidence_repo_root=Path(__file__).resolve().parents[1],
        domain_evidence_product="tcm",
        skill_paths=[skill],
        agent_workspace_enabled=True,
        capture_workspace_artifacts=True,
        compact_skill_briefing_enabled=False,
        client_factory=FakeClient,
    )

    assert client.complete([{"role": "user", "content": "x"}], model="gpt-5.6-luna") == '{"ok":true}'
    assert seen["web_search_enabled"] is True
    assert seen["calculation_tools_enabled"] is True
    assert seen["domain_evidence_mcp_enabled"] is True
    assert seen["domain_beta6_frontier_enabled"] is False
    assert seen["domain_evidence_product"] == "tcm"
    assert seen["skill_paths"] == [skill.resolve()]
    assert seen["agent_workspace_enabled"] is True
    assert seen["capture_workspace_artifacts"] is True
