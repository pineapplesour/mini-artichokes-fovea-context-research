# Author-released ClassEval snapshots

Source: https://github.com/FudanSELab/ClassEval
Authors: Xueying Du, Mingwei Liu and the ClassEval contributors.
Repository code: MIT. Dataset: CC BY-NC4.0
(https://creativecommons.org/licenses/by-nc/4.0/).

`ClassEval_data.json` is downloaded unchanged from releasev1.0.0 commit
90825141e640418ae6dc8257397345ee3ac36cbc. SHA256:
d13f5e3bac96f57c1cc9bfa282cf6c0cca4605d4748d621b83a0dae72d08ed2f.
It contains100 tasks and410 methods. Solutions/tests in this local evaluator
copy must never be mounted into solver workspaces.

The author's2024-09-02 data update was inspected separately, unchanged:
e22643b9f1c9df889886e38b47d54d845d9b4658, SHA256
50a1ac0e4d0c238573c10c0ab11feae00b14a80ae9e4c9cc28148707ecf0b6a2.
It does not change the failed test suites found in the release smoke check.
It has NOT replaced the frozen release and has not been used for model calls.

Runtime feasibility check: all100 reference implementations evaluated in
`runs/classeval100-source-overlap-20260905-reference-v1/`, with91 full passes.
This is NOT a model result or an overlap accuracy gain. No model calls have
been made on this dataset as of that check. Do not silently omit or fix the
nine affected tasks to manufacture a clean full-benchmark result.
