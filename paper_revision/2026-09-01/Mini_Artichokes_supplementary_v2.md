# Supplementary Material for “Mini Artichokes: Verifier-Gated Recursive Portfolios for Test-Available Program Repair”

This supplement expands the data construction, frozen prompts, evaluation,
per-category results, execution receipts, and boundary analyses for the main
paper. It does not introduce a broader claim than the main text. The primary
system is recursive verified redundancy with direct and overlap-aware final
routes; TOV is the overlap-aware component rather than the whole-system causal
claim. The coding evidence retains three complete official Aider tracks:
Rust30 development, prospective Python34 confirmation, and unchanged C++26
extension. All 90 official tasks in those tracks are retained. A fourth,
previously untouched complete Go39 track evaluates the recursive system under
a before-call freeze; its original Generic comparator was transport-null, so
the later same-input replacement is sensitivity evidence rather than a
confirmatory primary result. A cleanly frozen fifth Aider track retains all 49
JavaScript tasks, and an independent BigCode HumanEvalFixDocs evaluation
retains all 164 Python tasks. JavaScript gives strong end-to-end gains but an
equal-call Generic tie; HumanEvalFix reaches the ordinary-repair ceiling. The
older Java20 and 60-task campaigns document
failure-driven development; MMLU-Pro is a secondary answer-overlap boundary.
Universal and LEET are development screens, and the Korean legal reserve is a
negative domain boundary.

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
| Cumulative score JSON | Descriptive unchanged-policy aggregate | `bdf7e36abcf05b8a05d921a259590b919f54da2b7a1658dcc4057acabc905fec` |
| Aider confirmation freeze | Official 10-Python/10-Rust hidden-test batch | `aa21718408670a2367687c42be538d1766ad74e222e61d726b54f1c13cdaa3e9` |
| Aider replication freeze | Remaining official 20-Rust hidden-test batch | `b3634fb1f3e424f77112996e877adc379af9ce9901c270c855b13f49d7d6ec7e` |
| Aider pooled score JSON | Exploratory paired coding result | `0c618e58ab5720e1044da799193325a5018c27e911179ed75048351af72461c1` |
| Aider Java20 final freeze | SHA-ranked official Java hidden-test batch | `b12e7d7a4904084b35cae8bca1f492d9173a46d7ee6c8dcfe8165cd3a27111c0` |
| Aider Java20/family score JSON | Java matched ablation and 60-task summary | `d1abe2a31712c0d446bba8728118246ce2a262bc44124600de95351df75ed9e6` |
| Java20 session-replication protocol | Five-session confirmatory contract | `d26ce9ce1896cd5c144559425efafcf37b9f6128d5482f22436fbd029a6ca072` |
| Java20 session-replication scorer | Frozen whole-session analysis | `9bfc70b60899c2dc0f205b9d2e484a3d3dd82499db5db50c280d8274bfb1fbe5` |
| Java20 session-replication result | Five-session outcomes and fixed-sequence tests | `75eb1d868b5d5663b77d5730107b01e91f372fb4d58d180caef812e7c7b7be9b` |
| Ordinary-control extension protocol | Review-triggered five-call matched-control contract | `9bd15311378024d798ceef3e1b26ad90135d791f94b852551153b904984de95d` |
| Ordinary-control extension scorer | Frozen matched-minus-ordinary analysis | `4a0447c816738f6619a7eafe23a83ee3f07036992ce86b12911409e331aee430` |
| Ordinary-control extension result | Secondary same-evidence repair comparison | `2f9240417643e193e932d8979052ab137e5450808dbd42e0b6040913d0e03676` |
| Rust30 TOV v2 protocol | Complete-track development contract | `36ec95ab51c64bf7534395015fcb34e13ab8eac0a589166f19ebda3eb54b414d` |
| Rust30 TOV v2 result | Anchored semantic-overlap development outcome | `d2dede77b0fe1a3882f8a4f4ddec9ccd78d5a69ecfa490f3ce2c9d9d53b53d72` |
| Python34 TOV v2 protocol | Prospective unchanged-policy confirmation contract | `c3be8eac9a5f5591a744e2f8a1720ab20904fb4955c41d9e1ea594d93618b291` |
| Python34 TOV v2 result | Complete-track confirmation outcome | `c245e50de3f9c3187fa0f2e0b25f9a48b8cc71ed7a34d4a751cf869fa1614dfc` |
| C++26 TOV v2 protocol | Unchanged-policy complete-track extension | `c5ca6ee814926281b4a3cda08702f0081742742daa86cedace67c24548d1869d` |
| C++26 TOV v2 result | Complete-track extension outcome | `f2f1f24ded5107b72eb4134221ae6189b1ad3dc1963921f843f4920fc186c50b` |
| Shared TOV v2 runner | Verified union, anchor restoration, matched final arms | `b9336d6a8503b0c41f9303a3241b0cc039f9c387c9ca1060484e15f37cb2fb93` |
| Semantic-free structured-control protocol | Review-triggered overlap-specific control over all 90 tasks | `41eb09f2e2c2018b1fd4438c025f345431a79c26365f8804e606d0aff4c9e9ca` |
| Python34 five-pair protocol | Frozen whole-track session replication | `9c4623e39a628698c6a61683c1740975823fb301a2792f00bb4c4dc1c672b126` |
| Python34 five-pair report | Intention-to-treat session and integrity analysis | `6971d78697236c640afe9adcce95d89993ae2733760b720fe0dac01d7d221b18` |
| C++26 five-pair protocol | Frozen second-setting whole-track replication | `6887286920345430148ae09afc9a92efea4b969af43d9957cd01c014dfe433df` |
| C++26 five-pair report | Intention-to-treat session and integrity analysis | `d3d091278fbac6f2002cf29490e99bb8227c3da725d35d6b9039d7ed4882f80b` |
| Replication runner | Candidate-ID-separated final arms | `31e5077308b6bd7b8a4301d104e07c06863bf43aad87a7f6d1ed6b71cfba7134` |
| Recursive dual-route report | Exploratory equal-call and repeated-union analysis | `5cba5ce58492d08312bde1f7723c2f2a5a8d3b47d28889b071f1cf6597148065` |
| Go39 recursive protocol | Before-call frozen complete-track contract | `1281da4fcb0401890543e9d4b6fda46eef9c210344ea7938a6a337ee67cc2308` |
| Go39 replacement-sensitivity protocol | One same-input Generic transport replacement | `59ebe70d94af3720ca8403a15f09e21ab679b07101dd857f0687dd86bb503706` |
| Go39 recursive report | Scores, transport event, integrity, discordance, compute, and Go38 sensitivity | `ded36a1b0db0a4f6bf52224393796a83def26a7176cf26d3cc58bde64a5f684f` |
| Go39 valid Generic replacement result | Post-primary same-input sensitivity arm | `04e33a4660564490ff5f0f3b99c89bc3db11bee061b6a6c917145c5088b5f762` |
| Go39 TOV result | Before-call-frozen overlap route | `5a8418b06dc1cb9493ff04067a5e0def88d9aadf2519af4fdcc76f88b49807aa` |
| JavaScript49 recursive protocol | Clean before-call-frozen complete-track contract | `0db8e0037ecdc4fc376a582a6a4628f2f471a542017141ee6ae610c17b54ea0d` |
| JavaScript49 valid freeze | Corrected full-suite environment frozen before calls | `6abd5a0ee1e4792115bec699485e99d2d39064e435d5f621a70802f0291d55ca` |
| JavaScript49 analysis | Scores, exact tests, unions, integrity, and compute | `4bfc944623b2d59690ad74aff5ad8814539011df5449c4df8874e5bbfd1b4a20` |
| JavaScript49 report | Complete prospective result, invalid smoke-test disclosure, and stability audit | `e72923e43a79ca5e84600dfa05abe372f6643c8db36b97f2ad60cd34c7abad9b` |
| HumanEvalFix164 recursive protocol | Independent-family before-call-frozen contract | `47585a6fb48a96fb4daaf481a30f32d5fab3561fc8be01980288a2fef314c5e5` |
| HumanEvalFix164 freeze | Full 164-task hidden-test package | `07c52db96d1017657ac3161e81c9da3606929b7ce18cfea1edb0a7366f392836` |
| HumanEvalFix164 analysis | Scores, exact tests, unions, integrity, and compute | `197d5c00ea04d3717d20efd8a24202dcce3d421f472017dfa160a72f583641c7` |
| HumanEvalFix164 report | Complete ceiling result and runtime deviation | `c39b96e9656c4490bfa9fb41146cdbfb8a47deaff826b9d9eca8d348cdf4865f` |

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
  rows. It is directional prior evidence in the revised claim hierarchy.
- **Replication 2:** the next disjoint category-proportional 1,000 rows under
  the identical mechanism and prompts; this is the confirmatory evaluation.
- **Negative boundary:** 464 balanced Korean civil/tax outcome cases. This
  reserve is not pooled with MMLU-Pro. Its direct reference is the
  plain-instruction P1 arm; D1-D3 denote separate structured draws.
- **Confirmatory coding replication:** five new independently initialized
  whole-batch sessions on the same frozen official Java20 set. The prior Java
  pilot is excluded; the session is the inferential unit.
- **Review-triggered coding control:** one short ordinary-repair call added to
  each of those immutable Graph sessions after matched outcomes were known.
  It is a secondary same-budget mechanism diagnostic, not confirmation.
- **Secondary coding transfer:** three disjoint 20-task batches from the
  official Aider Polyglot repository: Python/Rust, remaining Rust, and
  SHA-ranked Java. They are never pooled with MMLU-Pro.
- **Method screen:** one official LEET 2026 visible-options block of 20 items,
  used only to compare bounded prompt realizations during development.
- **TOV v2 development:** every official Rust task (30/30 denominator). This
  run froze anchor priority, semantic ledger, prompts, and analysis.
- **TOV v2 prospective confirmation:** every official Python task (34/34)
  under the unchanged Rust-frozen policy.
- **TOV v2 unchanged extension:** every official C++ task (26/26) under the
  same policy. The three-track total is cumulative evidence, not a single new
  pre-registered 90-task experiment.
- **Final-stage session replications:** five new TOV/control pairs on complete
  Python34 and five on complete C++26, each under a frozen alternating-order
  protocol. The original motivating calls are excluded from primary
  replication inference.
- **Recursive Go39 system evaluation:** all 39 official Go tasks under a
  before-call-frozen recursive design. The system and TOV arms are valid; the
  preregistered equal-call primary endpoint is unavailable because the original
  Generic call had no model output. One later model-complete Generic call is
  explicitly post-primary sensitivity evidence.
- **Prospective JavaScript49 system evaluation:** all 49 official Aider
  JavaScript tasks under a clean before-call freeze. All six calls are valid;
  system-versus-Plain and system-versus-ordinary are positive, while the
  equal-call TOV and Generic systems tie exactly.
