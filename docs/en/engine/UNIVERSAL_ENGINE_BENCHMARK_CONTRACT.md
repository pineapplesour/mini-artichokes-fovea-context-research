# Universal Engine Official Benchmark Contract

Status: **normative**
Baseline date: 2026-07-24

This document fixes the universal engine's objective, benchmark sources,
comparison conditions, grading rules, and prohibited overfitting. Benchmark
runners, engine implementations, and reports must not silently contradict the
repository-root `AGENTS.md` or this current contract. The older Beta6/DB
inventory below is compatibility and expansion evidence; it does not fix the
final architecture.

## 0. Current top-level promotion gate

The first quantitative target is to beat sealed direct/no-DB Plain Codex on the
same hash-bound 619-case choice-hidden/open-response benchmark.

| Reference | Pass | Fail | Unresolved | Overall accuracy |
| --- | ---: | ---: | ---: | ---: |
| Plain Codex (`gpt-5.6-luna`, no DB) | 393 | 218 | 8 | 63.4895% |
| Latest Universal v3 candidate | 367 | 212 | 40 | 59.2892% |

The headline success condition is more than 393 passes and accuracy above
63.4895% on the same cases and scorer. Unresolved rate, latency, calls, tokens,
and cost must be disclosed to assess generality and sustainability. Gains from
hand-written benchmark routing or answer leakage do not count. The latest v3
candidate did not beat the accuracy baseline and is not promoted.

The 619 cases comprise law 16, Korean medicine 37, Christian Bible 91,
Christian Provao 85, Islamic finance 86, Islam AQA 3, and psychology 301. Of
945 original MCQs, 473 could become open response by hiding the options. The
remaining 472 were ambiguous without choices; closed independent adjudication
accepted 146 meaning-preserving rewrites, while 326 were left out.

Here `law 16` is the LEET subset admitted to the 619-case promotion gate, not
the size of the complete legal benchmark. The LEET source contains 70 cases:
30 Language Comprehension and 40 Logical Reasoning. One case was already ready;
15 of the remaining 69 meaning-preserving rewrites were approved, yielding a
gate slice of 6 Language Comprehension and 10 Logical Reasoning cases. The 54
cases that could not retain a safe unique answer were kept outside the gate,
not deleted.

The separate precedent-grounded legal benchmark has 3 underlying task families
expressed as 10 variants. Canonical legal coverage is therefore 70 exam cases
plus 3 end-to-end task families / 10 execution variants. The two Yangyang
hard-retrieval queries are identical to the two Yangyang end-to-end variants
and are not additional questions. The legacy executable registry has 1,235
unique cases: 945 source MCQs plus 290 natively short-answer Buddhist cases.
A 2026-07-24 audit of the complete user-designated official Islam source folder
showed that the old registry mistook a four-item AQA derivative for the full
source. Restoring AQA20, BYU16, and Cambridge32 produces 1,299 scorable exam
cases. Combining the 619 validated conversions with those 290 native cases
still gives the historical 909 open-response-capable coverage count; it is not
the new visible-options baseline.

The pending visible-options baseline gives all 1,299 exam cases plus the ten
legal variants to one isolated Plain Codex solver invocation. The solver writes
one complete `answers.jsonl`; one separate Codex grader invocation later sees
that frozen file plus every private key/rubric and writes `grades.jsonl`.
Historical answers are not reused and missing rows are not topped up with
additional calls.

## 1. Final objective

The objective is one fast, high-accuracy general answer engine for every
practical class of problem. “Codex as an element” means a candidate uses Codex
as a core problem-solving component and beats Plain Codex on accuracy. Two
research families are active: (1) direct Codex connected to Codex-selected
tools/skills and (2) a general harness around Codex that seeks algorithmic
robustness or a structural advantage through iteration, verification, durable
artifacts, evaluators, or other domain-agnostic mechanisms. A database and
Beta6 are optional tools or comparison arms, not mandatory stages.

The evaluation is not Gemma-only. Other provider/models, including models
callable through `codex exec`, are allowed. Within any engine-effect comparison,
provider, exact model ID, reasoning effort, decoding, token budget, timeout, and
retry policy must be identical. Results from different models cannot establish
an engine advantage.

## 2. Comparison arms

Every promotion evaluation runs at least Direct and Candidate on the same
questions. Add Beta6 and DB arms only when testing those hypotheses.

| Arm | Model | DB | Path |
| --- | --- | --- | --- |
| Direct | same model | none | neutral shared output contract only |
| Candidate | same model | none or declared optional tools | new Codex-centered universal engine |
| Beta6 (optional) | same model | benchmark DB | historical source-grounded comparison |
| DB ablation (optional) | same model | declared identical snapshot | tool-effect diagnosis |

The benchmark harness may mount the declared benchmark DB. The production
engine may not inspect the domain or question and choose domain-specific logic.

