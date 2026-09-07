# universal-artichoke beta-6 아키텍처 리뷰 및 "컨텍스트 검색" 설계 제안

---

## 1. 현재 상황 진단

### 1.1 숫자부터 정리

| 실행 | 결과 | 신뢰도 |
|---|---|---|
| Direct Gemma (검색 없음) | 26/50 = 52% | 확정 baseline |
| Product API | 22/50 = 44% | 확정, **baseline보다 나쁨** |
| Graph (스크린샷) | 30/50 | **미재현. 현재는 주장에 불과** |
| Graph (현재 rerun, 10문항) | 6/10 = 60% | n=10, 통계적 무의미 |

n=10에서 6/10은 52% baseline과 구별 불가능합니다(이항검정으로 p ≈ 0.4 이상). **현 시점에서 graph가 이긴다는 증거는 없습니다.** 30/50이 재현될 때까지 graph 우위를 전제한 의사결정을 하면 안 됩니다.

### 1.2 더 중요한 신호: Product < Direct

Product 22/50 < Direct 26/50이고 selector status가 대부분 `fallback_no_selection`이라는 것은:

- **검색이 노이즈를 주입해 모델을 더 나쁘게 만들고 있다**는 뜻입니다. selector가 아무것도 못 고르는데 그 과정에서 프롬프트가 오염되거나, fallback 경로가 direct보다 열등한 프롬프트를 만들고 있음.
- 이것은 graph 이전의 문제입니다. **"검색 결과가 없거나 나쁠 때 direct와 동등하게 동작한다"는 하한선(do-no-harm floor)이 깨져 있음.** graph q5/q9 회귀(direct 대비)도 같은 계열의 증상일 가능성이 높음.

### 1.3 무엇이 과적합/착시인가

beta-6-lawkey-graph-test1에 들어간 기능들을 일반성 기준으로 분류하면:

| 기능 | 일반 엔진 기여 | 벤치마크 형식 착취 |
|---|---|---|
| lawkey_graph / tcm_graph 확장 | ○ (방향은 맞음) | |
| domain_adapters | ○ | |
| TCM MCQ 파싱 | 중립 (I/O 계층) | |
| **option-term search** | | ● 객관식 선지 문자열이 코퍼스에 존재할 때만 작동 |
| **exact option lookup** | | ● 사실상 "선지 = 사전 표제어" 구조 착취 |
| **option-balanced source selection** | | ● MCQ 4~5지선다 구조 전제 |
| selector local recovery, writer fallback | ○ (견고성) | |

option 계열 3종은 leakage는 아니지만 **벤치마크 형식 과적합**입니다. 법률 벤치마크 A/B/C 같은 서술형 질의에는 아예 적용 불가이고, "graph가 이겼다"는 스크린샷의 이득이 실제로는 option lookup에서 왔을 가능성을 배제 못 합니다. → 5절 ablation에서 이걸 분리해야 함.

### 1.4 Graph가 옳은 방향인가

**방향은 옳지만 현재 구현은 아마 아닙니다.** 현재 graph 확장이 용어 동시출현/인접 청크 확장 수준이라면, 사용자가 지적한 핵심 문제 — "첫 케이스에 답이 없으면 그 케이스 안에서 확장해봐야 소용없다, 케이스 **간** 관계로 이동해야 한다" — 를 해결하지 못합니다. Yangyang(C) 벤치마크가 정확히 이걸 검증하는 케이스입니다: 익명화된 1심 판결문은 키워드로 도달 불가이고, 공개된 항소심/관련 사건에서 **관계 엣지를 타고** 넘어가야 합니다.

결론: graph 자체가 아니라 **엣지의 의미론**이 문제. 지금 필요한 것은 "이벤트 프레임 기반의 케이스 간 유형 엣지"입니다.

---

## 2. "컨텍스트 검색" 아키텍처: Event Frame Graph

### 2.1 단위(Units)

