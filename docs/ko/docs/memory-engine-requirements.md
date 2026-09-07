# 메모리 엔진 요구 사항

최종 업데이트 날짜: 2026년 7월 24일(KST)

이 문서는 메모리/검색/추천 엔진에 대한 독립형 요구 사항 전달입니다. 제품/API/디자인 구조를 정의하고 이 엔진을 교체 가능한 블랙박스로 취급하는 `docs/overall-structure-requirements.md`와는 별개입니다.

## 최종 목표

프로젝트의 최종 목표는 메모리 엔진 자체가 아니라 빠르고 정확한 하나의
범용 답변 엔진입니다. 기본 출발점은 얇은 공통 하네스의 direct Codex이고,
메모리·검색·DB는 Codex가 필요할 때 선택하는 도구입니다. 이 문서는 “X에
대한 모든 정보 구성”처럼 외부 자료가 필요한 질문에서 원본 근거를 누락 없이
선택하고 검증 가능하게 전달하는 선택적 메모리 능력을 규정합니다.

현재 가장 잘 알려진 메모리 능력 기준선은 Lawkey에서 채택한 베타-6입니다.
이는 전체 답변 엔진의 기본값이나 고정 추론 단계가 아닙니다. 모든 추가
메모리 경로는 direct Codex 대비 완전한 답변 정확도·지연·비용 개선을
증명해야 합니다.

## 제품 의도 및 컨텍스트 보존

이 선택적 능력의 목표는 "더 멋진 RAG 데모를 만드는 것"이 아닙니다. 외부
근거가 필요할 때 신중한 전문가가 사용 가능한 자료를 검사한 것처럼 올바른
원본 증거와 문서 간 컨텍스트를 Codex/UI에 전달하는 메모리·검색 능력입니다.

이 문서의 운영 방향은 다음과 같이 요약될 수 있습니다.

- 원본 소스를 잃지 하지 않아야 합니다.
- 원래 범위가 필요한 경우 요약에서 답변하지 않아야 합니다.
- 눈에 보이는 문구를 속이거나 과대적합하여 벤치마크를 해결하지 않아야 합니다.
- 좁은 일회성 규칙으로 검색 실패를 수정하지 않아야 합니다.
- 법률, 학교 자료, 종교, 의학, 심리학 및 추천에 충분히 보편적인 엔진을 만듭니다.
- 모든 중요한 선택을 검사 가능하고, 되돌릴 수 있으며, 이전 시도와 비교할 수 있도록 합니다.
- 시스템이 명령에 대해 확신이 없을 때, 추측하는 대신 해석을 말하고 질문합니다.
- 실제 앱 경로를 통해 테스트한 후에만 성공을 보고합니다.

대표적인 어려운 상황:

- 강의녹화는 자동으로 매칭되어야 하는 슬라이드, 회로 이미지, PDF, HWP 유인물을 말합니다.
- 교수가 더 넓은 범위를 먼저 말한 후 시험 범위를 변경합니다.
- 요청은 "모든 문제", "이 문제에 대한 정확한 설명", "시험은 언제입니까?" 또는 "교수님이 강조한 내용은 무엇입니까?"를 묻는 경우 일반적인 요약에서는 핵심 증거가 손실됩니다.
- 동일한 사실이 여러 파일에 나타나며 중복된 잡음보다는 반복적으로 언급하는 것이 중요할 수 있습니다.
- a legal query needs the exact KakaoTalk/military-key/snowboard evidence, not just a semantically similar case;
- 추천 작업은 거부된 아차 실패를 포함하여 전체 코퍼스를 검사한 후 전문가가 내리는 선택에 접근해야 합니다.
- 종교적/의학적/심리학적 답변에는 유창한 자유 형식 합성이 아닌 소스 계층 구조와 안전 경계가 필요합니다.

이것이 현재 요구 사항이 출처, 중복/반복 원장, 참조 해결, 시간 그래프, 청구 카드, 소스 창, 적용 범위 보고서 및 벤치마크 게이트를 고집하는 이유입니다. 이것은 장식적인 분야가 아닙니다. 이는 이전 검색 시스템이 실패한 정확한 방식에 대한 보호입니다. 중요한 소스 누락, "해당 항목"을 잘못된 파일에 바인딩, 중복 항목을 두 번 계산, 대체된 설명을 현재로 처리, 소스 대신 요약 인용, 감사할 수 없는 그럴듯한 답변 생성 등이 있습니다.

## 전작에서 선택한 것

이전 작업의 다음 아이디어는 요구 사항 또는 시험 지침으로 명시적으로 보존됩니다.

| 보존항목 | 왜 중요한가 | 본 계약서에 나타나는 위치 |
|---|---|---|
| beta-6 / Lawkey 스타일의 선택된 증거 전달 | 현재 가장 강력한 기준선; 증거를 먼저 선택하고 요약이 증거인 것처럼 가장하지 않습니다 | `Current Beta-6 Shape`, `Required Evidence Objects`, `Promotion Gate` |
| 상황 요약, 청구 요약, 견적 및 범위가 포함된 청구 카드 | 작성자가 유용한 인용을 선택하고 인용이 중요한 이유를 UI에서 설명할 수 있습니다. `Claim Card`, `Passage Window`, `Evidence Shape Gate` |
| 정확한 강조 표시 및 제한된 확장이 가능한 소스 창 | 사용자는 대용량 파일을 로드하지 않고 인용을 클릭하고 정확한 원본 범위를 확인해야 합니다 | `Passage Window`, `Full User-Path Gate` |
| top-k 선택된 100개의 소스 핸드오프 | 이전 시스템은 풍부한 후보자 컨텍스트에 의존했습니다. 증거 형태가 우연히 축소되는 일을 막기 위한 것입니다 | `Current Beta-6 Shape`, `Evidence Shape Gate` |
| Hit-Thunder 커버리지 패치 아이디어 | 검색은 누락된 축을 열거하고 조기에 중지하는 대신 다시 검색해야 합니다. | `Coverage Patch Loop`, `External Architecture Ideas`, `engine/references/README.md` |
| 미니 아티초크 중복 융합 아이디어 | 고위험 바인딩에는 특히 날짜/범위/역전/견적 범위/권장 사항과 같은 독립적인 합의가 필요합니다. `Redundant Verification`, `Required Engine Work Packages` |
| 메모리 계층 구조: 리프 -> 섹션 -> 문서 -> 컬렉션 -> 루트 | 모든 부모가 아동 보장 범위와 해결되지 않은 격차를 추적하는 경우에만 요약이 탐색에 도움이 될 수 있습니다 | `Hierarchical Memory Tree` |
| 그래프 메모리 / 뇌와 유사한 관계 | 파일 간/시간/참조 질문에는 분리된 청크가 아닌 관계가 필요합니다 | `Graph Memory`, `Reference Resolution And Time Policy` |
| 손실 최소화 압축 | 작은 모델/파서는 압축/추출할 수 있지만 지침/엔티티/동사/날짜/부정/참조는 살아남아야 함 | `Loss-Minimizing Compression`, `Exhaustive Small-Model Passes` |
| 다중 모드 수집 및 정렬 | 녹음은 일반적으로 자료를 가리킵니다. 성적표만으로는 불완전함 | `Ingestion Requirements`, `Multimodal mismatch` |
| 도메인 전반에 걸친 독립적인 하드 벤치마크 | 더 나은 엔진은 가시적인 테스트에서 승리하는 것이 아니라 일반성을 입증해야 합니다 | `Benchmark Requirements`, `Anti-Overfit Gate` |

