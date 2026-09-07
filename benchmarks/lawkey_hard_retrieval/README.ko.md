# Lawkey 하드 검색 벤치마크

이 폴더는 Lawkey 엔진이 실제 질문에서 필요한 판례를 상위 결과로 찾아오는지 검증하는 작은 하드 벤치입니다. 정답 데이터와 통과 규칙은 코드 밖 JSON에 둡니다.

## 실행

```bash
python3 tools/verify_lawkey_hard_bench.py \
  --db /absolute/path/to/precedents.sqlite3 \
  --bench benchmarks/lawkey_hard_retrieval/yangyang-complainant-age.json
```

Lawkey 로컬 DB가 기본 경로에 없으면 `RELIGION_LAWKEY_DB_PATH` 또는 `LAWKEY_PRECEDENT_DB_PATH`를 지정해도 됩니다.

```bash
RELIGION_LAWKEY_DB_PATH=/absolute/path/to/precedents.sqlite3 \
python3 tools/verify_lawkey_hard_bench.py \
  --bench benchmarks/lawkey_hard_retrieval/yangyang-complainant-age.json
```

## 양양 군수 민원인 나이 벤치

질문 예시는 다음과 같습니다.

```text
김진하 군수 민원인 나이를 추정해봐
김진하 양양 군수 사건 민원인 나이를 추정해봐
```

주 판례는 `춘천지방법원속초지원-2025고합5.pdf`입니다. 정답 span은 해당 판례 원문 안의 `D(여, 64세)`입니다.

`서울고등법원춘천-2025노158.pdf`, `대법원-2026도1657.pdf`는 관련 상급심 판례입니다. 관련 판례를 함께 찾는 것은 진단 신호로 기록하지만, 이 판례들만 찾았다고 통과하지 않습니다.

## 통과 규칙

- 주 판례가 상위 `primaryMustAppearWithin`개 안에 있어야 합니다.
- 정답 span은 주 판례의 `full_text`에 있어야 합니다.
- 상급심 판례는 보조 신호일 뿐이며 통과 조건이 아닙니다.
- 후보를 1만 개 반환하고 그 안에 정답이 있다는 식의 통과는 허용하지 않습니다. 검증기는 JSON의 `candidateLimit`만 조회하고, 그 안에서도 `primaryMustAppearWithin`만 합격 창으로 사용합니다.
- 벤치 id, 파일명, 사건번호, 정답 span을 엔진 코드에 박아 넣는 방식은 금지됩니다.
- `김진하`, `양양`, `양양군수` 같은 공개 사건명 alias를 `title`이나 `case_name` 같은 검색 메타데이터에 넣으면 실패입니다. 이 벤치는 질문만 넣었을 때 익명화된 판례 원문과 기존 법원/사건번호 메타데이터만으로 연결되는지 확인합니다.

## PDF를 DB에 넣는 방법

원본 PDF가 DB에 없다면 아래 도구로 `precedents`와 `precedents_fts`에 적재합니다. 이 벤치에서는 `--alias`를 사용하지 않습니다.

```bash
python3 tools/ingest_lawkey_pdf_precedents.py \
  --db /absolute/path/to/precedents.sqlite3 \
  --pdf-dir /absolute/path/to/yangyang-bench-pdfs \
  --source-dataset lawkey_yangyang_bench \
  --source-path-prefix "G:\내 드라이브\양양벤치"
```

이 도구는 PDF 원문을 보존하고, 파일명에서 법원과 사건번호를 추출합니다. 일반 제품 검색에서는 공개 사건명 alias 색인을 별도 기능으로 연구할 수 있지만, 이 하드 벤치에서는 alias-assisted retrieval을 통과로 보지 않습니다.