- **Independent-family ceiling evaluation:** all 164 official BigCode
  HumanEvalFixDocs Python tasks. Plain leaves seven failures, but ordinary
  execution-feedback repair reaches 164/164 before the final routes; the
  benchmark is retained as a portability and ceiling boundary.

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

### S4.1 Expected-gain decomposition

Let `T` be the trigger, `S` an authorized switch from frozen base `B` to
candidate `C`, and all correctness indicators be binary. Write
`q01=Pr(B=0,C=1|T)`, `q10=Pr(B=1,C=0|T)`, and let `s01` and `s10` be the
conditional switch probabilities in those two discordant states. With
`τ=Pr(T)`, cases where both candidates are correct or both are wrong cancel,
giving the exact identity

\[
Δ = τ (q01 s01 - q10 s10).
\]

No draw-independence assumption is needed. Candidate correlation enters
through `q01` and `q10`; judge quality enters through `s01` and `s10`; and
trigger rarity scales the maximum full-denominator effect. SC3 sets both
switch probabilities to one on an eligible conflict. OJ3 can improve over GJ3
only if the support field changes those probabilities in a favorable weighted
direction. Replication 2 realized 28 OJ3 rescues and 5 harms, so the identity
gives `(28-5)/1,000=.023`. The OJ3-versus-GJ3 contrast depends only on their
small decision-disagreement set, not the full 1,000 rows.

For coding, take `B` as the frozen Graph task outcome, `C` as the repaired
outcome, `T` as observed test evidence, and `S` as an authorized edit. The
same rescue-minus-harm identity holds over the task-session distribution.
Preservation can reduce opportunities for harm, but boundedness alone does not
imply positive gain; the empirical condition remains rescues greater than
harms.

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

### S5.3 Replication and fixed-sequence control

Confirmation 1 was scored before replication 2 was authorized. To avoid an
unsupported adaptive-pooling claim, replication 2 alone is confirmatory; the
unchanged-policy 2,000-question aggregate is descriptive.

Within replication 2, hypotheses were tested in this fixed order at one-sided
alpha=.05:

1. OJ3 > D1;
2. OJ3 > SC3;
3. OJ3 > GJ3.

Formal testing stopped after the first unrejected comparison. Thus OJ3>D1 was
rejected (`p=3.309e-5`), OJ3>SC3 was reached but not rejected (`p=.6875`), and
OJ3>GJ3 was descriptive only. All cohort and aggregate estimates are still
disclosed.

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

The post hoc integrity audit found exactly 1,000 rows, the expected schema, and
the expected ID order. D2 had fewer unmapped rows (128) than D1 (151) or D3
(146). Its raw letter choices matched 25 of the first 26 gold answers before
accuracy collapsed over later positions and categories. A constant-offset
scan found its best raw-choice alignment at offset zero (170 matches); every
nonzero shift was worse. The evidence rules out truncation, schema loss, and a
simple fixed row shift, but it cannot distinguish among semantic trajectory,
long-context, cache, or other session-level causes.

### S6.2 Paired results by cohort

| Cohort and comparison | Rescues | Harms | Net | One-sided exact p | Two-sided exact p | Bootstrap 95% CI (pp) |
|---|---:|---:|---:|---:|---:|---:|
| Confirmation 1: OJ3 vs D1 | 5 | 1 | +4 | .109375 | .21875 | [0.0, +0.9] |
| Confirmation 1: OJ3 vs SC3 | 5 | 0 | +5 | .03125 | .0625 | [+0.1, +1.0] |
| Confirmation 1: OJ3 vs GJ3 | 1 | 0 | +1 | .5 | 1.0 | [0.0, +0.3] |
| Replication 2: OJ3 vs D1 | 28 | 5 | +23 | 3.309e-5 | 6.619e-5 | [+1.2, +3.5] |
| Replication 2: OJ3 vs SC3 | 2 | 2 | 0 | .6875 | 1.0 | [-0.4, +0.4] |
| Replication 2: OJ3 vs GJ3 | 5 | 3 | +2 | .36328 | .72656 | [-0.3, +0.8] |

### S6.3 Descriptive pooled paired results

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
   session. It was neither discarded nor rerun. Its complete ordered output,
   ordinary invalid count, and failed constant-offset recovery rule out the
   simplest formatting explanations but do not identify a semantic cause.
   Replication 2 recovered, and its standalone OJ3>D1 result was significant.
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
   D1. The confirmatory replication gain is 2.3 points; across both cohorts,
   the descriptive OJ3 path costs 3.53 times D1's observed tokens.
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

## S11. Official Aider coding transfer

### S11.1 Source, task selection, and information boundary

The source was `Aider-AI/polyglot-benchmark` at Git commit
`7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`. The repository contains 225
curated Exercism tasks across six languages; this study evaluates only the 60
tasks described below and is not an Aider leaderboard submission.

| Batch | Selection | Tasks | Freeze SHA-256 |
|---|---|---:|---|
| Confirmation | Seed-ranked 10 unseen Python + 10 Rust | 20 | `aa21718408670a2367687c42be538d1766ad74e222e61d726b54f1c13cdaa3e9` |
| Replication | Every remaining Rust task not in confirmation, lexicographic | 20 | `b3634fb1f3e424f77112996e877adc379af9ce9901c270c855b13f49d7d6ec7e` |
| Java confirmation | 20 lowest frozen SHA ranks from 47 Java tasks | 20 | `b12e7d7a4904084b35cae8bca1f492d9173a46d7ee6c8dcfe8165cd3a27111c0` |

The sets have no shared task ID. Before any model call, gold
`.meta/example.*` implementations were removed from both public and evaluator
copies. Official test files were removed from the agent copy and retained only
under a private evaluator root. Bubblewrap masked host `/home`, `/mnt`, `/root`,
`/tmp`, and `/var/tmp`, then mounted only the agent workspace, Codex executable,
and authentication file. An explicit probe confirmed that the private root was
unreachable and no test file remained public. For Java, the evaluator removed
only progressive-unlock `@Disabled` annotations in its temporary private copy;
all test bodies and expected values were unchanged. Untouched starter scores
were 0/20, 0/20, and 1/20 (Java `tree-building`).

### S11.2 Exact method leads

Every arm used `gpt-5.6-luna`, medium reasoning, low verbosity, no web,
plugins, skills, memory, or multi-agent delegation. One call received all 20
tasks in a batch. The complete official task prose and solution-file list were
appended after these leads.

Plain lead:

```text
Solve the complete frozen batch directly from the official instructions and
starter files. Tests are intentionally hidden. Infer edge cases, implement the
smallest complete solutions, and edit only listed solution files.
```

Graph lead:

```text
Solve every official exercise from first principles without access to tests.
For each exercise, form a compact reasoning graph covering requirements,
implementation choices, edge cases, and invariants. Use supports, contradicts,
and depends-on relations, and try to falsify the chosen implementation with at
least one derived counterexample. Keep the graph internal and edit only listed
solution files.
```

Ordinary repair received the frozen Graph patch and its exact official failure
stdout, followed by:

```text
This is an ordinary second-pass test-feedback repair baseline. Continue from
the frozen Graph implementation. Use the supplied official failure output to
fix every failing task, without changing tasks that passed unless required by
a shared concrete defect. Edit only listed solution files. The hidden tests
remain unavailable.
```

The proposed repair received the identical patch and stdout, followed by:

```text
Act as a graph-overlap completion verifier and minimal repairer. For each task
independently reconstruct three views: the original requirement graph, the
current implementation/diff, and the observed official test failures or pass.
Localize a defect only when at least two views overlap on the same unmet
obligation. Derive the smallest counterexample and repair the general
obligation instead of memorizing the reported example. Preserve passing tasks
unless concrete cross-view evidence shows an incomplete requirement. Perform a
completion audit twice: re-read every original task, check each claimed fix
against the supplied evidence, inspect the final diff for scope edits, and
confirm every observable outcome.
```

Before the Java sample was frozen, both repair leads were strengthened to
share counterexample generation and the same KIRA-inspired double audit. The
matched lead used the three sources as ordinary evidence; the strict lead
instead added this treatment sentence:

```text
For every proposed defect, explicitly record which of three independent views
supports it: the original specification, the current implementation/diff, and
the observed official test outcome. Authorize a change only when at least two
views converge on the same unmet obligation.
```

No Java prompt was changed after any Java call or score. Both arms received the
same frozen Graph patch and the same complete 99,934-byte failure stdout.

### S11.3 Task results and paired comparisons

Pooled over both disjoint batches, Plain solved 14/40 tasks, Graph 11/40,
ordinary repair 21/40, and the Graph-overlap proposal 22/40.

| Batch / arm | Passed | Accuracy | Agent seconds | Patch lines |
|---|---:|---:|---:|---:|
| Confirmation Plain | 8/20 | 40% | 315.945 | 355 |
| Confirmation Graph | 5/20 | 25% | 411.461 | 379 |
| Confirmation ordinary repair | 12/20 | 60% | 356.982 | 426 |
| Confirmation proposal | 13/20 | 65% | 379.493 | 406 |
| Replication Plain | 6/20 | 30% | 482.176 | 496 |
| Replication Graph | 6/20 | 30% | 486.149 | 223 |
| Replication ordinary repair | 9/20 | 45% | 319.493 | 234 |
| Replication proposal | 9/20 | 45% | 381.007 | 232 |

| Pooled comparison | Rescue / harm | Difference | Exact p, one/two-sided | Task bootstrap 95% CI |
|---|---:|---:|---:|---:|
| Proposal vs Plain | 10 / 2 | +8/40 (+20 pp) | .019287 / .038574 | [+5,+35] pp |
| Proposal vs Graph | 11 / 0 | +11/40 (+27.5 pp) | .000488 / .000977 | [+15,+42.5] pp |
| Proposal vs ordinary repair | 3 / 2 | +1/40 (+2.5 pp) | .5 / 1.0 | [-7.5,+12.5] pp |

The 100,000-draw bootstrap used seed `20260902` and resampled paired tasks. It
is not cluster robust: all 20 outcomes in a batch share one model call, giving
only two independent calls per arm. The two-sided proposal-versus-Plain exact
test crosses .05 at the task level, but this dependence and the exploratory
two-batch sequence preclude a broad population claim.

### S11.4 Java matched ablation and 60-task summary

| Java arm | Passed | Accuracy | Agent seconds | Patch lines |
|---|---:|---:|---:|---:|
| Plain | 3/20 | 15% | 429.392 | 211 |
| Graph | 3/20 | 15% | 499.927 | 238 |
| Matched structured repair | **7/20** | **35%** | 549.682 | 242 |
| Strict overlap repair | 5/20 | 25% | 436.436 | 243 |

Matched repair versus Plain and Graph had four rescues and no harms: +20
points, one-sided exact `p=.0625`, two-sided `p=.125`, and paired bootstrap
[+5,+40] points. Strict overlap versus matched repair had zero rescues and two
harms: -10 points, two-sided `p=.50`, bootstrap [-25,0] points.