## 사전 체험 레슨 및 실패 패턴

프로젝트 메모리에는 베타-6 및 관련 시험에서 얻은 여러 교훈이 포함되어 있습니다. 팀이 매력적이지만 잘못된 지름길을 반복하는 것을 방지하기 때문에 제약 조건으로 사용됩니다.

1. **핫 캐시 방지는 콜드 엔진 방지가 아닙니다.** 캐시가 웜 상태가 된 후의 빠른 결과는 엔진이 실제 최초 사용 쿼리에 충분히 빠르다는 것을 증명하지 않습니다.
2. **선택기 단독 성공은 오해의 소지가 있을 수 있습니다.** 선택기 변형은 단독으로 더 빠르거나 깔끔해 보일 수 있지만 전체 앱 경로에 실패하거나 선택한 소스 종류를 변경하거나 나중에 증거가 부족할 수 있습니다.
3. **작업자 수만으로는 대기 시간이 해결되지 않습니다.** 하나의 선택기 배치가 느린 경우 작업자를 추가하면 병렬 backlog만 줄어듭니다. 느린 batch 바닥은 제거되지 않습니다.
4. **키워드 라운드를 낮추는 것은 무해하지 않습니다.** 이전 TCM 실험에서는 키워드 라운드가 줄어들면 증거 구성이 크게 바뀔 수 있다는 점을 보여주었습니다.
5. **늦은 키워드 고갈은 현실이었습니다.** 광범위한 첫 번째 라운드는 경계를 채우고 나중에 더 구체적인 용어가 고려되는 것을 방지할 수 있습니다.
6. **프롬프트 크기 축소가 자동으로 더 좋아지는 것은 아닙니다.** 증거 종류, 중복, 인용 품질 및 답변 유용성을 보존해야 합니다.
7. **청구항 수가 충분하지 않습니다.** UI에는 후보/인용 청구 분할, 소스 창 및 정확한 하이라이트가 표시되어야 합니다.
8. **요약은 기억으로 취급되면 위험합니다.** 요약은 색인화, 경로 지정 또는 압축할 수 있지만 최종 사실 주장은 원래 증거로 추적되어야 합니다.
9. **한 번 잘못된 바인딩으로 인해 모든 것이 망가질 수 있습니다.** 잘못된 시험 범위, 잘못된 "이것/저것" 참조, 잘못된 소스 ID 또는 잘못된 인용 범위는 전체 답변을 무효화할 수 있습니다.
10. **벤치마크는 숨겨지거나 회전해야 합니다.** 팀이 알려진 카카오톡/스노보드/학교 예시를 이름별로 최적화한다면, 이는 부정행위이지 더 나은 엔진이 아닙니다.

선택기 크기, 키워드 정책, 청구 카드 구성, 소스 창 동작 또는 벤치마크 정의를 변경하기 전에 이 강의를 읽어야 합니다.

## 협상할 수 없는 원칙

1. 원본 데이터는 항상 보존됩니다. 요약, 임베딩, 그래프 노드 및 압축 형식은 인덱스 또는 앵커이며 소스 텍스트를 대체하지 않습니다.
2. 답변 엔진은 사실적 주장에 대해 메모리 요약만이 아닌 선택된 증거를 사용해야 합니다.
3. 선택한 모든 주장은 출처 ID, 인용, 정확한 인용문 또는 범위, 맥락 요약, 주장 요약, 소스 창 좌표 등 출처를 유지해야 합니다.
4. 시스템은 조기 정리보다 회상 완전성을 선호해야 합니다. 중요도 채점은 비용이 많이 드는 작업의 우선순위를 정할 수 있지만 시스템에는 여전히 모든 관련 데이터에 대한 명시적인 적용 경로가 있어야 합니다.
5. 어떤 단계에서든 잘못된 바인딩으로 인해 최종 결과가 손상될 수 있습니다. 참조 해결, 시간 순서, 중복 계산, 견적 범위 일치 및 소스 신원은 가정이 아닌 검증되어야 합니다.
6. 하나의 벤치마크나 하나의 알려진 쿼리에 대해 최적화하지 않아야 합니다. 벤치마크 대상 해킹은 금지됩니다.
7. 성공 여부는 격리된 내부 기능뿐만 아니라 사용자가 사용하는 것과 동일한 사용자 경로를 통해 테스트되어야 합니다.
8. 사용자의 지시가 모호한 경우 에이전트나 엔진은 위험한 작업을 수행하기 전에 해석을 명시하고 확인을 요청해야 합니다.

## 현재 엔진 경계

현재 진입점:

```python
Beta6JobManager.answer_sync(product, query, language="", limit=8)
Beta6JobManager.create_job(product, query, language="", limit=8, session_token, account_subject="")
```

비동기 제품 경로는 `Beta6JobManager.create_job(...)`를 호출하고 나중에 공유 작업 엔드포인트를 통해 상태/결과를 노출하는 `POST /api/{product}/jobs`를 통해 이 엔진에 들어갑니다. 동기화 응답은 테스트/개발에만 존재합니다.

현재 엔진 입력:| 필드 | 의미 |
|---|---|
| `product` | `ProductProfile` 키: 현재 `islam`, `tcm`, `simli`. |
| `query` | 사용자의 자연어 목표/질문. |
| `language` | 해결된 답변 언어. 생략하면 감지된/UI/기본 언어가 사용됩니다. |
| `limit` | 선택된 증거 수를 요청했습니다. 현재 베타-6는 효과적인 top-k를 강제합니다. 기본값은 100입니다. |
| `ProductProfile.db_path` | 읽기 전용 코퍼스 DB 경로입니다. |
| `ProductProfile.db_shape` | `precedents` 또는 `documents`. |
| `llm_client` | 구성 시 현재 기본값은 Lawkey/Gemma4입니다. 로컬 결정론적 선택에 대해 비활성화될 수 있습니다. |
| `model` | 현재 생산 모델은 `gemma-4-26b-a4b-it`입니다. |
| `runs_root` | 내구성 있는 아티팩트 루트, 기본값 `/workspace/bunjum2/religion/runs`. |
| `cache_root` | 배치 캐시 루트는 현재 앱 경로의 실행별 루트 `_beta6_batch_cache`입니다. |

현재 엔진 출력은 `source-grounded-v2`를 충족해야 합니다.

```json
{
  "answer": "Markdown with [S#] and/or [C#] citations",
  "answerReadiness": "final_answer",
  "writer": {},
  "selector": {},
  "answerSections": [],
  "citationMap": {},
  "passages": [],
  "selectedEvidence": [],
  "claimCards": [],
  "candidateClaimCards": [],
  "citedClaimCards": [],
  "passageWindows": [],
  "answerPlan": {},
  "coverageReport": {},
  "beta6": {}
}
```

