"""Separate no-model-call replay; original run and source operator are immutable."""
from tools import replay_classeval_helper_union as replay
from tools import classeval_subtree_overlap as subtree


if __name__ == "__main__":
    replay.union = subtree
    raise SystemExit(replay.main())
