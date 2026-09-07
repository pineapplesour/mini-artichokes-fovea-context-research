"""No-model-call application of frozen subtree crossover after ordinary repair."""
from pathlib import Path
import sys

from tools import replay_classeval_helper_union as replay
from tools import classeval_subtree_overlap as subtree


if __name__ == "__main__":
    subtree.PROTOCOL = Path(__file__).resolve().parents[1] / "experiment_protocols/2026-09-05-classeval-postrepair-subtree-development.md"
    replay.union = subtree
    if "--after-ordinary-repair" not in sys.argv:
        sys.argv.append("--after-ordinary-repair")
    raise SystemExit(replay.main())