플랫폼과 디자인 레이어는 이 결과 계약을 넘어서는 숨겨진 엔진 내부에 의존해서는 안 됩니다.

## 현재 베타-6 형태

현재 베타-6 엔진 단계는 다음과 같습니다.

```text
keyword_generation
candidate_search
source_selection
chunking
claim_cards
answer_plan
writer
coverage
```

현재 기본값 및 형태:

| 설정 | 현재 가치/행동 |
|---|---|
| 선정된 증거 top-k | `LAWKEY_DEFAULT_TOP_K_PRECEDENTS = 100`; 코드가 변경되고 입증되지 않는 한 효과적인 top-k는 이 기본값보다 낮지 않습니다. |
| 키워드 개수 | 기본적으로 라운드 당 `10`. |
| 키워드 라운드 | 최대 `3`; 최소 라운드 기본값 `2`. |
| 이슬람/TCM 국경 표적 | `max(top_k * 12, 1000)`, 일반적으로 상위 k 100의 경우 `1200`. |
| 이슬람/TCM 프론티어 스톱 플로어 | `max(top_k * 8, 600)`, 일반적으로 상위 k 100의 경우 `800`. |
| Simli 국경 목표 | `max(top_k * 4, 400)`, 일반적으로 `400`. |
| 키워드별 FTS 제한 | 기본적으로 `700`. |
| 선택자 후보 제한 | 이슬람/TCM은 일반적으로 최대 `1200`, Simli는 일반적으로 `400`까지입니다. |
| 선택기 배치 크기 | 이슬람 `100`, TCM `100`, Simli `25`. |
| 선별기 작업자 | 이슬람교/기본 `4`, TCM `6`, Simli `2`, 배치 수로 제한됩니다. |
| 선택기 시간 초과 | 기본 기본 선택기 시간 초과 `90s`; Simli 선택기 시간 초과 `45s`. |
| 시간 초과 복구 | 더 작은 하위 배치, 기본 복구 작업자 `min(4, sub_batch_count)`. |
| 선택기 발췌 바이트 | 구성되지 않은 경우 이슬람 `360`, TCM `560`, Simli/generic `0`. |
| 이슬람 선택기 입력 모드 | 2026년 5월 9일 이후 기본적으로 `raw_excerpt_v1+compact_lines_v1`. |
| TCM/Simli 컴팩트 라인 | `RELIGION_SELECTOR_COMPACT_LINES=1`가 아니면 기본값은 꺼집니다. 승진하기 전에 냉간 증거가 필요합니다. |
| 청구 분석기 | 기본적으로 청크 기반이며 소스 모드는 env fallback을 통해 계속 사용할 수 있습니다. |
| 클레임 분석기 소스 제한 | 기본값은 100입니다. |
| 클레임 분석기 소스 문자 | 이슬람 `900`, 소스 분석기의 소스당 기타 `1400`; 청크 분석기에는 별도의 청크 문자 기본값이 있습니다. |
| 청크 토큰 예산 | `100000`. |
| 응답 플래너 시간 초과 | `90s`. |
| 최소 답변 문자 | 이슬람 `2200`, TCM `2400`, Simli `1500`; 필러가 아닌 소스 접지여야 합니다. |

이 숫자는 임의적이지 않습니다. 교체품이 이 문서의 승격 게이트를 통과하지 않는 한 속도를 위해 변경하지 않아야 합니다.

## 현재 내구성 유물

각 실행은 검사 및 재개가 가능해야 합니다. `runs/<jobId>/` 아래의 현재 파일:

```text
request.json
status.json
selected_records.json
selector_meta.json
claim_cards.json
candidate_claim_cards.json
cited_claim_cards.json
passage_windows.json
claim_analyzer_meta.json
answer_plan.json
coverage_report.json
chunk_plan.json
prompt_input.json
result.json.pending
result.json
```

내구성 있는 대기열 행:

```text
runs/_beta6_queue/<jobId>.json
runs/_beta6_queue/.<jobId>.claim.lock
```

모든 미래 엔진은 동등한 아티팩트 검사 기능 또는 문서화된 버전 대체 기능을 제공해야 합니다.

## 필수 증거 객체

### 선택된 증거

UI/작성기에 노출된 각 선택된 소스에는 다음이 포함되어야 합니다.```json
{
  "id": "canonical source id",
  "label": "S1",
  "title": "...",
  "citation": "...",
  "authorityBody": "...",
  "date": "",
  "topic": "",
  "type": "",
  "dataset": "",
  "path": "",
  "url": "",
  "score": 0.0,
  "excerpt": "bounded text preview",
  "language": "",
  "school": "",
  "tradition": "",
  "sourceKind": "",
  "authorityLevel": 0,
  "authorityLabel": ""
}
```

선택적 선택기 원장 보강:

```json
{
  "selectorContextSummary": "what context this source belongs to",
  "selectorClaimSummary": "what this source contributes",
  "selectorQuoteCandidate": "possible exact quote",
  "selectorStance": "support|limit|variant|gap|school_position",
  "selectorSourceRole": "scripture|commentary|guideline|..."
}
```

### 청구 카드

각 청구 카드에는 다음이 포함되어야 합니다.

```json
{
  "claimId": "C1",
  "label": "S1",
  "sourceId": "canonical source id",
  "citation": "human citation",
  "role": "source role",
  "claimAxis": "what issue axis this card covers",
  "stance": "support|limit|variant|gap|school_position|source_claim",
  "contextSummary": "source context",
  "claimSummary": "what the quote contributes to the user query",
  "quote": "exact consecutive substring from the source",
  "span": {"start": 123, "end": 180, "exact": "same quote"},
  "quoteVerified": true,
  "analysisSource": "llm_claim_analyzer or deterministic_source_card",
  "quoteMatch": "exact|retry|force_match",
  "school": "",
  "tradition": "",
  "sourceKind": ""
}
```

청구 카드는 선택한 메모리와 답변 쓰기 사이의 다리입니다. 작성자가 유용한 인용 구절을 선택할 수 있을 만큼 풍부해야 하며 UI는 각 인용이 중요한 이유를 설명할 수 있어야 합니다.

### 통로 창

인용문이 포함된 각 클레임은 제한된 소스 창에 매핑되어야 합니다.

```json
{
  "claimId": "C1",
  "sourceId": "canonical source id",
  "windowStart": 0,
  "windowEnd": 900,
  "text": "bounded original text",
  "highlightStart": 100,
  "highlightEnd": 155,
  "hasBefore": true,
  "hasAfter": true
}
```

정확한 인용문이 표시되고 강조 표시되어야 합니다. 컨텍스트 확장은 증분적이고 제한적이어야 합니다.

## 엔진이 해결해야 하는 범용 검색 문제

시스템은 법률, 학교 자료, 종교, 의학, 심리학 및 미래 영역 전반에 걸쳐 이러한 문제를 해결해야 합니다.

