# Mini Artichokes: frozen balanced legal confirmation v1

Status: **frozen before any confirmation solver or judge call**  
Date: 2026-09-01 KST

## Purpose

Test one development-selected Mini Artichokes policy on a fresh, case-disjoint,
domain-by-label-balanced legal reserve.  The scientific contribution is the
problem-solving policy and its measured accuracy, not the execution receipts,
hashes, runners, or other infrastructure used to protect the result.

The selected mechanism preserves the Universal Artichoke overlap idea:
independent candidate solutions are compared only when their conclusions
conflict, and repeated support for the same numbered evidence clause and
direction is exposed to a blinded adjudicator as an advisory signal.  The
adjudicator must still check the case itself; overlap is neither a vote nor an
independent proof.

## Frozen cohort and gold

- Public input: `runs/mini-legal-confirmation-balanced-v1-20260901/confirmation.public.jsonl`
- Public SHA-256: `af9a621d321fe8a64510fd93ced8c590dada7b2104996f0d61abbf12545a852f`
- Private gold: `runs/mini-legal-confirmation-balanced-v1-20260901/confirmation.private.jsonl`
- Private SHA-256: `67ee40537670a20ccb2f3f2b4a491b8f966f0c69da1ae128bd71a30acab4d7ea`
- Fixed denominator: 464 unique first-instance cases.
- Cells: civil grant 136, civil dismiss 136, tax grant 96, tax dismiss 96.
- Case-disjoint source reserve: 526 rows; source public SHA-256
  `abca66a6d680b774d3f7ea46fa2d36e7fcf47cdacbfd981c752e9aa7322f2fa9`.
- Gold rule: audit-calibrated holding parser v2.  The two independent audit
  streams covered 393 unique cases, agreed on all 127 common cases, and all
  392 accepted eligible audit labels matched the final parser.  One ambiguous
  appellate item (`outcome-confirm-fba0251f6ae153551656`) is excluded.

The private file is never placed in a solver or judge working directory and is
not read by an execution process.  It is opened by the deterministic scorer
only after every frozen arm has completed or recorded its one allowed null.

## Development-only selection record

The exposed civil development set contains 180 cases and is not included in
the confirmation denominator.  Three structured Luna draws and conditional
anonymous judges gave the following full-denominator results when invalid or
missing answers were counted as wrong:

| Development arm | Correct / 180 |
|---|---:|
| structured D1 | 115 |
| structured D2 | 117 |
| structured D3 | 108 |
| SC3 with D1 fallback | 116 |
| anonymous Luna judge without overlap signals | 114 |
| anonymous Luna judge with overlap signals | **119** |
| anonymous Sol judge without overlap signals | 119 |
| anonymous Sol judge with overlap signals | 115 |
| four-draw Luna generic judge | 119 |
| four-draw Luna overlap judge | 119 |

For the selected three-draw Luna policy versus its same-candidate,
same-judge-budget generic ablation, the paired development table was 7 rescues
and 2 harms (one-sided exact McNemar p=0.08984375).  Versus D1 it was 9 rescues
and 5 harms.  These are selection data only and will not be pooled with the
fresh confirmation p-values.  No fifth draw, stronger-model judge, learned
router, case-specific rule, or further development arm will be added.

## Model and isolation

- Model for every confirmation call: `gpt-5.6-luna`.
- Runtime account: `CODEX_HOME=/home/pineapple/.codex-new-account`.
- Reasoning effort: high; verbosity: low; service tier: default.
- Web, shell, files, MCP, plugins, skills, memory, and collaboration are
  disabled inside model calls.
- Every case-by-arm solver unit is a fresh Codex process.  Every disagreement
  judge is also a fresh process and receives exactly one case.
- One semantic attempt and zero retry/top-up calls.  A malformed, missing,
  timed-out, or refused output remains null on the 464-case denominator.

## Frozen solver arms

All model-created rationales must use only the public case packet.

1. **P1 — Direct Luna-1.** One Luna call receives the native case question and
   a minimal machine-readable outcome/rationale wrapper.  It returns one of
   `인용됨`, `기각`, or `ABSTAIN`.  This is the standalone Luna control.