This rule rejects hand-written domain/case routing and narrow exceptions. A
domain-agnostic planner, verifier, or structure selector remains eligible if it
shows a sustainable accuracy advantage over Plain Codex across disjoint tasks.

## 3. Non-negotiable prohibitions

The following do not count as universal-engine progress even if they improve a
score:

- placing benchmark keywords, question strings, benchmark IDs, answers, case
  numbers, or correct options in production code, prompts, ranking, or routing;
- changing retrieval, reasoning, top-k, thresholds, rerankers, context budget,
  or answer policy behind branches such as `if islam`, `if christian`, or
  `if tcm`;
- maintaining per-benchmark synonym dictionaries, query-rewrite rules, or
  answer-leading prompts;
- treating the presence of a target answer in a large candidate set as an
  end-to-end pass;
- choosing a favorable model per dataset and aggregating those results as one
  engine result; or
- exposing prior `AI :` answers, explanations, or gold answers to the model.

A DB adapter may mechanically normalize storage fields into the common evidence
schema. It may not alter semantic search strategy, weights, prompts, or decision
policy by domain.

## 4. Expansion and regression benchmark inventory

The rebuilt 1,299-case source inventory and legal-retrieval tasks in this
section remain useful for coverage and regression evaluation. The legacy
executable registry had 1,235 cases. The current fixed top-level promotion gate
remains the 619-case open-response benchmark in section 0 until a later target
is explicitly promoted.

### 4.1 Legal tasks

Legal tasks use multiple meaning-preserving formulations and separate held-out
paraphrases. Evaluator case numbers and answers are never exposed to the engine.

#### KakaoTalk/Telegram access through a suspect's SIM

Question meaning: whether investigators may remove a suspect's SIM, place it in
another device, log into the suspect's KakaoTalk or Telegram account, and collect
evidence.

All three judgments must be substantively used in the final legal analysis:

- Seoul Administrative Court, 2025-01-21, 2024Guhap65355
- Seoul Central District Court, 2021-08-12, 2020Gohap886
- Seoul High Court, 2022-07-21, 2021No1520

A pass requires correct application to SIM removal/reinsertion, authentication
or login on another device, account access, warrant scope, seizure of electronic
information, and illegally collected evidence/admissibility. Merely retrieving
the cases among hundreds or thousands of candidates, or name-dropping them, is
not a pass.

#### Military key management

Question meaning: how physical keys for military facilities or units must be
stored and controlled.

- Primary target: Suwon District Court, 2025-01-16, 2023Guhap75301.
- A genuinely equivalent military-key authority is acceptable if it is actually
  used and supports the answer.
- The answer must correctly cover dual/separate control, storage, handover,
  inspection, locks, or related controls.
- A semantic drift to human height or physical growth is a failure.

#### Yangyang case

Question meaning: the age of the complainant who provided the bribe in the Kim
Jin-ha/Yangyang county-head case.

The target judgment masks the public names and location. A pass requires using
the masked judgment to answer `D (female, age 64)`. An unsupported guess is not
an end-to-end pass even if the number happens to match.

### 4.2 Exam banks

| Domain | Official set | Cases | Primary grading |
| --- | --- | ---: | --- |
| Legal | 2026 LEET Language Comprehension | 30 | exact option ID |
| Legal | 2026 LEET Logical Reasoning | 40 | exact option ID |
| TCM | 81st Korean Medicine National Exam p1-50 | 50 | exact option ID |
| TCM | Wikia evaluated set | 64 | exact option ID |
| Christian | Presbyterian University Bible entrance exam | 100 | exact option ID |
| Christian | PROVÃO 2012 Reformed/systematic theology | 92 | exact option ID |
| Islam | CISI Islamic Finance official sample | 100 | exact option ID |
| Islam | AQA 8062/15 2022–2023 | 20: 4 MCQ + 16 constructed | keyed option content / official raw marks |
| Islam | BYU official Islam quiz | 16 | keyed option content, including multi-select |
| Islam | Cambridge 2068 2025 specimen Papers 1–2 | 32 constructed parts | official raw marks |
| Psychology | MIT Intro Psychology | 240 | exact option ID |
| Psychology | Sangmyung University banks | 247 | exact option ID |
| Buddhist | 2022 Level-3 Sangha short-answer bank | 290 | exact final-answer string |

The confirmed rebuilt inventory contains 1,299 unique exam questions. The
legacy executable registry contains 1,235. The Islam `CISI wrong26` set is a
hard slice of 26 previously missed questions from the same CISI 100 and is not
counted as additional unique data.

## 5. Source and deduplication policy

### 5.1 LEET 2026

Use `2026년도 법학적성시험.zip` from the Wikia post `LawKey AI 2026년도
법학적성시험 벤치마킹 결과 공유`. The canonical ZIP SHA-256 is
`6c2e7ff3255fa0336928a52f3c5dcda7f3b58efa24fa9486359a41c100cb3828`.

