# Mini Artichokes / FoveaContext research snapshot

This is a public, reproducibility-oriented snapshot of the Mini Artichokes research work. It contains the public-safe implementation code, benchmark definitions and public inputs, experiment protocols, aggregate reports, paper-revision sources, and the exact raw transcript of the FoveaContext idea that motivated the latest representation experiment.

This repository is an honest research record. It does **not** claim that the image/overlap method has already won, that a legal-corpus experiment was completed, or that the paper has already received an overall score of 4.

## Start here

- [Idea versus implementation](docs/IDEA_AND_IMPLEMENTATION.md)
- [Public-scope and reproducibility notes](docs/PUBLICATION_SCOPE.md)
- [Exact raw idea transcript](docs/original_user_idea_chat_2026-09-06.md)
- [Latest C++26 image-representation assay](benchmark_reports/2026-09-06-aider-cpp26-image-representation/RESULTS.md)
- [Paper evidence boundary](paper_revision/2026-09-01/evidence/EVIDENCE_SCOPE.md)

## What is included

The snapshot includes:

1. deterministic source-to-image and text/image paired runners, canonical-view and permission tests, and the surrounding overlap, verifier, critic/graph/ToV, and benchmark tooling;
2. public benchmark manifests/inputs and full-denominator experiment protocols;
3. aggregate result reports from the Mini Artichokes development campaign;
4. Markdown paper drafts, review notes, evidence ledgers, and provenance documentation;
5. a public-safe copy of the original user idea, without silently rewriting it.

The code is organized as an experimental archive rather than a polished package. Paths in historical reports may refer to the original local workspace; the raw run directories are intentionally not part of this public snapshot.

## Current evidence status

The latest full Aider C++26 image-representation assay completed all 12 planned sessions on the full official 26-task denominator. Its report records the arm totals and the pre-registered gates. The image/overlap interaction gate did not pass, so no superiority claim is made from that experiment. Earlier reports contain both positive-looking development results and counterevidence; they are preserved so the paper can separate exploration from confirmation.

In particular, a high aggregate score in a development arm is not treated as proof of general superiority. The public reports should be read together with their protocol, denominator, evaluator, and exclusion notes.

## Reproducing a small check

From the repository root:

```bash
python -m pytest tools/test_aider_cpp26_image_representation.py \
  tools/test_aider_cpp26_canonical_views.py \
  tools/test_aider_cpp26_native_permissions.py \
  tools/test_classeval_image_text_blind_smoke.py
python tools/run_aider_cpp26_image_representation.py --help
```

Full agent campaigns require the model/provider setup described by each protocol and are intentionally not run by an install step. Use the official public benchmark sources and record model, seed, timeout, evaluator, denominator, and every failed/retried case.

## Public-data and safety boundary

No API keys, Telegram credentials, account-auth files, hidden evaluator source, answer keys, private JSONL runs, or raw legal archive are published here. The candidate Korean-law archive found locally was approximately 9.85 GB, but its provenance/content/count was not verified; it is therefore explicitly excluded rather than presented as a completed 600k-case experiment. Public legal manifests and governance notes remain where they are safe to share.

Credential adapters in the working tree were either omitted or reduced to environment-variable interfaces. Do not add real credentials to this repository.

## Attribution

Benchmark and tool-specific attribution is recorded in the relevant protocol/report files. This snapshot does not redistribute hidden benchmark tests or proprietary model outputs.
