# Standalone Fallback Maintenance Workflow

Last updated: 2026-05-15 KST

This is the fallback workflow for contributors working from a minimal local environment. It is not the normal day-to-day development path. Normal work should still use branches, PRs, review, tests, and the full local development toolchain when available.

The point is portability: if someone only has a downloaded repository zip, Python, a browser, and a unified diff, they can still apply the change, checkpoint it, wire DB/API/engine/frontend, and open a server.

The portable runner lives at the repository root:

```text
standalone_run.py
run-standalone.sh
run-standalone.ps1
tools/standalone_apply_diff_and_run.py
```

The active platform code lives at the repository root. New work must target the root layout.

## One-Command Fallback

From the repository root:

```bash
python3 standalone_run.py --product islam
```

With a unified diff:

```bash
python3 standalone_run.py --product islam --diff change.patch
python3 standalone_run.py --product lawkey
```

With a full DB path:

```bash
python3 standalone_run.py --product simli --db /absolute/path/to/psych.sqlite
```

PowerShell:

```powershell
.\run-standalone.ps1 -Product islam
.\run-standalone.ps1 -Product lawkey
.\run-standalone.ps1 -Product simli -DbPath "C:\data\psych.sqlite" -Diff ".\change.patch"
```

The runner:

- applies an optional unified diff only after `git apply --check` or `patch --dry-run` succeeds;
- creates `standalone_checkpoints/<timestamp>-before-diff/` before applying the diff;
- sets the product DB environment variable, for example `RELIGION_ISLAM_DB_PATH`;
- uses real LLM keys when configured, otherwise sets deterministic writer-required mode;
- runs contract/static parity checks unless `--skip-verify` is passed;
- starts the selected product API/web server;
- smokes `/api/health`, landing page, chat page, and `/api/{product}/search`;
- opens the landing page unless `--no-open-browser` is passed.

This does not mean all development should be done by diff. It only guarantees the project is still editable and runnable when the full development toolchain is unavailable.

## Before Editing

1. Read `STRUCTURE_REQUIREMENTS.md`.
2. Read the relevant contract:
   - engine: `engine/ENGINE_REQUIREMENTS.md`;
   - frontend/design: `frontend/FRONTEND_REQUIREMENTS.md`;
   - DB/corpus: `db/DB_SHARING_GUIDE.md`.
3. Create a branch:

```bash
git checkout -b frontend/<name>/<task>
```

4. Run the contract smoke:

```bash
python3 tools/verify_repo_contracts.py
```

## Manual Diff Path

Ask the worker to provide a unified diff from the repository root, not loose snippets:

```text
Return one unified diff only. Do not omit file paths. Do not include unrelated refactors.
```

Save the diff as `change.patch`, then apply from the repository root:

```bash
git apply --check change.patch
git apply change.patch
```

If there is no Git available, use:

```bash
patch -p1 < change.patch
```

After applying, run the relevant verification section below.

The root runner automates this manual flow:

```bash
python3 ../standalone_run.py --diff ../change.patch --product islam
```

## Making A Change

Use patches or normal editor changes. Keep write scope inside your team area unless the PR says it changes a boundary.

Do not:

- edit generated heavy artifacts under `runs/` or `checkpoints/`;
- commit secrets;
- bypass the API/engine/frontend contracts;
- fix UI bugs by adding one-off inline event handlers in product pages.

## Minimal Verification

For docs-only:

```bash
python3 tools/verify_repo_contracts.py
```

For frontend:

```bash
python3 tools/verify_repo_contracts.py
pytest tests/test_frontend_static.py tests/test_app_shell_parity.py -q
python3 tools/sync_native_shell_assets.py --check
```

For engine:

```bash
python3 tools/verify_repo_contracts.py
python3 -m py_compile shared_platform/beta6.py shared_platform/search.py shared_platform/engine_contract.py
pytest tests/test_beta6_runtime.py -q
```

For API/platform:

```bash
python3 tools/verify_repo_contracts.py
pytest tests/test_api.py tests/test_product_profiles.py -q
```

## Running A Local Server

From the repository root, start a single product server:

```bash
RELIGION_LLM_DISABLED=1 python3 -m uvicorn apps.islam.server:app --host 127.0.0.1 --port 8061
RELIGION_LLM_DISABLED=1 python3 -m uvicorn apps.tcm.server:app --host 127.0.0.1 --port 8062
RELIGION_LLM_DISABLED=1 python3 -m uvicorn apps.simli.server:app --host 127.0.0.1 --port 8063
RELIGION_LAWKEY_DB_PATH=/absolute/path/to/precedents.sqlite3 python3 -m uvicorn apps.lawkey.server:app --host 127.0.0.1 --port 8037
```

Open:

```text
http://127.0.0.1:8061/islam-bayyinah.html
http://127.0.0.1:8062/tcm.html
http://127.0.0.1:8063/simli.html
http://127.0.0.1:8037/
```

Lawkey uses the original Expo/FastAPI app from `external/lawkey-original/`; do not create `web/lawkey.html` or a replacement shared shell for it.

For real engine behavior, remove `RELIGION_LLM_DISABLED=1` and provide the production model/key environment expected by the engine contract.

## Standalone Handoff Package

A contributor using the fallback workflow should be able to receive:

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

They should return:

```text
unified diff
verification commands run
server URL tested
known limits
rollback note
```

## PR Description

Every PR should state:

```text
What changed:
Contract touched:
Verification run:
Known limits:
Rollback:
```

## Rollback

If Git is available:

```bash
git status
git diff
git revert <merge_commit>
```

If Git is not available, copy changed files into `checkpoints/<timestamp>/` before editing and include a `CHECKPOINT.md` listing copied paths and commands.