```
Corpus → Document(판결문/경전/교재) → Case(사건 단위, 법률에서만) 
       → Passage(청크, 512~1024토큰) → EventFrame(청크에서 추출된 사건 구조)
       → Entity(정규화된 행위자/객체)
```

핵심 신규 단위는 **EventFrame**: "누가(역할) 무엇에(객체) 어떤 방식으로(수단) 무엇을 했고(행위), 어떤 쟁점이 발생했고(issue), 법원/문헌의 판단은 무엇이었나(outcome)".

### 2.2 스키마 (SQLite/Postgres 기준)

```sql
CREATE TABLE event_frames (
  frame_id      TEXT PRIMARY KEY,
  doc_id        TEXT NOT NULL,
  chunk_id      TEXT NOT NULL,
  -- 정규화 필드 (택소노미 노드 ID)
  actor_class   TEXT,   -- 예: LEGAL/STATE_ACTOR/INVESTIGATIVE/POLICE
  action_class  TEXT,   -- 예: ACCESS/TECHNICAL_INTERVENTION/DEVICE_LOGIN
  object_class  TEXT,   -- 예: COMM/DEVICE/SIM, COMM/ACCOUNT/MESSENGER
  method_class  TEXT,   -- 예: PHYSICAL_SEIZURE, CREDENTIAL_REUSE, HACK
  patient_class TEXT,   -- 예: SUSPECT, THIRD_PARTY
  -- 원문 표층형 (감사/디버깅용)
  actor_surface TEXT, action_surface TEXT, object_surface TEXT,
  -- 판단 구조
  issue_tags    TEXT,   -- JSON array: ["WARRANT_SCOPE","ELECTRONIC_EVIDENCE"]
  outcome       TEXT,   -- LAWFUL | UNLAWFUL | CONDITIONAL | NONE
  outcome_condition TEXT, -- CONDITIONAL일 때 조건 요약
  holding_quote TEXT,   -- 판시/근거 원문 인용 (writer가 그대로 써야 함)
  confidence    REAL,
  extractor_ver TEXT
);

CREATE TABLE frame_edges (
  src_frame_id TEXT, dst_frame_id TEXT,
  edge_type    TEXT,  -- 아래 2.4 참조
  weight       REAL,
  evidence     TEXT,  -- 엣지 생성 근거 (인용문구, 유사도 점수 등)
  PRIMARY KEY (src_frame_id, dst_frame_id, edge_type)
);

CREATE TABLE case_edges (        -- 케이스(문서) 레벨 엣지
  src_doc_id TEXT, dst_doc_id TEXT,
  edge_type  TEXT,  -- CITES | APPEAL_OF | OVERRULED_BY | SAME_STATUTE | SHARED_ENTITY
  weight REAL, evidence TEXT,
  PRIMARY KEY (src_doc_id, dst_doc_id, edge_type)
);

CREATE TABLE taxonomy (
  node_id TEXT PRIMARY KEY,     -- "LEGAL/STATE_ACTOR/INVESTIGATIVE/POLICE"
  parent_id TEXT, domain TEXT, aliases TEXT  -- JSON: ["경찰","사법경찰관",...]
);
```

인덱스 4종:
1. **FTS** (기존 유지)
2. **Dense chunk index** (기존/신규, 청크 임베딩)
3. **Frame structured index**: `(actor_class, action_class, object_class, issue_tag)` 튜플에 대한 inverted index. 택소노미 조상 노드로 일반화한 튜플도 함께 색인 (예: POLICE → INVESTIGATIVE → STATE_ACTOR 각 레벨).
4. **Frame embedding index**: 프레임을 템플릿 직렬화한 텍스트의 벡터 (3절 참조).

### 2.3 오프라인 프레임 추출