1. **원자 단위가 너무 큼:** 파일, 강의 기록, PDF 페이지 또는 HWP 섹션이 하나의 LLM 호출을 초과할 수 있습니다. 엔진은 순서, 참조, 제목, 이미지/표 또는 인용 가능성을 잃지 않고 이를 분할해야 합니다.
2. **파일 간 참조:** "지난번", "2주 전", "위에서 말한 대로", "파일 3 참조", "내일", "이전 슬라이드"와 같은 문구 및 대명사는 연대순 및 문서 관계를 사용하여 해결해야 합니다.
3. **작업별 중요성:** 중요한 것은 사용자 목표에 따라 다릅니다. 시험의 경우, 원래의 해결된 문제, 발표된 시험 범위/날짜, 교수 강조, 문제 스타일이 일반적인 요약보다 더 중요할 수 있습니다.
4. **순서, 시간, 중복:** 반복적으로 언급되는 내용은 잡음이 아닌 증거일 수 있습니다. 개수는 중복된 요약을 이중으로 계산해서는 안 됩니다. 수정, 반전, 유효성 창 및 연대순을 모델링해야 합니다.
5. **핵심 결론 위험:** 엔진은 문서의 주요 결론을 놓치거나 뒤집어서는 안 됩니다.
6. **계단식 바인딩 오류:** 하나의 잘못된 링크, 성적표 오류, 시험 범위 반전 또는 소스-참조 매핑으로 인해 최종 결과가 망가질 수 있습니다. 중요한 바인딩에는 중복 확인이 필요합니다.
7. **다중 모드 불일치:** 녹음 내용은 슬라이드, PDF, HWP 유인물, 도면, 표 또는 회로 이미지를 참조하는 경우가 많습니다. 엔진은 가능한 경우 오디오/비디오 대본을 원본 자료에 맞춰야 합니다.
8. **추천 정확도:** 추천 작업은 단순히 의미상 유사한 검색이 아닌 전체 코퍼스에서 전문가 수준의 선택을 목표로 해야 합니다.

## 제거할 구체적인 실패 모드

엔진 팀은 다음 내용을 선택적인 마무리 작업이 아닌 실제 문제 설명으로 처리해야 합니다. 일반적인 질문에 답하지만 이러한 경우 중 하나에 실패하는 시스템은 아직 완전한 메모리 엔진이 아닙니다.| 실패 모드 | 사용자 요청 예시 | 필수대책 | 필수 출력 증거 |
|---|---|---|---|
| 대형 소스 장치 | "이 3시간 강의에서 테스트 문제만 응답함" | 안정적인 순서, 제목, 타임스탬프 및 상위 문서 ID를 사용한 리프 수준 분할 | 리프 범위 ID, 상위 체인, 순서 색인, 생략된 범위 보고서 |
| 상호 참조가 손실됨 / 반대어 | "저번 시간에 그 회로", "앞서 경쟁 범위" | 연대순, 파일 링크, 발표자 회전, 슬라이드/오디오 정렬 및 상호 참조에 대한 참조 확인자 | 자신있게 `resolvedReferences[]`, 지원 범위, 미해결 항목 |
| 중복된 혼란 | 동일한 PDF가 다시 업로드되고, 내용이 슬라이드 텍스트를 반복하고, 인용문이 여러 책에 나타납니다 | 정확한 중복, 거의 중복, 의미 중복, 반복 언급 원장 분리 | `duplicateLedger`, `countPolicy`, 정식 소스 ID, 반복 증거 수 |
| 시간 또는 반전 오류 | 교수는 먼저 중간고사가 Ch.1-4를 다루고 나중에 Ch.1-3으로 변경된다고 말합니다. 유효성 창이 있고 가장자리를 대체하는 시간 그래프 | `timeline[]`, 활성 문, 대체된 문, 충돌 증명 |
| 작업 별 현저성 손실 | 일반 요약에는 해결된 문제, 시험 힌트, 교수 스타일이 누락되었습니다. 검색 전 적용 범위 축을 생성하는 목표 해석기 | `coverageAxes[]`, 만족/약함/누락 축 보고서 |
| 잘못된 소스 바인딩 | 인용문이 잘못된 파일/장/연사에 기인한 경우 | 소스 ID, 인용 범위, 메타데이터 및 독립 패스를 사용한 중복 바인딩 검사 | 견적 검증 현황, 대체 후보, 불일치 신고 |
| 다중 모드 불일치 | 그래프가 PDF 또는 이미지에 있는 동안 오디오에서 "이 그래프"라고 말함 | 타임스탬프, 슬라이드/페이지/이미지 ID, OCR/객체 추출을 통한 사본-문서 정렬 | 정렬된 미디어 범위, 이미지/테이블 ID, 기록 타임스탬프 |
| 추천 바로가기 | "100만 개 중 제일 맞는 변호사/교수/자료 추천해" | 후보 생성 + 철저한 적용 범위/재순위 + 최근접 이웃 감사 방지 | top-k 근거, 고려된 풀, 거부될 뻔한 이유 |
| 증거 없는 환각 | 사용자가 명시되지 않은 날짜를 요청합니다 | 명시적인 "찾을 수 없습니다" 증명이 있는 부정 검색 경로 | 검사 범위, 축 누락 보고서, 증거 부재 상태 |

## 필수 엔진 작업 패키지