The structured-repair family uses the earlier Graph-overlap arm for the first
two batches and matched structured repair for Java. Because the lead was
strengthened before Java, the aggregation is descriptive rather than an
identical-prompt replication.

| 20-task batch | Structured repair | Plain | Graph | Net vs Plain |
|---|---:|---:|---:|---:|
| Python10 + Rust10 | 13 | 8 | 5 | +5 (+25 pp) |
| Disjoint Rust20 | 9 | 6 | 6 | +3 (+15 pp) |
| SHA-ranked Java20 | 7 | 3 | 3 | +4 (+20 pp) |
| **All 60** | **29** | **17** | **14** | **+12 (+20 pp)** |

Across all 60 tasks, the family versus Plain had 14 rescues and 2 harms:
one-sided exact `p=.002090`, two-sided `p=.004181`, and batch-stratified
bootstrap [+8.33,+31.67] points. Versus Graph it had 15 rescues and no harms:
two-sided `p=6.10e-5`, bootstrap [+15,+36.67] points. All three batch effects
were positive, but the one-sided sign test over the three call clusters is
`p=.125`. Task-level inference is conditional on those realized sessions.

### S11.5 Predeclared five-session Java20 replication

The motivating Java pilot above was excluded from the confirmatory test. Before
any replication call, the Java20 tasks, evaluator, runner, Graph lead,
matched-repair lead, model, effort, exactly five new sessions, alternating
Plain/Graph order, fixed hypothesis sequence, and analysis were frozen. Each
matched-repair call started from its own session's Graph patch and received
that attempt's complete official failure stdout. No result-led rerun, top-up,
task deletion, prompt change, or sixth session was allowed.

| New whole-batch session | Call order | Plain | Graph | Matched repair | Matched - Plain | Matched - Graph |
|---:|---|---:|---:|---:|---:|---:|
| 1 | P, G, M | 4/20 | 1/20 | **5/20** | +1 (+5 pp) | +4 (+20 pp) |
| 2 | G, P, M | 2/20 | 2/20 | **6/20** | +4 (+20 pp) | +4 (+20 pp) |
| 3 | P, G, M | 2/20 | 3/20 | **6/20** | +4 (+20 pp) | +3 (+15 pp) |
| 4 | G, P, M | 2/20 | 3/20 | **4/20** | +2 (+10 pp) | +1 (+5 pp) |
| 5 | P, G, M | 2/20 | 2/20 | **4/20** | +2 (+10 pp) | +2 (+10 pp) |

The first fixed-sequence comparison, matched repair > Plain, had five positive,
zero tied, and zero negative session differences. The exact one-sided sign
test was `p=.03125`; the mean difference was +13 percentage points, median
+10, and the 100,000-draw paired whole-session bootstrap 95% interval
[+8,+18]. Because it rejected, the second comparison was reached. Matched
repair > Graph likewise had five positive, zero tied, and zero negative
sessions, exact `p=.03125`, mean +14 points, median +15, and interval [+9,+19].

Repeated task-session counts were 15 rescues and 2 harms versus Plain (net
+13/100) and 15 rescues and 1 harm versus Graph (net +14/100). The same 20
tasks recur, so these are descriptive outcomes rather than 100 independent
tasks. The exact sign tests use the five independently initialized complete
sessions. The result establishes same-task session repeatability of the
predeclared matched policy; it does not establish new-task generality or
identify a causal contribution from its structured components.

Frozen receipt hashes:

- Protocol SHA-256: `d26ce9ce1896cd5c144559425efafcf37b9f6128d5482f22436fbd029a6ca072`.
- Scorer SHA-256: `9bfc70b60899c2dc0f205b9d2e484a3d3dd82499db5db50c280d8274bfb1fbe5`.
- Result SHA-256: `75eb1d868b5d5663b77d5730107b01e91f372fb4d58d180caef812e7c7b7be9b`.

### S11.6 Review-triggered ordinary-repair control

After the matched results and v6 reviewer critique were known, we froze one
short ordinary-repair call for each immutable Graph session. Both repair arms
received the identical Graph patch, original tasks, and complete official
failure stdout, and each added one Luna/medium call. The ordinary prompt only
asked the model to fix failures, preserve passed tasks absent a shared defect,
and edit listed solution files. The five calls, order, runner, prompt, and
analysis were fixed before any ordinary outcome. This controls call count and
evidence, but its post-matched commissioning makes the inference secondary.

| Session | Matched structured repair | Ordinary repair | Matched - ordinary |
|---:|---:|---:|---:|
| 1 | 5/20 | 4/20 | +1 |
| 2 | 6/20 | 6/20 | 0 |
| 3 | 6/20 | 8/20 | -2 |
| 4 | 4/20 | 4/20 | 0 |
| 5 | 4/20 | 5/20 | -1 |

Matched-minus-ordinary differences were `[+1,0,-2,0,-1]`: one positive, two
tied, and two negative sessions. The mean was -2 percentage points, median 0,
paired whole-session bootstrap 95% interval [-7,+2], one-sided exact sign
`p=.875`, and two-sided `p=1.0`. Repeated task-session accounting gave 3
matched rescues and 5 harms. Ordinary repair totaled 27/100 repeated outcomes
versus 25/100 for matched repair; these are not independent-task totals.

As an unplanned descriptive check, ordinary-minus-Plain session differences
were `[0,+4,+6,+2,+3]`, mean +15 points, interval [+6,+24], with four positive
sessions and one tie (`p=.0625`). Ordinary-minus-Graph differences were
`[+3,+4,+5,+1,+3]`, mean +16 points, interval [+10,+21], with five positives
(`p=.03125`). The result supports a separate failure-feedback repair call over
Graph alone, but supplies no accuracy evidence that the explicit counterexample,
preservation, or double-audit instructions add value beyond generic repair.

Frozen extension hashes:

- Protocol SHA-256: `9bd15311378024d798ceef3e1b26ad90135d791f94b852551153b904984de95d`.
- Scorer SHA-256: `4a0447c816738f6619a7eafe23a83ee3f07036992ce86b12911409e331aee430`.
- Result SHA-256: `2f9240417643e193e932d8979052ab137e5450808dbd42e0b6040913d0e03676`.

### S11.7 Compute

| Batch / path | Calls | Agent seconds | Input tokens | Output tokens |
|---|---:|---:|---:|---:|
| Confirmation Plain | 1 | 315.945 | 541,362 | 14,300 |
| Confirmation Graph + ordinary | 2 | 768.443 | 2,163,137 | 35,137 |
| Confirmation Graph + proposal | 2 | 790.954 | 2,401,902 | 36,142 |
| Replication Plain | 1 | 482.176 | 1,707,134 | 21,790 |
| Replication Graph + ordinary | 2 | 805.642 | 2,721,842 | 35,864 |
| Replication Graph + proposal | 2 | 867.156 | 2,756,476 | 38,703 |
| Java Plain | 1 | 429.392 | 675,424 | 16,575 |
| Java Graph + matched repair | 2 | 1,049.609 | 3,679,189 | 39,985 |
| Java Graph + strict overlap | 2 | 936.363 | 2,826,151 | 36,150 |
| Five-session Plain total | 5 | 2,056.922 | 3,869,510 | 84,137 |
| Five-session Graph total | 5 | 2,430.984 | 4,690,002 | 99,608 |
| Five-session matched-repair calls only | 5 | 1,975.104 | 6,557,770 | 78,114 |
| **Five-session complete Graph + matched path** | **10** | **4,406.088** | **11,247,772** | **177,722** |
| Five-session ordinary-repair calls only | 5 | 2,378.479 | 9,000,911 | 91,415 |
| Five-session complete Graph + ordinary path | 10 | 4,809.463 | 13,690,913 | 191,023 |

Input counts include cached input as reported by Codex. The proposed path is
not an efficiency improvement over Plain and has no established accuracy gain
over ordinary repair. Ordinary was slightly cheaper in the first two batches
but used more time and tokens in the later five-session extension, illustrating
trajectory-dependent cost. The Java matched path was more accurate but also
more expensive than strict overlap. In the five-session replication, the
matched-only row is not the full system cost; the complete path is the sum of
Graph and matched repair shown in bold. Java model
workspaces lacked a local runtime/compiler; Plain and Graph could not compile,
while both repair arms received the same host-evaluated failure output.

### S11.8 Deviations and excluded invalid campaigns

Before any Java model call, a starter audit showed that Exercism's Java tests
kept all but the first assertion disabled. The private evaluator was revised
to remove only `@Disabled` markers in its temporary copy, then rehashed and
frozen. The final pre-call freeze is the one reported above. The all-tests
starter score was 1/20; no task, prompt, or outcome was inspected to change the
selection.

The replication corrected one language-specific packaging sentence. The
generic instruction renderer used in confirmation incorrectly told Rust tasks
to use the Python standard library. All confirmation arms saw the identical
sentence, and the method leads above were unchanged. Replication used the
correct Rust-standard-library wording, so it tests the same method family and
outcome but is not a byte-identical prompt replication.

Two invalid replication preparations are retained outside the accepted result.
The first was stopped before model access after two auxiliary Rust tests not
enumerated by `.meta/config.json` were found in the public workspace. The next
campaign ran Plain once, then marked it unsafe because the generated contract
both allowed and forbade a `Cargo.toml` that the official task explicitly
listed as a solution file. Graph and repair arms were never run. A corrected
v2 contract with zero allowed/forbidden intersections was frozen before the
four accepted arms. Exclusion was therefore based on information integrity and
contract validity, not observed comparative performance.

## S12. Official LEET reasoning-method development screen

One 20-question block from the official LEET 2026 visible-options source was
frozen before solver calls. Option IDs were scored deterministically; no model
grader was used. All calls used Luna/high, low verbosity, and no external
information source. Each named method is a bounded prompt realization.

| Method | Calls | Correct | Total tokens | Elapsed seconds |
|---|---:|---:|---:|---:|
| Plain | 1 | 14/20 | 359,582 | 280.687 |
| Self-Consistency SC3 | 3 | 16/20 | 1,631,495 | 886.890 |
| Tree of Thoughts | 1 | 15/20 | 823,376 | 490.597 |
| Reflexion | 1 | 14/20 | 506,204 | 258.806 |
| Self-Refine | 1 | 14/20 | 564,516 | 306.238 |
| Critic/Verifier Separation | 1 | 15/20 | 477,434 | 294.555 |
| Skeleton-of-Thought | 1 | 15/20 | 1,408,183 | 574.593 |
| Graph-of-Thought | 1 | **19/20** | 1,190,101 | 760.879 |
| Three drafts + judge + veto | 5 | 17/20 | about 2,474,621 | about 1,515.5 |

SC3 was the mechanical majority of three independent direct draws, with the
preassigned first draw as a three-way-tie fallback. Graph's +25-point result
over Plain is a development observation from 20 items and is not a powered
generality claim. Its failure to improve on Plain in official hidden-test
coding is evidence that the useful structure depends on the task and feedback
regime.

## S13. Anchored TOV v2 complete-track experiment

### S13.1 Frozen treatment and matched control

