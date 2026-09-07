# Supplementary Material for “Mini Artichokes: Selective Arbitration of Repeated LLM Disagreement”

This supplement expands the data construction, frozen prompts, evaluation,
per-category results, execution receipts, and boundary analyses for the main
paper. It does not introduce a broader claim than the main text. The two fresh
MMLU-Pro cohorts are the only confirmatory performance evidence; the Universal
set is development evidence and the Korean legal reserve is a negative domain
boundary.

## S1. Reproducibility map

### S1.1 Confirmatory artifacts

| Artifact | Role | SHA-256 |
|---|---|---|
| Official MMLU-Pro test parquet | Source population (12,032 rows) | `0e24a191921c2f453518a537a8b2117bd137e7714d4ef1565e9ba06c1ecb9ad8` |
| Confirmation-1 public JSONL | Gold-free solver input, 1,000 rows | `b7f7962ea0b3da74257c69f68e05116a54c11b96308040e692f725d5f31301f6` |
| Confirmation-1 private JSONL | Separated scoring labels | `c87d2722fc332493d18b4f0d46e1f89be850348a5f1b5f6b1a9b7aec6fa22697` |
| Confirmation-1 score JSON | Frozen score output | `5ba78d945aff95e5c3b7d93b0a44d592bbe16b2587d4d2228d179f5e1339128f` |
| Replication-2 public JSONL | Gold-free solver input, 1,000 rows | `de26ddbd37f67fa088867debff8af65b6ca90746059c03a4fe25c417135e197f` |
| Replication-2 private JSONL | Separated scoring labels | `637627ba77e968ded9a48ce45e86bfce53bfac1cc5aaa8f27e855d15319055cb` |
| Replication-2 protocol | Unchanged-policy replication contract | `0fe6bd59e759d1c761770267fe9b7a8f2bef5e2f47ba6c768e57cfe35352c9a7` |
| Replication-2 score JSON | Frozen score output | `2442d9018a0241e203500f85e859d76c78cda52f74277090856f5b40d3ca7685` |
| Cumulative score JSON | Primary pooled result | `bdf7e36abcf05b8a05d921a259590b919f54da2b7a1658dcc4057acabc905fec` |

The source repository was `TIGER-Lab/MMLU-Pro` at Git commit
`b189ec765aa7ed75c8acfea42df31fdae71f97be`. The two public ID lists have
intersection zero and union size 2,000. Hashes and execution receipts are
provenance controls, not scientific contributions.

### S1.2 Evidence roles

The evidence was partitioned before interpreting the final claim:

- **Development:** 941 previously inspected Universal Artichoke questions.
  These were used to select the strict overlap-policy family and cannot be
  treated as confirmation.
- **Confirmation 1:** the first category-proportional MMLU-Pro sample of 1,000
  rows. This produced the first statistical look.
- **Replication 2:** the next disjoint category-proportional 1,000 rows under
  the identical mechanism and prompts.
- **Negative boundary:** 464 balanced Korean civil/tax outcome cases. This
  reserve is not pooled with MMLU-Pro. Its direct reference is the
  plain-instruction P1 arm; D1-D3 denote separate structured draws.

## S2. Dataset construction and separation

### S2.1 Deterministic MMLU-Pro selection

The selection seed was
`mini-artichokes-mmlu-pro-confirmation-v1-20260901`. The builder first removed
exact duplicate normalized prompts and screened against the 1,309-row
Universal public question file. The selected MMLU-Pro rows had zero exact
normalized prompt matches or sufficiently long question-containment matches
with that prior file.

Let category k contain N_k eligible questions and let N be the
requested cumulative sample size. We assigned

\[
qₖ = N × Nₖ / Σⱼ Nⱼ
\]

questions by the largest-remainder method. Within each category, the ordering
key was SHA-256 of `(seed, category, question_id)`. Neither `answer`,
`answer_index`, nor `cot_content` was an input to selection. Confirmation 1
used cumulative ranks 0--999. Replication 2 was the difference between the
largest-remainder allocations for cumulative N=2,000 and N=1,000,
which yields the immediately following disjoint 1,000 ranks.