- 비싼 모델(예: 대형 LLM) 배치로 청크당 0~N개 프레임 추출. JSON schema 강제, 택소노미 노드 ID로만 분류 허용, 매핑 실패 시 surface만 남기고 `class=NULL`.
- 택소노미는 도메인 어댑터가 소유. **법률 도메인부터 시작** (행위자 ~30노드, 행위 ~50, 객체 ~60, 쟁점 ~40이면 벤치마크 A/B/C 커버 가능). TCM/종교는 나중에 이식(진단→처방→약재 구조 등).
- `holding_quote`는 반드시 원문 span offset과 함께 저장 → 환각 인용 차단.

### 2.4 엣지 타입과 생성 규칙

| edge_type | 생성 방법 | 결정적? |
|---|---|---|
| `CITES` | 판례번호 정규식 파싱 (사건번호 패턴 확정적) | ✅ |
| `APPEAL_OF` / `OVERRULED_BY` | 사건번호 + 심급 메타데이터 | ✅ |
| `SAME_STATUTE` | 인용 조문 파싱 (형사소송법 §106 등) | ✅ |
| `SHARED_ENTITY` | 익명화 인지 entity resolution: 날짜/금액/직위/지명 조합 매칭 (Yangyang bridge가 이것) | 규칙+임계값 |
| `ANALOGOUS_FRAME` | 프레임 구조 유사도 ≥ τ (3절) — **케이스 간에만** 생성 | 점수 기반 |
| `SAME_ISSUE` | issue_tags 교집합 ≥ 1 | ✅ |

**Yangyang용 SHARED_ENTITY 규칙 예시**: 두 문서에서 (사건 발생 연도, 뇌물 액수, 직위 클래스=지자체장, 죄명=뇌물수수) 4-튜플이 일치하면 weight 0.9 엣지. "양양군수" 문자열이 필요 없음.

### 2.5 런타임 순회 알고리즘

```
def context_retrieve(query, budget=40, hops=2, beam=8):
    # 1. 쿼리 프레임 추출 (소형 LLM 1콜, 실패 시 프레임 없이 진행)
    q_frames = extract_query_frames(query)      # 보통 1~2개

    # 2. Seed: 하이브리드 (FTS ∪ dense) top-20 + frame structured index 매치
    seeds = hybrid_seed(query) ∪ frame_index_match(q_frames, level="exact")

    # 3. 프레임 매치 실패 시 택소노미 일반화 사다리
    #    exact tuple → actor 1단계 상향 → action 상향 → issue-only
    #    각 단계 결과 수가 min_k 미만일 때만 다음 단계로 (과잉 일반화 방지)

    # 4. Beam search over frame_edges + case_edges:
    frontier = seeds
    for h in range(hops):
        candidates = expand(frontier, edge_types=[CITES, APPEAL_OF,
                            SHARED_ENTITY, ANALOGOUS_FRAME, SAME_ISSUE])
        # 케이스 내부 인접 청크 확장은 답 프레임이 있는 청크 주변 ±1로 제한
        score(c) = α·frame_sim(q_frames, c.frame)
                 + β·edge_weight_path(c)
                 + γ·text_relevance(query, c.chunk)
                 - δ·generalization_penalty(c)   # 일반화 단계당 감점
        frontier = top(candidates, beam)
    return top(all_visited, budget)  # 청크 + 프레임 + 경로 증거 반환
```

핵심 설계 결정:
- **케이스 간 이동은 반드시 유형 엣지를 통해서만** — "같은 케이스 내 확장"과 "케이스 간 도약"의 예산을 분리 (예: 30/70). 사용자 지적("첫 케이스에 답이 없으면") 직접 대응.
- 반환값에 **경로 증거**(어떤 엣지를 왜 탔는지)를 포함 → selector와 claim card가 사용, ablation과 디버깅에 필수.

---

## 3. "임베딩의 임베딩 / 관계 유사도"의 실용적 구현

사용자 직관의 본질: "police removed SIM ≈ prosecutors hacked password"는 표층 임베딩 유사도가 아니라 **(행위자 역할, 행위 유형, 객체 유형, 법적 쟁점) 구조의 유사도**. 세 가지 구현안:

