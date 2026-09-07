# 전체 벤치마크 및 실행 결과 공개 패키지

생성 기준일: 2026-07-17

> 이 디렉터리는 정답키와 문제 전문을 포함한다. 현재 GitHub 저장소가 PRIVATE인 것을 전제로 하며, 공개 전환 전에는 별도의 저작권·개인정보 검토가 필요하다.

## 용어 교정

`Wikia 내장 AI`라는 기능이나 실행 주체는 없다. Wikia는 공유 저장소일 뿐이다. 이 패키지는 기존 파일의 답을 `source-provided historical run`으로 표기하며, TCM만 게시글에서 beta6 실행임이 확인된다.

## 파일 구성

- `catalog.json`: 전체 벤치마크와 문항 수
- `protocols.json`: 모델, 인터넷·코드 허용, DB 검색, batching, 구조
- `runs.json`: 공식·과거·진단·무효 실행의 점수와 상태
- `cases/*.jsonl`: 모든 문제·정답과 실행별 예측·원응답·정오·검색 trace·artifact 해시
- `wrong_answers/*.md`: 실행별로 틀린 문제와 정답, 실제 답변 전문
- `all_case_results.csv`: 전체 실행 레코드의 스프레드시트용 평면 테이블
- `SHA256SUMS`: 생성 파일 무결성

## 벤치마크 목록

| ID | 문항/variant | 실행된 문항 | 실행 레코드 |
|---|---:|---:|---:|
| `buddhist290` | 290 | 0 | 0 |
| `christian192` | 192 | 0 | 0 |
| `islam104` | 104 | 104 | 482 |
| `leet70` | 70 | 70 | 70 |
| `legal10` | 10 | 10 | 40 |
| `psychology487` | 487 | 0 | 0 |
| `tcm92` | 92 | 92 | 713 |

객관식·단답형 고유 시험은 총 1,235문항이며, 법률 E2E 10 variants는 별도다.

## 공식 실행 결과

| Run | 상태 | 프로토콜 | 점수 |
|---|---|---|---:|
| `legal.direct.luna` | `completed` | `luna.direct.closed_book.per_case` | 0/10 |
| `legal.frozen_beta6.luna` | `completed` | `luna.frozen_beta6.db.per_case` | 0/10 |
| `legal.universal.luna` | `completed` | `luna.universal.db.per_case` | 10/10 |
| `legal.solpro.closed_book` | `completed` | `solpro.direct.closed_book.legal10.batch` | 0/10 |
| `tcm92.direct.luna` | `completed` | `luna.direct.closed_book.per_case` | 68/92 |
| `tcm92.frozen_beta6.luna.corrected` | `completed` | `luna.frozen_beta6.db.per_case` | 69/92 |
| `tcm92.universal.luna.real_db` | `completed` | `luna.universal.db.per_case` | 71/92 |
| `tcm92.solpro.closed_book` | `completed` | `solpro.direct.closed_book.tcm92.batch` | 81/92 |
| `islam104.direct.luna` | `completed` | `luna.direct.closed_book.per_case` | 83/104 |
| `islam104.frozen_beta6.luna` | `completed` | `luna.frozen_beta6.db.per_case` | 78/104 |
| `islam104.universal.luna` | `completed` | `luna.universal.db.per_case` | 78/104 |

## 공유 파일의 선행 결과

| Run | 확인된 구조 | 점수 |
|---|---|---:|
| `source.tcm.beta6.43of64` | The Wikia post explicitly identifies the run as beta6; exact model and tool policy are absent. | 43/64 |
| `source.islam.answers.78of104` | Answers were recorded in source files. Eight abstentions refer to supplied religious texts, but the exact engine receipt is absent. | 78/104 |
| `source.leet.lawkey_ai.34of70` | The post title says LawKey AI; analysis mode, model, retrieval, web, and code settings were not recorded. | 34/70 |

## 진단·중단·무효 실행

이 결과는 공식 점수와 합치지 않는다.

| Run | 상태 | 관측 |
|---|---|---:|
| `tcm16.direct.luna.smoke` | `diagnostic` | 14/16 |
| `tcm16.frozen_beta6.luna.smoke` | `diagnostic` | 14/16 |
| `tcm16.universal.luna.smoke` | `diagnostic` | 15/16 |
| `tcm92.universal.luna.v45` | `superseded` | 68/92 |
| `tcm22.evidence_arbiter` | `rejected` | 8/22 |
| `tcm92.frozen_beta6.provider_fallback_contaminated` | `invalid_provider_fallback` | 35/92 |
| `tcm27.frozen_beta6.fixture_db_mixed` | `invalid_database_binding` | 24/27 |
| `islam.web_optional.partial29` | `stopped_at_case_boundary` | 21/29 |
| `islam.web_optional.wrong21` | `gold_informed_retry` | 5/21 |
| `islam.web_required.wrong16` | `gold_informed_second_retry` | 7/16 |

## 핵심 실행 조건

- 정식 Luna 3-arm은 `gpt-5.6-luna`, low reasoning/verbosity, 문항별 독립 호출, 최대 2회 전송, worker 1이다.
- Direct는 질문만 사용하며 인터넷·코드·파일·DB가 모두 금지된다.
- frozen beta6와 Universal은 엔진 코드가 로컬 SQLite를 검색하지만 Luna 자체의 인터넷·코드 도구 호출은 금지된다.
- 이슬람 web retry만 일반 인터넷 검색과 파일 I/O 없는 계산용 read-only shell을 허용했다. 실제 command 실행은 0회였다.
- Sol Pro는 `gpt-5-6-pro`, closed-book/no-web/no-tools이며 법률10과 TCM92를 각각 한 대화의 batch로 실행했다.
- 법률 정오는 Luna low semantic judge가 artifact당 독립 2회 판정했다.

세부 조건과 예외는 반드시 `protocols.json` 및 `runs.json`을 함께 본다.

## 관련 하네스 참고 자료

- [Ralphthon @ ICML 2026 리뷰 에이전트·연구 하네스 확정 로컬 코드 아카이브](references/ralphthon-review-agents.md): Ralph Reviewer를 포함한 Track 1·2 소스, 감사 보고서, 복원 가능한 Git bundle의 출처·해시·실행 구조를 정리했다. 이 자료는 벤치마크 점수에 합산되는 실행 결과가 아니라 이후 리뷰/연구 에이전트 구조를 설계할 때 참고하는 별도 코드 원장이다.
