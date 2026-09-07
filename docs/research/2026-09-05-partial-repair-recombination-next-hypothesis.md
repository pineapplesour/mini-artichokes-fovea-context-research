# Next structural hypothesis after the frozen probe/portfolio studies

This is research planning, not a launched experiment or performance claim.
Finish the live generic controls unchanged. Do not replace them with this idea.

## Closest primary sources

EvolRepair organizes repair candidates by passed-test subsets, recombines
partial repairs, and applies semantic mutation. Its experiments use generated,
partially correct programs derived from sampled LiveCodeBench problems and up
to41 repair attempts in the reported comparison. Thus its algorithm is useful
prior art, but copying its curated workload would violate our user's complete
official-benchmark requirement, and its budget is not our few-whole-track-call
setting. [Paper](https://arxiv.org/html/2604.02134v1)

PatchFusion performs deterministic fixed-pool fusion using repeated edit atoms
and compatible scopes without decision-time tests. Its published setting is
different from our test-available repair loop. It supplies a concrete comparator
for claims about repeated edits, and warns against attributing ordinary
candidate composition to Mini as a new invention. An implementation release
was not located in the inspected article; do not claim to have reproduced it.
[Paper](https://arxiv.org/html/2607.01597v1)

## Local evidence and proposed distinction

The Java overlap agent actually replayed all47 task entries against all three
source snapshots and rejected some bad independently authored probes. Yet its
first completed candidate passed12/47 and its verified system13/47 over an
11-task prefix floor. This is not an established matched-control win.

An important unresolved question is whether several failing candidates already
contain complementary correct implementations INSIDE one task. Task-wise union
cannot exploit that. Inspect behavioral coverage and compatible method/guard
differences, then test explicit within-task recombination against equally
budgeted generic repair and a genuine candidate-fusion baseline. All generated
combinations still need the complete official verifier; overlapping text is
not correctness evidence.

Existing Java feedback has a concrete limitation: each stored official failure
tail is capped at8000 characters and the agent-facing packet at1800; some
tails contain only framework stack traces. Do not claim a richer diagnostic
algorithm has been tested on those traces. Any new feedback extraction must be
provided identically to controls, recorded as a new protocol, and not presented
as the scientific contribution. Similarly, generated-probe success is too weak
to close a task whose authoritative official outcome remains failing.

The prospective six-execution heterogeneous-versus-generic-repeat study answers
the cheaper system-complementarity question first. Only after those actual
results should the next implementation be chosen. No new model, hand-authored
answer rule, selected task subset, or outcome-driven replacement is authorized
by this note.

## Bounded diagnostic scheduled after the frozen portfolio evaluation

The primary Java comparison is now fully scored: overlap13/47, generic A12/47,
with a14-task observed union. Consequently the still-pending heterogeneous
portfolio can beat the generic-repeat portfolio by at most2tasks on these
realized candidates (the latter already contains generic A). The pending
comparison will finish unchanged; this bound is not its final result.

The next concrete check uses zero new model calls: re-evaluate exactly the
existing Plain, Graph and ordinary-repair candidates on all47 official tasks,
retain each JUnit test-case status, and require every task-level outcome vector
to reproduce its original result. The original evaluator and live arms remain
unchanged. The new observation helper is
`tools/inspect_aider_java_partial_repairs.py`; its queue starts only after the
existing six-execution portfolio materialization ends.

For every original task, measure the union and intersection of passed test
cases, the gain of their union over the best individual candidate, and whether
the observed union covers the full case inventory despite no passing complete
implementation. Missing compilation/test reports stay unknown. Differing case
inventories are flagged rather than silently aligned. Graph and its subsequent
ordinary repair share lineage and are not two independent votes. No task is
selected or removed based on this diagnostic.

Even complete union coverage is only an optimistic indication of complementary
partial behavior: those behaviors may be incompatible in one program. It is
not a merged executable, an accuracy improvement, or a result for a new solver.
Use the observed pattern to decide whether a short partial-repair recombination
experiment is justified. Any such experiment must supply the same richer raw
feedback to generic controls; better log extraction alone is not our claimed
contribution. No new synthesis model execution is launched by this diagnostic.

## Result and next action,07:15 KST

All three captures completed with exact original task-vector reproduction.
Only `pig-latin` showed observed complementary coverage among unresolved tasks:
all candidates20/22 individually,22/22 as a non-executable case union. Nine tasks
have at least one missing candidate case report; those observations are unknown.
The proposed pure recombination experiment was therefore not launched.

Instead, froze and launched the two-arm, four-execution-system comparison in
`experiment_protocols/2026-09-05-java47-shared-failure-overlap-v1.md` (4357ad3).
The treatment aligns repeated failed requirements across candidate lineages and
repairs their common cause; both it and unrestricted generic repair receive the
same richer raw feedback and derived overlap fields. This is a new development
hypothesis, not a positive result or a replacement for the invalid Generic-B.