Plain, Graph, and ordinary repair were shared candidates. The private evaluator
identified the verified union with frozen passing-candidate priority
`ordinary repair > Graph > Plain`. For every selected task, the complete bytes
of all solution files were stored. The unresolved set contained tasks passed by
none of the three candidates.

Generic and TOV received the same task text, candidate patches, per-task
outcomes, bounded failure traces, verified union, unresolved IDs, model
(`gpt-5.6-luna`), medium reasoning effort, one-call limit, and output cap. After
each final call, the same deterministic adapter restored verified solution
files byte for byte. The final evidence artifacts were byte-identical within
each track. Thus candidate diversity, test feedback, verified-union selection,
and anchor preservation are controlled; the treatment is the final TOV
decision procedure.

For each unresolved task, TOV had to emit exactly one ledger row containing
fault location, violated invariant, counterexample class, edit intent,
semantic candidate agreements/disagreements, falsification attempt, and
selected evidence/action. Semantic agreement was neither sufficient nor
required for editing. It raised confidence; disagreement triggered an explicit
attempt to disprove the leading hypothesis. A requirement-to-diff audit and a
completion audit followed all edits. Literal line intersection and a hard
two-of-three gate were prohibited because the Java predecessor showed that
they can suppress complementary repairs.

### S13.2 Complete denominators and scores

| Track and evidence role | Starter | Plain | Graph | Ordinary | Generic union | TOV v2 | Anchored tasks | Unresolved ledger rows |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Rust all 30, development | 0 | 5 | 8 | 15 | 16 | **18** | 16 | 14 |
| Python all 34, prospective confirmation | 0 | 6 | 5 | 17 | 21 | **23** | 19 | 15 |
| C++ all 26, unchanged extension | 0 | 4 | 8 | 13 | 14 | **17** | 13 | 13 |
| **Cumulative 90** | **0** | **15** | **21** | **45** | **51** | **58** | **48** | **42** |

No task was selected from inside a track. QuixBugs Python40 was separately run
as the complete official suite, but Plain passed all 40 tasks. It is a ceiling
diagnostic, not evidence for TOV.

### S13.3 Paired effects and uncertainty

| TOV contrast, cumulative 90 | Rescues | Harms | Net / percentage points | One-sided exact p | Track-stratified paired-bootstrap 95% CI |
|---|---:|---:|---:|---:|---:|
| TOV vs Plain | 43 | 0 | +43 / +47.8 pp | `1.1369e-13` | `[+37.8,+57.8]` pp |
| TOV vs Graph | 38 | 1 | +37 / +41.1 pp | `7.276e-11` | `[+31.1,+51.1]` pp |
| TOV vs ordinary repair | 13 | 0 | +13 / +14.4 pp | `.0001221` | `[+7.8,+22.2]` pp |
| **TOV vs matched generic union** | **7** | **0** | **+7 / +7.8 pp** | **`.0078125`** | **`[+3.3,+13.3]` pp** |

The bootstrap used 50,000 paired resamples within track and seed 20260902.
The exact task-level test conditions on realized whole-track model calls.
Matched TOV-minus-generic differences were +2 Rust, +2 Python, and +3 C++.
Treating language as the unit yields 3/3 positive signs and one-sided
`p=.125`; three clusters are insufficient for a language-population claim.

### S13.4 Per-track matched contrasts

| Track | TOV vs Plain rescue:harm | One-sided p | TOV vs ordinary rescue:harm | One-sided p | TOV vs generic rescue:harm | One-sided p |
|---|---:|---:|---:|---:|---:|---:|
| Rust30 | 13:0 | `.0001221` | 3:0 | `.125` | 2:0 | `.25` |
| Python34 | 17:0 | `7.629e-6` | 6:0 | `.015625` | 2:0 | `.25` |
| C++26 | 13:0 | `.0001221` | 4:0 | `.0625` | 3:0 | `.125` |

Individual matched generic contrasts are sparse, but all point in the same
direction and their frozen cumulative discordance is 7:0. C++ was added only
after the Python confirmation and is identified as an unchanged extension,
not retroactively folded into the Python confirmatory test.

### S13.5 Anchor and ledger integrity

Rust anchored 32 files across 16 tasks, Python 19 files across 19 tasks, and
C++ 26 files across 13 tasks. Every post-call file matched its frozen anchor
SHA-256. TOV ledger cardinalities were exactly 14, 15, and 13, equal to the
unresolved task counts. The TOV ledger hashes were respectively
`2397192277d983d8482765d242c150421582ea096e2a4c5f38e4652a907be30a`,
`309cf87caa9e873eb9b789822124ebaef575742bdf33432a7f8d099f0d5296f2`,
and `f1612f6ee2312c224593505201a2369330fc392f2adf4572903a49ef58c37f62`.
These are manipulation and provenance checks, not scientific contributions.

### S13.6 Realized final-call cost

| Track | Generic elapsed s | TOV elapsed s |
|---|---:|---:|
| Rust30 | 433.311 | 543.510 |
| Python34 | 395.808 | 439.273 |
| C++26 | 404.511 | 439.527 |

Final arms had the same call count and cap but not exact realized token or time
cost. The comparison therefore supports accuracy at a matched semantic-call
budget, not efficiency or monetary-cost dominance.

## S14. Review-triggered semantic-free structured control

### S14.1 Isolation target

MAC v9 correctly noted that TOV's advantage over the generic Critic could come
from its ledger, falsification, or two audits rather than semantic overlap.
After that critique and all TOV outcomes were known, a secondary control was
frozen. It reused every immutable candidate, outcome trace, verified anchor,
and unresolved task across Rust30, Python34, and C++26. Exactly one new
whole-track call was run per track; no candidate or TOV call was rerun.

The control wrote the same fields and performed the same counterexample-based
falsification and two completion audits. Its semantic relation field was fixed
to `withheld-by-control`, and it was prohibited from treating convergence or
disagreement as confidence, routing, or authorization evidence. This is a
natural-language treatment and does not make internal trajectories identical,
but it directly matches the explicit operations named by the reviewer.

### S14.2 Results

| Track | Semantic-free structured | TOV | TOV difference | TOV rescue:harm | One-sided exact p |
|---|---:|---:|---:|---:|---:|
| Rust30 | **19/30** | 18/30 | -1 (-3.3 pp) | 0:1 | 1.0 |
| Python34 | 19/34 | **23/34** | +4 (+11.8 pp) | 4:0 | .0625 |
| C++26 | 13/26 | **17/26** | +4 (+15.4 pp) | 4:0 | .0625 |
| **All90** | **51/90** | **58/90** | **+7 (+7.8 pp)** | **8:1** | **.01953125** |

The cumulative two-sided exact p-value is `.0390625`; the 50,000-draw
track-stratified paired-bootstrap 95% interval is `[+2.22,+14.44]` points.
Track differences are `[-1,+4,+4]`; a one-sided sign test over three track
clusters is `.5`. This secondary task-level result conditions on the realized
whole-track calls and is not evidence of session repeatability.

TOV-only passes were Python `forth`, `go-counting`, `grade-school`, and
`list-ops`, and C++ `complex-numbers`, `kindergarten-garden`, `robot-name`, and
`yacht`. Their ledger evidence concerns alternative plausible interface
obligations such as definition lifetime, exported constants, attempt-history
semantics, fold order, namespace/API aliases, enum/roster mapping, uniqueness,
and string-versus-enum overloads. The only control-only pass was Rust `fizzy`;
TOV diagnosed the genericity obligation but left an extra closing brace and
failed compilation. The apparent interface-ambiguity concentration is a post
hoc nine-row observation, not a prospectively tested taxonomy.

### S14.3 Integrity and cost

| Track | Expected/observed rows | Withheld field | Restored anchor files | Byte mismatches | Forbidden paths |
|---|---:|---:|---:|---:|---:|
| Rust30 | 14/14 | 14/14 | 32 | 0 | 0 |
| Python34 | 15/15 | 15/15 | 19 | 0 | 0 |
| C++26 | 13/13 | 13/13 | 26 | 0 | 0 |

All staged candidate/evidence/anchor artifacts were byte-identical to TOV.
The control used 7,060,198 input tokens, 6,728,448 cached input tokens, 54,728
output tokens, and 1,392.675 seconds. TOV used 6,608,440 / 6,232,576 / 59,551
tokens and 1,422.310 seconds. Calls and caps were matched, not exact tokens.

Control result SHA-256 values for Rust, Python, and C++ are
`f35107c0d52b1020dfa60ac66914dbfa6537c38a0e892beb999cc86f5a1f2a71`,
`ec3d3c275a516ff6fbe78c8328cb1d2df21f21e2effa3d11c8f78107f5f15460`,
and `8d582796c334a74fbca81a447c44cd0f9a4ef2ea3472d04c85d394b257aa15b4`.

## S15. Python34 five-pair final-stage replication

### S15.1 Frozen design and session inference

After the original 23/34 TOV versus 19/34 semantic-free observation, a new
protocol froze five whole-track pairs on the same complete official Python34
track. All calls reused the same 19 anchored tasks, 15 unresolved tasks,
candidate patches, candidate outcomes, bounded traces, model
(`gpt-5.6-luna/medium`), and caps. Within-pair order alternated TOV/control,
control/TOV, TOV/control, control/TOV, TOV/control. No rerun, replacement,
task deletion, or top-up was permitted. The motivating pair is excluded from
the primary analysis.

| Session | TOV | Control | Difference | TOV rescue:harm |
|---:|---:|---:|---:|---:|
| 1 | **24/34** | 20/34 | +4 | 4:0 |
| 2 | 21/34 | **23/34** | -2 | 1:3 |
| 3 | **23/34** | 21/34 | +2 | 3:1 |
| 4 | 23/34 | 23/34 | 0 | 1:1 |
| 5 | **22/34** | 20/34 | +2 | 2:0 |
| **Mean** | **22.6/34** | **21.4/34** | **+1.2 (+3.53 pp)** | -- |

The paired differences are `[+4,-2,+2,0,+2]`: three wins, one tie, and one
loss. The exact one-sided sign test over four nonzero pairs is `.3125`; the
100,000-draw paired-session bootstrap interval with seed 20260902 is
`[-2.35,+8.24]` points. Across 170 repeated task-session outcomes, TOV has
113 passes and control 107, with 11 rescues and 5 harms. The corresponding
one-sided `.1051` task-session value is descriptive because tasks and
within-call trajectories are dependent.

`sgf-parsing` and `rest-api` each supplied three TOV rescues and
`grade-school` supplied two. However, control-only passes also occurred for
`go-counting` twice and once each for `sgf-parsing`, `list-ops`, and
`rest-api`. The original interface/contract moderator is therefore an
opportunity hypothesis, not a stable task-level rule.

### S15.2 Integrity and compute

All ten calls were agent-complete and safe. All 19 anchors were byte-exact,
each ledger had the exact 15-ID set, all control relation fields were
`withheld-by-control`, evidence packets were byte-identical, and forbidden
paths were zero. TOV session 3 and control session 5 changed only ledger row
order. Because the frozen protocol required exact order, every call remains in
intention-to-treat analysis but the strict promotion gate fails.

