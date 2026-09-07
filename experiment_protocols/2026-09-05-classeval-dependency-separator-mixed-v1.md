# ClassEval-Pro mixed Luna/Gemma E_B screen v1

Status: development-only screen. This protocol authorizes no O/C calls and
makes no efficacy, superiority, unseen-test, paper, or MAC-score claim.

The runner reads the terminal ordinary ClassEval-Pro full-300 parent (268
passed, fixed U32) and the terminal old E/D/O tail's E/A Luna artifacts. It
validates the exact frozen tail contract, per-call source hashes, exact U32
coverage, and byte equality of reconstructed `tail-E-A` and `tail-E-B` prompts
against the cached `prompt.txt` files before any model call. The denominator
remains 300; no subset is created and no frozen runner, projection, selector,
evaluator, or protocol is modified.

For each U task, the runner first evaluates the cached Luna E/A through the
unchanged `frozen_tail._full_view`, then sends exactly one fresh Gemma E/B
request using the unchanged E independent-repair prompt. The official
isolated evaluator remains authoritative for the raw and canonical reports.
All 32 tasks are attempted and accounted for; a single task result never
short-circuits the screen. Gemma uses `gemma-4-26b-a4b-it`, thinking level
`high`, temperature 0.6, maxOutputTokens 16384, timeout 120 seconds, one
request per task, and fixed approved key assignment by official task ordinal
modulo 10. No retries or failure-based key rotation are allowed. Only a STOP,
non-truncated, parseable response is valid; thought-token usage is reported
separately. Returned `modelVersion`, `responseId`, and HTTP status are persisted;
an explicit model-version mismatch or missing model evidence is invalid, and
the expected model is never silently asserted without returned evidence. API
status is recorded without response headers, keys, or unredacted error bodies.
Receipt durations are summed per request and are not end-to-end campaign time.

The continuation gate is evaluated only after all 32 calls:

`usableB >= 24 AND (novelCaseTasks >= 1 OR newWholePassVsOldE >= 1)`.

`usableB` means normal STOP completion, parseable complete Python, and a
successful canonical E view; it is not a whole-task correctness threshold.
`novelCaseTasks` requires a Gemma canonical passing case absent from both the
ordinary prefix and cached E/A. `newWholePassVsOldE` requires a Gemma whole
task pass while the old E final failed. Both novelty counts require a usable
response. A failed gate produces a screen-only terminal artifact and no
follow-up calls. The terminal artifact still carries a full-300 status map (268
`stopped`, 32 `screened`) plus `screenCompleted=32`; it is not a partial
benchmark result. A passed gate is only a decision input for a separately
approved future design; this runner does not implement or launch that design.

The future candidate, if separately approved, would reuse accepted E/B
receipts exactly and compare arm-specific O/B prompts plus fresh Luna C calls,
64 fresh model calls per E/O arm and 128 total. That plan must keep E/B and
O/B prompts distinct, cache A separately per arm, preserve the existing graph O
projection and `_select`, and report cached versus physical calls/evaluations
separately. It is not part of this screen.

Execute only with an explicit root approval:

```text
python -m tools.run_classeval_dependency_separator_mixed \
  --parent-root runs/classeval-pro300-text-overlap-20260905-development-v2 \
  --e-cache-root runs/classeval-pro300-overlap-repair-tail-20260905-development-v1 \
  --run-root runs/classeval-pro300-dependency-separator-mixed-screen-20260905-development-v1 \
  --keys-file /home/pineapple/bunjum2/work27/yt-predict/gemini_keys.txt \
  --execute
```
