# Documentation Map

Universal Artichoke documentation is split by language and by layer. Root-level files under `docs/` are indexes or compatibility pointers only. They must not contain the authoritative operating text.

Actual operating documents live here:

```text
docs/ko/   authoritative Korean operating documents
docs/en/   authoritative English operating documents
```

Layer layout:

```text
docs/{ko,en}/STRUCTURE_REQUIREMENTS.md          top-level architecture contract
docs/{ko,en}/docs/                              platform, runtime, governance, standalone workflow
docs/{ko,en}/engine/                            engine contracts and references
docs/{ko,en}/frontend/                          frontend contracts
docs/{ko,en}/db/                                DB sharing contracts
docs/{ko,en}/corpus/                            corpus fixture guide
docs/{ko,en}/corpus/reference/                  corpus source catalogs and collection notes
benchmarks/                                     executable benchmark data
```

Rules:

- Do not add new long-form instruction content directly under `docs/`.
- If a root `docs/*.md` file is needed for compatibility, keep it as a short pointer to both language versions.
- Korean and English instruction files must be updated together.
- Korean instruction prose uses formal `~입니다` style.
- Korean-only corpus notes belong under `docs/ko/corpus/reference/`; an English companion or summary belongs under `docs/en/corpus/reference/`.