### 안 A — 고전적/구조적: 택소노미 격자 유사도 (추천 1순위)

```
frame_sim(f, g) = Σ_slot w_slot · tax_sim(f.slot, g.slot)
tax_sim(a, b) = 2·depth(LCA(a,b)) / (depth(a)+depth(b))   # Wu-Palmer
w = {actor: 0.2, action: 0.25, object: 0.2, issue: 0.35}
```

- POLICE와 PROSECUTOR는 LCA=INVESTIGATIVE이므로 tax_sim ≈ 0.86 → "경찰 SIM 압수"와 "검찰 계정 접근"이 issue가 같으면 높은 점수.
- 완전 결정적, 디버깅 가능, 점수 분해 가능. MAC/FAC 계열 유추 검색의 실용 축소판.
- 한계: 택소노미 미커버 개념은 0점. 커버리지가 병목.

### 안 B — 신경망: Frame2Vec + 인용 그래프 약지도

1. **베이스라인 (학습 없음)**: 프레임을 템플릿 문장으로 직렬화 후 instruction 임베더로 임베딩:
   `"An investigative agency (police) performed technical access (SIM extraction and re-insertion) on a suspect's communication device, raising issues of warrant scope and electronic evidence admissibility. Outcome: unlawful."` → 이 문장의 임베딩이 곧 "관계의 임베딩". 표층이 아니라 정규화된 구조를 임베딩하므로 사용자의 "embedding of embeddings" 직관과 동형.
2. **학습 (2주 이후)**: 서로 인용하는 케이스 쌍의 프레임을 positive, 무관 케이스를 negative로 하는 contrastive projection head (임베딩 위 2층 MLP, 수 시간 학습). **인용 그래프가 무료 레이블** — "법원이 유사하다고 판단한 관계"를 직접 학습.

풀 pairwise chunk-relation 임베딩(청크쌍 concat/diff 임베딩)은 O(n²)라 **비추천** — 프레임이 그 압축입니다.

### 하이브리드 권고 (구현 대상)

```
1단계 (hard filter, 결정적): issue_tags 교집합 ≥1 AND actor가 동일 상위 클래스
2단계 (rerank): 0.5·안A + 0.5·안B(무학습 버전) 
3단계 (임계값): frame_sim < τ=0.55 이면 ANALOGOUS_FRAME 엣지 미생성
```

hard filter가 "신장(腎) vs 열쇠(key)" 같은 동형이의어 실패(벤치마크 B)를 구조적으로 차단합니다 — 임베딩이 아무리 비슷해도 issue class가 다르면 탈락.

---

## 4. 기존 파이프라인 통합

```
[기존]  FTS → adapters → graph expansion → selector → claim cards → plan → writer
[제안]  hybrid seed(FTS∪dense∪frame-index) → adapters(택소노미 제공)
        → frame-graph traversal(2.5) → selector → frame-claim cards
        → deterministic answer plan → writer
```

| 단계 | 결정적 / LLM | 변경점 |
|---|---|---|
| Query frame 추출 | 소형 LLM 1콜 (+실패 시 스킵) | 신규. 캐시 필수 |
| Seed + traversal | **완전 결정적** | 점수식·엣지·예산 전부 로그 |
| Selector | LLM, 단 입력을 결정적 pre-filter로 top-15 캡 + 프레임 메타데이터(issue/outcome/경로) 첨부 | `fallback_no_selection` 시 **결정적 top-5 사용, direct 모드로 절대 프롬프트 오염 금지** — 1.2 문제 수정 |
| Claim cards | 오프라인 프레임에서 결정적 생성 (frame → card 매핑: claim = holding_quote, stance = outcome, provenance = span) | LLM 런타임 추출 제거 방향 |
| Answer plan | **결정적 규칙**: (a) 쿼리 issue와 일치하는 카드 ≥1 필수, (b) outcome 상충 시 심급/최신성/OVERRULED_BY로 우선순위, 상충 자체를 plan에 명시, (c) 조건 미충족 시 "근거 불충분" 플랜 | 신규 규칙 3개 |
| Writer | LLM + 기존 결정적 fallback 유지. **인용은 holding_quote 원문만 허용** | 환각 인용 차단 |
| MCQ 경로 | option lookup류는 **별도 플래그 뒤로 격리** (`--enable-mcq-heuristics`) | ablation 분리용 |