이는 새롭거나 개선된 엔진이 결국 제공해야 하는 구체적인 모듈입니다. 먼저 베타-6 내에서 구현될 수 있지만 입력/출력은 검사 가능한 상태로 유지되어야 다른 팀이 나중에 하나의 모듈을 교체할 수 있습니다.| 모듈 | 입력 | 출력 | 증명해야 합니다 |
|---|---|---|---|
| 수집 정규화 도구 | 원시 PDF/HWP/DOCX/PPTX/XLSX/오디오/비디오/이미지/데이터베이스 행 | 불변의 원시 자산 레지스트리, 표준 문서 ID, 추출된 리프 범위 | 원시 파일이 보존됩니다. 파서 출력이 원본을 대체하지 않습니다 |
| 리프 스플리터 | 표준 문서 및 미디어 트랙 | 텍스트/이미지/테이블/오디오 범위를 포함하는 정렬된 리프 노드 | 제목, 페이지 번호, 타임스탬프, 표 셀 또는 이미지 참조가 손실되지 않습니다 |
| 중복 제거 및 반복 원장 | 리프 노드, 해시, 임베딩, 메타데이터 | 정확한/근접/의미적 중복 클러스터와 반복 언급 횟수 | 반복 자체가 관련되지 않는 한 중복은 이중으로 계산되지 않습니다 |
| 참조 리졸버 | 리프 노드, 연대기, 화자 차례, 문서 그래프 | 해결된 상호 참조 및 해결되지 않은 상호 참조 | "저번/앞서/이것/그 자료/file 3" 바인딩은 명시적이고 테스트 가능합니다 |
| 시간적/출처 그래프 | 사실, 주장, 참고문헌, 개정 | 유효성 창 및 출처가 있는 그래프 가장자리 | 취소 및 대체는 덮어쓰지 않고 표시됩니다. |
| 계층적 메모리 트리 | 리프 노드 및 요약 | 루트/컬렉션/문서/섹션/리프 메모리 계층 구조 | 모든 요약에는 해당 아동과 해결되지 않은 격차가 나열되어 있음 |
| 다중 인덱스 검색 플래너 | 사용자 목표, 제품 프로필, 코퍼스 통계 | 키워드/벡터/BM25/그래프/테이블/이미지/오디오 검색 계획 | 모든 적용 범위 축에는 검색 전략이 있음 |
| 프론티어 수집가 | 검색 계획 및 색인 | 감사 대상 후보 경계 | 후보 수, 축별 적용 범위, 소스 종류 다양성 |
| 선택기/재순위 지정 | 감사 대상자 및 목표 축 | 선택된 증거 세트, 일반적으로 100개 레코드 | 전체 감사 대상 경계가 고려됩니다. 늦은 키워드 기아를 방지합니다 |
| 청구 카드 빌더 | 선택된 증거 및 원래 범위 | 견적, 맥락 요약, 청구 요약, 범위가 포함된 청구 카드 | 작성자는 인용할 수 있고 UI는 정확한 소스 창을 열 수 있습니다 |
| 커버리지 감사자/패처 | 목표 축, 선택된 증거, 청구 카드 | 누락/취약한 범위 보고 및 후속 검색 | 축 누락으로 인해 새로 검색된 내용이 아닌 다른 검색 또는 명시적인 공백 발생 |
| 답변 플래너 및 작가 핸드오프 | 청구 카드, 적용 범위 보고서, 사용자 언어 | 제한된 답변 계획 및 인용/후보 주장 분할 | 최종 텍스트는 요약이 아닌 원본 증거를 사용함 |
| 추천랭커 | 선택된 후보자 풀, 작업 기준, 사용자 제약 | 이유와 거부된 대안이 포함된 옵션 순위 | 의미론적 유사성뿐만 아니라 전문가 수준의 선택 |
| 벤치마크 하네스 | 숨겨진/회전 작업 및 아티팩트 | 도메인 전반에 걸쳐 비교 가능한 보고서 | 과적합 방지, 콜드 대기 시간, 충실도, 소스 창 증명 |

## 중복, 개수 및 ID 정책

엔진은 "중복 항목 제거"를 단일 부울로 처리하면 안 됩니다. 눈에 보이는 원장이 필요합니다.

- **정확한 중복:** 동일한 바이트 또는 동일한 정규화된 텍스트입니다. 하나의 표준 소스 ID를 유지하고 모든 파일 위치를 유지합니다.
- **거의 중복됨:** OCR/파서 차이가 있는 동일한 문서입니다. 검색을 위해 병합하고 검증을 위해 변형을 보존합니다.
- **의미적 중복:** 동일한 주장이 다르게 표현되었습니다. 작업이 반복되는 멘션 횟수에 관심이 없는 경우가 아니면 축소하지 않아야 합니다.
- **반복 언급:** 강의나 파일 전반에 걸쳐 동일한 사실이 반복됩니다. 시험/교수 스타일 과제의 경우 반복이 중요성을 높일 수 있으므로 계산해야 합니다.
- **인용 중복:** 다수의 2차 출처에서 인용된 동일한 인용 출처입니다. 인용 체인을 유지합니다. 모든 2차 출처가 독립적인 1차 증거인 척하지 않아야 합니다.

중복 항목을 다루는 출력에는 다음이 포함되어야 합니다.

```json
{
  "duplicateLedger": [],
  "canonicalSourceId": "...",
  "sourceLocations": [],
  "countPolicy": "dedupe_for_identity | count_repetition | preserve_citation_chain",
  "repetitionCount": 0
}
```

## 참조 해상도 및 시간 정책

엔진은 작업이 참조에 의존하는 경우 요약하거나 응답하기 전에 참조를 명시적으로 해결해야 합니다.

필수 참조 유형:

- 대명사 및 한국어 생략대상
- "앞서/위에서/저번/다음/내일/2주 전/파일3/슬라이드 오른쪽/이 그림/그 문제";
- 성적 증명서의 발표자 참고자료
- 문서 간 인용;
- 슬라이드, 유인물, 표 또는 보드 그림을 가리키는 오디오/비디오 타임스탬프
- 수정, 철회 및 변경된 시험 범위.

필수 출력:

```json
{
  "resolvedReferences": [
    {
      "surface": "저번 시간에 말한 회로",
      "resolvedTo": "doc:lecture-03-slide-12:image-1",
      "confidence": 0.87,
      "evidenceSpans": ["transcript:lecture-04:00:12:31", "slide:lecture-03:12"],
      "alternatives": [],
      "status": "resolved"
    }
  ],
  "unresolvedReferences": []
}
```

중요한 참조가 해결되지 않은 경우 엔진은 추측하는 대신 명확한 질문을 하거나 답변을 불완전한 것으로 표시해야 합니다.

## 필수 알고리즘 기능

미래 엔진은 입증된 경우 다음 아이디어를 결합해야 합니다.

### 손실 최소화 압축

- 청크를 인덱스 레이어로만 압축합니다.
- 지침, 명명된 엔터티, 동사, 부정, 수량, 날짜 및 소스 참조를 보존합니다.
- 압축된 내용, 생략된 내용, 불확실한 내용, 해결되지 않은 내용을 추적해야 합니다.
- 최종 인용에는 원문을 사용해야 합니다.

### 계층적 메모리 트리

트리 만들기:

```text
root corpus summary
  -> collection/domain summaries
    -> document summaries
      -> section/chunk summaries
        -> leaf original text/image/table/audio spans
```

각 상위 요약에는 아동 적용 범위, 해결되지 않은 참조, 시간 범위, 중복 정책 및 출처가 나열되어야 합니다.

### 그래프 메모리

청크와 문서 간의 관계 구축:

```text
translation_of
commentary_on
cites
applies
explains
same_topic
contrasts
localizes
supersedes
refers_to_previous
refers_to_next
audio_mentions_slide
image_depicts
table_supports
duplicate_of
near_duplicate_of
```

그래프 가장자리에는 신뢰도, 증거 및 소스 범위가 필요합니다. 시간이 유효한 사실에는 유효성 창이 필요합니다.

### 적용 범위 패치 루프

사용자 소유의 Hit-Thunder 아이디어를 포함하여 적용 범위 패치 원칙을 차용합니다.

1. 사용자 목표를 정의합니다.
2. 필요한 적용 범위 축을 열거합니다.
3. 각 축을 만족하는 청크/파일/증거를 표시합니다.
4. 누락된/약한 축을 감지합니다.
5. 해결되지 않은 부분을 다시 검색하거나 검사합니다.
6. 모든 축이 만족되거나 사용할 수 없다고 명시적으로 표시될 때까지 반복합니다.

루프는 만들어진 콘텐츠가 아닌 명확한 검색 간격으로 중지되어야 합니다.

### 중복 검증

`mini-artichokes` 스타일 수렴과 같은 중복성을 사용합니다.

