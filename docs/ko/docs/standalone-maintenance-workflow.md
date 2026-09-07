# 독립형 대체 유지 관리 워크플로

최종 업데이트 날짜: 2026년 5월 15일(KST)

이는 최소한의 로컬 환경에서 작업하는 기여자를 위한 대체 워크플로입니다. 이는 정상적인 일상적인 개발 경로가 아닙니다. 일반 작업에서는 가능한 경우 브랜치, PR, 검토, 테스트 및 전체 로컬 개발 도구 체인을 계속 사용해야 합니다.

요점은 이식성입니다. 다운로드한 저장소 zip, Python, 브라우저 및 통합 diff만 있는 경우에도 변경 사항을 적용하고 체크포인트를 지정하고 DB/API/엔진/프론트엔드를 연결하고 서버를 열 수 있습니다.

휴대용 실행기는 저장소 루트에 있습니다.

```text
standalone_run.py
run-standalone.sh
run-standalone.ps1
tools/standalone_apply_diff_and_run.py
```

활성 플랫폼 코드는 저장소 루트에 있습니다. 새로운 작업은 루트 레이아웃을 대상으로 해야 합니다.

## 단일 명령 대체

저장소 루트에서:

```bash
python3 standalone_run.py --product islam
```

통합 diff를 사용하는 기본 흐름은 다음과 같습니다.

```bash
python3 standalone_run.py --product islam --diff change.patch
python3 standalone_run.py --product lawkey
```

전체 DB 경로 사용:

```bash
python3 standalone_run.py --product simli --db /absolute/path/to/psych.sqlite
```

파워셸:

```powershell
.\run-standalone.ps1 -Product islam
.\run-standalone.ps1 -Product lawkey
.\run-standalone.ps1 -Product simli -DbPath "C:\data\psych.sqlite" -Diff ".\change.patch"
```

주자:

- `git apply --check` 또는 `patch --dry-run`가 성공한 후에만 선택적 통합 diff를 적용합니다.
- diff를 적용하기 전에 `standalone_checkpoints/<timestamp>-before-diff/`를 생성합니다.
- 제품 DB 환경 변수를 설정함(예: `RELIGION_ISLAM_DB_PATH`).
- 구성 시 실제 LLM 키를 사용하고, 그렇지 않으면 결정론적 작성자 필수 모드를 설정합니다.
- `--skip-verify`가 전달되지 않는 한 계약/정적 패리티 검사를 실행합니다.
- 선택한 제품 API/웹 서버를 시작합니다.
- `/api/health`, 랜딩 페이지, 채팅 페이지 및 `/api/{product}/search`를 흡연합니다.
- `--no-open-browser`가 전달되지 않으면 랜딩 페이지가 열립니다.

이는 모든 개발이 diff로 수행되어야 한다는 의미는 아닙니다. 이는 전체 개발 툴체인을 사용할 수 없을 때에도 프로젝트가 여전히 편집 가능하고 실행 가능하다는 것을 보장합니다.

## 편집하기 전에

1. `STRUCTURE_REQUIREMENTS.md`를 읽어볼 것.
2. 관련 계약서를 읽으해야 합니다.
   - 엔진: `engine/ENGINE_REQUIREMENTS.md`;
   - 프런트엔드/디자인: `frontend/FRONTEND_REQUIREMENTS.md`;
   - DB/코퍼스: `db/DB_SHARING_GUIDE.md`.
3. 브랜치를 생성함:

```bash
git checkout -b frontend/<name>/<task>
```

4. 계약 연기를 실행합니다.

```bash
python3 tools/verify_repo_contracts.py
```

## 수동 비교 경로

작업자에게 느슨한 조각이 아닌 저장소 루트의 통합 diff를 제공하도록 요청해야 합니다.

```text
Return one unified diff only. Do not omit file paths. Do not include unrelated refactors.
```

차이점을 `change.patch`로 저장한 다음 저장소 루트에서 적용합니다.

```bash
git apply --check change.patch
git apply change.patch
```

사용 가능한 Git이 없으면 다음을 사용해야 합니다.

