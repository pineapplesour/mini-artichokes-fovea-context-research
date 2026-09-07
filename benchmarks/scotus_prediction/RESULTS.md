# SCOTUS oral-argument prediction v0 — results (2026-08-18)

Purely pre-decision inputs (official oral argument transcripts only; no
judge-authored documents), 29 post-cutoff decided cases (opinions 2026-02+,
model cutoff 2026-01), labels parsed from official slip opinions
(REVERSE 21 / AFFIRM 8).

claude-fable-5, per-case, high reasoning:

| Metric | Value |
| --- | ---: |
| Accuracy | **25/29 = 86.2%** |
| Balanced accuracy | **0.827** (REVERSE 19/21, AFFIRM 6/8) |
| Majority baseline (always-REVERSE) | 72.4% |
| conf>=0.8 | **15/15 = 100%** |
| Misses | 4, all self-flagged low confidence (0.65-0.75) |

This realizes the original design goal — predict outcomes from both sides'
live arguments alone — with structural contamination sealing and calibrated
confidence. Caveat: n=29 (one term's decided-with-transcript pool); CI wide;
extend with prior terms using time-sealing discipline for larger n.

---

# 2024-term backtest — memorization contamination measurement (2026-08-18)

Question: can archived terms (decided before the model cutoff) be used to
extend n, if surface identifiers are redacted? Method per law-bench leak
controls: same task, three arms over the SAME 30 cases (15 AFFIRM /
15 REVERSE, class-balanced, chance=50%), labels parsed from bound-volume
preliminary prints with a fi-ligature-tolerant disposition pattern
("affirmed" extracts as "affrmed" in those PDFs — naive parsing yields an
impossible 40/40 REVERSE).

claude-fable-5, high reasoning, per-case:

| Arm | Input | Acc | BA | conf>=0.8 |
| --- | --- | ---: | ---: | ---: |
| probe | caption+docket only, NO transcript | **30/30 = 100%** | 1.000 | 30/30 |
| asis | full transcript | 29/30 = 96.7% | 0.967 | 21/21 |
| anon | transcript, parties/docket/counsel redacted | **30/30 = 100%** | 1.000 | 23/23 |
| (reference) post-cutoff 2025 term | full transcript | 86.2% | 0.827 | 15/15 |

Findings:
1. **The probe arm alone settles it**: the model recalls every 2024-term
   outcome from the case name, at high stated confidence. Backtest accuracy
   on pre-cutoff terms measures memory, not prediction.
2. **Anonymization does not help** (100% even with parties, docket and
   arguing counsel redacted). The reasoning texts explicitly re-identify
   cases from their facts (names TikTok, NRC v. Texas, Smith & Wesson
   despite redaction). Supreme Court cases are individually famous; their
   fact patterns are unique identifiers. No surface redaction can seal them.
3. Memorization inflation is therefore +10~14pp on this task. The only
   valid protocol is **temporal sealing** (post-cutoff cases), exactly the
   law-bench doctrine. n grows by waiting for new decisions, not by
   backfilling old terms.

Artifacts: `scotus_bt24_{asis,anon,probe}.public.jsonl`,
`scotus_bt24.private.jsonl`, `labeled_cases_2024.json` (55 labeled:
40 REVERSE / 15 AFFIRM; spot-checked against 4 independently known
outcomes), runs in `runs/scotus-bt24-fable/`. Builder:
`tools/build_scotus_backtest.py`.