### S2.2 Category allocation

| Category | Confirmation 1 | Replication 2 | Pooled |
|---|---:|---:|---:|
| Biology | 60 | 59 | 119 |
| Business | 66 | 65 | 131 |
| Chemistry | 94 | 94 | 188 |
| Computer science | 34 | 34 | 68 |
| Economics | 70 | 70 | 140 |
| Engineering | 81 | 80 | 161 |
| Health | 68 | 68 | 136 |
| History | 32 | 31 | 63 |
| Law | 91 | 92 | 183 |
| Math | 112 | 113 | 225 |
| Other | 77 | 77 | 154 |
| Philosophy | 41 | 42 | 83 |
| Physics | 108 | 108 | 216 |
| Psychology | 66 | 67 | 133 |
| **Total** | **1,000** | **1,000** | **2,000** |

### S2.3 Public/private boundary

The public JSONL contained only an ID, category, language, suite, response
format, and formatted question with answer options. The private JSONL held the
correct option index and source metadata. Private files were not mounted in
solver or judge workspaces. Scoring began only after D1--D3, GJ3, and OJ3 had
accepted final receipts. Model sessions had no network, retrieval, memory,
plugins, applications, MCP services, or access to other candidate outputs.

### S2.4 Korean legal-reserve construction and governance

The legal reserve was selected from a local 526-case Korean precedent corpus
and balanced to 464 cases across civil/tax and grant/dismiss cells. Source
labels in the selected records were 384 `01_joonhok_precedents`, 75
`02_lbox_open`, and five `lawlaw`. The first source is a Hugging Face dataset
labelled OpenRAIL and described as a 2023 snapshot of precedents from the
Korean government Law Open Data service. The LBox Open repository identifies
Law Open Data as a source and is licensed CC BY-NC 4.0. The five legacy
`lawlaw` records have no recoverable reuse metadata in the local corpus.

Before model access, the construction script omitted the target holding and
replaced target court, case number, and decision date with fixed placeholders
when present. Among the 464 selected records, 116 had at least one such
replacement: 288 court-field occurrences, 91 case-number occurrences, and 100
date-field occurrences were replaced, with multiple occurrences and fields
possible in one record. These transformations minimize direct source metadata;
they do not establish comprehensive de-identification of narrative facts.
Distinctive events can retain residual re-identification risk. For this
reason, and because five records lack recoverable reuse metadata, item-level
legal text and model outputs are withheld pending governance review. Only the
frozen protocol and aggregate negative-boundary statistics are reported.

## S3. Frozen model and prompt contract

### S3.1 Runtime configuration

Every semantic call used `gpt-5.6-luna`, reasoning effort `high`, verbosity
`low`, service tier `default`, and an authenticated isolated Codex CLI profile.
The machine-specific account path is intentionally omitted from the
double-blind artifact. Provider temperature was not exposed by this runtime.
No model training or fine-tuning occurred.

Each draw was one isolated invocation over the complete 1,000-row file. The
machine ran heavy calls sequentially for memory safety, but the draws had
identical immutable input and could not read one another. A completed call was
not eligible for item-level retries, repairs, or top-ups.

### S3.2 Exact D1--D3 solver instructions

The following text was supplied as `input/RUN_INSTRUCTIONS.md` to each of the
three candidate sessions:

```text
# MMLU-Pro whole-file solver contract

This is one model invocation over the complete 1,000-question public file.
Do not spawn agents, call another model, browse the web, or inspect paths
outside this isolated workspace. Solve every row in `input/questions.jsonl`
independently from its question and options.

For each row, write the exact text of one selected option to `finalAnswer`.
Do not write only an option letter or number, and do not append a rationale.
Write progress to `output/answers.partial.jsonl`. When all rows are complete,
atomically finish `output/answers.jsonl` in input order. Every line must be
exactly one UTF-8 JSON object with no extra keys:

`{"id":"the exact input id","finalAnswer":"exact selected option text"}`

There must be exactly 1,000 non-empty rows and every supplied ID exactly once.
The final chat message should only state whether the complete file was made.
```