| Arm, five calls | Input tokens | Cached input | Output tokens | Reasoning output | Agent seconds |
|---|---:|---:|---:|---:|---:|
| TOV | 9,331,229 | 8,803,328 | 96,052 | 19,242 | 2,322.317 |
| Control | 8,446,558 | 7,917,312 | 98,411 | 18,509 | 2,357.817 |

## S16. C++26 five-pair final-stage replication

### S16.1 Frozen second setting

C++26 was frozen as a second complete-track setting after the original 17/26
TOV versus 13/26 semantic-free observation. It reused the same 13 anchored
tasks, 13 unresolved tasks, artifacts, model, caps, five-pair alternating
order, and no-rerun rule. The motivating pair is again excluded.

| Session | TOV | Control | Difference | TOV rescue:harm | Safety |
|---:|---:|---:|---:|---:|:---|
| 1 | **16/26** | 15/26 | +1 | 1:0 | TOV generated `a.out` |
| 2 | 15/26 | **16/26** | -1 | 1:2 | both safe |
| 3 | 18/26 | 18/26 | 0 | 1:1 | both safe |
| 4 | **19/26** | 14/26 | +5 | 5:0 | both safe |
| 5 | 17/26 | **20/26** | -3 | 1:4 | both safe |
| **Mean** | **17.0/26** | **16.6/26** | **+0.4 (+1.54 pp)** | -- | -- |

The differences `[+1,-1,0,+5,-3]` give two wins, one tie, and two losses.
The one-sided session sign value is `.6875`; the 100,000-draw paired-session
bootstrap interval with seed 20260903 is `[-6.92,+11.54]` points. Across 130
repeated task-session outcomes, TOV has 85 passes and control 83, with 9
rescues and 7 harms; the descriptive task-session value is `.4018`.

`clock`, `complex-numbers`, `crypto-square`, `robot-name`, and `yacht` crossed
between arms. `circular-buffer` favored control two-to-one; only
`kindergarten-garden` and `queen-attack` were TOV-only without reverse
crossover, each in one pair. A private-outcome oracle union would score 92/130,
seven above TOV and nine above control. This is selection headroom, not a
deployable result, because private outcomes choose the final file.

### S16.2 Integrity, safety, and compute

All ten calls were agent-complete. All 260 evaluated anchor-file comparisons
(26 files by 10 calls) were byte-exact. Every ledger contained the exact 13 IDs
in exact frozen order, every control relation field was `withheld-by-control`,
and all within-pair evidence packets were byte-identical. TOV session 1 created
forbidden `a.out`; it is retained without rerun and invalidates strict protocol
promotion. A sensitivity over the remaining four safe pairs has mean +0.96
points and bootstrap interval `[-8.65,+13.46]`, so it does not change the
accuracy conclusion.

| Arm, five calls | Input tokens | Cached input | Output tokens | Reasoning output | Agent seconds |
|---|---:|---:|---:|---:|---:|
| TOV | 9,104,298 | 8,573,952 | 95,153 | 16,537 | 2,283.360 |
| Control | 7,460,079 | 6,950,656 | 95,171 | 16,050 | 2,268.891 |

Together S15--S16 show positive but small average differences with wide
session-level uncertainty and large crossover. They support verified anchoring
as the stable component and motivate a calibrated selector between
overlap-aware and direct repairs; they do not establish repeatable
overlap-specific superiority.

## S17. Recursive verified-redundancy construction

### S17.1 Rule and equal-call control

The repeated crossovers motivated a second application of the anchor rule.
Mini Artichokes runs TOV and semantic-free direct repair from the same
verified `P/G/R` union, tests both final outputs, and copies all listed solution
files from a passing route for each task. The equal-call non-overlap system
replaces TOV with the generic Critic while retaining `P/G/R` and the same
direct route. Both systems therefore contain five model calls and use the same
external per-task verifier.

| Track | Generic + direct union | TOV + direct union | Difference | TOV-union rescue:harm |
|:---|---:|---:|---:|---:|
| Rust30 | 19/30 | 19/30 | 0 | 0:0 |
| Python34 | 21/34 | **23/34** | +2 | 2:0 |
| C++26 | 14/26 | **17/26** | +3 | 3:0 |
| **All90** | **54/90** | **59/90** | **+5 (+5.56 pp)** | **5:0** |

The five unique passes are Python `forth` and `go-counting`, and C++
`complex-numbers`, `robot-name`, and `yacht`. The one-sided exact p-value is
`.03125`, the two-sided value `.0625`, and the 50,000-draw within-track
bootstrap interval with seed 20260902 is `[+1.11,+10.00]` points. Track
differences `[0,+2,+3]` have sign value `.25` over the two nonzero tracks.

The construction and analysis were selected after the crossovers were known.
They are exploratory even though task-wise union and priority are
deterministic. Nominal calls are matched between the two systems; realized
tokens and latency are not.

An offline minimal task-wise union applied to the same stored route outputs
has exactly the same task vector by construction. Recursive promotion is not a
new selector beyond this max operation. The claimed systems contribution is
the online enforcement of complete-state anchoring, unresolved-only branching,
heterogeneous routes, and fail-closed promotion; it is not an advantage over a
minimal union given identical outputs and labels.

### S17.2 Repeated-session stabilization

Applying the same union to the already completed pairs requires no new model
calls. Python union session scores are `24,24,24,24,22` (118/170); C++ scores
are `16,17,19,19,21` (92/130). Across both tracks the union has 210/300 passes,
versus 198 for TOV and 190 for direct repair. It exceeds TOV in six sessions
and ties four. These are descriptive counts, not a sign-test demonstration of
superiority: the union is non-inferior to either constituent by construction on
the same stable test labels.

This dominance is not a compute-matched comparison with one branch: the union
uses both final calls and external test results. Its scientific role is to show
that verified redundancy converts heterogeneous branch crossovers into
test-label-preserved successes in a test-available setting. It does not show that
semantic overlap alone is repeatably superior, nor that an evidence-only
selector would work without tests.

The C++ session-1 source call created forbidden `a.out`. A recursive
implementation copies only declared solution files and therefore would not
promote that artifact, but the original protocol violation remains and the
strict replication gate still fails. A new complete track must freeze the
dual-route rule before any branch call to provide confirmatory evidence.

### S17.3 Preservation-contract checklist

The formal property in the main text applies only when all five checks pass:

1. task units have disjoint declared solution-file and verifier scope;
2. routes run in isolated workspaces under the same fixed verifier;
3. promotion copies a complete declared task state, never merged patch lines;
4. all prior anchor bytes are restored before evaluation; and
5. missing files, forbidden paths, verifier errors, and non-passes fail closed.

For the reported Aider tracks, language directories are the task units,
solution paths come from the frozen task manifest, private tests are restored
only by the evaluator, and anchor audits compare every selected file byte for
byte. The rule does not claim semantic correctness beyond the official tests
or robustness to nondeterministic tests.

## S18. Before-call-frozen complete Go39 recursive evaluation

### S18.1 Complete track and fixed systems

The recursive rule was next frozen before any call on all 39 official Go tasks
from Aider commit `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`.
Tasks were retained in alphabetical order with no ranking or removal. The
model workspace had zero `*_test.go` files; the evaluator restored 61 official
test files. The frozen source hash was
`ebbb01078961617728451d80d4837ef98be4a022184952fb965575784779d061`.
Every arm was one whole-track Luna-medium call.

The shared calls were Plain, Graph, ordinary repair, and semantic-free Direct.
The non-overlap system added Generic; Mini Artichokes added the overlap-aware
route instead. Both systems contain five nominal calls. The final three routes
received the same 26 byte-locked anchors and 13 unresolved tasks, the same
candidate patches, outcomes, bounded failure traces, and evidence index.

| Arm/system | Passes / 39 | Additions above 26-anchor floor |
|:---|---:|:---|
| Starter | 3 | -- |
| Plain | 17 | -- |
| Graph | 16 | -- |
| Ordinary repair | 25 | -- |
| Candidate verified union | 26 | -- |
| Semantic-free Direct | 29 | `matrix`, `octal`, `protein-translation` |
| Valid replacement Generic | 29 | `matrix`, `react`, `scale-generator` |
| TOV | **32** | `bottle-song`, `matrix`, `poker`, `protein-translation`, `scale-generator`, `two-bucket` |
| Direct∪Generic | 31 | five tasks |
| **Direct∪TOV** | **33** | seven tasks |

The official `counter` exercise reports `no tests to run`. It remains in all
scores because it is part of the complete frozen track.

### S18.2 Original transport-null arm and analysis status

The preregistered fifth Generic invocation failed after 15.403 seconds. Its raw
events contain only thread/turn start, WebSocket and HTTPS 404 retries, a
transport error item, and `turn.failed`. There is no model message, reasoning
item, tool call, token usage, or final message. The resulting workspace's
26/39 is the deterministic verified-anchor seed, not a Generic output.

The original prospective experiment therefore fails the requirement that all
six calls be agent-complete, and its equal-call primary endpoint is unavailable.
It is not scored by substituting the later run. After TOV results were known,
the transport-replacement sensitivity protocol froze one identical Generic
call at a separate candidate ID. Its prompt hash
`8a72a48f567a19b311f3c18d7b13c0a27cf3d47f164ed4bf55535f31e3a24b08`
matches the failed invocation exactly. This second invocation completed and is
used only for the sensitivity values below.

### S18.3 Paired outcomes

| Contrast | Scores | Rescue:harm | Difference | One-sided exact | Two-sided exact | 50,000-draw paired bootstrap 95% CI |
|:---|---:|---:|---:|---:|---:|:---|
| TOV vs Direct | 32:29 | 4:1 | +3/39 (+7.69 pp) | .1875 | .3750 | `[-2.56,+17.95]` pp |
| TOV vs replacement Generic | 32:29 | 4:1 | +3/39 (+7.69 pp) | .1875 | .3750 | `[-2.56,+17.95]` pp |
| Direct∪TOV vs Direct∪Generic | 33:31 | 3:1 | +2/39 (+5.13 pp) | .3125 | .6250 | `[-5.13,+15.38]` pp |
| Direct∪TOV vs Plain | 33:17 | 16:0 | +16/39 (+41.03 pp) | 1.526e-5 | 3.052e-5 | `[+25.64,+56.41]` pp |
| Direct∪TOV vs ordinary repair | 33:25 | 8:0 | +8/39 (+20.51 pp) | .003906 | .007812 | `[+7.69,+33.33]` pp |

The bootstrap seed is 20260903. Relative to replacement Generic, TOV-only
passes are `bottle-song`, `poker`, `protein-translation`, and `two-bucket`;
Generic-only is `react`. Relative to Direct, TOV-only passes are
`bottle-song`, `poker`, `scale-generator`, and `two-bucket`; Direct-only is
`octal`. At equal five-call system level, recursive-only passes are
`bottle-song`, `poker`, and `two-bucket`; non-overlap-only is `react`.

