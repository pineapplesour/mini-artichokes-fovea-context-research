# Team Collaboration Workflow

Last updated: 2026-05-15 KST

Universal Artichoke is organized so DB, engine, frontend, and operations work can move in parallel without breaking shared contracts.

## Operating Principles

- Teams work on branches and submit pull requests.
- Team leads coordinate scope, review implementation quality, and verify contract compliance.
- The owner gives final approval before changes enter `main`.
- Contract changes are versioned and documented in the same PR as the implementation.
- Verification evidence is part of the deliverable, not an optional follow-up.
- Direct pushes to `main` are not the normal workflow. All ordinary work must be completed on a branch, fully working on that branch, and merged to `main` only after explicit owner approval.

## Wednesday Review Cadence

Teams may report progress whenever there is meaningful movement. The formal review checkpoint is every Wednesday.

Each team lead should provide:

- changes completed;
- goal advanced;
- commands and verifiers run;
- artifacts proving real behavior when UI/API/engine behavior changed;
- remaining blockers and proposed next steps.

The team lead is responsible for orchestration and verification. The owner should not be the first person to discover a contract violation, stale artifact, or untested user path.

## Branch Workflow

Recommended branch names:

```text
team1/engine/<short-topic>
team2/ui-fix/<product-or-bug>
team3/design/<product>
db/<short-topic>
docs/<short-topic>
hotfix/<short-topic>
```

Team members may commit to their own working branches. Team leads may manage team branches and request cleanup before review. Once review begins, avoid force-pushing unless the team lead explicitly asks for it.

`main` is not a working branch. Do not use `main` for experiments, design exploration, benchmark trials, or temporary data publication.

A branch is mergeable to `main` only when:

- the product or scope works fully on that branch;
- relevant contract tests and verifiers pass;
- UI/API/engine/native behavior changes include real user-path artifacts;
- the owner has explicitly approved the merge.

## Layer Ownership

| Team | Owns | Must not break |
|---|---|---|
| Team 1 Engine | `shared_platform/beta6.py`, search, engine artifacts, benchmarks, `engine/` docs | `source-grounded-v2`, source-window IDs, product API routes |
| Team 2 Existing UI | existing Islam/TCM/Simli pages, UI bug fixes, browser verification | engine contract, DB schemas, product manifest parity |
| Team 3 New Designs | new product skins and product-specific UI composition | shared UI kernel, data attributes, i18n completeness, job lifecycle |
| DB/Data | corpus DBs, manifests, releases | stable canonical IDs and `ProductProfile.db_shape` compatibility |
| Operations/Lead | CI, branch policy, deployment scripts, release process | review and rollback guarantees |

## Weekly Instruction Files

Team instructions live under:

```text
tasks/team-instructions/week-YYYY-MM-DD/
```

Each team file must state:

- scope;
- files or folders the team may edit freely;
- files requiring cross-team review;
- required tests and verifiers;
- contracts that must not change;
- expected handoff artifact.

Contributors should read the relevant weekly file plus `README.md`, `STRUCTURE_REQUIREMENTS.md`, and the local layer requirements before editing.

## Review Checklist

Every PR or direct owner-controlled setup commit must answer:

- What contract does this touch?
- What files changed?
- What commands were run and what passed?
- Was a real user path tested when behavior changed?
- Are there stale experimental files left behind?
- Does the change require DB release, native shell sync, or deployment updates?
- What is the rollback path?

## Cleanup Rule

Experimental files that are not referenced by manifests, routes, docs, tests, or release inventory must be removed or moved to an explicit archive before merge.