The invocation prompt was: “Read `input/RUN_INSTRUCTIONS.md` completely, obey
it, process the complete input file, and produce the required final output
file.” A deterministic parser mapped exact or meaning-preserving option text
back to an option. Unmapped answers counted wrong; no row was removed.

### S3.3 Exact common judge instructions

Both GJ3 and OJ3 received the same common text:

```text
# Matched MMLU-Pro candidate judge

This is one invocation over the complete supplied conflict file. Do not spawn
agents, call another model, browse the web, or inspect paths outside this
isolated workspace. Each row contains one original MCQ and two anonymous
candidate answers. Choose the candidate that is actually correct. You may use
short local calculations, but you may not synthesize a third answer.

For every row, `finalAnswer` must copy exactly one supplied candidate answer,
with no label, explanation, or rewriting. Write progress to
`output/answers.partial.jsonl`, then atomically finish
`output/answers.jsonl` in input order. Every line must have exactly:

`{"id":"exact input id","finalAnswer":"exact candidate answer"}`

Include every supplied ID exactly once. The final chat message is only a
completion notice.
```

GJ3 then received only this note:

```text
Candidate order is deterministically randomized and carries no provenance or
support information. Judge only correctness against the public question.
```

OJ3 instead received only this treatment note:

```text
Each row also states the mechanical independent support count for each
candidate: one candidate came from one complete-file draw, and the other is
the common canonical option from two other independent complete-file draws.
This count is not proof of correctness; correlated solvers can agree on the
same wrong answer. Use it only after checking the public question.
```

Candidate order was rotated deterministically by a hash of the case ID. The
hidden map used roles `base` and `consensus`; the judge saw only C1/C2. GJ3 and
OJ3 had the same eligible IDs, candidate strings, rotation, model, reasoning
effort, semantic call count, and base fallback. Only OJ3 received the
one-versus-two support field and warning.

## S4. Arm construction and invariants

For every row, D1 was the preassigned base and D2/D3 were auxiliary draws.
The eligible conflict event was C=1 when D1, D2, and D3 all mapped to options
and D2=D3≠D1; otherwise C=0.

- **D1:** return D1.
- **SC3:** return the option with at least two valid votes; otherwise D1.
- **GJ3:** on (C=1), let an anonymous support-hidden judge choose D1 or the
  D2=D3 candidate; otherwise D1.
- **OJ3:** identical to GJ3, with the support-count treatment described above.

The following invariants were machine checked before private scoring:

1. input IDs were unique and outputs followed the exact ID order;
2. all arms used the complete 1,000-row denominator;
3. generic and support-aware judges received identical conflict IDs and
   anonymous candidate role maps;
4. judge output had to copy one supplied candidate; invalid choices retained
   D1;
5. selection, prompts, model, effort, fallback, and statistics were unchanged
   between cohorts;
6. the two public ID sets were disjoint; and
7. no third cohort was permitted under the confirmatory protocol.

SC3's majority rule has one boundary outside the all-valid conflict event: an
invalid D1 with valid, agreeing D2 and D3. A post hoc audit found zero such
rows in confirmation 1 and two in replication 2 (`mmlu-pro-06430` and
`mmlu-pro-01180`). SC3 used the D2/D3 consensus on both; both consensus
answers were wrong, and invalid D1 was also scored wrong. Requiring all-three
validity for SC3 would therefore change neither accuracy nor any paired
comparison. The 68-row conflict set reported for GJ3 and OJ3 remains exactly
the pre-specified all-valid event.

## S5. Statistical procedures

### S5.1 Paired exact test

