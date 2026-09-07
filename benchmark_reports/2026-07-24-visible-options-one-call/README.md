# Latest Plain Codex visible-options benchmark (2026-07-24)

> **LATEST BENCHMARK WORK:** As of 2026-07-24, this directory is the
> repository's current entry point for the complete visible-options Plain
> Codex evaluation. The sealed 619-case choice-hidden benchmark remains the
> primary engine-promotion gate; this 1,309-row run is a separate baseline and
> execution-shape study.

## Scope and protocol

- 1,299 exam cases: 961 MCQ, 290 native short answer, and 48 constructed
  responses worth 338 raw marks.
- All 10 registered legal end-to-end variants: Kakao 4, military-key 4, and
  Yangyang 2.
- One isolated solver invocation receives the entire public file and must
  write 1,309 ordered JSONL answers.
- One separate isolated grader invocation receives the frozen answers plus
  private gold and rubrics and must write 1,309 ordered JSONL grades.
- No subject DB, Universal/Beta6 engine, skill, memory, plugin, MCP, or second
  agent is available. The solver may use audited native web search and local
  code, subject to the anti-exam-lookup policy. The grader is tool-closed.
- The public question file is identical across the high and low solver runs:
  SHA-256 `f2d92bbdd6f0ea30693dcd70ff1846f5c0b2fe50e42f1e71705a398cc0ad9d5e`.

The operational default is `gpt-5.6-luna` with high reasoning for both solver
and grader. The Sol/xhigh grade is retained as a sensitivity audit, not as the
default recurring evaluator.

## Headline results

Official exam points combine 1,251 binary exam points with 338 possible
constructed-response marks. Legal E2E is reported separately.

| Solver | Grader | Binary exam | Constructed | Official exam points | Legal E2E | Status |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Luna/high | Luna/high | 721/1,251 | 55/338 | **776/1,589 (48.84%)** | 0/10 | default accepted result |
| same Luna/high answers | Sol/xhigh | 738/1,251 | 56/338 | **794/1,589 (49.97%)** | 0/10 | accepted sensitivity audit |
| Luna/low | Luna/high | 9/1,251 | 5/338 | **14/1,589 (0.88%)** | 0/10 | whole-file method collapse; not a capability baseline |

The Sol audit changes the high-solver grade by 18 points, or 1.13 percentage
points of the 1,589-point denominator. Seventeen points are TCM MCQs whose
answer text exactly matches the keyed option but whose OCR-damaged option
markers defeated the Luna grader's parser. Two AQA constructed rows differ by
a net one point. Four Buddhist short-answer verdicts swap in opposite
directions and have zero net effect. The conclusion is unchanged: the
one-file high run is substantially weaker than a normal small-batch baseline,
and legal E2E remains unsolved.

For recurring work, Luna/high grading is sufficiently close to the Sol/xhigh
audit to remain the default. Objective MCQs should still receive a
deterministic keyed-option-text audit so OCR parsing errors are not silently
turned into model errors.

## Benchmark breakdown

`pass/total` is used for binary sets; `marks/max` is used for constructed
responses.

| Benchmark | Luna/high + Luna/high | Luna/high + Sol/xhigh audit | Luna/low diagnostic |
| --- | ---: | ---: | ---: |
| LEET 2026 | 29/70 | 29/70 | 0/70 |
| Korean medicine 92 | 41/92 | 58/92 | 0/92 |
| Christian Bible 100 | 88/100 | 88/100 | 0/100 |
| Christian Provao 92 | 20/92 | 20/92 | 0/92 |
| Islamic finance CISI 100 | 76/100 | 76/100 | 0/100 |
| Islam AQA MCQ | 4/4 | 4/4 | 0/4 |
| Islam AQA constructed | 55/98 | 56/98 | 0/98 |
| Islam BYU | 13/16 | 13/16 | 0/16 |
| Islam Cambridge constructed | 0/240 | 0/240 | 5/240 |
| Psychology 487 | 190/487 | 190/487 | 0/487 |
| Buddhist short answer 290 | 260/290 | 260/290 | 9/290 |
| Legal E2E | 0/10 | 0/10 | 0/10 |

## Why the low run is diagnostic only

The low solver completed the JSONL contract but did not solve the suite
normally. It used only 507 reasoning-output tokens for 1,309 cases. Among the
961 MCQs, 170 answers literally say `해당 선택지의 정답`, while 755 visibly
contain multiple choices instead of selecting one. One generic sentence is
repeated for 277/290 Buddhist items, one boilerplate answer for 45/48
constructed items, and one legal answer for all 10 legal variants.

This is valid evidence that `one huge file + Luna/low` is an unsafe execution
shape. It is not a valid estimate of Luna/low accuracy under per-case or
small-batch execution.

## Published artifacts

- [`artifacts/luna-high-answers.jsonl`](artifacts/luna-high-answers.jsonl):
  exact accepted 1,309-row default solver output.
- [`artifacts/luna-high-luna-high-grades.jsonl`](artifacts/luna-high-luna-high-grades.jsonl):
  exact accepted default grade output.
- [`artifacts/luna-high-sol-xhigh-audit-grades.jsonl`](artifacts/luna-high-sol-xhigh-audit-grades.jsonl):
  exact accepted Sol/xhigh sensitivity grade.
- [`artifacts/luna-low-diagnostic-answers.jsonl`](artifacts/luna-low-diagnostic-answers.jsonl)
  and [`artifacts/luna-low-diagnostic-luna-high-grades.jsonl`](artifacts/luna-low-diagnostic-luna-high-grades.jsonl):
  exact accepted diagnostic artifacts for the collapsed low run.
- [`results.json`](results.json): models, timing, tokens, scores, per-benchmark
  aggregates, receipt identities, and artifact hashes.
- [`SHA256SUMS`](SHA256SUMS): hashes for every committed file in this bundle
  except the checksum file itself.

Private gold packets and grader traces are intentionally excluded from this
folder because the traces contain answer-key and rubric excerpts. Public
questions remain in the executable manifests linked by
[`benchmarks/plain_codex_visible_options_registry.json`](../../benchmarks/plain_codex_visible_options_registry.json).

## Reproduction and interpretation

- [Frozen protocol](../../docs/research/plain_codex_visible_options_rerun_protocol_20260724.md)
- [Bundle builder and validator](../../tools/prepare_plain_codex_file_benchmark.py)
- [Isolated one-agent runner](../../tools/run_plain_codex_file_agent.py)
- [Primary 619-case promotion gate](../2026-07-21-choice-hidden-full/README.md)

Do not compare `776/1,589` directly to `393/619` as if they were the same
benchmark. The former shows all original choices, includes restored official
Islam sources and Buddhist short answers, adds constructed raw marks, and uses
one whole-suite solver invocation. The latter hides choices, uses 619 validated
open-response cases, and remains the exact engine-promotion denominator.
