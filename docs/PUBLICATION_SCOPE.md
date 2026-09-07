# Public publication and reproducibility scope

## Included artifacts

This repository was assembled from the Mini Artichokes working tree as a tracked-safe snapshot. It includes public source code, tests, public benchmark inputs/manifests, experiment protocols, aggregate reports, and paper Markdown/evidence files. The exact idea transcript is copied verbatim into `docs/`.

## Explicit exclusions

- API keys, keyrings, auth/session files, Telegram identifiers, and account-specific setup;
- hidden tests, answer keys, labeled private case files, and evaluator-only sources;
- raw per-call JSONL, receipts, local run directories, and large generated artifacts;
- the unverified 9.85 GB Korean-law archive and any claim that it represents a completed 600k-case evaluation;
- DOCX/PDF/PNG exports with embedded metadata or private review-agent material.

These exclusions are for confidentiality and reproducibility integrity, not data deletion from the original working tree.

## Denominator rule

Public experiments must use the complete benchmark denominator named by the protocol. A smaller sample may be used only as a clearly labeled smoke test; it must not be presented as a full benchmark result. Every report should state task IDs, seed/session count, model, timeout, evaluator, retries, and exclusions.

## Interpretation rule

The archive contains exploratory and confirmatory-looking campaigns. A result is not promoted to a paper claim merely because its point estimate is high. Read the protocol and report together, retain counterevidence, and prefer confidence intervals or predeclared gates over post-hoc narrative.

## Credentials

Provider clients use environment-variable interfaces in the public code. Real values must remain outside Git and outside issue/PR text. Reproduction requiring a paid or authenticated provider is optional and must follow that provider's official terms.