For candidate system S and reference R, let b be rescues
(S correct, R wrong) and c be harms (S wrong, R correct).
Under the paired null, the exact one-sided McNemar p-value for superiority is

\[
p = Pr[X ≥ b], where X ~ Binomial(b+c, 0.5).
\]

Two-sided values are (2\min[\Pr(X\le c),\Pr(X\ge b)]), capped at one. The
effect estimate is ((b-c)/N). Ties contribute to accuracy but not the exact
discordant-pair test.

### S5.2 Confidence intervals

Confidence intervals used 20,000 paired bootstrap resamples. Cohort-level
analyses were stratified by category. The pooled analysis was stratified by
`(cohort, category)` so that the original cohort sizes and disciplinary mix
were preserved. Each resample recomputed the full-denominator paired accuracy
difference.

### S5.3 Two-look and fixed-sequence control

Confirmation 1 was the first look. Because it did not cross .025, exactly one
unchanged, disjoint replication was allowed. The pooled headline boundary was
one-sided alpha=.025, yielding a conservative Bonferroni familywise bound of
.05 over two looks.

Within the pooled analysis, hypotheses were tested in this fixed order at
alpha=.025:

1. OJ3 > D1;
2. OJ3 > SC3;
3. OJ3 > GJ3.

Formal testing stopped after the first unrejected comparison. Thus OJ3>D1 was
rejected, OJ3>SC3 was reached but not rejected, and OJ3>GJ3 was descriptive
only. All estimates and unadjusted p-values are still disclosed.

## S6. Full results

### S6.1 Accuracy and mapping by cohort

| Arm | Confirmation 1 correct | Confirmation 1 unmapped | Replication 2 correct | Replication 2 unmapped | Pooled correct |
|---|---:|---:|---:|---:|---:|
| D1 | 597 | 151 | 590 | 137 | 1,187 |
| D2 | 145 | 128 | 607 | 138 | 752 |
| D3 | 587 | 146 | 586 | 133 | 1,173 |
| SC3 | 596 | 151 | 613 | 135 | 1,209 |
| GJ3 | 600 | 151 | 611 | 137 | 1,211 |
| OJ3 | **601** | 151 | **613** | 137 | **1,214** |

Unmapped outputs were retained in the denominator and counted wrong. The D2
confirmation-1 anomaly was not merely a high-unmapped event: 872 responses
mapped, but the complete-file session still scored only 145/1,000. Its receipt
and output were preserved rather than repaired. Replication 2 independently
shows the headline direction without relying on that session.

### S6.2 Paired results by cohort

| Cohort and comparison | Rescues | Harms | Net | One-sided exact p | Two-sided exact p | Bootstrap 95% CI (pp) |
|---|---:|---:|---:|---:|---:|---:|
| Confirmation 1: OJ3 vs D1 | 5 | 1 | +4 | .109375 | .21875 | [0.0, +0.9] |
| Confirmation 1: OJ3 vs SC3 | 5 | 0 | +5 | .03125 | .0625 | [+0.1, +1.0] |
| Confirmation 1: OJ3 vs GJ3 | 1 | 0 | +1 | .5 | 1.0 | [0.0, +0.3] |
| Replication 2: OJ3 vs D1 | 28 | 5 | +23 | 3.309e-5 | 6.619e-5 | [+1.2, +3.5] |
| Replication 2: OJ3 vs SC3 | 2 | 2 | 0 | .6875 | 1.0 | [-0.4, +0.4] |
| Replication 2: OJ3 vs GJ3 | 5 | 3 | +2 | .36328 | .72656 | [-0.3, +0.8] |

### S6.3 Pooled paired results

