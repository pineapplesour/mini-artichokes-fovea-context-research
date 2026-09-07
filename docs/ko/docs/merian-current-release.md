# Merian 현재 최신본 기준

이 저장소의 공유 종교/TCM Merian 제품군 최신 기준은 `2026-07-01 KST`
`bunjum2/religion` 운영본을 승격한 상태이다.

## 현재 최신 버전

- Merian asset version: `20260701-mobile-send-icon-1`
- Service worker cache: `shared-platform-shell-reference-v55`
- 기반 디자인 단계: `20260630-design-progress-5`

## 적용 제품

동일 Merian 런타임과 공유 beta6 엔진 경로가 다음 제품군에 적용되어야 한다.

- Islam: `/islam`, `/islam-merian-chat.html`
- Buddhist: `/buddhist`, `/buddhist-merian-chat.html`
- Christian/Catholic: `/christian`, `/catholic`, `/catholic-merian-chat.html`
- Hindu: `/hindu`, `/hindu-merian-chat.html`
- TCM/Hanui: `/tcm`, `/tcm-merian-chat.html`

## 포함된 최신 수정

- 부팅 중 잔상 방지: `merian-booting` 클래스와 첫 페인트 shield를 JS 초기화 이후 해제한다.
- 채팅 입력창 위치: desktop composer bottom `104px`, mobile composer bottom `68px`.
- 입력창 정렬: textarea와 전송 버튼의 세로 중앙을 맞춘다.
- 최종 답변 전환: 완료 시 진행/progress entry를 최종 답변 entry로 교체한다.
- 모바일 전송 버튼: 단색 주황 타일이 아니라 경계선이 있는 icon button으로 보이게 한다.
- 공유 엔진: `shared_platform` beta6 job lifecycle, product routes, native shell manifest, frontend tests/tools를 같은 운영본 기준으로 맞춘다.

## 명시적 제외

Gemma gateway/API 단일 PowerShell 전달 파일은 이 git repo의 소스 산출물이 아니다.
그 파일은 외부 전달용으로 Google Drive에 올려야 하며, repo에는 gateway client token이나
단일 PS1 파일을 커밋하지 않는다.

## 최소 확인 명령

```bash
python3 tools/verify_repo_contracts.py
node --check web/merian-chat.js
node --check web/sw.js
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q \
  tests/test_islam_merian_preview.py \
  tests/test_frontend_static.py \
  tests/test_app_shell_parity.py \
  tests/test_merian_canonical_routes.py \
  tests/test_native_shell_parity.py \
  tests/test_product_profiles.py
python3 tools/verify_app_parity.py --json
```