- 결정이 큰 영향을 미치는 경우 다양한 프롬프트/모델/색인을 사용하여 독립적인 패스를 실행합니다.
- 시험 날짜, 역방향 범위, 인용된 범위 또는 권장 사항 상위 선택과 같은 중요한 구속력에 대한 동의가 필요합니다.
- 불일치를 숨기지 않고 격차로 표면화합니다.

사용자 소유 참조:

- Hit-Thunder 적용 범위 패치 아이디어: https://github.com/pineapplesour/Hit-Thunder
- 미니 아티초크 중복성/융합 아이디어: https://github.com/pineapplesour/mini-artichokes

## 사용자 요구 사항에서 정확한 벤치마크 작업

이는 벤치마크 제품군이 최종적으로 인코딩해야 하는 예입니다. 이 현에만 튜닝하지 않아야 합니다. 의역, 언어 변형 및 숨겨진 등가물을 생성합니다.| 면적 | 필수 어려운 작업 |
|---|---|
| 법률 | 카카오톡 관련 정확한 증거를 찾아봐야 합니다. 군사 핵심 벤치마크를 통과합니다. 스노보드 벤치마크를 통과해야 합니다. 정확한 인용문/컨텍스트 및 인용 소스 창을 보존합니다. |
| 학교/과정 | "문제만 다와"; "이 문제가 실제로 작동함"; "시험범위"; "시험 언제 보자"; "회로 사진 그대로"; "교수가 중요한 역할을 한다"; "교수가 어떤 문제는 후반일지 후반작업 다동작". |
| 종교 | 기존 엔진과 기본 모델이 놓친 이슬람교/힌두교/불교/기독교 어려운 질문을 만듭니다. 기독교는 가톨릭, 정교회, 성공회, 개신교 주요 교단을 분리해 경전/해설/전통 계층 구조 및 다국어 용어를 테스트합니다. |
| 한의학 | 처방 없이 고전 출처, 제제/약초 기록, 금기 사항, 안전 경계 및 현대 참고 자료를 분리합니다. |
| 심리 | 별도의 DSM/ICD/지침/연구/사례 자료; 위기/안전 경계를 보존합니다. 진단하지 않아야 합니다. |
| 추천 | 거의 누락된 거부 이유를 포함하여 전체 자료를 읽은 후 전문가가 선택한 항목을 일치시킵니다. |
| 부정적인 증거 | 주장된 날짜/범위/인용문/이미지가 자료에 없는 경우 부재를 증명합니다. |

### 철저한 소형 모델 패스

소규모 로컬 LLM, 파서, OCR/ASR 도구 및 스트리밍 프로세서는 대규모 모델 호출보다 저렴하다면 철저한 1차 통과 추출을 수행할 수 있습니다. 대규모 모델은 모든 것을 맹목적으로 다시 읽는 것이 아니라 해결되지 않은 고가치 결정에 토큰을 사용해야 합니다.

## 수집 요구 사항

메모리 엔진은 다음을 지원하거나 플러그 가능한 수집 기능을 갖추고 있어야 합니다.

| 데이터 유형 | 요구사항 | 사용자 연구를 통한 후보자 추천 |
|---|---|---|
| PDF | 읽기 순서, 표, 수식, 차트/이미지, 스캔 OCR, 머리글/바닥글 필터링 | OpenDataLoader PDF, Docling, Marker, RAGFlow 파서 |
| HWP/HWPX | 한국어 문서 텍스트, 표, 이미지/자산, 제목, 변형 파일 | kordoc, JDoc, unhwp, DocsRay |
| DOCX/PPTX/XLSX | 구조화된 텍스트, 슬라이드, 표, 발표자 노트 | Docling, OmniParse, 코르독 |
| 오디오/비디오 | ASR, 타임스탬프, 분할, VAD, 참조 문서에 대한 정렬 | WhisperX, pyannote.audio, OmniParse, DocsRay |
| 이미지/다이어그램 | OCR/레이아웃, 차트, 회로도, 시각적 소스 범위 | dots.ocr, CircuitVision, 데이터시트-cli |
| 중복 | 정확한 해시, 거의 중복, 의미 중복, 출처 병합 | Epstein 파이프라인 스타일의 3단계 중복 제거 |
| 상호 참조 | 한/영 대명사, 줄임표, 화자 참고문헌, "이것/저것" | KoreanCoreferenceResolution, KoBookNLP, fastcoref |

현재 완벽한 모든 형식의 추출을 입증하는 단일 공개 저장소는 없습니다. 엔진은 모듈식이어야 데이터 유형별로 더 나은 파서를 교체할 수 있습니다.

## 평가할 외부 아키텍처 아이디어

이는 자동 종속성이 아닌 연구 및 테스트에 대한 참조입니다.| 후보자 | 유용한 아이디어 | 주의 |
|---|---|---|
| RAG플로우 | 심층적인 문서 이해, 템플릿 청크, 추적 가능한 인용, 통합 리콜/재지정, KG/RAPTOR/PageIndex/검색 테스트 | 제품과 유사하지만 리소스/보안/버전 검토가 필요합니다. |
| KAG | 지식덩어리 상호인덱싱, 스키마제한 지식구성, 논리형식유도추론, 멀티인덱스 | 참조/시간/논리 문제에 매우 적합합니다. 저장소는 모든 부분에 대해 완전히 독립적이지 않을 수 있습니다. |
| 그라피티 | 시간 그래프, 원시 에피소드 출처, 증분 업데이트, 양방향 추적 | 시간/역전/출처에 유용합니다. 로컬/모델/보안 제약 조건을 검증합니다. |
| 라이트래그 | 경량 그래프 RAG 모드 및 순위 변경 경로 | 강력한 LLM/재순위 지정 및 신중한 인증/보안 검토가 필요합니다. |
| 돌이켜보면 | 융합 및 재지정을 통한 병렬 의미/BM25/그래프/시간 회상 | 누락 방지 패턴이 좋습니다. |
| Pathway llm-앱 | 파일/DB/클라우드 변경사항에 대한 실시간 동기화 검색 인프라 | 전체 추론 엔진보다 더 많은 인프라. |
| 위노라 | 기업 문서 Q&A, 상위-하위 청킹, 미리보기, 테넌트 격리 | 유용한 UI/제품 참조. |
| 의미론/코그니 | 출처/시간적/추론 프레임워크 아이디어 | 채택하기 전에 성숙도를 평가해야 합니다. |
| 마이크로소프트 그래프RAG | 커뮤니티 계층 구조, 글로벌/로컬/DRIFT 아이디어 | 기초/데모 유사; 드롭인 풀 제품이 아닙니다. |
| 히포RAG | 멀티홉/센스메이킹 메모리 코어 | 작동 부분이 남아 있을 수 있습니다. |

모든 후보자는 README 주장뿐만 아니라 이 프로젝트의 벤치마크 및 소스 창 계약을 통해 평가되어야 합니다.

## 벤치마크 요구 사항

엔진은 라이트 도메인 적응 기능을 갖춘 일반 엔진입니다. 독립된 도메인 전체에서 테스트되어야 합니다.

사용자 지침/메모리에서 현재 알려진 벤치마크 제품군:

