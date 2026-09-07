# Mini Artichokes MMLU-Pro confirmation v1

## Status and frozen scientific question

This protocol is frozen before any MMLU-Pro model answer is generated and
before the private answer file is opened for scoring. It tests one mechanism:

> When two independent whole-file Luna draws agree on a different canonical
> MCQ option from a frozen Luna base draw, does a support-aware, fail-closed
> candidate judge improve full-denominator accuracy over the base, ordinary
> self-consistency, and a matched support-hidden candidate judge?

The claim is about selective problem-solving accuracy. Isolation, hashes,
receipts, and validators are evidence controls and are not scientific
contributions.

## Frozen data

- Source: `TIGER-Lab/MMLU-Pro`, official Hugging Face dataset repository.
- Source Git commit: `b189ec765aa7ed75c8acfea42df31fdae71f97be`.
- Source test parquet SHA-256:
  `0e24a191921c2f453518a537a8b2117bd137e7714d4ef1565e9ba06c1ecb9ad8`.
- Source license: Apache-2.0.
- Source test population: 12,032 rows in 14 categories.
- Confirmation denominator: 1,000 rows.
- Selection seed:
  `mini-artichokes-mmlu-pro-confirmation-v1-20260901`.
- Selection rule: category-proportional largest-remainder allocation, then
  SHA-256 ordering of `(seed, category, question_id)` within category.
  Answers and `cot_content` are not inputs to selection.
- Existing Universal question screen: zero exact normalized prompt or
  sufficiently long question-containment overlaps with the frozen 1,309-row
  Universal public file.
- Public file:
  `benchmarks/mmlu_pro_confirmation_v1/mmlu_pro_stratified1000.public.jsonl`.
- Public SHA-256:
  `b7f7962ea0b3da74257c69f68e05116a54c11b96308040e692f725d5f31301f6`.
- Private file:
  `benchmarks/mmlu_pro_confirmation_v1/mmlu_pro_stratified1000.private.jsonl`.
- Private SHA-256:
  `c87d2722fc332493d18b4f0d46e1f89be850348a5f1b5f6b1a9b7aec6fa22697`.
- Base campaign freeze SHA-256:
  `10d8cc983810dbed0c66ac522a8552f7da5e33cf11ac1fd76b1e4f7c56bb9888`.

The private file is not staged in any solver or judge workspace. It may be
opened only after D1-D3 and both matched judges have complete final receipts.

## Model and execution contract

All semantic calls use:

- model `gpt-5.6-luna`;
- reasoning effort `high`;
- verbosity `low`;
- `CODEX_HOME=/home/pineapple/.codex-new-account`;
- service tier `default`;
- native web search disabled;
- databases, memory, skills, MCP, apps, and multi-agent access disabled;
- one isolated Codex process responsible for the complete file it receives.

The three drafts run sequentially because of the machine memory policy, but
each receives the identical 1,000-row public file and has no access to another
draft. A completed call cannot receive item-level retries, repairs, or top-ups.
An incomplete call is preserved and cannot be selectively completed under
this protocol.

Each draft must output exactly one nonempty `finalAnswer` per ID, in public
input order, containing the exact text of one option and no rationale. A-J
option mapping is deterministic. Unmapped output counts wrong.

## Frozen arms

### D1: Plain Luna

One independent complete-file Luna call. This is the headline plain-model
reference and the fallback answer for every invalid downstream decision.

### D2 and D3: independent auxiliary draws

Two additional complete-file calls with the identical model, effort, prompt,
tool policy, and public rows. They provide alternative candidates; neither is
selected based on private accuracy.

### SC3: ordinary self-consistency

For each row, choose the canonical option with at least two votes among
D1-D3. If no mapped majority exists, keep D1. No semantic call is added.

### GJ3: matched support-hidden selective judge

The gold-free conflict set contains exactly rows where D1, D2, and D3 all map
to canonical options and `D2 = D3 != D1`. For each conflict, deduplicate the
answers into the D1 option and the D2/D3 option, rotate them deterministically
to anonymous C1/C2 roles, and present the public question plus those two
candidates to one complete-file Luna judge. The judge is not told which
candidate has one or two generating draws and must copy one candidate exactly.
Non-conflicts and invalid judge outputs keep D1.

### OJ3: Mini Artichokes support-aware selective judge

Use the identical conflict IDs, identical anonymous candidate role rotation,
identical model/call budget, and identical no-synthesis constraint as GJ3.
The only added field is a mechanical independent-support count: one candidate
has one complete-file draw and the other has two. The instructions explicitly
state that agreement can be correlated and is not proof; the judge must check
the public question. Non-conflicts and invalid judge outputs keep D1.

OJ3 uses four semantic calls end to end (D1-D3 plus OJ3). GJ3 has the same
four-call budget. SC3 uses three calls and D1 uses one. The OJ3-versus-D1
comparison is therefore an accuracy comparison, not a compute-matched claim;
calls, tokens, wall time, and the complete critical path must be reported.

## Frozen evaluation

All primary accuracy metrics use the complete 1,000-row denominator. Null,
unmapped, missing, duplicated, synthesized, or otherwise invalid outputs count
wrong or fall back to D1 only where explicitly stated above.

The familywise confirmatory sequence uses one-sided exact McNemar tests at
alpha 0.05 and stops after the first unrejected hypothesis:

1. OJ3 > D1;
2. OJ3 > SC3;
3. OJ3 > GJ3.

For every comparison report rescues, harms, net correct, discordant count,
the one-sided exact p-value, the two-sided exact p-value, and a 20,000-sample
category-stratified paired bootstrap 95% interval for the accuracy difference.
Also report full per-category accuracy, unmapped counts, conflict count,
individual execution receipts, tokens, elapsed time, and total calls.

Secondary, non-familywise diagnostics include SC3 versus D1, GJ3 versus D1,
D2/D3 accuracy, conflict-set candidate headroom, and signal-following rates.
No category-specific policy, threshold, item exception, or post-score repair
may change a primary arm.

## Relationship to earlier evidence

The reused Universal 941-row result (`+21`, one-sided exact McNemar
`p=0.0005325`) remains mechanism-development evidence because its candidates
and outcomes were previously exposed. The balanced 464-row Korean legal
outcome experiment is a separately preserved boundary-condition result: its
mechanical overlap signal was correct on only 32/65 signaled conflicts and is
not pooled with this MCQ confirmation. Neither prior dataset is used to tune a
row or threshold in this protocol.
