# Korean legal-reserve source and governance note

## Scope

This note records the bounded source audit for the frozen 464-case negative
boundary. It is a documentation correction, not new performance evidence.

## Selected source labels

The reserve was balanced from a local 526-case corpus. The selected 464 rows
carry the following local source labels:

| Local source label | Selected rows | Recoverable source information |
|---|---:|---|
| `01_joonhok_precedents` | 384 | Hugging Face `joonhok-exo-ai/korean_law_open_data_precedents`; dataset card labels the dataset OpenRAIL and describes a snapshot of Korean Law Open Data precedents |
| `02_lbox_open` | 75 | LBox Open; repository identifies Law Open Data as a source and states CC BY-NC 4.0 |
| `lawlaw` | 5 | No license or reuse metadata recoverable from the frozen local corpus |

Primary source pages:

- https://huggingface.co/datasets/joonhok-exo-ai/korean_law_open_data_precedents
- https://github.com/lbox-kr/lbox-open
- https://open.law.go.kr/LSO/openState/orgList.do

## Input minimization

The public model packet omitted the target holding. The construction step
replaced target court, case number, and decision date with fixed placeholders
when present. In the selected reserve, 116 rows had at least one replacement:
288 court-field occurrences, 91 case-number occurrences, and 100 date-field
occurrences. A row can contain multiple replaced occurrences and fields.

These operations minimize direct metadata but do not fully de-identify
narrative facts. Distinctive events can remain re-identifiable. Because of
that residual risk and the five records without recoverable reuse metadata,
the paper releases only the protocol and aggregate negative-boundary results,
not item texts or model outputs, pending a separate governance review.

## Arm-label correction

The frozen scorer distinguishes the direct plain-instruction Luna arm P1 from
the structured D1-D3 draws. The correct legal results are:

| Arm | Correct / 464 | Accuracy |
|---|---:|---:|
| P1 | 284 | 61.21% |
| D1 | 259 | 55.82% |
| GJ3 | 263 | 56.68% |
| OJ3 | 255 | 54.96% |

OJ3's 30 rescues, 59 harms, and net -29 are relative to P1. The prior v1
manuscript label "D1 284/464" was a transcription error; the score artifact
already contained the correct P1 and D1 identities and no score was changed.
