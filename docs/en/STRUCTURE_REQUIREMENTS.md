# Universal Artichoke Repository Structure Requirements

Last updated: 2026-07-24 KST

This is the top-level collaboration and architecture contract for the repository. It does not replace the deeper product requirements in `docs/overall-structure-requirements.md`; it fixes how different teams work without waiting for each other.

The repository-root `AGENTS.md` controls the final product direction. The DB,
`source-grounded-v2`, and product-shell contracts below are current deployment
compatibility boundaries, not a mandatory reasoning topology for every query.

## Goal

Universal Artichoke contains one general answer engine for solving every class
of problem quickly and accurately, plus its delivery surfaces:

```text
question -> Codex -> optional generic tools -> checked answer
                                      -> frontend/web/native shell
```

The current `DB/corpus -> source-grounded-v2 -> frontend` path remains a
compatible product route for questions that require external evidence. Do not
make host-side domain or keyword routing the foundation.

The current product compatibility path retained for deployment/API verification
is:

```text
DB/corpus -> memory engine -> answer contract -> frontend/web/native shell
```

The teams may change their own side aggressively, but they must not break the contracts between the layers.

## Canonical Documents

| Area | Canonical file |
|---|---|
| Whole product/API/native/web structure | `docs/overall-structure-requirements.md` |
| Runtime/language/framework policy | `docs/runtime-architecture-options.md` |
| Instruction language and tone policy | `docs/instruction-language-policy.md` |
| Memory/search/recommendation engine | `docs/memory-engine-requirements.md` and `engine/ENGINE_REQUIREMENTS.md` |
| Frontend/design/runtime safety | `frontend/FRONTEND_REQUIREMENTS.md` and `frontend/contracts/kernel-boundary.md` |
| Frontend-to-engine connection | `frontend/contracts/engine-connection-guide.md` |
| DB publication and corpus compatibility | `db/DB_SHARING_GUIDE.md` |
| GitHub governance and merge rules | `docs/repository-governance.md` |
| Diff-based fallback workflow | `docs/standalone-maintenance-workflow.md` |

If a contributor changes behavior across a boundary, they must update the relevant contract file in the same PR.

## Ownership Boundaries

| Area | Owner team | May change | Must not change without cross-team review |
|---|---|---|---|
| `db/`, corpus manifests, DB snapshots | DB/data team | corpus manifests, import/export docs, schema compatibility adapters | runtime API field names, source IDs, quote span meaning |
| `engine/`, `shared_platform/beta6.py`, `shared_platform/search.py`, `shared_platform/engine_contract.py` | Engine team | retrieval, ranking, claim cards, source-window generation, latency strategy | `source-grounded-v2` output shape, job progress contract, product manifest capability semantics |
| `frontend/`, `web/`, `native/` | Frontend/design team | visual shells, layout, product skins, animation, route composition | shared frontend foundation, API endpoints, job token semantics, state machine invariants, i18n key contract |
| `apps/`, `shared_platform/server.py`, `ops/` | Platform lead/team lead | server runtime, queue, auth binding, deployment scripts | public API contract without migration/versioning |
| `.github/`, CI, branch rules docs | Team lead | merge gates, CODEOWNERS, PR template, release policy | bypass/merge rules without team notice |

## Required Layer Contracts

### DB -> Engine

The engine reads a product corpus through a declared product profile:

```json
{
  "product": "islam",
  "dbPath": "/absolute/path/to/db.sqlite3",
  "dbShape": "precedents",
  "sourceIdField": "canonical_id",
  "textField": "full_text"
}
```

The DB layer must preserve:

- stable canonical source IDs;
- full original text;
- citation/title/path metadata;
- enough schema compatibility for `precedents` or `documents` search adapters;
- optional richer tables without breaking compatibility.

### Engine -> Frontend

The frontend only consumes `source-grounded-v2` public result fields:

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

The frontend must not scrape prompts, logs, local run files, or hidden engine internals.

### Frontend -> API

Every web/native client uses the same public API:

```text
POST /api/{product}/jobs
GET  /api/jobs/{jobId}
GET  /api/jobs/{jobId}/events
GET  /api/jobs/{jobId}/result
POST /api/jobs/{jobId}/cancel
GET  /api/{product}/source-window
```

All job reads/cancels must carry job access token and session token.

### Product Skin -> Shared Frontend Foundation

Designs connect through declarative slots and attributes:

```text
Product skin -> shared UI kernel -> shared client/job runtime -> product API
```

The product skin controls presentation. The shared frontend foundation controls engine connection, job ownership, chat persistence, language state, offline queueing, and source-window mapping.

## Repository Layout

The active implementation lives at the repository root:

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

Do not add alternate root directories for active runtime, contracts, tests, DB manifests, or repo-level tooling.

## Collaboration Rule

No contributor should need to wait for another team if they preserve the boundary contract.

- Engine team may replace beta-6 internals if `source-grounded-v2`, artifacts, source windows, and app-path tests pass.
- Frontend team may redesign every product if the UI runtime contract, i18n coverage, job semantics, and source-window behavior pass.
- DB team may rebuild corpus tables if compatibility views/adapters and stable source IDs remain.

## Required Merge Gate

Every PR to `main` must pass. Normal work must not be pushed directly to `main`; it must be completed on a branch and merged only after owner approval.

```bash
python3 tools/verify_repo_contracts.py
pytest tests/test_api.py tests/test_app_shell_parity.py tests/test_frontend_static.py -q
python3 tools/sync_native_shell_assets.py --check
```

Engine PRs must additionally run the relevant beta-6/app-path gates listed in `engine/ENGINE_REQUIREMENTS.md`.

Frontend PRs must additionally run the frontend gates listed in `frontend/FRONTEND_REQUIREMENTS.md`.

DB/corpus PRs must update `db/db-manifest.example.json` or the real manifest and run the DB checks described in `db/DB_SHARING_GUIDE.md`.