| 도메인 | 벤치마크/작업 유형 | 요구사항 |
|---|---|---|
| 법적 | 카카오톡 증거, 밀리터리 핵심 벤치마크, 스노보드 벤치마크 | 벤치마크명에 과적합되지 않고 정확한 증거와 사례/자료를 찾아야 합니다. |
| 학교/교재 | "모든 문제 추출", "이 문제에 대한 정확한 설명 가져오기", "시험 범위", "시험 날짜", "중요한 진술", "교수 문제 스타일", "회로 이미지" | 성적 증명서, 슬라이드, 파일, 이미지, 연대순, 정확한 인용문을 지원해야 합니다. |
| 이슬람교 | 현재 엔진/모델이 누락되었는지 질문합니다. 학교/종파/출처 구별 | 파트와 바인딩을 피하고, 아랍어/소스 계층 구조를 보존하고, 관련된 경우 성경/주석/fiqh를 검색해야 합니다. |
| 힌두교 | 현재 시스템에서 놓치는 독립적인 어려운 질문 | 산스크리트어/음역/해설/전통 구별을 처리해야 합니다. |
| 한의학 | 약초/공식/고전/안전 금기사항 문의 | 처방해서는 안 됩니다. 고전, 의학, 공식, 안전, 현대적 참고자료를 구분해야 합니다. |
| 심리 | 임상/DSM/ICD/지침/연구/사례 구분 | 진단해서는 안 됩니다. 안전과 지침 증거를 우선시해야 합니다. |
| 추천 | 거대한 말뭉치에서 전문가 최고의 선택 | 가장 가까운 이웃 유사성뿐만 아니라 모든 데이터를 전문가가 읽는 것과 유사해야 합니다. |

벤치마크 규칙:

- 엔진이 고정된 쿼리를 기억할 수 없도록 테스트 세트를 숨기거나 회전시킵니다.
- 적대적인 변형, 의역, 다른 언어, 오타 및 오해의 소지가 있는 광범위한 용어를 포함합니다.
- 증거가 없는 부정적인 사례도 포함합니다.
- 회상도, 정확성, 출처, 인용 하이라이트, 답변 충실도, 시간/비용, UI 경로를 평가합니다.
- 한 도메인에 대해 홍보된 변형은 명시적인 사용자 승인 없이 다른 활성 제품을 회귀해서는 안 됩니다.

## 더 나은 엔진을 위한 프로모션 게이트새로운 엔진이나 주요 베타-6 변형은 모든 관련 관문을 통과한 경우에만 현재 기본값을 대체할 수 있습니다.

### 기계 계약 게이트

- `source-grounded-v2` 또는 문서화된 이전 버전과 호환되는 버전을 생성합니다.
- 선택한 소스 레이블과 소스 창 ID를 유지합니다.
- 정확한 견적 범위가 포함된 청구 카드를 생성합니다.
- 내구성 있는 아티팩트 및 캐시 메타데이터를 유지합니다.
- 비동기 작업 상태/진행/취소를 지원합니다.

### 증거 모양 게이트

최근 승인된 기준과 비교:

- 사용자가 새로운 핸드오프 횟수를 명시적으로 승인하지 않는 한 선택된 횟수는 100으로 유지됩니다.
- 후보자 프론티어 및 감사된 후보자 수가 기록됩니다.
- 근원종/전통/학파의 다양성은 기준선이 있었던 곳에서 보존됩니다.
- 선택된 중복은 동일한 쿼리/말뭉치가 사용될 때 선택된 임계값을 충족합니다.
- 새로운 증거는 단지 다르기만 한 것이 아니라 설명 가능하게 더 좋아야 합니다.

현재 선택기 비교 도구는 이미 다음 중 일부를 시행하고 있습니다.

```text
tools/compare_selector_probe_variants.py
  --require-same-selector-shape
  --require-baseline-kinds
  --require-variant-cold-selector
  --require-clean-selector
  --require-prompt-reduction
  --speed-floor <artifact>
```

### 콜드 엔진 레이턴시 게이트

속도 주장은 새로운 콜드 엔진 아티팩트를 사용해야 합니다.

- 키워드/검색/선택기/클레임/답변 계획/작성기 캐시 적중률은 0이거나 명시적으로 설명되어야 합니다.
- 누락된 타이밍 필드가 증명에 실패합니다.
- 총 대기 시간은 `max(engineTotalSec, wallElapsedSec)`로 확인되어야 합니다.
- 소스 선택 지연 시간은 별도로 측정해야 합니다.

현재 도구:

```text
tools/verify_app_path_gemma4.py --require-cold-engine-cache --max-total-sec ... --max-source-selection-sec ...
tools/verify_app_path_budget_matrix.py --require-cold-engine-cache --require-products islam,tcm,simli ...
tools/compare_app_path_variants.py --max-total-sec ... --max-source-selection-sec ...
```

### 전체 사용자 경로 게이트

하나 이상의 실제 제품 경로가 통과해야 합니다.

```text
landing input -> chat route -> visible progress -> final answer
-> citations -> source-window exact highlight -> local chat persistence
```

웹/PWA의 경우 브라우저 제출 확인기를 사용해야 합니다. 네이티브의 경우 Android/iOS 런타임/WebView 검증기를 사용해야 합니다. API만의 성공만으로는 사용자 경로의 성공에 충분하지 않습니다.

### 과적합 방지 게이트

- 변형 설계 중에 사용되지 않은 도메인을 하나 이상 실행해야 합니다.
- 숨겨진 하드 케이스나 새로 생성된 하드 케이스를 하나 이상 실행해야 합니다.
- 부정적인 사례를 포함합니다.
- 카운트뿐만 아니라 실제 답변 텍스트도 검사해 볼 것.

## 현재 알려진 엔진 상태

현재 강점:

- 이슬람/TCM/Simli에 대한 공유 Lawkey/Gemma4 베타-6 경로가 존재합니다.
- 비동기 내구성 작업, 진행, 취소, 로컬 채팅 지속성, 소스 창 UI 및 Android 에뮬레이터 WebView 증명이 존재합니다.
- top-k 100개의 선택된 소스 핸드오프가 존재합니다.
- 청구 카드, 답변 계획, 인용 지도, 구절 창, 인용/후보 청구 분할이 존재합니다.
- 프롬프트 크기 원격 측정 및 비교기 게이트는 이제 여러 가지 잘못된 속도 주장을 방지합니다.
- 10k 내구성 허용 및 1k LLM 비활성화 드레인이 입증되었습니다.

현재 차단제:

- 하드 쿼리의 경우 콜드 전체 응답 대기 시간은 여전히 몇 분입니다.
- 최신 증거에서 냉간 이슬람 소스 선택은 `<=30s`보다 훨씬 높습니다.
- 선택기 작업자 수 조정만으로는 대기 시간 분석기에 의해 배제됩니다.
- 전체 10k Gemma4 응답 처리량은 입증되지 않았습니다.
- 벤치마크 적용 범위가 너무 작습니다.
- 실제 저가형 Android 하드웨어와 iOS 증명이 누락되었습니다.
- 전체 다중 모드 수집 및 파일 간 참조 확인은 일반 엔진으로 구현되지 않습니다.