```bash
patch -p1 < change.patch
```

신청 후, 아래 해당 인증 섹션을 실행해야 합니다.

루트 실행기는 이 수동 흐름을 자동화합니다.

```bash
python3 ../standalone_run.py --diff ../change.patch --product islam
```

## 변경하기

패치 또는 일반 편집기 변경 사항을 사용해야 합니다. PR에서 경계를 변경한다고 명시하지 않는 한 팀 영역 내부에 쓰기 범위를 유지해야 합니다.

하지 말아야 해야 합니다:

- `runs/` 또는 `checkpoints/`에서 생성된 무거운 아티팩트를 편집합니다.
- 비밀을 저지르다;
- API/엔진/프론트엔드 계약을 우회합니다.
- 제품 페이지에 일회성 인라인 이벤트 핸들러를 추가하여 UI 버그를 수정합니다.

## 최소한의 검증

문서 전용:

```bash
python3 tools/verify_repo_contracts.py
```

프런트엔드의 경우:

```bash
python3 tools/verify_repo_contracts.py
pytest tests/test_frontend_static.py tests/test_app_shell_parity.py -q
python3 tools/sync_native_shell_assets.py --check
```

엔진의 경우:

```bash
python3 tools/verify_repo_contracts.py
python3 -m py_compile shared_platform/beta6.py shared_platform/search.py shared_platform/engine_contract.py
pytest tests/test_beta6_runtime.py -q
```

API/플랫폼의 경우:

```bash
python3 tools/verify_repo_contracts.py
pytest tests/test_api.py tests/test_product_profiles.py -q
```

## 로컬 서버 실행

저장소 루트에서 단일 제품 서버를 시작합니다.

```bash
RELIGION_LLM_DISABLED=1 python3 -m uvicorn apps.islam.server:app --host 127.0.0.1 --port 8061
RELIGION_LLM_DISABLED=1 python3 -m uvicorn apps.tcm.server:app --host 127.0.0.1 --port 8062
RELIGION_LLM_DISABLED=1 python3 -m uvicorn apps.simli.server:app --host 127.0.0.1 --port 8063
RELIGION_LAWKEY_DB_PATH=/absolute/path/to/precedents.sqlite3 python3 -m uvicorn apps.lawkey.server:app --host 127.0.0.1 --port 8037
```

열기:

```text
http://127.0.0.1:8061/islam-bayyinah.html
http://127.0.0.1:8062/tcm.html
http://127.0.0.1:8063/simli.html
http://127.0.0.1:8037/
```

Lawkey는 `external/lawkey-original/`의 원래 Expo/FastAPI 앱을 사용합니다. `web/lawkey.html` 또는 이에 대한 대체 공유 쉘을 생성하지 않아야 합니다.

실제 엔진 동작을 위해서는 `RELIGION_LLM_DISABLED=1`를 제거하고 엔진 계약에서 예상하는 생산 모델/키 환경을 제공합니다.

## 독립형 핸드오프 패키지

대체 워크플로를 사용하는 기여자는 다음을 받을 수 있어야 합니다.

```text
STRUCTURE_REQUIREMENTS.md
engine/ENGINE_REQUIREMENTS.md
frontend/FRONTEND_REQUIREMENTS.md
frontend/contracts/
db/DB_SHARING_GUIDE.md
docs/standalone-maintenance-workflow.md
tools/verify_repo_contracts.py
the changed source files
```

그들은 다음을 반환해야 합니다:

```text
unified diff
verification commands run
server URL tested
known limits
rollback note
```

## 홍보설명

모든 PR에는 다음 사항이 명시되어야 합니다.

```text
What changed:
Contract touched:
Verification run:
Known limits:
Rollback:
```

## 롤백

Git을 사용할 수 있는 경우:

```bash
git status
git diff
git revert <merge_commit>
```

Git을 사용할 수 없는 경우 편집하기 전에 변경된 파일을 `checkpoints/<timestamp>/`에 복사하고 복사된 경로와 명령을 나열하는 `CHECKPOINT.md`를 포함합니다.