| Comparison | Rescues | Harms | Discordant | Net | Difference (pp) | One-sided exact p | Two-sided exact p | Bootstrap 95% CI (pp) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **OJ3 vs D1** | **33** | **6** | **39** | **+27** | **+1.35** | **7.150e-6** | **1.430e-5** | **[+0.75, +1.95]** |
| OJ3 vs SC3 | 7 | 2 | 9 | +5 | +0.25 | .08984 | .17969 | [-0.05, +0.55] |
| OJ3 vs GJ3 | 6 | 3 | 9 | +3 | +0.15 | .25391 | .50781 | [-0.15, +0.45] |
| SC3 vs D1 | 35 | 13 | 48 | +22 | +1.10 | .001044 | .002088 | [+0.45, +1.80] |
| GJ3 vs D1 | 29 | 5 | 34 | +24 | +1.20 | 1.928e-5 | 3.856e-5 | [+0.65, +1.80] |

### S6.4 Pooled results by category

These category results are descriptive; no category-specific policy or
multiplicity-adjusted claim was pre-specified.

| Category | n | D1 | SC3 | GJ3 | OJ3 |
|---|---:|---:|---:|---:|---:|
| Biology | 119 | 89/119 (74.8%) | 88/119 (73.9%) | 89/119 (74.8%) | 88/119 (73.9%) |
| Business | 131 | 88/131 (67.2%) | 89/131 (67.9%) | 89/131 (67.9%) | 89/131 (67.9%) |
| Chemistry | 188 | 96/188 (51.1%) | 97/188 (51.6%) | 99/188 (52.7%) | 99/188 (52.7%) |
| Computer science | 68 | 36/68 (52.9%) | 38/68 (55.9%) | 38/68 (55.9%) | 38/68 (55.9%) |
| Economics | 140 | 90/140 (64.3%) | 93/140 (66.4%) | 92/140 (65.7%) | 93/140 (66.4%) |
| Engineering | 161 | 70/161 (43.5%) | 76/161 (47.2%) | 75/161 (46.6%) | 76/161 (47.2%) |
| Health | 136 | 99/136 (72.8%) | 99/136 (72.8%) | 99/136 (72.8%) | 100/136 (73.5%) |
| History | 63 | 44/63 (69.8%) | 45/63 (71.4%) | 45/63 (71.4%) | 45/63 (71.4%) |
| Law | 183 | 106/183 (57.9%) | 110/183 (60.1%) | 110/183 (60.1%) | 111/183 (60.7%) |
| Math | 225 | 114/225 (50.7%) | 115/225 (51.1%) | 115/225 (51.1%) | 115/225 (51.1%) |
| Other | 154 | 98/154 (63.6%) | 98/154 (63.6%) | 99/154 (64.3%) | 99/154 (64.3%) |
| Philosophy | 83 | 54/83 (65.1%) | 54/83 (65.1%) | 54/83 (65.1%) | 54/83 (65.1%) |
| Physics | 216 | 108/216 (50.0%) | 112/216 (51.9%) | 112/216 (51.9%) | 112/216 (51.9%) |
| Psychology | 133 | 95/133 (71.4%) | 95/133 (71.4%) | 95/133 (71.4%) | 95/133 (71.4%) |
| **All** | **2,000** | **1,187 (59.35%)** | **1,209 (60.45%)** | **1,211 (60.55%)** | **1,214 (60.70%)** |

The effect is not uniform: OJ3 was one answer below D1 in biology and equal in
several categories. These cells are too small for separate superiority claims.

## S7. Conflict-set mechanism diagnostics

The trigger fired on 14 confirmation-1 questions and 54 replication-2
questions, 68/2,000 (3.4%) in total. All following analyses are descriptive.

| Quantity on pooled conflicts | Count |
|---|---:|
| D1/base correct | 13 |
| D2=D3 consensus correct | 35 |
| Both available candidates wrong | 20 |
| SC3 correct | 35 |
| GJ3 correct | 37 |
| OJ3 correct | 40 |
| GJ3 consensus selections | 47 |
| GJ3 base selections | 21 |
| OJ3 consensus selections | 52 |
| OJ3 base selections | 16 |

