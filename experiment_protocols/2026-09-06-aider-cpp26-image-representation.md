# Aider C++26 text/image representation development assay

Status: preparation only; no benchmark session is authorized by this file.
Freeze: `runs/aider-cpp26-tov-v2-extension-20260902/freeze`.
Official source: https://github.com/Aider-AI/polyglot-benchmark,
commit `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f` (complete C++ track).
Canonical input is the frozen 26-task manifest; tests and gold remain unavailable.

## Fixed design

- Render each manifest `instruction` verbatim, with its stable `taskId`, into
  deterministic readable PNG pages (41 pages at the frozen font/settings). T receives the canonical text packet; I
  receives only the protected rules/index plus image attachments.  I must not
  receive a second full-text copy in its initial prompt.
  Font is DejaVu Sans, 24px, 1800px-wide pages with 42 rows; font hash is stored.
  A full-source character coverage test is required. A preparation-only Nanum
  page lost superscript glyphs and was rejected before any benchmark model call;
  it is preserved as an invalid rendering preflight, not an OCR/model result.
- The same cloned workspace exposes original requirements through
  `benchmark_manifest.json` and the starter source to both views. The frozen
  source does not include `.docs` files. Shell events are best-effort source-read
  exposure; they do not prove that an image caused a particular thought.
- Four independent initial whole-track calls are fixed: T1, T2, I1, I2.
  Each uses Luna medium, a 900-second agent cap, and the unchanged official
  evaluator with an 1800-second evaluator cap.
- Pair inputs are fixed before pair calls: TT=(T1,T2), II=(I1,I2),
  TIa=(T1,I1), TIb=(I2,T2). The two mixed pairs counterbalance modality order.
  Each pair has two calls, G and O, for 12 total solver sessions, not necessarily
  12 API requests. Policy order is frozen: TT G→O, II O→G, TIa O→G, TIb G→O;
  it is not chosen from intermediate scores.
  G and O receive the same immutable full candidate sources, patches, bounded
  evaluator reports, and deterministic verified-union seed.  The first-listed
  candidate wins a passing-task tie; unresolved tasks remain at frozen source.
- G is generic repair/adjudication.  O uses exact-source-grounded
  shared-premise/boundary reasoning as a hypothesis generator, not proof.
  Both policies have the same native shell/tool opportunity and original
  source access.  No task selection, retries, or prior model output as a fresh
  control is allowed.

## Integrity and evaluation

The runner must remove legacy `--sandbox` and `sandbox_mode` settings and invoke
the named `paired` permission profile with approval-never, workspace-write, credential-path deny,
and network-disabled policy; the actual argv is saved per session.  Image and
pair inputs are read-only binds.  The official evaluator runs all 26 tasks for
every session; failures and timeouts remain in the denominator.  This is an
official-test-feedback development assay, not a sealed held-out end-to-end test.

Each session records prompt/profile/code/source/page/patch hashes, model usage,
cache usage, elapsed time, evaluator result, and the best-effort source-read
ledger.  Whole-track elapsed time is not inferred from token totals.

After each of the four baseline sessions, the runner persists its score and
checks agent completion, evaluator completion, the exact 26-row inventory,
scope, and all input/hash integrity fields.  Any failure, timeout, bad
evaluator exit, incomplete inventory, forbidden edit, or hash mismatch stops
the entire campaign as `incomplete` before pair staging; it never substitutes
another parent, filters tasks, or retries.  Pair verified-union selection is
likewise restricted to these complete valid parents.

## Advance gate

Define \(d_X = mean(score(O)-score(G))\) over pair X's 26-task vectors.
Define \(d_{TI}=mean(d_{TIa},d_{TIb})\), \(d_H=mean(d_{TT},d_{II})\), and
interaction \(I=d_{TI}-d_H\).  A prospective continuation gate requires:

1. \(d_{TI} \ge 2/26\);
2. \(I \ge 1/26\);
3. mean O score over TIa/TIb is no lower than mean O over TT and no lower
   than mean O over II.

These are development screening criteria, not significance claims, iid
task claims, a paper-grade result, or permission to alter the denominator.
Any pipeline invalidity is reported separately; it never authorizes selective
retry or task exclusion.  If all four pairs have 26/26 verified-union
anchors, stop as a design ceiling without further reconciliation.
All saved-code scores remain reported on the full denominator, including timed-out
or failed sessions. Advancement additionally requires normal session completion,
valid complete evaluator inventories, no forbidden submitted-file changes, and
unchanged source/evidence. An incomplete run cannot be promoted by its partial score.

This first assay tests initial requirement-view representation and source-grounded
overlap reconciliation. It is not a complete FOVEA atlas, cache/epoch replacement
system, learned neuralese codec, or hard original-read ticket enforcement.
Both I and T may consult exact original requirements. An I session rereading all
requirements is retained as assigned, not excluded or replaced; it is not evidence
of image-only cognition. Realized input/output/cache tokens and elapsed time can
differ despite equal model, tool opportunity and caps. No fixed image-token or
cost-reduction claim is made.

Positive screening must be followed by fresh whole-session replication. Close
prior art includes modality-switch self-correction (MSSC/VLSR,
https://arxiv.org/abs/2511.15703), LensVLM (https://arxiv.org/abs/2605.07019),
and OCR-Memory (https://arxiv.org/abs/2604.26622); this combination is not presumed
novel merely because the views use different modalities.
