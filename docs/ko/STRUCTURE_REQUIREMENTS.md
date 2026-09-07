# 유니버설 아티초크 저장소 구조 요구 사항

최종 업데이트 날짜: 2026년 7월 24일(KST)

이는 저장소에 대한 최상위 협업 및 아키텍처 계약입니다. `docs/overall-structure-requirements.md`의 더 깊은 제품 요구 사항을 대체하지 않습니다. 서로 기다리지 않고 서로 다른 팀이 작업하는 방식을 수정합니다.

최종 제품 방향은 저장소 루트 `AGENTS.md`가 우선합니다. 아래의 DB,
source-grounded-v2, 제품 셸 계약은 현재 배포 호환 경계이며 모든 질문의 고정
추론 구조가 아닙니다.

## 목표

Universal Artichoke는 모든 종류의 문제를 빠르고 정확하게 푸는 하나의
범용 답변 엔진과 그 전달 표면을 포함하는 저장소입니다.

```text
question -> Codex -> optional generic tools -> checked answer
                                      -> frontend/web/native shell
```

현재 `DB/corpus -> source-grounded-v2 -> frontend`는 외부 근거가 필요한
질문을 위한 호환 제품 경로로 유지합니다. host-side 도메인·키워드 라우팅은
최종 기반에 넣지 않습니다.

기존 배포/API 검증기가 사용하는 현재 제품 호환 경로 표기는 다음과 같습니다.

```text
DB/corpus -> memory engine -> answer contract -> frontend/web/native shell
```

팀은 자신의 영역을 적극적으로 바꿀 수 있지만, 계층 간 계약을 깨서는 안 됩니다.

## 정식 문서

| 면적 | 정식 파일 |
|---|---|
| 전체 제품/API/네이티브/웹 구조 | `docs/overall-structure-requirements.md` |
| 런타임/언어/프레임워크 정책 | `docs/runtime-architecture-options.md` |
| 수업 언어 및 어조 정책 | `docs/instruction-language-policy.md` |
| 메모리/검색/추천 엔진 | `docs/memory-engine-requirements.md` 및 `engine/ENGINE_REQUIREMENTS.md` |
| 프런트엔드/디자인/런타임 안전 | `frontend/FRONTEND_REQUIREMENTS.md` 및 `frontend/contracts/kernel-boundary.md` |
| 프런트엔드-엔진 연결 | `frontend/contracts/engine-connection-guide.md` |
| DB 출판 및 코퍼스 호환성 | `db/DB_SHARING_GUIDE.md` |
| GitHub 거버넌스 및 병합 규칙 | `docs/repository-governance.md` |
| Diff 기반 대체 워크플로 | `docs/standalone-maintenance-workflow.md` |

기여자가 경계를 넘어 행동을 변경하는 경우 동일한 PR에서 관련 계약 파일을 업데이트해야 합니다.

## 소유권 경계

| 면적 | 소유자 팀 | 변경될 수 있습니다 | 팀 간 검토 없이 변경하면 안 됩니다 |
|---|---|---|---|
| `db/`, 코퍼스 매니페스트, DB 스냅샷 | DB/데이터팀 | 코퍼스 매니페스트, 문서 가져오기/내보내기, 스키마 호환성 어댑터 | 런타임 API 필드 이름, 소스 ID, 인용 범위 의미 |
| `engine/`, `shared_platform/beta6.py`, `shared_platform/search.py`, `shared_platform/engine_contract.py` | 엔진팀 | 검색, 순위, 청구 카드, 소스 창 생성, 대기 시간 전략 | `source-grounded-v2` 출력 형태, 작업 진행 계약, 제품 매니페스트 기능 의미 |
| `frontend/`, `web/`, `native/` | 프론트엔드/디자인팀 | 시각적 쉘, 레이아웃, 제품 스킨, 애니메이션, 경로 구성 | 공유 프론트엔드 기반, API 엔드포인트, 작업 토큰 의미, 상태 머신 불변, i18n 키 계약 |
| `apps/`, `shared_platform/server.py`, `ops/` | 플랫폼 리더/팀 리더 | 서버 런타임, 대기열, 인증 바인딩, 배포 스크립트 | 마이그레이션/버전 관리가 필요 없는 공개 API 계약 |
| `.github/`, CI, 분기 규칙 문서 | 팀장 | 병합 게이트, CODEOWNERS, PR 템플릿, 릴리스 정책 | 팀 통지 없이 규칙 우회/병합 ​​|

## 필수 레이어 계약

### DB -> 엔진