---

## 5. Ablation 매트릭스와 벤치마크 프로토콜

### 5.1 매트릭스

| 축 | 값 |
|---|---|
| Seed | FTS only / dense only / hybrid |
| Expansion | none / 기존 naive graph / frame graph |
| MCQ heuristics (option lookup 등) | on / off |
| Selector | LLM / 결정적 top-k |
| Writer | LLM / 결정적 fallback |
| + Direct baseline | (전부 off) |

전조합 대신: baseline → +hybrid → +frame graph → ±MCQ heuristics → ±selector → ±writer의 **누적 사다리 + one-off ablation**. 각 셀 3회 반복 (temperature>0이면), TCM은 50문항 전체, **McNemar 검정으로 direct 대비 유의성** 보고.

### 5.2 성공 기준

**법률 A (SIM/카톡)** — 패러프레이즈 10개(행위자·수단·메신저·어순 변형) 자동 생성 후:
- Retrieval: 3개 목표 판례 중 ≥2개가 top-10 진입, 10개 변형 중 ≥8개에서 성공
- Answer: 2024구합65355 인용 + 위법/적법 판단 방향 정답 + holding 인용이 원문 span과 일치 + **존재하지 않는 판례 인용 0건**

**법률 B (군 열쇠)**:
- 2023구합75301 또는 동등 판례 인용, "분리/이중 관리" 논지 포함
- 최종 인용 목록에 신장(腎) 관련 문서 0건 (retrieval 후보에는 있어도 됨 — hard filter 검증)

**법률 C (양양)**:
- 익명화 1심 문서가 **SHARED_ENTITY 또는 APPEAL_OF 엣지 경로**로 도달 (경로 로그로 검증), 나이 정답
- 키워드-only ablation에서는 실패해야 정상 (bridge 검증)

**시험 벤치마크 (TCM/기독교/이슬람/불교/심리)**:
- full engine ≥ direct + 5pt (p<0.05, McNemar)
- **MCQ heuristics off에서도 이득의 ≥50% 유지** — 미달 시 "형식 착취"로 판정
- 5개 도메인 중 ≥4개에서 direct 이상 (일반성 조건)

### 5.3 누출/과적합 탐지

1. 시험 유래 문서를 제거한 코퍼스로 재색인 후 재실행 (점수 유지되면 코퍼스 오염 없음)
2. 카나리아: 정답을 의도적으로 뒤바꾼 가짜 문항 5개 — 엔진이 뒤바뀐 "정답"을 내면 파싱/키 누출
3. 런타임 프로세스에서 `answer_key`, `tcm81` 문자열 grep + 파일 open 트레이스 (기존 감사의 자동화)
4. 패러프레이즈 강건성: 원문 대비 변형 질의 정답률 낙폭 >15pt이면 키워드 과적합 경보

---

## 6. 2주 구현 계획

**Week 1 — 구조 계층 + 결정적 순회**

| Day | 산출물 |
|---|---|
| 1 | `taxonomy.py` + 법률 택소노미 YAML v0 (행위자/행위/객체/쟁점, 벤치 A/B/C 커버 우선). 테스트: alias 매핑, LCA/Wu-Palmer |
| 2 | `event_frames`/`frame_edges`/`case_edges` 마이그레이션 + `frame_extractor.py` (배치 LLM, JSON schema, span 검증). 골든 픽스처: A/B/C 관련 판결문 각 1건 수동 정답 프레임 |
| 3 | 결정적 엣지 빌더: `build_cites_edges()` (사건번호 정규식), `build_appeal_edges()`, `build_shared_entity_edges()` (양양 4-튜플 규칙). 테스트: 양양 익명화 픽스처 bridge 성립 |
| 4 | `frame_sim()` (안A) + frame structured index + `ANALOGOUS_FRAME` 엣지 빌더 (hard filter + τ). 테스트: 경찰-SIM ↔ 검찰-계정 유사도 ≥ τ, 열쇠 ↔ 신장 < filter |
| 5 | `context_retrieve()` 순회 (2.5) + 경로 로깅. 통합: 기존 graph expansion을 플래그로 교체 가능하게 |

