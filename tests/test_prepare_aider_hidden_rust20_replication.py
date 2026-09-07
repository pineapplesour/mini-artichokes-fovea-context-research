from pathlib import Path

from tools.prepare_aider_hidden_rust20_replication import digest, rust_task_instruction


def test_digest_is_sha256() -> None:
    assert digest(b"x") == "2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881"


def test_rust_instruction_does_not_inject_python_constraint(tmp_path: Path) -> None:
    docs = tmp_path / ".docs"
    docs.mkdir()
    (docs / "instructions.md").write_text("Implement the exercise.", encoding="utf-8")
    rendered = rust_task_instruction(tmp_path, ["src/lib.rs"])
    assert "Implement the exercise." in rendered
    assert "Rust standard library" in rendered
    assert "Python" not in rendered
