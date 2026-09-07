"""Replay frozen contrast-overlap ordering, without any new model invocation."""
from tools import replay_classeval_helper_union as replay
from tools import classeval_contrast_overlap as contrast


if __name__ == "__main__":
    replay.union = contrast
    raise SystemExit(replay.main())