For OJ3's 16 base-retention decisions, base and consensus accuracy differed
on nine: base was correct in seven and consensus in two. Both candidates were
wrong in the other seven. This gives +5 over always choosing the consensus.
OJ3 and GJ3 differed on 13 conflicts: OJ3 alone was correct in six, GJ3 alone
in three, and both were wrong in four. The resulting +3 estimate does not
establish a causal benefit of displaying the support count.

The mechanism supported by the experiment is therefore narrower than the
original “validated overlap” wording: a two-against-one agreement event can be
a useful review route on MMLU-Pro, and anonymous arbitration can avert some
majority harms. Same-model agreement is not validation, and the additional
support annotation remains unconfirmed relative to GJ3.

## S8. Compute, latency, and receipts

### S8.1 Per-call execution

All calls below had one semantic model invocation and status `accepted`.
`Input` includes cached input; `Total` is the provider-reported total token
count.

| Cohort | Call | Elapsed (s) | Input | Cached input | Output | Reasoning output | Total |
|---|---|---:|---:|---:|---:|---:|---:|
| Confirmation 1 | D1 | 1,375.057 | 7,805,925 | 7,417,344 | 64,160 | 51,272 | 7,870,085 |
| Confirmation 1 | D2 | 1,552.692 | 8,143,819 | 7,795,456 | 73,068 | 55,381 | 8,216,887 |
| Confirmation 1 | D3 | 1,155.807 | 4,363,513 | 4,074,752 | 51,413 | 40,417 | 4,414,926 |
| Confirmation 1 | GJ3 | 207.962 | 215,280 | 191,232 | 10,255 | 7,407 | 225,535 |
| Confirmation 1 | OJ3 | 267.971 | 319,857 | 280,576 | 13,333 | 8,717 | 333,190 |
| Replication 2 | D1 | 1,101.886 | 5,090,888 | 4,780,288 | 48,348 | 35,220 | 5,139,236 |
| Replication 2 | D2 | 1,399.071 | 5,739,660 | 5,397,248 | 65,344 | 51,116 | 5,805,004 |
| Replication 2 | D3 | 1,576.353 | 13,543,705 | 12,879,616 | 66,590 | 50,031 | 13,610,295 |
| Replication 2 | GJ3 | 357.338 | 487,823 | 427,008 | 17,858 | 14,313 | 505,681 |
| Replication 2 | OJ3 | 358.947 | 566,221 | 488,192 | 17,936 | 15,036 | 584,157 |

### S8.2 Aggregate compute

| System | Semantic calls per cohort | Pooled tokens | Ratio to D1 |
|---|---:|---:|---:|
| D1 | 1 | 13,009,321 | 1.00x |
| SC3 | 3 | 45,056,433 | 3.46x |
| GJ3 | 4 | 45,787,649 | 3.52x |
| OJ3 | 4 | 45,973,780 | 3.53x |

The OJ3 judge stage added 917,347 tokens beyond D1--D3, 2.04% of the SC3
three-draw total. OJ3 and GJ3 differed by 186,131 tokens, 0.41% of GJ3.
Observed parallelized critical paths, using the slowest of D1--D3 plus the OJ3
judge, were 1,820.7 s and 1,935.3 s; the corresponding D1 elapsed times were
1,375.1 s and 1,101.9 s. These measurements characterize the whole-file
runtime and do not imply equal monetary cost or per-question deployment
latency.

### S8.3 Receipt hashes