중요한 부정적 결과:

- TCM 최소 키워드 라운드를 낮추면 증거 구성이 대폭 변경되므로 기본값으로 설정해서는 안 됩니다.
- 선택기 발췌 크기를 축소하면 선택기 전용 속도를 통과할 수 있지만 전체 앱 경로에 실패하거나 증거 종류가 손실될 수 있습니다.
- 깨끗한 원시 + 역할 다양성이 중복/프롬프트/시간 초과 문제로 인해 이슬람 기본 승격에 실패했습니다.
- 선택기 증거 캡슐/원장 변형은 유용한 실험이었지만 기본 승격을 위한 증거 모양 게이트에 실패했습니다.
- 핫 캐시 앱 경로 아티팩트는 콜드 대기 시간 증거로 인용될 수 없습니다.

## 필수 다음 엔진 방향

다음 심각한 엔진 작업은 증거 품질을 보존하는 구조적 회상/지연 시간 개선에 초점을 맞춰야 합니다.1. 감사 대상 범위를 줄이지 않고 기본 프롬프트 비용을 줄이는 계층적 또는 2단계 선택기입니다.
2. 선택된 증거를 왜곡하지 않는 것으로 입증된 더 나은 소스 요약/원장.
3. 최종 검색 전에 문서 간 참조 및 시간 순서를 해결하는 그래프/트리 메모리.
4. 검사한 내용을 명시적으로 증명하는 Coverage 중심의 누락축 검색.
5. 다중 모드 수집 및 사본-문서 정렬.
6. 벡터 유사성뿐만 아니라 철저한/커버리지 증거를 사용하는 추천별 순위 지정.
7. 법률, 학교, 이슬람교, 힌두교, TCM 및 Simli 전반에 걸쳐 더 광범위한 벤치마크 활용.

## 향후 교체를 위한 독립형 엔진 인터페이스

모든 교체 엔진은 내부 코드가 다르더라도 이 개념적 인터페이스를 구현해야 합니다.

```json
{
  "request": {
    "schemaVersion": 1,
    "product": "islam",
    "query": "user goal/question",
    "language": "ko",
    "limit": 100,
    "corpus": {
      "dbPath": "/absolute/path/to/db.sqlite3",
      "dbShape": "precedents"
    },
    "runtime": {
      "runDir": "/absolute/path/runs/job-id",
      "cacheRoot": "/absolute/path/runs/_beta6_batch_cache",
      "llmProvider": "lawkey_gemini_generate_content",
      "model": "gemma-4-26b-a4b-it"
    },
    "policy": {
      "productSafetyNotice": "...",
      "answerMustUseOriginalEvidence": true,
      "noBindingFatwaOrDiagnosis": true
    }
  }
}
```

응답:

```json
{
  "engine": {"name":"new-engine","contractVersion":"source-grounded-v2"},
  "selector": {
    "status": "completed",
    "candidateCount": 1200,
    "auditedCandidateCount": 1200,
    "selectedCount": 100,
    "selectedIds": [],
    "cache": {},
    "timings": {}
  },
  "selectedEvidence": [],
  "claimCards": [],
  "candidateClaimCards": [],
  "citedClaimCards": [],
  "passageWindows": [],
  "answerPlan": {},
  "coverageReport": {},
  "answer": "Markdown answer",
  "writer": {},
  "artifacts": {}
}
```

엔진이 `answer`를 생성할 수 없는 경우 `answerReadiness = evidence_selected_writer_required`를 반환할 수 있지만 여전히 선택된 증거와 청구 카드를 생성해야 합니다.

## 개발 워크플로 요구 사항

엔진 동작을 변경하기 전에:

1. `memory/MEMORY.md`, `tasks/lessons.md` 및 이 문서를 읽어볼 것.
2. 광범위한 검색이나 대량 실행 전에 WSL 메모리를 확인해야 합니다.
3. 체크포인트를 생성합니다.
4. 주장된 동작에 대해 실패한 테스트 또는 검증자를 추가합니다.
5. 근본 원인을 해결하는 최소한의 구조적 변경을 수행합니다.
6. 집중 테스트를 실행해야 합니다.
7. Run a real artifact proof when behavior depends on LLM/provider/corpus.
8. 증거 형태 및 지연 시간을 기준선과 비교합니다.
9. 해당되는 경우 `tasks/todo.md`, 일일 메모리, 교훈/승리를 업데이트합니다.
10. 검증 결과가 입증될 때까지 완료를 주장하지 않아야 합니다.

## 최소 확인 명령

베타-6 코드 변경의 경우:

```bash
python3 -m py_compile shared_platform/beta6.py tests/test_beta6_runtime.py
pytest tests/test_beta6_runtime.py -q
```

앱 경로 증명 변경의 경우:

```bash
pytest tests/test_app_path_gemma4_verifier.py tests/test_app_path_budget_matrix.py tests/test_app_path_variant_comparator.py -q
```

선택기 변형 증명의 경우:

```bash
python3 tools/probe_beta6_selector.py ... --require-cold-selector --output runs/<variant>.json
python3 tools/compare_selector_probe_variants.py --baseline runs/<baseline>.json --variant runs/<variant>.json --require-same-selector-shape --require-baseline-kinds --require-variant-cold-selector --require-clean-selector --output runs/<compare>.json
```

전체 제품 경로:

```bash
python3 tools/verify_app_path_gemma4.py ... --require-cold-engine-cache --output runs/<artifact>.json
python3 tools/verify_browser_submit_path.py ... --output runs/<artifact>.json
```

최종 목표:

```bash
python3 tools/verify_completion_audit.py --json --output runs/completion_audit_current_<date>.json
```

## 읽을 메모리 및 참조

필수 저장소 참조:

```text
memory/MEMORY.md
memory/2026-05-06.md
memory/2026-05-07.md
memory/2026-05-08.md
memory/2026-05-09.md
tasks/requirements-audit.md
tasks/completion-audit-2026-05-08.md
tasks/lessons.md
tasks/wins.md
shared_platform/beta6.py
shared_platform/search.py
shared_platform/engine_contract.py
docs/religion-db-architecture.md
```

새로운 엔진을 설계할 때 평가하기 위한 사용자 제공 연구 참고 자료:

```text
RAGFlow, KAG, Graphiti, LightRAG, Pathway llm-app, WeKnora, Hindsight,
Semantica, Cognee, Microsoft GraphRAG, HippoRAG,
DocsRay, OmniParse, kordoc, JDoc, unhwp, OpenDataLoader PDF,
Docling, Marker, WhisperX, pyannote.audio, Epstein Pipeline,
KoreanCoreferenceResolution, KoBookNLP, fastcoref,
dots.ocr, CircuitVision, datasheet-cli,
Hit-Thunder coverage patch idea, mini-artichokes redundancy idea.
```

이러한 참조는 증거가 아닙니다. 로컬 테스트를 통해 이 프로젝트의 증거 품질, 대기 시간, 견고성 또는 수집 범위가 향상되는 것으로 나타난 후에만 유용해집니다.
