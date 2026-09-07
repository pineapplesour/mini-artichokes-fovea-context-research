# Review Court v18 — verified consensus with rating-stage failure

## Run status

- PDF: `Mini_Artichokes_Main_Revised_v18.pdf`, SHA-256
  `f6f311ea1d35fef97928f2d721afb07fcf1f68260d66e8f35a338de0b4bf6fbb`.
- Model: `gpt-5.6-luna`, high reasoning.
- Run ID: `run_914907de30dae72953f31438`.
- The initial runtime completed mapping and three specialist reviews, then hit
  an isolated provider-directory cleanup race. A new runtime copied only the
  byte-identical immutable stages `run_authority`, `uploaded`, `parsed`,
  `mapped`, and `reviewing` and resumed with a process-local `shutil.rmtree`
  retry. No review prompt, schema, verifier, consensus, rating, or paper logic
  was changed.
- The resumed run completed 44 evidence/impact verification calls and
  consensus. It then terminated `INFRA_FAIL/RATING_EVIDENCE_UNATTRIBUTED`
  because one accepted comparison finding had no objective target ID.
- No official Court rating, composition, final audit, or publishable export
  exists for v18. The consensus below is evidence-verified feedback, not a
  Court score.

## Verified strengths

- The A1--A5 preservation invariant is technically well specified and
  appropriately conditional.
- Complete official tracks plus the independent HumanEvalFixDocs family provide
  substantive coverage and a portability/ceiling check.
- The paper preserves negative results and explicitly separates end-to-end
  effectiveness from semantic-overlap causality.
- Pinned sources, protocols, hashes, traces, ledgers, and complete results give
  unusually strong audit provenance.

## Verified major weaknesses

- The largest headline gains remain nested additional-compute comparisons.
- The original recursive comparison is post hoc; the Go equal-call replacement
  is sensitivity-only; JavaScript and HumanEvalFix do not establish a TOV gain.
- Internal prompt-level Plain/Graph/ordinary/Generic arms are not a comparison
  against full contemporary external repair agents.
- A minimal task-wise verifier union over the same stored outputs is
  algebraically identical to recursive promotion; novelty must be framed as an
  enforced systems composition, not a new selection operator.
- The empirical artifact did not visibly establish every A1/A2
  noninterference and verifier-stability assumption.
- Go39 includes `counter`, whose official command reports no tests to run.
- Whole-track calls leave task-level inference conditional on a small number of
  realized trajectories, and semantic ledger text lacks independent labels.

## v19 actions taken from the verified consensus

- Added a test-covered Go38 sensitivity; removing `counter` subtracts one pass
  from every arm and leaves all discordant counts and exact tests unchanged.
- Added two repeated verifier runs for each new materialized union. JavaScript
  reproduces the same 47/49 task vector; HumanEvalFix reproduces 164/164.
- Added manifest noninterference audits showing unique, non-nested task roots
  and zero multiply owned declared solution paths for JavaScript49 and
  HumanEvalFix164.
- Explicitly stated equivalence to a minimal union given identical stored
  outputs and narrowed novelty to enforced systems composition.
- Added the missing external-agent comparison limitation and source-license
  handling.
- Corrected the actual HumanEvalFix runtime to Python 3.13.11 and disclosed its
  mismatch with the preregistered 3.13.5 value as a protocol deviation.

## Stage hashes

- original reviewing: `69831deda0de84d9f3bf45458f40eb6ff0c5404b1faa8bbef0d38762d3b786af`
- resumed verifying: `236b02fc84d96cd9e240ffa88e44620cf26c337f638fa4e3c00f7198d3b48fc6`
- resumed consensus: `da26ceb0d156b1cf39e4b108ca409948d1ea7625e573e02993177e6a3c17ee90`