The large contrasts with Plain and ordinary repair are nested system
comparisons: verified union includes their successes and uses more calls. They
show end-to-end system quality but cannot identify an overlap-specific causal
effect. The equal-call sensitivity is the tighter component comparison and
does not pass `.05` or the frozen +8/39 strong-effect gate.

Because official `counter` has no active tests, a post-review sensitivity
treats it as unverified and excludes it from every arm. The resulting
test-covered denominator is 38: Plain 16, Graph 15, ordinary 24, floor 25,
Direct 28, replacement Generic 28, TOV 31, Direct∪Generic 30, and
Direct∪TOV 32. Discordant counts and exact tests do not change. Mini versus
Plain is +16/38 (+42.11 pp; bootstrap `[+26.32,+57.89]`), versus ordinary is
+8/38 (+21.05 pp; `[+7.89,+34.21]`), and versus the equal-call sensitivity is
+2/38 (+5.26 pp; `[-5.26,+15.79]`). The no-test row affects absolute accuracy,
not the direction or task count of any contrast.

### S18.4 Integrity and compute

Direct, replacement Generic, and TOV have identical hashes for all staged
candidate patches, bounded test-evidence files, the evidence index, seed patch,
and verified-anchor map. Seed SHA-256 is
`6e7ce9080f8b402bce5bbf3ab6cfc20d0d24d2b6acf7a2d7dc12581616ed6e57`;
evidence-index SHA-256 is
`d14301db8b6479467d7c4eea794d3f2850b452b97cd467cf2ec5a2392227f84f`.
All 26 anchored files match selected candidate bytes in all three final routes
(78/78 checks). All changed paths are declared Go solution files. Direct and
TOV ledgers contain the exact 13 unresolved IDs in frozen order, and all 13
Direct semantic fields are `withheld-by-control`.

| Arm/system | Input tokens | Cached input | Output tokens | Reasoning output | Agent seconds |
|:---|---:|---:|---:|---:|---:|
| Plain | 1,876,878 | 1,793,280 | 24,160 | 2,179 | 580.4 |
| Graph | 2,705,128 | 2,612,736 | 25,677 | 3,372 | 610.7 |
| Ordinary | 2,312,559 | 2,213,120 | 16,326 | 5,514 | 422.2 |
| Direct | 3,187,198 | 3,066,368 | 20,199 | 3,252 | 529.9 |
| Generic replacement | 2,401,990 | 2,294,528 | 17,214 | 2,930 | 397.8 |
| TOV | 3,883,660 | 3,751,424 | 23,396 | 4,580 | 632.7 |
| Non-overlap five-call system | 12,483,753 | 11,980,032 | 103,576 | 17,247 | 2,541.0 |
| Recursive-TOV five-call system | 13,965,423 | 13,436,928 | 109,758 | 18,897 | 2,775.9 |

Calls and caps are matched; realized tokens and time are not. The recursive
system uses 1,481,670 more input tokens (mostly cached), 6,182 more output
tokens, and 234.9 more agent seconds than the non-overlap sensitivity system.
No compute-efficiency claim is made.

## S19. Prospective complete JavaScript49 recursive evaluation

### S19.1 Freeze and full denominator

The source is the complete JavaScript track at Aider commit
`7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`: 49/49 official tasks in
alphabetical order. No task was selected, removed, replaced, or topped up. The
valid freeze SHA-256 is
`6abd5a0ee1e4792115bec699485e99d2d39064e435d5f621a70802f0291d55ca`;
the manifest and task-packet hashes are
`ceced6ab0b227a3505b77a9f89070d69a077e2bc8df609a995d65ada29072fd0`
and `00677d9332c8fd0b0bb3cfaf7ef82b9f6d1cdacfb696c14943581229dad1a7e3`.
The starter passes 1/49. Model workspaces omit all declared test files; the
evaluator restores one official test file per task.

The protocol hash is
`0db8e0037ecdc4fc376a582a6a4628f2f471a542017141ee6ae610c17b54ea0d`.
It froze Plain, Graph, ordinary repair, Direct, Generic, and TOV in that order,
one whole-track call each, with no retries or top-ups. Direct∪Generic and
Direct∪TOV each reuse the first four calls and add one distinct final route.
The primary endpoint was Mini minus the non-overlap system; +10/49 was the
separately named strong-effect gate.

Before any model call, an evaluator smoke test failed because the common npm
dependency directory was not on `NODE_PATH`. The invalid freeze and receipts
are preserved under `campaign/invalid-freeze-missing-node-path/`. After fixing
only that evaluator environment, the starter and dependency lock were
rechecked and the experiment was frozen anew. No scored call existed to reuse
or discard.

### S19.2 Scores, discordance, and interpretation

| Arm/system | Passes / 49 | Additions above 42-task floor |
|:---|---:|:---|
| Starter | 1 | -- |
| Plain | 27 | -- |
| Graph | 27 | -- |
| Ordinary repair | 42 | -- |
| Candidate verified union | 42 | -- |
| Direct | 45 | three |
| Generic | **47** | five |
| TOV | **47** | five |
| Direct∪Generic | **47** | five |
| **Direct∪TOV** | **47** | five |

| Contrast | Rescue:harm | Difference | One-sided exact | Two-sided exact | 50,000-draw paired bootstrap 95% CI |
|:---|---:|---:|---:|---:|:---|
| Mini vs Plain | 20:0 | +20/49 (+40.82 pp) | 9.537e-7 | 1.907e-6 | `[+26.53,+55.10]` pp |
| Mini vs ordinary | 5:0 | +5/49 (+10.20 pp) | .03125 | .06250 | `[+2.04,+18.37]` pp |
| Mini vs Direct∪Generic | 0:0 | 0 | 1.0 | 1.0 | `[0,0]` pp |
| TOV vs Generic | 0:0 | 0 | 1.0 | 1.0 | `[0,0]` pp |

The bootstrap seed is 20260904. Mini rescues `beer-song`, `food-chain`,
`go-counting`, `killer-sudoku-helper`, and `twelve-days` over ordinary repair.
Both final alternatives solve the identical 47 tasks. The clean prospective
primary result therefore supplies no overlap-specific advantage. It does,
however, show that the frozen recursive system strongly outperforms Plain and
retains all ordinary-repair passes on a complete new language track.

### S19.3 Integrity, ledgers, and realized compute

All six calls were agent-complete and safe, with no retry, timeout, or
forbidden path. Direct, Generic, and TOV received byte-identical candidate
patches, candidate outcomes, bounded failure traces, evidence index, seed, and
verified-anchor map. There were 126/126 exact route-by-anchor file comparisons.
Direct and TOV each produced seven ledger rows for the seven common unresolved
tasks. Direct marked every semantic relation `withheld-by-control`; its ledger
SHA-256 is
`cc9f709529e4b7962f675f4e55c879a8b6887833c0e12e69f9baeb078fea7e94`.
The TOV ledger SHA-256 is
`7185c65c534f1acbadddb51757eafb1fd41ed308e4d2f8489eb6e3b77fbef52f`.
Both materialized union workspaces were directly tested at 47/49.

A post-result stability audit ran the materialized Mini union twice more.
Both reruns produced the identical 47/49 task vector; after excluding timing
fields, the outcome-vector SHA-256 was
`f6eee9417245ba316134fb16875dda1d4fbaa63df2c63fa1714e41c67a52d8ad`
in both runs. A manifest noninterference audit found 49 unique IDs, 49
non-nested task roots, 49 uniquely owned declared solution paths, and no
multi-owner file.

| Arm/system | Input | Cached input | Output | Reasoning output | Agent s |
|:---|---:|---:|---:|---:|---:|
| Plain | 1,666,148 | 1,578,240 | 21,710 | 2,262 | 476.4 |
| Graph | 1,542,883 | 1,455,616 | 20,962 | 2,685 | 450.5 |
| Ordinary | 2,007,987 | 1,907,200 | 15,015 | 5,166 | 354.0 |
| Direct | 1,500,303 | 1,408,512 | 15,226 | 2,050 | 324.9 |
| Generic | 819,905 | 736,000 | 9,736 | 2,209 | 219.5 |
| TOV | 1,147,397 | 1,052,672 | 13,387 | 2,712 | 287.1 |
| Direct∪Generic | 7,537,226 | 7,085,568 | 82,649 | 14,372 | 1,825.3 |
| Direct∪TOV | 7,864,718 | 7,402,240 | 86,300 | 14,875 | 1,892.9 |

Calls and hard caps are matched; realized tokens and latency are not. The TOV
system uses 4.35% more input, 4.42% more output, and 3.70% more agent time.
The complete analysis hash is
`4bfc944623b2d59690ad74aff5ad8814539011df5449c4df8874e5bbfd1b4a20`.

## S20. Independent HumanEvalFixDocs Python164 ceiling evaluation

### S20.1 Source and separation

The source is BigCode HumanEvalPack at dataset revision
`9a41762f73a8cb23bb5811b73d5aab164efcf378`. We retain all 164 Python
`HumanEvalFixDocs` rows in numeric ID order. The source parquet SHA-256 is
`ed5f15d789156e21222bfcd556c425a39042355c84ae1e8b058abd6a3d7f8075`.
The public workspace contains a separate `solution.py` for every buggy
implementation and its docstring. It contains neither canonical solutions nor
official tests. The private evaluator maps the supplied test function to the
public entry point and runs each case in isolation. The starter passes 0/164.

The protocol, freeze, manifest, private-case, and task-packet SHA-256 values are
respectively
`47585a6fb48a96fb4daaf481a30f32d5fab3561fc8be01980288a2fef314c5e5`,
`07c52db96d1017657ac3161e81c9da3606929b7ce18cfea1edb0a7366f392836`,
`be7fb0c0fab142faa2fc0c9022867f6a113676162f8f111a397f8cc971144a06`,
`38d32a2cf88f374f991c571e563a508f7667d321458b4c8e904d96393f60001a`,
and `19d29a475e830825d8eb7093132de8cf1c2f36f7a82493132549c6314ba136ce`.
The same six-arm call order and five-call systems were frozen before calls.

### S20.2 Complete-suite ceiling

| Arm/system | Passes / 164 |
|:---|---:|
| Plain | 157 |
| Graph | 154 |
| Ordinary repair | **164** |
| Candidate verified union | **164** |
| Direct | **164** |
| Generic | **164** |
| TOV | **164** |
| Direct∪Generic | **164** |
| **Direct∪TOV** | **164** |

Mini rescues seven Plain failures (IDs 038, 050, 093, 120, 132, 140, and 145):
+4.27 points, 7:0, one-sided exact `p=.0078125`, two-sided `p=.015625`,
and paired bootstrap `[+1.22,+7.32]` points. Ordinary repair already reaches
the complete 164/164 ceiling. All later contrasts are consequently 0:0 ties
with `p=1` and `[0,0]` intervals. The +33/164 strong-effect gate is not met.
This is an independent-family ceiling boundary, not overlap evidence.

