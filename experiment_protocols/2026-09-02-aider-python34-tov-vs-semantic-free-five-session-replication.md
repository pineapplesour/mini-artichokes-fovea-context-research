# Frozen five-session replication: TOV versus semantic-free control on Python34

Status: frozen before any replication call. Existing Rust30, Python34, C++26,
TOV, generic, and first semantic-free-control outcomes are known. Python34 is
selected because it was TOV v2's original prospective unchanged-policy
confirmation track and because its complete official task set exhibited the
interface/semantic-contract pattern motivating the repeated test. This is a
prospective replication of final-stage session behavior on that fixed setting,
not an unselected language-population experiment.

## Question and inferential unit

When the immutable Plain/Graph/ordinary candidates, test evidence, 19 verified
anchors, and 15 unresolved tasks are held fixed, does TOV v2 repeatedly
outperform the semantic-free structured control across independently
initialized final calls?

The primary unit is one paired whole-track final-stage session, not one task.
Exactly five new pairs are permitted. The existing first TOV/control results
motivate the study but are excluded from the primary five-session test.

## Frozen inputs and arms

Reuse only the frozen candidate and evaluator artifacts under
`runs/aider-python34-tov-v2-confirmation-20260902`. Every final call uses:

- all 34 official Python tasks;
- the same deterministic 19-task verified union and 19 restored anchor files;
- the same Plain, Graph, and ordinary-repair patches;
- the same per-task outcomes, bounded failure tails, and unresolved IDs;
- `gpt-5.6-luna`, medium reasoning, web disabled, and
  `CODEX_HOME=/home/pineapple/.codex-new-account`;
- one whole-track call, 30-minute agent cap, and 30-minute evaluator cap.

TOV uses the unchanged semantic-relation ledger, disagreement-triggered
falsification, and two audits. The control uses the unchanged identical schema,
falsification, and audits with every semantic relation field fixed to
`withheld-by-control`. Both use post-call byte restoration. Runner SHA-256:
`31e5077308b6bd7b8a4301d104e07c06863bf43aad87a7f6d1ed6b71cfba7134`.

## Exact calls and order

No call may be rerun, replaced, topped up, or stopped based on intermediate
scores. Execute:

1. session 1: TOV, then control;
2. session 2: control, then TOV;
3. session 3: TOV, then control;
4. session 4: control, then TOV;
5. session 5: TOV, then control.

Candidate IDs are respectively
`semantic_overlap_verified_union_rep1` through `rep5` and
`semantic_free_structured_verified_union_rep1` through `rep5`.

## Frozen analysis

For session `s`, define `d_s` as TOV correct minus control correct on the full
34-task denominator. The primary directional hypothesis is TOV > control using
an exact one-sided sign test over nonzero `d_s`. Report all five values, wins,
ties, losses, mean and median percentage-point difference, and a 100,000-draw
paired whole-session bootstrap with seed 20260902. With five nonzero pairs,
five positive differences yield one-sided `p=.03125`; no other outcome can be
called significant at `.05` under this test.

Secondary reporting includes the 170 repeated task-session outcomes, paired
rescues/harms, and their exact task-level test, explicitly labeled descriptive
because the same tasks recur and share calls. Do not pool the motivating first
call into the primary test. A separate six-session descriptive sensitivity may
show it but cannot replace the predeclared five-session result.

Every session must also pass:

- zero anchor-byte mismatches;
- exact 15-row ledger IDs and order in both arms;
- `withheld-by-control` in every control semantic field;
- byte-identical evidence packets within the pair; and
- zero forbidden changed paths.

Report calls, tokens, cached tokens, output tokens, and latency. Call and cap
matching does not establish exact-token matching. The experimental machinery
is provenance, not a paper contribution.