**Week 2 — 통합 + 평가**

| Day | 산출물 |
|---|---|
| 6 | `extract_query_frames()` (소형 LLM + 캐시), 실패 시 graceful skip. selector 입력에 프레임 메타 첨부 |
| 7 | selector fallback 수정 (1.2/4절): `fallback_no_selection` → 결정적 top-5, direct 프롬프트 무오염 보장. 회귀 테스트: 빈 검색 결과 시 direct와 출력 동일 |
| 8 | frame → claim card 결정적 매핑 + answer plan 규칙 3종 (issue 일치 필수 / outcome 상충 처리 / 불충분 선언) |
| 9 | ablation harness: 매트릭스 실행기 + McNemar + 경로 로그 리포트. MCQ heuristics 플래그 격리 |
| 10 | 법률 A/B/C 실행 + 패러프레이즈 10종. 실패 케이스 분석 |
| 11 | TCM 50 전체 ×3회: direct / product / frame-graph / frame-graph−MCQ-heuristics. **스크린샷 30/50 재현 시도 포함** |
| 12 | 안B 무학습 버전 (frame 직렬화 임베딩) rerank 추가, on/off 비교 |
| 13–14 | 누출 감사 자동화(5.3), 결과 리포트, 다음 스프린트 결정 |

---

## 7. 리스크 / 실패 모드

1. **결과 극성 반전 (최대 위험)**: "경찰이 SIM을 뽑아 로그인 → **위법**" 판례를 유추 검색이 가져왔는데 writer가 적법 근거로 인용. → `outcome` 필드 필수화 + answer plan에서 극성 검증 + holding 원문 인용 강제.
2. **폐기/파기된 판례 인용**: 유사도는 높지만 상급심에서 뒤집힌 케이스. → `OVERRULED_BY`/`APPEAL_OF` 엣지로 우선순위 강등, 상충 시 plan에 명시.
3. **과잉 일반화 드리프트**: 택소노미 사다리를 너무 올라가면 모든 프레임이 매치. → 단계당 감점(δ) + 단계별 최소결과수 조건에서만 상향.
4. **프레임 추출 오류의 복리 효과**: 추출이 틀리면 엣지·카드·플랜이 연쇄 오염. → confidence 필드, 저신뢰 프레임은 엣지 생성 제외, 골든 픽스처 회귀 테스트.
5. **관할/법령 불일치 유추**: 구조는 같지만 다른 법령 체계의 케이스 (행정 vs 형사). → `SAME_STATUTE` 엣지 가중 + issue tag에 법령 계열 포함.
6. **비용/지연**: 오프라인 추출은 배치라 무관, 런타임 추가는 쿼리 프레임 LLM 1콜뿐. 순회는 결정적 — 예산 상수로 상한.
7. **택소노미가 새 병목**: 커버리지 부족 도메인에서 frame 경로가 침묵. → frame 매치 0건 시 하이브리드 seed로 자동 강등 (never worse than baseline 설계).

---

## 8. 결론: 먼저 만들 것 / 아직 만들지 말 것

**즉시 (이 순서대로):**
1. **Selector fallback 수정** — product가 direct보다 나쁜 것은 무엇을 만들든 먼저 고쳐야 할 버그
2. **Ablation harness + MCQ heuristics 격리** — graph 30/50 재현과 이득 출처 규명이 모든 판단의