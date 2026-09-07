# Post-repair case complementarity diagnostic

This is a development diagnostic, not a new accuracy comparison or model run.
It follows the frozen obligation-view A/O/B study. The original P/G/R captures
remain untouched; they were inputs to that study. No live repair runner,
normalizer, materialization analyzer, or primary evaluator is changed.

The three completed, normally terminating, source-safe candidate IDs are:

- `obligation_view_v1_case_local` (A, raw 12/47);
- `obligation_view_v1_obligation_overlap` (O, raw 16/47);
- `obligation_view_v1_case_local_b` (B, raw 20/47).

The raw candidate vectors are already known. Case-level complementarity between
these three repaired candidates has not been inspected. Evaluate all 47 tasks
for every candidate on fresh private copies, using the existing official
commands and 240-second per-task limit. Require each complete task vector to
match its original result. Missing case reports are unknown. Do not supply
test source or reference code to a model. Preserve the original outcome of any
invalid or nonmatching diagnostic; do not repair source to obtain agreement.

Output is a new directory:
`runs/aider-java47-tov-development-20260902/diagnostics/partial-finals-v1/`.
The existing inspector receives only an optional list of candidate IDs; its
default P/G/R selection and its grading and summary semantics are unchanged.
The diagnostic starts after PID 2000692 (the frozen B/portfolio queue) exits,
and only if that queue produced its complete portfolio summary. It uses no
additional semantic/model calls and does not restart any existing arm.

Report unresolved tasks for which the observed union of passing cases exceeds
the strongest individual candidate, plus the narrower set with full observed
case coverage. These counts are not executable fused solutions, a guaranteed
repair ceiling, or accuracy gains. They only decide whether implementing a
general within-task recombination operator is a worthwhile next experiment.
If there is little complementarity, do not build a large recombination pipeline
merely to pursue this idea. Any next actual operator and its generic comparator
need a separate frozen protocol and fresh, fully evaluated outputs.
