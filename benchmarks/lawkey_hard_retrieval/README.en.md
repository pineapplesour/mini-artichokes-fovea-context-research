# Lawkey Hard-Retrieval Benchmarks

This directory stores hard Lawkey retrieval benchmarks as data. The expected targets and pass rules live outside engine code.

## Run

```bash
python3 tools/verify_lawkey_hard_bench.py \
  --db /absolute/path/to/precedents.sqlite3 \
  --bench benchmarks/lawkey_hard_retrieval/yangyang-complainant-age.json
```

If the Lawkey DB is not at the default path, `RELIGION_LAWKEY_DB_PATH` or `LAWKEY_PRECEDENT_DB_PATH` can also be used.

```bash
RELIGION_LAWKEY_DB_PATH=/absolute/path/to/precedents.sqlite3 \
python3 tools/verify_lawkey_hard_bench.py \
  --bench benchmarks/lawkey_hard_retrieval/yangyang-complainant-age.json
```

## Yangyang Governor Complainant-Age Benchmark

Example queries:

```text
김진하 군수 민원인 나이를 추정해봐
김진하 양양 군수 사건 민원인 나이를 추정해봐
```

The primary judgment is `춘천지방법원속초지원-2025고합5.pdf`. The required answer span is `D(여, 64세)` inside that district-court judgment.

`서울고등법원춘천-2025노158.pdf` and `대법원-2026도1657.pdf` are related appellate judgments. Finding them is recorded as a diagnostic signal, but they are not sufficient for a pass.

## Pass Rules

- The primary judgment must appear within `primaryMustAppearWithin`.
- The required answer span must exist in the primary judgment `full_text`.
- Related appellate judgments are diagnostic only.
- Returning 10,000 candidates and containing the correct judgment somewhere inside them is not a pass. The verifier retrieves only `candidateLimit` results and accepts only the `primaryMustAppearWithin` rank window.
- Engine code must not hard-code benchmark ids, file names, case numbers, or answer spans.
- Public case-name aliases such as Kim Jin-ha, Yangyang, or Yangyang governor must not be injected into searchable `title` or `case_name` metadata for this benchmark. This benchmark tests whether the query alone can connect to anonymized judgment text and ordinary court/case-number metadata.

## Ingest PDFs Into The DB

If the source PDFs are not already in the DB, ingest them into `precedents` and `precedents_fts`. Do not use `--alias` for this benchmark:

```bash
python3 tools/ingest_lawkey_pdf_precedents.py \
  --db /absolute/path/to/precedents.sqlite3 \
  --pdf-dir /absolute/path/to/yangyang-bench-pdfs \
  --source-dataset lawkey_yangyang_bench \
  --source-path-prefix "G:\내 드라이브\양양벤치"
```

The ingester preserves the PDF text and extracts court/case-number metadata from file names. Public case-name alias indexing may be researched as a separate product feature, but alias-assisted retrieval does not pass this hard benchmark.