### S20.3 Integrity, compute, and runtime limitation

All six calls were agent-complete and safe. Final-route evidence was
byte-identical, all 492 route-by-anchor comparisons were exact, and both
materialized system unions passed 164/164. Because the candidate floor already
anchors every task, Direct and TOV correctly emit empty decision ledgers with
the shared SHA-256
`37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`.

| Arm/system | Input | Cached input | Output | Reasoning output | Agent s |
|:---|---:|---:|---:|---:|---:|
| Plain | 1,253,558 | 1,174,016 | 16,709 | 4,033 | 374.3 |
| Graph | 1,137,136 | 1,053,696 | 16,552 | 4,383 | 375.4 |
| Ordinary | 196,377 | 170,752 | 3,453 | 782 | 87.1 |
| Direct | 107,339 | 88,320 | 2,898 | 848 | 74.6 |
| Generic | 308,073 | 261,376 | 3,301 | 1,033 | 93.8 |
| TOV | 102,941 | 80,384 | 2,871 | 684 | 75.6 |
| Direct∪Generic | 3,002,483 | 2,748,160 | 42,913 | 11,079 | 1,005.3 |
| Direct∪TOV | 2,797,351 | 2,567,168 | 42,483 | 10,730 | 987.1 |

The actual freeze manifest and evaluator executable used Python 3.13.11,
rather than the protocol's predeclared 3.13.5 or the benchmark paper's Python
3.9.13 reference environment. This is a protocol deviation: the complete run
is retained as a ceiling/portability evaluation, not strict confirmation.
Dataset rows and tests remain pinned. A post-result audit ran the materialized
Mini union twice more; both evaluations reproduced 164/164 with byte-identical
stdout SHA-256
`c37bd431873259b50d981f631331c5a3672fa385bb50d2f38a5f90b87fc2843a`.
The manifest contains 164 unique IDs, 164 non-nested task roots, 164 uniquely
owned declared solution paths, and no multi-owner file. The analysis
SHA-256 is
`197d5c00ea04d3717d20efd8a24202dcce3d421f472017dfa160a72f583641c7`.

## S21. Complete-inventory equal-call portfolio sensitivity

After all five Aider tracks were complete, reviewer concern about the nested
Plain and ordinary-repair comparisons motivated a direct inventory summary of
the two five-call portfolios. No model was called, no task was removed, and no
outcome was replaced for this aggregation. Both systems contain the same
Plain, Graph, ordinary-repair, and semantic-free Direct calls and use the same
task-wise verifier union. Their fifth route is Generic or TOV.

| Complete track and evidence stage | Direct∪Generic | Direct∪TOV | Rescue:harm | Net |
|:---|---:|---:|---:|---:|
| Rust30, original post-hoc union | 19/30 | 19/30 | 0:0 | 0 |
| Python34, original post-hoc union | 21/34 | 23/34 | 2:0 | +2 |
| C++26, original post-hoc union | 14/26 | 17/26 | 3:0 | +3 |
| Go39, post-primary replacement sensitivity | 31/39 | 33/39 | 3:1 | +2 |
| JavaScript49, prospective | 47/49 | 47/49 | 0:0 | 0 |
| **All Aider tasks** | **132/178** | **139/178** | **8:1** | **+7/178 (+3.93 pp)** |

On the nine discordant tasks, the conditional one-sided exact paired value is
`.01953125` and the two-sided value is `.0390625`. A 50,000-draw paired task
bootstrap with NumPy `default_rng(20260904)` yields `[+1.12,+7.30]`
percentage points. Track-level net differences are `[0,+2,+3,+2,0]` in the
listed order; the one-sided sign value over the three nonzero tracks is `.125`.

The aggregate is a fairness sensitivity, not a prospective multi-track
endpoint. The original three-track recursive rule was selected after
crossovers, Go uses a separately labelled replacement executed after its TOV
outcome, and JavaScript is a clean prospective tie. The conditional task test
does not make the realized whole-track calls independent. Nominal call count
and hard caps match, but realized tokens, time, and monetary cost do not.

The derived report SHA-256 is
`847a78164e649a81bd40c81c39f96461587d4ef90fa90b888f335ee59833c728`.

## S22. Initial prospective HumanEvalFixDocs Java164 completion-lock case

### S22.1 Failure-driven policy freeze

Two complete HumanEvalPack development tracks exposed distinct defects in the
original final policy. On JavaScript164, several candidates converged on the
wrong interpretation of signed digits. On Go164, a semantically correct repair
left an official compiler-visible unused import unresolved. We therefore added
one final completion gate: enumerate every observed compiler, runtime,
assertion, expected/actual, timeout, and scope failure atom; map each atom to a
concrete construct in the actual final file; and continue repairing whenever a
closure witness is absent. Semantic overlap proposes hypotheses, but literal
failure closure is checked last. A same-input Go development run recovered its
remaining task; it is not counted as confirmation.

The revised prompt and complete Java population were frozen before Java calls.
The protocol SHA-256 is
`b81898d41f8376f01289304f39851e25cccbfeb85516725155779b0e4e4f7c1f`.
The source is all 164 Java rows from BigCode HumanEvalPack revision
`9a41762f73a8cb23bb5811b73d5aab164efcf378`; the parquet SHA-256 is
`0be942d715894e3b350149f1cde6593e95eda495aa4bd1750f09428c0b3e3e9c`.
No task was selected, excluded, replaced, or topped up. Model workspaces contain
documentation and buggy `Solution.java` files but not tests or canonical code.

Before any model call, buggy starters scored 0/164 and official canonical
solutions scored 164/164. The evaluator SHA-256 is
`5e673e892d0cca814b39d0cc8db7cb7f19f8f0ef6d7126f81ba81ce0daf51a78`.
It uses OpenJDK 17.0.17 rather than OctoPack's reported Java 18.0.2; this
deviation was known and recorded before calls.

### S22.2 Complete results and exact pairing

| Arm/system | Pass / 164 | Agent s |
|:---|---:|---:|
| Plain | 147 | 714.1 |
| Graph | 129 | 1,290.9 |
| Ordinary repair | 162 | 307.7 |
| `P/G/R` verified floor | 163 | deterministic |
| Semantic-free Direct | 163 | 234.6 |
| Generic | 163 | 230.8 |
| Completion-locked TOV | **164** | 224.1 |
| Direct∪Generic five-call system | 163 | 2,778.2 summed |
| **Direct∪completion-locked TOV** | **164** | **2,771.5 summed** |

The two five-call systems share Plain, Graph, ordinary repair, and Direct and
differ only in their fifth final route. Mini has one rescue and zero harms,
`+1/164=+0.610` percentage points. The exact one-sided paired value is `.5`
and the two-sided value is `1`. Thus the frozen positive-direction rule is met,
but the isolated task contrast is not statistically significant.

The systems are also close in realized compute. Direct∪Generic uses 10,560,445
input, 10,073,344 cached-input, 92,793 output, and 26,154 reasoning-output
tokens. Direct∪completion-locked TOV uses 10,577,460, 10,097,920, 94,103,
and 25,773 respectively. The candidate therefore uses 0.16% more input tokens
and 0.24% less summed agent time.

### S22.3 Mechanistic audit of the sole discordance

The shared verified floor leaves only `humanevalfix-java/145` unresolved. Its
example specifies a signed-leading-digit convention. Plain and Graph preserve
the cross-operand bug. Ordinary repair sums `Character.getNumericValue` over
the whole signed string, thereby treating `'-'` as a numeric contribution.
Direct instead adopts absolute digit sums, and Generic subtracts one for each
negative number. Both plausible reinterpretations fail the official test.

Completion-locked TOV preserves the signed-leading-digit invariant and removes
the second operand's contamination by the first. Its final file SHA-256 is
`5ffbd75e040d4ce8472bcda0a9d01622210f52f6fc883bf3097f2ceae854c38b`,
byte-for-byte identical to the official canonical solution. The ledger contains
exactly one row, both observed failure atoms, and a nonempty closure map whose
witness `sum2 = -sum2;` is present in the final file while the contaminating
expression is absent.

### S22.4 Integrity and limits

Direct, Generic, and completion-locked TOV have the same evidence-index SHA-256
`40ac447c8e29a3dad05fc38f669b71f4e54c04f650ec59c66631331b6f73fda7`
and verified-anchor-map SHA-256
`a649b593eb8fd147b1f7cdf7cfbae77695823b5ed8270c496d6be4094ffb1c25`.
All 163 anchors in each of three final workspaces match their selected passing
candidate bytes: 489/489 exact comparisons. Every call is agent-complete and
safe. Two post-result candidate reevaluations both reproduce 164/164 with
byte-identical stdout SHA-256
`6fdfac26bd45c95f3c0cc4edc1f35dabb7344b316010eca6b57cf444cde220dc`.

This is the first prospective test of completion-locked TOV, not an unchanged
replication of TOV v2. One exact canonical rescue gives unusually clear case
evidence for the proposed failure-closure mechanism, but one task cannot
support a stable language-population or large-effect claim. The runtime
deviation also prevents an exact OctoPack environment claim. The complete
analysis and report SHA-256 values are
`53bda821d5d8807a33f6b30753598fd5130b8654d0ce1a4a024184b4c4c7a4b1`
and `fae7a365de75add1068dae3c00138009aab973f5815f4209adab54739d5b0cf9`.

## S23. HumanEvalFixDocs Java164 five-pair replication

The initial one-task result in S22 motivated a predeclared replication in which
the original pair was excluded. Five new Generic and five new
Completion-Locked TOV calls each started from the identical frozen 163/164
verified floor, complete 164-task population, candidate artifacts, bounded
evidence, anchor map, model, reasoning effort, and execution caps. No failed
call was retried, replaced, topped up, or removed.

| Whole-track pair | Generic | Completion-Locked TOV | Candidate difference |
|---:|---:|---:|---:|
| Initial case (excluded) | 163 | **164** | +1 |
| Replication 1 | 163 | 163 | 0 |
| Replication 2 | 164 | 164 | 0 |
| Replication 3 | **164** | 163 | -1 |
| Replication 4 | **164** | 163 | -1 |
| Replication 5 | 163 | 163 | 0 |

Across the five new pairs, candidate-minus-Generic differences are
`[0,0,-1,-1,0]`: no wins, two losses, three ties, and mean -0.4/164
(-0.244 percentage points). The exact one-sided sign value for candidate
superiority is `1.0`; the two-sided value over the two nonzero pairs is `.5`.
Generic reaches 164/164 in three sessions and Completion-Locked TOV in one.
This replication changes the interpretation of S22 from confirmation to an
exact motivating case.

| Five final calls | Input | Cached input | Output | Reasoning output | Agent s |
|:---|---:|---:|---:|---:|---:|
| Generic | 1,378,670 | 1,159,424 | 25,259 | 11,910 | 707.91 |
| Completion-Locked TOV | 2,041,948 | 1,754,112 | 42,558 | 19,182 | 1,198.94 |