엔진은 선언된 제품 프로필을 통해 제품 코퍼스를 읽습니다.

```json
{
  "product": "islam",
  "dbPath": "/absolute/path/to/db.sqlite3",
  "dbShape": "precedents",
  "sourceIdField": "canonical_id",
  "textField": "full_text"
}
```

DB 계층은 다음을 유지해야 합니다.

- 안정적인 표준 소스 ID
- 전체 원본 텍스트
- 인용/제목/경로 메타데이터;
- `precedents` 또는 `documents` 검색 어댑터에 대한 충분한 스키마 호환성
- 호환성을 유지하면서 더 풍부한 테이블을 선택할 수 있습니다.

### 엔진 -> 프론트엔드

프런트엔드는 `source-grounded-v2` 공개 결과 필드만 사용합니다.

```text
answer / answerMarkdown
answerReadiness
selectedEvidence
claimCards
candidateClaimCards
citedClaimCards
passageWindows
answerPlan
coverageReport
citationMap
beta6
writer
selector
```

프런트엔드는 프롬프트, 로그, 로컬 실행 파일 또는 숨겨진 엔진 내부를 스크랩해서는 안 됩니다.

### 프론트엔드 -> API

모든 웹/네이티브 클라이언트는 동일한 공개 API를 사용합니다.

```text
POST /api/{product}/jobs
GET  /api/jobs/{jobId}
GET  /api/jobs/{jobId}/events
GET  /api/jobs/{jobId}/result
POST /api/jobs/{jobId}/cancel
GET  /api/{product}/source-window
```

모든 작업 읽기/취소에는 작업 액세스 토큰과 세션 토큰이 있어야 합니다.

### 제품 스킨 -> 공유 프런트엔드 기반

디자인은 선언적 슬롯과 속성을 통해 연결됩니다.

```text
제품 스킨 -> 공유 UI 커널 -> 공유 클라이언트/작업 런타임 -> 제품 API
```

제품 스킨은 화면 표현을 제어합니다. 공유 프런트엔드 기반은 엔진 연결, 작업 소유권, 채팅 지속성, 언어 상태, 오프라인 대기열 및 소스 창 매핑을 제어합니다.

## 저장소 레이아웃

활성 구현은 저장소 루트에 있습니다.

```text
README.md
.github/
STRUCTURE_REQUIREMENTS.md
docs/
engine/
  ENGINE_REQUIREMENTS.md
frontend/
  FRONTEND_REQUIREMENTS.md
  contracts/
db/
  DB_SHARING_GUIDE.md
shared_platform/
apps/
web/
native/
tools/
tests/
ops/
memory/
tasks/
```

활성 런타임, 계약, 테스트, DB 매니페스트 또는 저장소 수준 도구에 대한 대체 루트 디렉터리를 추가하지 않아야 합니다.

## 협업 규칙

경계 계약을 유지하는 기여자는 다른 팀을 기다릴 필요가 없습니다.

- 엔진 팀은 `source-grounded-v2`, 아티팩트, 소스 창 및 앱 경로 테스트를 통과하면 베타-6 내부를 교체할 수 있습니다.
- 프론트엔드 팀은 UI 런타임 계약, i18n 적용 범위, 작업 의미 및 소스 창 동작이 통과되면 모든 제품을 재설계할 수 있습니다.
- 호환성 보기/어댑터 및 안정적인 소스 ID가 남아 있는 경우 DB 팀은 말뭉치 테이블을 다시 작성할 수 있습니다.

## 필수 병합 게이트

`main`에 대한 모든 PR은 다음을 통과해야 합니다. 일반 작업은 `main`에 직접 푸시하지 않고 브랜치에서 완료한 뒤, 소유자 승인 후에만 병합합니다.

```bash
python3 tools/verify_repo_contracts.py
pytest tests/test_api.py tests/test_app_shell_parity.py tests/test_frontend_static.py -q
python3 tools/sync_native_shell_assets.py --check
```

엔진 PR은 `engine/ENGINE_REQUIREMENTS.md`에 나열된 관련 베타-6/앱 경로 게이트를 추가로 실행해야 합니다.

프런트엔드 PR은 `frontend/FRONTEND_REQUIREMENTS.md`에 나열된 프런트엔드 게이트를 추가로 실행해야 합니다.

DB/corpus PR은 `db/db-manifest.example.json` 또는 실제 매니페스트를 업데이트하고 `db/DB_SHARING_GUIDE.md`에 설명된 DB 검사를 실행해야 합니다.