2. **D1, D2, D3 — structured independent draws.** Three isolated Luna calls
   each return an outcome, a short rationale, and one or two numbered evidence
   atoms: issue code, clause ID, and grant/dismiss direction.  The prompt is
   byte-for-byte the selected development prompt apart from the case and draw
   identifier.  An otherwise parseable binary outcome survives malformed
   evidence for answer scoring, but its malformed evidence contributes no
   overlap signal.
3. **SC3.** Deterministic majority of the three valid binary outcomes; if no
   binary label has two votes, use D1.  If D1 is null, the result is null.
4. **GJ3 — generic anonymous judge.** When the valid D1-D3 outcomes contain
   both binary labels, pass every valid candidate, with hash-rotated anonymous
   roles, to one Luna judge.  The judge selects an existing candidate.  It
   receives no overlap field.  On no conflict, or on a missing/invalid judge,
   use D1 exactly.
5. **OJ3 — proposed overlap-aware anonymous judge.** It uses the identical
   D1-D3 candidates, conflict set, role rotation, judge prompt, model, and call
   budget as GJ3.  Its only additional input is the mechanically computed
   `mechanicalOverlapSignals` field described below.  On no conflict, or on a
   missing/invalid judge, use D1 exactly.

P1 and D1-D3 are generated once and shared by all deterministic and judged
arms; no comparator receives a selectively better or worse redraw.

## Frozen overlap signal and anonymous order

Candidate roles are sorted by SHA-256 of the exact byte sequence
`mini-legal-multiway-judge-dev-v1\0fixed-anonymous-order-2026-09-01\0<case-id>\0<draw-name>`
and renamed C1-C3.  Draw names and their original order are hidden from both
judges.

For each unordered pair of available candidates, emit a signal only when:

1. both candidates predict the same binary outcome; and
2. both contain at least one identical `(clauseId, direction)` atom.

The signal lists only the anonymous candidate keys, their shared outcome, and
the shared clause/direction pairs.  Issue codes and rationale text are not
used to create the signal.  A candidate pair with no exact shared
clause/direction pair creates no signal.  Both GJ3 and OJ3 must select one of
the supplied candidates rather than synthesize a new answer.

## Frozen scoring and hypothesis order

Every metric uses all 464 cases.  `ABSTAIN`, null, malformed output, and
missing output count as incorrect.  Headline accuracy is exact-match binary
outcome accuracy.  Civil, tax, grant, and dismiss cells are mandatory
subgroup reports but do not replace the aggregate primary test.

The confirmatory family uses a fixed-sequence, one-sided exact McNemar
procedure at alpha=0.05.  A later hypothesis is confirmatory only if every
earlier hypothesis rejects in the proposed direction; otherwise its p-value
is descriptive.

1. OJ3 > GJ3 (same candidates and same conditional judge budget; overlap
   mechanism test).
2. OJ3 > P1 (standalone Luna test).
3. OJ3 > SC3 (standard multi-draw self-consistency test).
4. OJ3 > D1 (structured single-draw sensitivity test).

For each comparison report both accuracies, paired rescues, paired harms, net
correct, discordant count, one-sided and two-sided exact McNemar p-values, and
the paired accuracy difference with a 95% case-stratified bootstrap interval.
The paper may claim confirmatory superiority only for hypotheses reached and
rejected by this sequence.  All other comparisons, subgroup analyses, and the
development set are explicitly exploratory or descriptive.

## Stop rules and reporting

- Do not inspect private labels between arms and do not change a prompt,
  signal, fallback, comparator, denominator, or test after calls begin.
- Do not rerun a failed item, replace an inconvenient result, or add an arm in
  response to confirmation accuracy.
- Report the complete call count, null count, token use, and wall time for each
  arm.
- After deterministic scoring, run Ralphthon MAC-n-CHEESE as the main
  evidence/claim revision loop and Review-Court-Sprint as an independent
  manuscript gate.  They may improve wording, analyses, and presentation but
  may not alter the frozen experiment or turn infrastructure into a research
  contribution.
- Rewrite the Main and Supplementary DOCX files only to match the surviving
  evidence and explicitly preserve non-significant or negative results.