Every call was agent-complete and safe, every anchor was restored byte for
byte, and private tests and canonical solutions were absent from model
workspaces. The complete analysis and report SHA-256 values are
`97478d790c45b1915584fa50b18253e64297e0970878c5e882961d3f6d211f6b`
and `1f843989c2f6ce254f12abed641b98e99e1da2e223dcf6d58cf00fa356888af4`.

## S24. Complete-suite transfer diagnostics

### S24.1 HumanEvalFixDocs C++164 language transfer

All 164 C++ translations at HumanEvalPack revision
`9a41762f73a8cb23bb5811b73d5aab164efcf378` were retained. Before model
calls, buggy starters scored 0/164 and canonical solutions 164/164. Each arm
was one whole-track `gpt-5.6-luna` call; there were no task-wise calls, retries,
replacements, or top-ups.

| Arm/system | Passes / 164 |
|:---|---:|
| Plain | 46 |
| Graph | 141 |
| Ordinary repair | 161 |
| Verified floor | 162 |
| Direct | **164** |
| Generic | **164** |
| Conservative-First Closure | 163 |
| Direct∪Generic | **164** |
| Direct∪Conservative-First | **164** |

The floor leaves tasks 132 and 145 unresolved. Direct and Generic solve both;
Conservative-First solves 145 but fails 132. Its ledger says that the actual
source passed the observed `is_nested("[[]") == false` atom even though the
evaluated function returns true at depth two and fails that assertion. This is
a concrete natural-language certificate failure: the replay claim was not
mechanically tied to the bytes evaluated by the host verifier.

| Five-call system | Input | Cached input | Output | Reasoning output | Agent s |
|:---|---:|---:|---:|---:|---:|
| Direct∪Generic | 5,511,073 | 5,160,704 | 80,090 | 24,881 | 2,226.60 |
| Direct∪Conservative-First | 7,261,614 | 6,867,712 | 92,639 | 28,070 | 2,600.23 |

C++ changes syntax but translates the same underlying HumanEval tasks as the
Java development track, so it is not an independent semantic population. The
protocol, analysis, and report SHA-256 values are
`abead87d78351a430d36d9dfc54cebe1c776c4e26a0d8e2f4fd9ef00a9e02aef`,
`1be1bd3c66381f9edbc0ae090ef196bcafc73a9335d92c027747bebeca1bae3e`,
and `d5e8fe47bf5d920d25c91f9be3f407c82a6148e5338a726be3dd3817153feef7`.

### S24.2 QuixBugs Python40 hidden-test transfer

All 40 official QuixBugs Python programs at upstream commit
`4257f44b0ff1181dedaedee6a447e133219fcebf` were retained. Model
workspaces contained buggy programs and embedded specifications but neither
official tests nor corrected programs. Pre-call controls scored starters at
0/40 and corrected programs at 40/40. Each arm was one whole-suite Luna call.

| Arm/system | Passes / 40 |
|:---|---:|
| Plain | 35 |
| Graph | 34 |
| Ordinary repair | 38 |
| Verified floor | 39 |
| Direct | **40** |
| Generic | **40** |
| Executable Claim Closure | **40** |
| Direct∪Generic | **40** |
| Direct∪Executable Claim Closure | **40** |

All final routes repair the sole residual `topological_ordering` program.
Executable Claim Closure imports the actual evaluated source into its replay
driver, records identical pre/post SHA-256 values, and executes the observed
failure atoms successfully. This shows that source-bound closure is feasible,
but it does not improve accuracy over Generic or Direct.

| Five-call system | Input | Cached input | Output | Reasoning output | Agent s |
|:---|---:|---:|---:|---:|---:|
| Direct∪Generic | 2,333,226 | 2,068,224 | 50,612 | 17,367 | 1,372.73 |
| Direct∪Executable Claim Closure | 2,688,667 | 2,422,784 | 54,454 | 18,646 | 1,469.53 |

The frozen forbidden glob `**/*test*.py` also matched the substring `test` in
three legitimate allowlisted `shortest_path*.py` solution names. Raw runner
flags are therefore false, while a separate exact allowlist audit confirms
that every changed file is one of the 40 predeclared solutions and that no test
or helper changed. We retain this preregistered integrity deviation and treat
the run as a ceiling sensitivity rather than a strict promotion-passing
confirmation. The protocol, analysis, and report SHA-256 values are
`0b659ddec0eee5d973b8b17de1a3f8ba11243481a84ab346b038ccb73e920b78`,
`79711191383cf468301e1495b4b4d8b1f973624d202c778ee66d988f20e07533`,
and `529baa3bf655f40e4f8dfa27d00277e6a4e75f08693c234233eafd635df1cf0c`.

## S25. Follow-up development: requirement alignment and matched portfolios

These studies use already exposed complete official tracks. They refine the
mechanism and characterize its limits; they do not enlarge the untouched-task
confirmation set. No model-generated task or selected fraction of a track is
added. The following chronology prevents a favorable later pair from replacing
earlier outcomes.

| Development study | Complete inventory and observed result | Interpretation |
|:---|:---|:---|
| Seed-matched fourth-candidate feedback | Python34: Generic 28/Overlap 27 with feedback, 25/25 without | No overlap gain; C++26 fourth candidate timed out, so no complete 60-task paired result |
| Independent documentation-probe repair | Java47: Generic 12/Overlap 13 materialized systems | Five executions each; rescues 2/harms 1, conditional one-sided p=.5; extra Generic-B violated source scope, so the planned six-execution comparison was not eligible |
| Original P/G/R case complementarity | Java47: only one unresolved task had observed case union beyond its strongest parent | pig-latin: 20/22 cases per parent, 22/22 union; not an executable fused solution |
| Shared-failure overlap v1 | Java47: Generic 14 system; overlap persisted candidate 18 at model timeout | No eligible overlap system or paired primary result; cutoff code is not a completed run |
| Shared-failure overlap v2 | Java47: Generic 16/Overlap 14 systems, both completed | Rescues 1/harms 3; predefined first-pair futility stopped the planned further four pairs |
| Expectation-aligned view | Java47: case-local A 12, overlap 17, fresh case-local B 21 systems | A/O representation pair and separately frozen five-execution system comparison described below |

### S25.1 Lossless expectation alignment

The Java47 P/G/R diagnostic contains 899 candidate-case failure records. A
conservative parser separates the framework expectation from the observed
wrong result only when an unambiguous expected/observed form is present. Cases
with ambiguous markers retain their original message. Both experimental views
provide the same parsed fields and permit byte-exact reconstruction of all 899
original `(task,case,candidate,diagnostic)` records.

The control groups records locally by case. The overlap view additionally
groups identical displayed expectation fields and parser forms, while keeping
different observed wrong results distinct. Candidate agreement is not treated
as ground truth, and Graph and its ordinary repair retain their common lineage.
Exact diagnostic-field equality is not asserted to prove a common semantic
cause. The representation therefore makes a specific repeated obligation easy
to inspect without adding a reference answer or another model's interpretation.

Case-local A and fresh B receive byte-identical 252,796-byte views; O receives
a 232,874-byte view. All three receive identical original R seed, P/G/R sources,
raw feedback, canonical records, generic instruction template, model/effort,
900-second cap and 180-second completion reserve. Only the additional layout
differs in O. The canonical-record SHA-256 is
`16f546b137f036d097bce5ffcca5357555d76357a2c19403e763020c824535e6`.
The normalizer and experiment were fixed at commits 691494c and bf92e8c before
the new A/O executions. All three executions subsequently passed normal exit,
source scope, unchanged inputs, complete 47-row ledger and materialized-vector
re-evaluation gates. A ledger gate checks inventory, not the truth of a model's
self-reported diagnosis.

### S25.2 Completed component results and sibling-system design

| Final execution | Raw candidate /47 | P/G/R plus final system /47 | Agent seconds | Output tokens |
|:---|---:|---:|---:|---:|
| Case-local A |12|12|639.069|20,170|
| Obligation-overlap O |16|17|701.810|22,055|
| Fresh case-local B |20|21|744.811|24,850|

The A/O difference is 6 rescues and 1 harm, or +5/47 (+10.64 percentage points).
The conditional exact one-sided McNemar value is .0625 and two-sided value .125.
This single whole-track execution pair does not establish session-level
superiority. O's raw book-store failure is restored from the previously passing
prefix by the common terminal selector. The full four-execution agent totals
are 2187.763 seconds/85,377 output tokens for A and 2250.503 seconds/87,262 tokens
for O. Those totals exclude official grading; assigned ceilings match but
realized compute does not.

Before either A or O result existed, commit 501459a separately fixed the
five-execution systems P/G/R+A+O and P/G/R+A+B. B starts from the original R
state and receives no A/O output, score, code or ledger. Both systems use the
same task-wise verifier selector: differing final route first, then A, R, G, P;
copy the first passing complete task state, falling back to the differing
route if none passed. Both whole-track materializations must be officially
re-evaluated; vector arithmetic alone is not the system endpoint. This is a
comparison against a repeated-generic portfolio, not against a constituent
that the overlap system contains by construction. B's 21-task system shows why
the 12-task A control cannot represent the strongest generic trajectory.

Both five-execution source portfolios subsequently reproduced their declared
complete vectors under official re-evaluation:

| System | Passes /47 | Total agent seconds | Total output tokens |
|:---|---:|---:|---:|
| P/G/R+A+O, overlap-containing | 18 | 2889.572 | 107,432 |
| P/G/R+A+B, repeated generic | 22 | 2932.573 | 110,227 |

The overlap system uniquely solves all-your-base, phone-number and pig-latin;
the generic system uniquely solves connect, food-chain, ocr-numbers,
palindrome-products, satellite, variable-length-quantity and wordy. The net
difference is -4/47 (-8.51 percentage points), with conditional exact one-sided
p=.9453125 in the prespecified overlap-improvement direction and two-sided
p=.34375. No repeated-session test is inferred from this single sibling pair.
Five executions are logical whole-track CLI executions, not five individual
API requests. The prefix and A are physically reused between systems; neither
receives an uncounted model candidate. Agent totals exclude official grading.
The result is preserved, not replaced with another generic draw or the weaker
four-execution A comparison.

The materialized-report SHA-256 values are
`bb8eb4f5aa03d65d34d6c41d27ae533f79571b6c3937eb4c27485622ba1cb088`
(overlap-containing) and
`324037da6b6766d01516ee2f2c7b5bd2526905c0df2bff4c32fde3ba5b8cd7ed`
(repeated generic).

Artifacts are under `runs/aider-java47-tov-development-20260902/arms/`, with
IDs `obligation_view_v1_case_local`, `obligation_view_v1_obligation_overlap`,
and `obligation_view_v1_case_local_b`. Protocols and dated result reports are
in `experiment_protocols/2026-09-05-java47-*` and
`benchmark_reports/2026-09-05-independent-probe-java47/`. These development
counts are not pooled into the paper's earlier confirmatory totals.