- Include all 30 Language Comprehension and 40 Logical Reasoning cases.
- Copy each shared Language Comprehension passage into every case in its group
  so that each manifest case is independently executable.
- Public manifests contain only the passage, question, and choices. Remove the
  historical `AI :` and `정답 :` lines from model input and keep the correct
  option ID only in the private scorer manifest.
- The 36-case wrong-answer compilation is a historical diagnostic slice, not
  36 additional cases. Its model/provider/decoding configuration is unknown,
  so it is not a controlled three-arm result.
- Preserve Wikia post/attachment IDs, per-file SHA-256 values, and separation
  checks in `benchmarks/lawkey_leet_2026/source_audit.json`.

### 5.2 Islam

The user-designated official workbook is identified portably by filename and
SHA-256 rather than by a personal absolute path.

| File | Role | SHA-256 |
| --- | --- | --- |
| `CISI_이슬람금융_공식샘플_100문항.txt` | official full 100 | `2b2dd5575fc07c86b9c320c366c2a3c2c5ca80a309eda986f446013891e774c6` |
| `AQA_원본_AQA-806215-QP-JUN22.PDF` + official MS | AQA 2022 paper / mark scheme | see `benchmarks/islam_official_source_audit.json` |
| `AQA_원본_AQA-806215-QP-JUN23.PDF` + official MS | AQA 2023 paper / mark scheme | see source audit |
| `해외공식_BYU_Official_Islam_Multiple_Choice_Quiz.pdf` | official keyed BYU16 | `07faac9365d97cfd0e580529a03bbd901d105eabbf65fa82e83e4648b0a3f92b` |
| Cambridge 2068 2025 specimen Papers 1–2 + official mark schemes | official Cambridge32 | see source audit |
| `AQA_객관식만_문제_정답_한국어번역.txt` | legacy derived AQA4 subset, not the full source | `8d19e479667ba4fa2ea965ea64da028b15ba306eb66c2c61c907cf7ef62a8c6f` |
| `CISI_이슬람금융_공식샘플_100문항 틀린 문제.txt` | 26-case hard slice | `19c460615358eb0fb088afb58fbb6061b3390d2a483449a7800ddcb15407cf85` |

The complete hash list and count audit are in
`benchmarks/islam_official_source_audit.json`. The existing
`mcq_islam_cisi_wrong26` manifest matches the designated hard-slice file in all
26 question numbers and prompt texts. Only questions and choices are given to
the model; prior `AI :` answers and explanations are removed.

### 5.3 Buddhist

Use the 290 short-answer cases from Wikia `불교 벤치마크.zip` as-is. Do not
invent multiple-choice options.

- Give the model only the question; remove prior AI answers and gold.
- Grade only the shared structured output field `finalAnswer`.
- After JSON decoding, the Unicode string must equal the gold string exactly.
  No synonyms, partial matches, omitted Hanja/parentheses, or partial credit.
- Canonical SHA-256:
  `dcae404d35264177df4c58160ce4da7ec81fdba73fa3ab270802a21c60f44e48`.

### 5.4 TCM 50/64

The content audit established:

- Wikia session-1 questions 1-22 are the same questions as current p1-50
  manifest questions 1-22. OCR damage changes strings, but session, number,
  stem, and choices correspond.
- The 42 Wikia questions from sessions 2-4 are different from the p1-50 set.
- Preserve both official suites; their unique union contains 92 questions.
- Report `p1-50` and `wikia-64` suite scores separately.
- Count the overlapping 22 only once in the unique aggregate.
- Prefer the cleaner Wikia prompt for duplicate canonical records, retain both
  source IDs as provenance, and verify gold against the official answer sheet.

## 6. Scoring and reporting

- Primary MCQ metric: exact official option-ID accuracy.
- Primary Buddhist metric: the strict exact-string accuracy defined above.
- Primary legal metric: private-oracle evaluation of final-answer authority use,
  legal application, factual linkage, and grounding. Retrieval recall remains a
  diagnostic and cannot replace end-to-end grading.
- Publish per-domain scores and unique-case macro/micro aggregates. Do not hide
  a weak domain inside the overall average.
- Record cost, latency, failure rate, parse-valid rate, source grounding,
  calibration, and robustness separately.
- Durable artifacts must record benchmark version, DB snapshot/digest, provider,
  model ID and configuration, prompt/output, seed, retry policy, and scorer
  version.

The final objective is not achieved without a same-model comparison in which
Universal beats both Direct and Beta6. A raw-selector improvement alone is also
insufficient.

## 7. Change control

Deleting or replacing questions, or changing gold answers, deduplication,
grading, or anti-overfit rules, requires preserved provenance/hash and user
approval. Failed questions may not be silently dropped, and a favorable subset
may not be presented as the final score.
