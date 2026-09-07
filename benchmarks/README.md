# Benchmark map

The complete private evidence publication—including every registered question
and answer key, all reportable execution answers, protocol/tool settings, and
wrong-answer details—is available at
[`benchmark_reports/2026-07-17-full/`](../benchmark_reports/2026-07-17-full/README.md).

The normative universal-engine benchmark contract is available in both
operating languages:

- [Korean contract](../docs/ko/engine/UNIVERSAL_ENGINE_BENCHMARK_CONTRACT.md)
- [English contract](../docs/en/engine/UNIVERSAL_ENGINE_BENCHMARK_CONTRACT.md)

Executable public/private manifests live under `benchmarks/unified/`. Source
answers and private legal oracles must never be passed to the production engine.

## Current executable legacy inventory

| Group | Benchmark | Cases |
| --- | --- | ---: |
| Legal end-to-end | Kakao/SIM access (4 variants), military key management (4), Yangyang age (2) | 3 tasks / 10 variants |
| Legal exam | 2026 LEET Language Comprehension + Logical Reasoning | 70 |
| TCM | Kuksiwon 81st unique union | 92 |
| Christian | Bible100 + Provao2012 | 192 |
| Islam | CISI100 + AQA4 | 104 |
| Psychology | MIT240 + Sangmyung247 | 487 |
| Buddhist | Sangha Level-3 short answer | 290 |

The currently executable legacy aggregate is 1,235 unique cases. It is not the
complete source inventory. The 2026-07-24 audit of the user-designated Islam
official-source folder confirms a 1,299-case rebuild after replacing AQA4 with
AQA20 and adding BYU16 and Cambridge32. Those three manifest families are now
built and verified, and the 1,309-row public solver bundle has passed isolated
dry-run without a model call; see
[`islam_official_source_audit.json`](islam_official_source_audit.json).

The new Plain Codex baseline is a file-oriented one-agent run: one isolated
solver workspace receives the complete public 1,299-case suite plus all ten
legal variants and must emit one complete answer file. One separate grader
invocation then receives that file and the private gold/rubrics and emits one
complete grade file. Historical answers are never copied into the new file.

Diagnostic slices are TCM p1-50, TCM Wikia64, and Islam CISI wrong26; they are
reported separately and are not double-counted.

Do not confuse inventory count with the primary converted-MCQ gate. LEET has 70
source cases, while only 16 validated choice-free conversions currently belong
to the sealed 619-case gate. The legal end-to-end row adds 3 underlying task
families or 10 execution variants, not both; the Yangyang hard-retrieval file
reuses the same two Yangyang variants and is not another question set. The 290
Buddhist cases were already short-answer and therefore were never part of the
945-MCQ conversion denominator.

## LEET 2026

The Wikia source audit is in
`benchmarks/lawkey_leet_2026/source_audit.json`. Rebuild its split manifests
from the downloaded, SHA-verified attachment with:

```bash
python3 tools/build_unified_benchmark_manifests.py leet-zip \
  --input /path/to/2026년도\ 법학적성시험.zip \
  --id-prefix lawkey-leet2026 \
  --benchmark-id mcq.lawkey.leet2026.v1 \
  --product lawkey \
  --public-out benchmarks/unified/mcq_lawkey_leet2026_70.public.json \
  --private-out benchmarks/unified/mcq_lawkey_leet2026_70.private.json
```

Run the same-model Direct/Beta6/Universal comparison for this registered
benchmark with a real Lawkey DB snapshot:

```bash
python3 tools/run_three_arm_benchmark_suite.py \
  --benchmark-id mcq.lawkey.leet2026.v1 \
  --db lawkey=/absolute/path/to/precedents.sqlite3 \
  --model <exact-model-id> \
  --output-dir runs/leet2026-three-arm
```

Selecting one benchmark intentionally produces a subset report and cannot by
itself satisfy the full-registry promotion gate.
