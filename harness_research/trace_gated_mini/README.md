# Trace-gated Mini coding harness

This is the smallest runnable coding analogue of Mini Artichokes. It preserves
the core overlap mechanism while replacing answer strings with candidate Git
patches and executable public traces.

## Frozen arms

- `direct`: one Codex attempt on the complete task.
- `kira`: one Codex attempt plus a KIRA-inspired completion audit. This is an
  adaptation, not KRAFTON's Terminus-KIRA implementation.
- `mini`: three independent complete-task attempts. A deterministic selector
  prefers safe public-test passes, then fewer failures, more passes, smaller
  scope, and a smaller patch. It keeps candidate `a` on exact evidence ties.
- `mini` bounded arbitration: only when every independent candidate fails the
  public verifier, or when public-passing candidates disagree at the patch
  level. It starts from the strongest deterministic trace and sees anonymous
  public traces and patches. It must actively falsify the candidate and may
  conservatively repair it. It never sees the evaluation-only tests or gold
  patch. A safe, public-passing arbitration result is selected; exact candidate
  agreement keeps the preassigned base.

Every candidate starts from an isolated clone of the same pinned Git ref. No
task is split between agents, and no benchmark/domain router is used.

The candidate and arbitration models may be frozen separately. For example,
`--model gpt-5.6-luna --arbiter-model gpt-5.6-sol` keeps all three independent
solutions on Luna and uses Sol only for the bounded disagreement/all-fail
arbitration. This asymmetric arm must be compared with direct Sol on the same
tasks so a model-strength gain is not mislabeled as a harness gain. A frozen
candidate result can also be re-arbitrated without rerunning candidates through
`harness_research.trace_gated_mini.rearbitrate`; the command verifies the
recorded candidate patch digests and records the frozen result's SHA-256.

An optional `--critic-model` adds a verification-only counterexample gate before
arbitration. The critic receives the same public repository, issue, traces, and
patches but no held-out tests or gold patch. It must derive a machine-checkable
contract, search for shared candidate blind spots, and emit a standalone public
`claim oracle`. Its workspace is never promoted; any mutation is recorded and
discarded. The repair model receives the critic's memo and independently verifies
it, then the harness runs the preserved oracle against the repair workspace. A
repair is ineligible unless the model completed normally, the ordinary public
tests pass, the claim oracle passes, and the patch is path-safe. This role is
generic rather than benchmark- or repository-routed.

`harness_research.trace_gated_mini.universal_overlap` is the stronger overlap
arm. It maps Universal Artichoke's selective-prediction principle to full-
coverage coding: three frozen whole-task candidates form the cheap region;
disagreement escalates to independent spec-first and regression-first critics;
both critics emit executable claim oracles; and a KIRA-style repair is accepted
only when it completes normally and passes public regression tests plus every
oracle. Unlike selective prediction, low-confidence tasks are escalated instead
of omitted from the denominator.

## Fairness contract

1. Freeze task IDs, base refs, prompts, commands, model, effort, timeouts, and
   task order before the confirmation run.
2. Use one model/account epoch for all arms; rotate arm order deterministically.
3. Keep evaluation-only tests unavailable to model calls and the selector.
4. Report calls, wall time, public traces, all candidate patches, and final
   evaluation results, including timeouts and invalid changes.
5. Use a development split only for policy choice. Report the first untouched
   confirmation run; do not answer-led rerun failed tasks.
6. Primary paired endpoint: task-level evaluation pass. Report exact McNemar
   inference and a paired bootstrap interval for the absolute percentage-point
   difference. The requested headline threshold is at least +20 percentage
   points over direct Codex/Luna on the frozen confirmation split.

## Attribution

The completion-audit baseline is informed by KRAFTON AI's Apache-2.0
Terminus-KIRA project, especially its original-instruction recheck and
double-confirmation idea. This implementation uses Codex's own native tools and
does not claim to reproduce KIRA's terminal driver, marker polling, multimodal
reader, or published Terminal-Bench scores.

## One-arm invocation

```bash
python -m harness_research.trace_gated_mini.cli \
  --source-repo /absolute/path/to/frozen/repo \
  --task /absolute/path/to/task.json \
  --output-dir /absolute/path/to/new/output \
  --arm mini \
  --codex-home /home/pineapple/.codex-new-account \
  --model gpt-5.6-luna \
  --reasoning-effort medium \
  --critic-model gpt-5.6-sol \
  --critic-reasoning-effort high \
  --arbiter-model gpt-5.6-sol \
  --arbiter-reasoning-effort high
```

The output directory is creation-only so an earlier result cannot be silently
overwritten.

For SWE-style tasks, omit `evaluation_test_command` from the task manifest.
After the arm has terminated, apply the held-out test patch with the separate
`harness_research.trace_gated_mini.evaluate` entry point. This makes the time
boundary between candidate selection and evaluation explicit in the receipts.

`swe_rebench.py` materializes an exact SWE-rebench V2 instance as a new,
history-free Git snapshot. It keeps the test patch in a separate private runtime
directory, records only its hash in public metadata, and never persists the gold
solution patch.
