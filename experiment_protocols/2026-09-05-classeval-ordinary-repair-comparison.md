# Predeclared ordinary-repair completion of the ClassEval-Pro comparison

This implements the stronger repair comparison specified BEFORE source-stage
model results in2026-09-05-classeval-pro-source-overlap-v1.md (retained byv2).
The source-only result is not the final architectural superiority comparison.
No source-stage algorithm, model call, test, result or live output is modified.

Only run after the parent root has a terminal result.json covering the exact
300 official task IDs and its runner/operator/evaluator hashes still match.
No partial-task campaign, selected retries, replacement parents or new gold
access. The original development/benchmark limitations remain in force.

For each policy (generic random composition and overlap-ranked composition),
preserve a fully passing selected source byte-for-byte with no extra model
call. Otherwise make one ordinary general feedback-repair call starting from
that policy's actual selected source. The SAME prompt template, original
skeleton, two original parent sources/feedback, Luna/medium, approved account,
120-second limit and100-second completion instruction apply. The starting
source and its observed feedback are the treatment-derived differences, not
a special overlap repair prompt. Every unresolved task receives one attempt;
none is removed because its official test metadata is problematic.

Only solution.py is submitted. The narrow non-submitted cache allowance and
symlink/extra-source prohibition are unchanged from source-stagev2. Public
feedback retains every observed case, limiting individual failure messages
to1600characters; unknown/invalid attempts are labeled, not treated as passes.
Input files must remain unchanged. Missing normal completion, timeout, unsafe
source or input edits make the repair candidate invalid. Preserve the prior
selected state if the candidate is not better on observed complete-test and
then case-level outcomes. A prediction or prose assertion is never a pass.

Each final system receives the same up-to-two shared parent model calls plus
up to one ordinary repair call and the same up-to16 source-trial budget.
Early successful stopping may reduce realized calls/trials differently;
report all actual inference/evaluator times and tokens, not equal realized
cost. All300 remain in the final denominator. Shared upstream calls are
charged to each system logically and once physically in development cost.
The stopped sourcev1 calls remain separate setup costs, not erased.

Implementation is tools/run_classeval_repair_comparison.py. Its preparation
while the source phase runs is NOT evidence that any repair call has executed.
No positive first-stage result triggers a review reroll before this stronger
comparison is complete. Replication decisions use full final system results.
