# ClassEval-Pro300 source-overlap v2: non-submitted bytecode-cache correction

All scientific conditions of2026-09-05-classeval-pro-source-overlap-v1.md
remain unchanged: full300, same official data, same prompt and independent
conditional A/B generation, Luna/medium120seconds, identical source pool and
16-trial cap, same generic and overlap algorithms, same known reference
limitations, and the still-pending stronger ordinary repair comparison.

V1 campaign session11647/driver3386478 was stopped with SIGINT (exit130) after
the first task and during the second task's A call. The reason was a verified
runner defect, not score selection: ClassEval_0/A ended normally112.421s with
exit0 and turn.completed, but was marked source-unsafe solely because its
explicit py_compile check created __pycache__/solution.cpython-312.pyc.
Such caches are never copied to the isolated evaluator, which receives only
the solution.py text. No actual A test outcome was available because the
incorrect source gate rejected it before evaluation.

V2 permits only that precisely scoped non-submitted cache pattern, rejects
all symlinks and other extra files, and records ignored cache paths. Only
solution.py is submitted, as before. Tests cover cache acceptance and extra
source/symlink rejection. No model, algorithm, budget, test or scoring rule
changes. Preserve the entire stoppedv1 root; do not relabel its invalid runs
as passes or choose between old/new answers. V2 starts a wholly fresh full300
campaign in a separate root, not selected-arm retries. Charge the three v1
initiated model calls as setup/development cost, separate from v2's full run.