| Cohort | Call | Receipt SHA-256 |
|---|---|---|
| Confirmation 1 | D1 | `10e9b583ef3ee2283c6890488952c6b90ca3012b431580093cf7c63e01e308e7` |
| Confirmation 1 | D2 | `b2e29e443757a8378e391fb1e287cf8e4f2a7d04e1607123b17237d2fa4ce469` |
| Confirmation 1 | D3 | `ec9bba97bdedbeb3af619b4722088defa91f5241db914a9c06268439c4afda7a` |
| Confirmation 1 | GJ3 | `716a7a0ea0fb9596a0d7c43ab78eb21655fe8c314bc67d784a9edbbf492df8fa` |
| Confirmation 1 | OJ3 | `f0dba93c9d748c3d87247e36759565df72e95a58258c805e7fa7f5599169db21` |
| Replication 2 | D1 | `857f28e3f0f24c288fa0e6707b021e2d3f6c4d5bd6a51a6ebb38f117529c0ff6` |
| Replication 2 | D2 | `33e6472e67052f2ac4e3dfcdec7ad77f472c5b054f59258d09cd5ef35997f113` |
| Replication 2 | D3 | `ab2121a834c582a06a7e6eb1d44b1f556487af2dea3d005845d6f3c6c7af11c6` |
| Replication 2 | GJ3 | `8bdf60e757e1caadf5601def055460ac807b6834d40a370f1c8518af5b099d38` |
| Replication 2 | OJ3 | `288027637b18e2ba7115476be0a935cd667e9689472d917d96a8aad3265cd82a` |

## S9. Development evidence and negative boundary

### S9.1 Universal development set

On the previously inspected 941-row Universal multiple-choice development
set, the base scored 566 and strict V3 scored 587: 30 rescues, 9 harms, +21,
with one-sided exact McNemar p=.0005325. This result motivated the conflict
policy but is post-selection evidence. It is not included in the MMLU-Pro
denominator, p-value, or confidence interval.

### S9.2 Korean legal-outcome reserve

The 464-case reserve was balanced across civil/tax and grant/dismiss outcome
cells. It differs substantively from MMLU-Pro: a partial fact pattern may not
determine a unique future judgment.

| Arm | Correct | Accuracy |
|---|---:|---:|
| P1 direct Luna | 284/464 | 61.21% |
| Structured D1 | 259/464 | 55.82% |
| GJ3 | 263/464 | 56.68% |
| OJ3 | 255/464 | 54.96% |

Relative to P1, OJ3 had 30 rescues and 59 harms, a net loss of 29. On the 65
cases carrying the stricter mechanical support signal, the supported outcome
was correct 32 times (49.2%). This is evidence against a domain-general overlap
claim. Shared assumptions under partial observation are one possible
explanation, but this comparison cannot isolate that mechanism because domain,
task, prompt, and label structure changed together.

## S10. Deviations, anomalies, and claim limits

No mechanism or prompt deviation occurred between the two MMLU-Pro cohorts.
The following observations limit interpretation:

1. D2 in confirmation 1 was an accepted but extreme low-performing whole-file
   session. It was neither discarded nor rerun. Replication 2 recovered, and
   its standalone OJ3>D1 result was significant.
2. Only 68/2,000 rows triggered arbitration, leaving the OJ3--GJ3 contrast
   imprecise.
3. Separate sessions of the same model are not independent at the model level.
4. MMLU-Pro may overlap model training data; “fresh” means unseen during policy
   development and disjoint between study cohorts, not post-training.
5. The whole-file design allows within-session context and cache effects; it
   is not equivalent to 1,000 independent API calls. The two cohorts reran the
   policy on different questions, not the same items, so paired item-level
   tests condition on the realized whole-file sessions and do not estimate
   between-session repeatability.
6. OJ3 is matched in semantic calls and approximately in tokens to GJ3, not to
   D1. The 1.35-point gain over D1 costs 3.53 times the observed tokens.
7. The confirmatory result supports OJ3 over direct Luna on this benchmark. It
   does not establish superiority over SC3 or GJ3, nor universal legal or
   open-ended transfer.
8. The legal reserve is a simultaneous domain/task/prompt/label shift and
   cannot identify the cause of non-transfer. Its item texts are not released
   because the source audit found residual re-identification risk and five
   records without recoverable reuse metadata.

The original exploratory Mini Artichokes tables are retained in the project
archive for provenance but are not mixed into this confirmatory supplement.
This replacement resolves the earlier mismatch between broad legacy claims
and the evidence available for statistical review.
