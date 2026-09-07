# Instruction Language Policy

Last updated: 2026-05-15 KST

Instruction documents in this repository are split by language and remain bilingual operating contracts. Korean content lives under `docs/ko/...`; English content lives under `docs/en/...`. The original document path keeps only a short stub that points to the split documents.

## Scope

- Requirements documents.
- Engine, frontend, DB, and collaboration contracts.
- Team-specific work instructions.
- Standalone maintenance workflow.
- Repository governance and permission policy.
- Corpus source catalogs and collection-policy reference documents.

## Korean Style

- Korean documents use formal explanatory prose.
- Korean sentences should normally end with forms equivalent to `~입니다`, `~합니다`, `~해야 합니다`, and `~하지 않아야 합니다`.
- Do not use jokey shorthand, slogans, or copied-request meta narration.
- The Korean version must not omit material requirements that exist in the English version.

## Do Not Translate

- Code identifiers.
- API fields.
- HTTP endpoints.
- File paths.
- CLI commands.
- Test names.
- Product keys.
- GitHub handles.
- Environment variable names.

## Frontend Boundary

- The shared UI kernel owns behavior only.
- In verifier terms, the shared UI kernel owns behavior only.
- Product skins own button placement, layout, card order, typography, color, animation, and brand expression.
- The kernel must not impose design geometry because that can break every product design at once.
- Product-specific JS must not duplicate submit, polling, cancellation, source-window, session, i18n, or offline behavior.

## Verification

- `python3 tools/verify_repo_contracts.py` checks that both `docs/ko` and `docs/en` files exist.
- The Korean version must keep enough line coverage and the same fenced code block count as the English version.
- Original instruction paths must remain stubs that point to the split documents.
