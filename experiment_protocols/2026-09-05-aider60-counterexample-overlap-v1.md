# Counterexample-directed overlap: complete-track development experiment

## Authority and scope

The user requested a goal pursuing a scientifically supported final paper with
valid committee Overall >=4/6. This experiment pursues problem-solving gain;
execution infrastructure and review scores are not scientific contributions.
All earlier artifacts remain unchanged. This is development on previously
exposed tasks, not new-task confirmation.

## Fixed question

Does explicit cross-candidate semantic comparison create more newly passing
solutions than strong generic repair, conditional on identical current code,
candidate evidence, feedback access, model, and execution-budget ceilings?

Two factors govern the fifth whole-track Codex execution:

* policy: generic repair versus counterexample-directed semantic overlap;
* feedback: with versus without the new fourth-candidate official outcomes.

All four cells start from the EXACT SAME fourth-candidate patch. They all see
the same P/G/R patches and bounded official outcomes plus the fourth patch.
The feedback-off cells lack only the fourth candidate's official outcome file.
The generic control may reason freely, including comparing candidates; it is
not instructed to avoid good reasoning. Both policies use the same compact
ledger schema, scratch execution access, and completion audit.

## Complete inventory and shared prefix

Use every task in Python34 and C++26, without selecting, removing, replacing,
or topping up tasks. Source: Aider Polyglot commit
7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f. Existing frozen roots:

* runs/aider-python34-tov-v2-confirmation-20260902
* runs/aider-cpp26-tov-v2-extension-20260902

Reuse each root's original Plain, Graph, and ordinary_repair as the common
three-execution prefix. Generate ONE fresh strong generic fourth candidate
with the existing generic_adjudicator arm and ID cex_v1_shared4. Then run four
fresh fifth candidates. Each evaluated system has five logical executions;
prefix sharing reduces NEW execution count to five per track, ten total.
This is a paired component study, not ten independent complete systems.

All executions use gpt-5.6-luna, medium reasoning, default service tier, low
verbosity, the existing isolated adapter and account
/home/pineapple/.codex-new-account. Per-execution agent ceiling: 480 seconds;
evaluator ceiling: 1800 seconds. No extra language roots are exposed. Official
test source and gold remain hidden; the provided outcome feedback is allowed.
Native scratch programs derived from documentation are allowed equally.
No per-problem model sessions, benchmark lookup, or answer-specific rules.

The ceiling is an execution-time budget, NOT a guarantee of identical realized
tokens. Report elapsed time, cached/uncached input and output/reasoning tokens,
and internal response count where available. A token-efficiency claim requires
actual supporting measurements; five Codex executions are not five LLM messages.

## Order and preservation

Python: shared4; generic_feedback; overlap_feedback; generic_blind; overlap_blind.
C++: shared4; overlap_feedback; generic_feedback; overlap_blind; generic_blind.
Every cell has an isolated workspace and unique artifact ID cex_v1_<cell>.
Never expose one fifth-cell result to another cell.

The terminal system preserves all five candidate snapshots. For each task,
select a complete evaluator-passing solution with fixed priority
fifth > fourth > ordinary_repair > graph > plain; if none passes, use fifth.
Materialize and execute the terminal system before declaring a system score.
This common selector is a baseline capability, not the proposed novelty.

Record interruption, unsafe scope, or transport failure separately. Do not
silently replace a failed cell or select the best repeated attempt. An invalid
cell leaves this experiment incomplete; unrelated valid cells may continue.

## Estimands and promotion

Primary: overlap_feedback system minus generic_feedback system across all 60
tasks. Report both track differences, rescue/harm, raw counts, percentage-point
and relative differences, and paired exact tests conditional on realized calls.
Secondary: policy differences without fourth feedback, and feedback-by-policy
interaction; candidate-only scores and marginal gains above the four-call union.

Development advancement requires a positive primary net with no negative track
delta. The ambitious strong-effect target remains +12/60 (+20 percentage points)
against the strong generic system, not against Plain. These are selection rules
for subsequent fresh paired sessions, not population significance guarantees.
No additional prompt variants are inserted after inspecting a cell's results.
Freeze a new protocol for any changed hypothesis.

## Before-call evidence

The known seed confound in the prior online/offline experiment is deliberately
removed here by identical fourth-candidate seeds. The old 43/60 versus 40/60
result is uncertain (two-sided p=.375) and does not establish a freeze effect.
Current paper v25 committee Overall is 3/6. Review reruns wait for meaningful
new evidence rather than restyling this same claim.
