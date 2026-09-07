# Mini Artichokes 2x2 redundancy development experiment

## Frozen status

This is a second, result-aware development experiment on the reused Universal
benchmark. It cannot supply a confirmatory p-value. Its purpose is to test a
precommitted safety improvement to the accepted single-verifier result.

The tested system has two forms of redundancy:

1. two separately sampled auxiliary candidates must agree on a canonical MCQ
   option different from the base; and
2. two separately invoked, mutually blinded Luna verifiers must both validate
   the proposed correction.

The final answer switches only on the intersection of the two `VALID+SWITCH`
sets. There is no union, score-aware tie break, confidence threshold, reason
text parser, domain rule, or post-output tuning.

## Validator 1: already frozen and observed

- Campaign: `runs/mini-overlap-confirm1-dev-v3-20260831`
- Input freeze: `45d03ecb89c67242e0f98bf522afb524dd758b04f57bd0ab00e71b8909b39ae7`
- Accepted receipt: `8d52c3082c313cae26516b6faf38553a636bdffea708c9e3a2365e843a0ac99e`
- Trace: `84450113ed71b50641045b3e020d0e35a65872360a7b5ee260accc4baf821ae4`
- Decisions: `59e217ebeae26fe4d0e3ce5faa75a2c4282cbf8d62f75abdc11263779b8b1eff`
- Answers: `c03291e2fe58a365306433059e0201298a7b4faf25f652b113f0361ad5c03c84`
- Valid-switch rows: 54
- Ordered valid-switch IDs: `f13d77797fc26027f2b159f4940d15dbd7a7e3798f751738c61b5a9ed71a0f74`
- Private development result on M=941: 587 correct, 30 rescues, 9 harms

## Validator 2: frozen before invocation

- Campaign: `runs/mini-overlap-confirm1-dev-v4-replicate-20260831`
- Input freeze: `45d03ecb89c67242e0f98bf522afb524dd758b04f57bd0ab00e71b8909b39ae7`
- Exact same public questions, candidates, eligibility, prompt, model, effort,
  verbosity, service tier, web policy, isolation, and 680-second timeout as
  validator 1
- Exactly one fresh non-resume `gpt-5.6-luna/high/default` invocation using
  `CODEX_HOME=/home/pineapple/.codex-new-account`
- Validator 2 receives no validator-1 output, decision, reason, trace, score,
  or private label. Bubblewrap exposes only its own frozen public input.
- It must independently pass the 1,309-answer/247-decision fail-closed
  validator and receive a distinct accepted receipt and invocation trace.

## Mechanical combination

- Predetermined output: `runs/mini-overlap-confirm1-dev-v5-2x2-20260831`
- Combination implementation commit: `97a1bad`
- Combination implementation SHA-256:
  `4b5310171db74f9085254826be6d9037339221e1725d130139361c8d662b0546`
- For each of the 247 frozen eligible IDs, SWITCH iff validator 1 and
  validator 2 both record `VALID+SWITCH`; otherwise copy the base exactly.
- For every ineligible ID, copy the base exactly.
- The combiner verifies identical input freezes/candidate bundles, both strict
  validations, two accepted one-call receipts, and distinct trace hashes.

Only this intersection is primary. Validator 2 alone is reported as a
stochastic replication diagnostic, not substituted for the primary system.

## Evaluation and promotion gate

Use the identical fixed M=941 cohort and count every unmapped output wrong.
The sorted M IDs remain
`2e46b0c759c185ed743d1109da1095f17643ebdd3c45bc4a30b08edbeb2b4047`.

Report full-denominator score, R/H versus base, paired one-sided exact
McNemar, switch count/precision/harm rate, eligible score, per-benchmark
rescues/harms, and paired differences against validator 1 and the existing
Universal adjudicator.

The 2x2 system becomes the preferred development system only if all hold:

1. both validator artifacts and the mechanical combination pass every
   integrity and provenance check;
2. validator 2 elapsed time is at most 680 seconds, so the two validators can
   run in parallel and the five-call solver critical path remains below 30
   minutes;
3. intersection harms `H <= 4` and `H <= floor(R/4)`;
4. intersection net gain over base `R-H >= 22`, i.e. at least 588/941 and
   strictly higher accuracy than validator 1's 587/941;
5. one-sided exact McNemar versus base `p <= .05`;
6. score exceeds the existing Universal adjudicator's 503/941;
7. every benchmark satisfies
   `H_d-R_d <= max(1, ceil(.01*n_d))`.

If the intersection trades some accuracy for much lower harm, it is retained
as a safety ablation but not relabeled as the accuracy winner. The next
challenger remains a new frozen experiment rather than a posthoc threshold on
these outputs.

Any future publication comparison for this five-call system must include
same-budget five-call controls: five-sample/self-consistency selection,
three candidates plus two ordinary adjudicators, critique-revise with matched
calls/tokens, a single-auxiliary two-verifier control, and an agreement-hidden
or shuffled/placebo control.
