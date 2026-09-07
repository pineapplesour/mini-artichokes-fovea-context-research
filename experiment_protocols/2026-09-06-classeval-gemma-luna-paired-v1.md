# ClassEval-Pro paired Luna/Gemma E/O development v1

Status: implementation only; separate root approval is required before
`--execute`.  This is a mechanism-development comparison, not a paper or MAC
result and not a fresh confirmation study.

## Fixed input and arms

- Use the official, ordered 300-task inventory and the terminal ordinary parent:
  268 passed tasks are stopped and exactly U32 are processed; the denominator
  remains 300.  No failure-selected subset, retry, high-thinking B reuse, or
  new benchmark is allowed.
- `LG_E` reuses old Luna E/A
  (`runs/classeval-pro300-overlap-repair-tail-20260905-development-v1/E/a`)
  and the completed minimal Gemma screen E/B
  (`runs/classeval-pro300-gemma-minimal-screen-20260906-development-v1/E/b`), then makes one
  fresh Luna E/C call per U task.
- `LG_O` reuses graph Luna O/A
  (`runs/classeval-pro300-dependency-separator-overlap-20260905-development-v1/O/a`),
  makes one fresh minimal Gemma O/B call per U task, then one fresh Luna O/C
  call per U task.  New Gemma B receipts are labelled `O_B`; no contract or
  receipt is rewritten after the call.
- Every arm retains the frozen E/O prompt construction, observed-feedback
  inputs, scope/projection rules, reconciliation input, and selector by
  delegating to `run_classeval_overlap_repair_tail._execute_arm` and
  `run_classeval_dependency_separator_overlap.run_task`.  Model changes do not
  alter the scientific policy or raw-floor/selection rule.

## Call and accounting contract

- Luna uses `gpt-5.6-luna`, medium effort, 120 seconds, through the existing
  `run_classeval_text_overlap.call`; Gemma uses `gemma-4-26b-a4b-it`, minimal
  thinking, temperature 0.6, max output 16384, 120 seconds, no tools, no
  retries, and task ordinal modulo 10 key assignment.  High-screen initiated
  calls and two non-benchmark smoke calls remain separate accounting scopes.
- Each arm has three logical tail candidate slots per U task: E/A, E/B, E/C
  and O/A, O/B, O/C.  Thus the full logical study has `192` candidate slots:
  Gemma `64` and Luna `128` (cached A `64` plus fresh C `64`).  Cached A/B
  slots are not new physical calls.  The remaining physical scope is Gemma
  `32` plus Luna `64`, total `96`; combined physical accounting across the
  completed minimal screen plus this study is Gemma `64` plus Luna `64`,
  total `128`, with cached Luna A excluded from that physical count.
- Cache materialization re-verifies source/receipt/prompt integrity and then
  invokes the unchanged evaluator for cached candidates when the frozen
  canonicalization path accepts them.  A planned cache-verification count is
  reported separately; actual current-run evaluator calls are the frozen
  `canonicalEvalCalls` plus valid fresh raw-candidate evaluations.  The
  frozen `rawEvalCalls` field includes historical raw validity for cached
  candidates and is not a current cost count.
- An invalid candidate is a counted failed candidate; the task may still pass
  through its prefix or another candidate.  A candidate-level invalid/timeout
  does not alone invalidate the full experiment; integrity failures do.

## Analysis and advancement gate

- Primary comparisons are task-wise `LG_O` versus `LG_E` and `LG_O` versus the
  reused Luna-only E control (`LL_E=278`), each on all 300 tasks with paired
  rescue/harm and exact two-sided McNemar tests with Holm correction across the
  two primary comparisons.  `LL_O=278` and the model-mix interaction in the
  descriptive 2x2 are secondary context, not a substitute control.
- Report exact IDs, pass vectors, valid/invalid receipts, physical and logical
  calls, evaluator calls, token usage, receipt-summed duration, and artifact
  hashes/paths.  A predeclared timeout or invalid candidate is a failed
  candidate, without removing its task from the denominator; “no validity
  failure” in the advancement rule means no integrity
  failure in inputs, cache binding, denominator, model/budget provenance, or
  score provenance.
- This development may advance to a separately approved fresh confirmation
  only if `LG_O` has net gain at least four tasks against each primary control
  and the run has no integrity failure.  Otherwise there is no automatic new
  model campaign, review, promotion, or paper update.  This threshold is a
  decision rule, not a significance claim.
- Repair/selection feedback is the same official final evaluation feedback
  used by the benchmark, so this is a test-guided/validation-assisted setting;
  no unseen-test performance claim or hidden split is made.  Reused controls
  and the prior screen prevent calling this a fresh independent replication.

## Fixed invocation (approval still required)

```text
python -m tools.run_classeval_gemma_luna_paired \
  --parent-root runs/classeval-pro300-text-overlap-20260905-development-v2 \
  --e-cache-root runs/classeval-pro300-overlap-repair-tail-20260905-development-v1 \
  --screen-root runs/classeval-pro300-gemma-minimal-screen-20260906-development-v1 \
  --o-cache-root runs/classeval-pro300-dependency-separator-overlap-20260905-development-v1 \
  --run-root runs/classeval-pro300-gemma-luna-paired-20260906-development-v1 \
  --keys-file /home/pineapple/bunjum2/work27/yt-predict/gemini_keys.txt
```

The command is dry-run unless `--execute` is explicitly added after a separate
root approval; no screen/high artifacts are used as new calls.
