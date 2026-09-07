# Frozen five-session replication: TOV versus semantic-free control on C++26

Status: frozen before any C++ replication call. Existing single-call C++26
outcomes (TOV17, semantic-free13), all Python34 replication outcomes, and all
earlier studies are known. C++26 is selected as a second setting because its
complete-track semantic-free contrast was the largest original full-denominator
effect (+4/26, +15.4 points) and its TOV-only tasks involved explicit
namespace, overload, enum, and API-contract disagreements. This is a targeted
prospective session replication in an already observed setting, not an
unselected language-population test.

## Question and unit

Does the C++26 TOV advantage over the matched semantic-free structured control
repeat across independently initialized final-stage whole-track calls when the
13 verified tasks, 26 anchored files, 13 unresolved tasks, candidates, and
evidence are held fixed?

The primary unit is one paired whole-track final-stage session. Exactly five
new pairs are permitted. The motivating original C++ call is excluded from the
primary test.

## Frozen arms and calls

Reuse only immutable artifacts under
`runs/aider-cpp26-tov-v2-extension-20260902`. Every call uses all 26 official
C++ tasks, `gpt-5.6-luna`, medium reasoning, web disabled,
`CODEX_HOME=/home/pineapple/.codex-new-account`, one final whole-track call,
and 30-minute agent/evaluator caps. No candidate is rerun.

TOV uses the unchanged semantic-relation ledger, disagreement-triggered
falsification, and two audits. Control uses the same schema, falsification, and
audits with semantic relation fixed to `withheld-by-control`. Both use identical
candidate/evidence packets and post-call anchor restoration. Runner SHA-256:
`31e5077308b6bd7b8a4301d104e07c06863bf43aad87a7f6d1ed6b71cfba7134`.

Execute exactly:

1. session 1: TOV, then control;
2. session 2: control, then TOV;
3. session 3: TOV, then control;
4. session 4: control, then TOV;
5. session 5: TOV, then control.

Use candidate IDs `semantic_overlap_verified_union_rep1` through `rep5` and
`semantic_free_structured_verified_union_rep1` through `rep5`. No retry,
replacement, top-up, prompt change, task deletion, or result-led stopping is
allowed.

## Frozen analysis

For session `s`, define `d_s = TOV correct - control correct` on all 26 tasks.
The primary directional test is an exact one-sided sign test over nonzero
session differences. Report all five differences, wins/ties/losses, mean and
median percentage-point effects, and a 100,000-draw paired whole-session
bootstrap with seed 20260903. Five nonzero positive differences yield
`p=.03125`; no weaker sign pattern is significant at `.05` with five pairs.

The 130 repeated task-session outcomes, rescues/harms, and exact paired test are
secondary descriptive statistics. The motivating original call is shown only
as a six-session sensitivity and cannot rescue the primary result.

Every call must have zero anchor mismatch, the exact set and order of 13 ledger
IDs, all control semantic fields equal to `withheld-by-control`, byte-identical
within-pair evidence packets, and zero forbidden paths. Any deviation is
reported; calls are not rerun or excluded. Report actual calls, tokens, cached
tokens, output tokens, and latency. No exact-compute or efficiency claim is
allowed. Infrastructure is provenance only.
