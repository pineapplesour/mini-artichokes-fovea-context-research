# ClassEval-Pro dependency-separator overlap (ROOT-APPROVED BOUNDED DEVELOPMENT; NOT CONFIRMATION)

Status: Root approved one 2026-09-05 full300/U32 O development run (96 new calls)
with hash-bound E/D controls reused; no confirmation claim.  Model/evaluator
execution remains gated on the checkpoint; `--execute` is explicit.
Dry-run status (2026-09-05): documented no-call command exit 0; U32, planned O=96,
fallback=0, planned overlap=28/32, invariants=32/32, prior S distribution matched.
## Scope and denominator

Use the official, ordered `classeval-pro` full 300 inventory and the completed
ordinary full-300 prefix.  The fixed unresolved set is U=32.  The existing
anchor-reordered D cut is retained.  Every task remains in the output, and
ordinary-pass tasks stop identically; E/D are hash-bound development controls
from the completed frozen tail, not a fresh confirmation.
## Candidate mechanism

For each unresolved task, parse only direct target-class `self.method()` and
`cls.method()` calls in the ordinary source.  Build the unique bipartite graph
between the ordered D left/right scopes, then use deterministic ordered maximum
matching and its minimum vertex cover S.  O assigns left∪S and right∪S,
preserving source order; all edges must be covered and both exclusive sides
must remain.  S=0 is exactly D and is recorded as no actual overlap.  Small-n,
missing-method, or parse failure uses the existing common E-style fallback;
the previously observed |S| distribution is diagnostic only, never a task gate.
## Calls, information, and evaluation

O makes exactly A+B+C=3 new Luna calls for each U task (96 planned calls);
there are no retries.  A and B independently receive the same ordinary source,
bounded observed feedback, ordered labels, anchor hint, and complete S metadata.
C receives only the new usable A/B outputs plus that common input.  Old E/D/O
outputs or scores, gold, solution, reference code, and raw tests are not prompt
inputs.  All candidates use the frozen AST canonicalization and evaluation
source path.  Raw automatic evaluations are discarded from selection and are
counted separately from canonical evaluations; raw+canonical suite evaluation
is capped at six per arm and logical prefix+tail calls at six.

Record every shared method's A/B/C body SHA and presence/active metadata as
provenance, not proof of causality.  Projection records actual assigned and
changed methods; invalid candidates are failures and do not receive canonical
evaluation.  The primary selector is unchanged (prefix, A, B, C fixed order).

## Integrity and reporting

Claim an independent sibling run root, write its contract before any call, and
bind parent/control contract and result hashes, official data hash, model
(`gpt-5.6-luna`), medium effort, 120-second timeout, evaluator, helper, runner,
and protocol hashes.  Progress is written per task; unexpected IO/call/eval
errors fail closed as incomplete, never a fabricated complete-300 result.
Later analysis keeps task-level full-300 denominators and reports O versus the
pre-specified controls with costs/usage separately.  This development reuse is
not fresh confirmation; a new full-300 prefix is required for confirmation.
Primary inference is O−E and O−D on all 300 tasks using two-sided exact paired
discordance/binomial tests with Holm-2; old single-bridge O is diagnostic only.
Cost accounting: planned new O=96; per-system common533+96=629; historical
827+96=923 if complete; comparison receipts common533+E96+D96+O96=821.

## Dry-run command (not executed)
```bash
python -m tools.run_classeval_dependency_separator_overlap \
  --parent-root runs/classeval-pro300-text-overlap-20260905-development-v2 \
  --control-root runs/classeval-pro300-overlap-repair-tail-20260905-development-v1 \
  --run-root runs/classeval-pro300-dependency-separator-overlap-20260905-development-v1
```
