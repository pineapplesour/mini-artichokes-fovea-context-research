from pathlib import Path

from tools.prepare_aider_hidden20 import rank


def test_rank_is_deterministic(tmp_path: Path) -> None:
    paths = []
    for name in ("a", "b", "c"):
        path = tmp_path / "python" / "exercises" / "practice" / name
        path.mkdir(parents=True)
        paths.append(path)
    assert [p.name for p in rank(paths, "seed")] == [p.name for p in rank(paths, "seed")]
