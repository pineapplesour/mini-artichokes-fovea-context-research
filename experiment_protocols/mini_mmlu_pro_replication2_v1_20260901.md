# Mini Artichokes MMLU-Pro disjoint replication 2

## Status and multiplicity boundary

This protocol is frozen after the first 1,000-row MMLU-Pro cohort was scored
and before any model answer is generated for replication 2. The first cohort
showed OJ3 601/1,000 versus D1 597/1,000 (5 rescues, 1 harm; one-sided exact
McNemar p=.109375), OJ3 601 versus SC3 596 (5 rescues, 0 harms; p=.03125), and
OJ3 601 versus matched GJ3 600 (1 rescue, 0 harms; p=.5). Only 14 conflicts
were eligible.

No policy, prompt, model, effort, fallback, candidate role, threshold, or
statistic is changed after seeing that result. Exactly one disjoint 1,000-row
replication is added. There is no third cohort under this protocol.

Because the first 1,000 rows were an interim look, the cumulative 2,000-row
headline claim uses a conservative one-sided alpha of .025. The first look did
not cross .025. The final pooled test must also be below .025; thus the two
looks have a Bonferroni familywise bound of .05.

## Frozen disjoint data

- Source: the same official `TIGER-Lab/MMLU-Pro` test parquet.
- Source Git commit: `b189ec765aa7ed75c8acfea42df31fdae71f97be`.
- Source parquet SHA-256:
  `0e24a191921c2f453518a537a8b2117bd137e7714d4ef1565e9ba06c1ecb9ad8`.
- Selection seed:
  `mini-artichokes-mmlu-pro-confirmation-v1-20260901`.
- First cohort: category-proportional SHA ranks 0-999.
- Replication 2: the immediately following category-proportional cumulative
  SHA ranks 1,000-1,999, implemented as the difference between the
  largest-remainder allocations at cumulative N=2,000 and N=1,000.
- Public ID intersection with cohort 1: 0; union size: 2,000.
- Public file:
  `benchmarks/mmlu_pro_confirmation_replication2_v1/mmlu_pro_stratified1000.public.jsonl`.
- Public SHA-256:
  `de26ddbd37f67fa088867debff8af65b6ca90746059c03a4fe25c417135e197f`.
- Private file:
  `benchmarks/mmlu_pro_confirmation_replication2_v1/mmlu_pro_stratified1000.private.jsonl`.
- Private SHA-256:
  `637627ba77e968ded9a48ce45e86bfce53bfac1cc5aaa8f27e855d15319055cb`.
- Base campaign freeze SHA-256:
  `2dc0cf6067ed0b79cb34bcc2ab5132eb4c0b936f4909af02f4a369cb97a034fa`.

Selection uses no answer or `cot_content` field. The private file is not
staged in any model workspace and may be opened only after all five semantic
calls for replication 2 have accepted final receipts.

## Identical frozen mechanism

Execution and scientific arms are identical to
`mini_mmlu_pro_confirmation_v1_20260901.md`:

- D1, D2, D3 are independent one-call whole-file `gpt-5.6-luna/high` draws;
- web, databases, memory, skills, MCP, apps, and multi-agent access are
  disabled;
- every draw receives all 1,000 public rows in one isolated invocation;
- answers must be exact option content and A-J mapping is deterministic;
- SC3 is canonical majority with D1 fallback;
- the gold-free conflict set is exactly mapped `D2 = D3 != D1` rows;
- GJ3 sees two anonymously rotated existing candidates but no source support;
- OJ3 sees the identical IDs, candidates, rotation, model, and call budget,
  plus only the mechanical 1-versus-2 complete-file support count;
- judges cannot synthesize a third answer;
- non-conflicts and invalid judge choices keep D1;
- incomplete calls cannot receive item-level retries or top-ups.

OJ3 and GJ3 each cost four end-to-end semantic calls including D1-D3. SC3
costs three and D1 costs one. Accuracy versus D1 is not a compute-matched
claim; individual and cumulative tokens, calls, elapsed time, and critical
path are mandatory reports.

## Replication-2 and cumulative evaluation

Replication 2 is scored on its full 1,000-row denominator with the same
per-category metrics, unmapped-as-wrong rule, rescues, harms, exact one- and
two-sided McNemar tests, and 20,000-sample category-stratified paired bootstrap
intervals as cohort 1. Its OJ3>D1 p-value is an independent replication
diagnostic and does not replace the cumulative multiplicity correction.

For the cumulative headline analysis, concatenate the two disjoint cohorts
without weighting. Sum rescue and harm counts over all 2,000 paired rows and
apply the exact one-sided binomial/McNemar upper tail. Use a 20,000-sample
paired bootstrap stratified by `(cohort, category)` for the accuracy-difference
interval.

The cumulative fixed sequence at alpha .025 is:

1. OJ3 > D1;
2. OJ3 > SC3;
3. OJ3 > GJ3.

Stop formal rejection after the first unrejected comparison. Report every
effect and p-value regardless of sequence reach. No category-specific policy,
post-score remapping, row exception, model-call replay, or third cohort may
alter these arms.

## Prior evidence boundary

The Universal 941-row development result (+21; p=.0005325), the Korean legal
boundary-condition result, and the first MMLU-Pro 1,000-row result remain
separate evidence. Only the two disjoint, identical-policy MMLU-Pro cohorts
enter the cumulative 2,000-row calculation.
