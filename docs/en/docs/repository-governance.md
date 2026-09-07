# Repository Governance

Last updated: 2026-05-15 KST

This document defines the repository permission model, review workflow, and history-protection requirements for Universal Artichoke.

## Target Permission Model

The intended operating model is:

| Role | GitHub capability | Main branch authority |
|---|---|---|
| Owner | Repository administration, final release approval, emergency recovery | May approve and merge to `main`; may change branch rules deliberately. |
| Team lead | Owns review and merge decisions for team branches and PRs | May approve team PRs; must not rewrite or delete `main`. |
| Team member | Creates branches, commits to their own branches, opens PRs | Cannot push directly to `main`; cannot force-push or delete protected shared branches. |
| Reviewer | Reviews and comments | No merge or history-rewrite authority unless separately granted. |

The important distinction is that **write access is not enough governance by itself**. Team members need the ability to commit to feature branches, but protected-branch rules must prevent direct writes, force-pushes, and deletion of `main`.

## Current GitHub Enforcement Status

Verified on 2026-05-15 KST:

```text
repo: pineapplesour/universal-artichoke
visibility: PRIVATE
default branch: main
viewer permission: ADMIN
```

Current collaborators returned by the GitHub API have either `admin` or `write` repository role. Ordinary `write` collaborators can create branches and push commits, but in this private personal repository the branch protection and rulesets APIs currently return:

```text
HTTP 403: Upgrade to GitHub Pro or make this repository public to enable this feature.
```

Therefore the target model is **documented but not fully enforceable on the hosted repository yet**. Until branch protection or rulesets are available, a `write` collaborator may be able to push directly to unprotected branches. This is an operational risk, not a completed control.

## Required Hosted Setup

Before broad team development begins, implement one of these:

1. Upgrade/move the repository to a GitHub plan or organization where private-branch protection and repository rulesets are available.
2. Move the repository into an organization and create GitHub teams for `team-leads`, `engine-team`, `frontend-team`, and `db-team`.
3. Make the repository public only if the code/data policy allows it.

After that, configure a ruleset for `main`:

- restrict direct updates to owner/team-lead bypass actors only;
- block force pushes;
- block branch deletion;
- require pull requests before merge;
- require CODEOWNERS review;
- dismiss stale approvals when new commits are pushed;
- require conversation resolution;
- require the `repo-contracts` status check;
- require additional engine/frontend/DB status checks when those areas are touched.

Configure shared release branches such as `release/*` and `prod/*` with the same force-push and deletion restrictions.

## Branch Authority

Allowed working branch prefixes:

```text
team1/engine/<short-topic>
team2/ui-fix/<product-or-bug>
team3/design/<product>
db/<short-topic>
docs/<short-topic>
hotfix/<short-topic>
```

Team members may push commits to their own working branches. Team leads may manage their team's branches, coordinate reviews, and request rewrites before review begins. Once a branch is under review, history should be preserved unless the team lead explicitly requests a rebase or cleanup.

No one except the owner should perform destructive repository operations. Team leads may manage team branches, but they must not delete `main`, rename `main`, force-push `main`, or rewrite `main` history.

Normal development must happen on a working branch. A branch may be merged to `main` only after the feature or documentation scope works fully on that branch, the relevant verifiers pass, and the owner explicitly approves the merge.

## CODEOWNERS Policy

The current `.github/CODEOWNERS` file uses `@pineapplesour` because this is a personal repository. That is the only reliable owner handle until the project is moved into an organization with real GitHub teams.

When organization teams exist, replace the owner handle with team handles:

```text
@team-leads
@engine-team
@frontend-team
@db-team
```

CODEOWNERS only routes review requests. It blocks merges only when branch protection requires code-owner review.

## No History Deletion Policy

The following are prohibited for normal development:

- force-pushing `main`, `release/*`, or `prod/*`;
- deleting `main`, `release/*`, or `prod/*`;
- rewriting shared review history after review has started without team-lead approval;
- removing review evidence, verification artifacts, or incident context from PR discussions;
- using `git filter-repo`, forced rebase, or forced push on shared history as a routine cleanup tool.

If a secret or legally sensitive file is committed, stop normal work and treat it as an incident. History rewriting for incident response is owner-controlled and must be documented.

## Pull Request Requirements

Every PR must include:

- purpose and affected layer;
- contract files touched;
- verification commands and results;
- real user-path artifact when UI/API/engine behavior changed;
- rollback notes;
- cross-team impact notes.

Direct pushes to `main` are acceptable only during owner-controlled repository setup or emergency repair. Normal feature, documentation, DB, and design work must be completed on a branch and merged only after owner approval. The same verification standard must still be included in the commit message or task log.

## Repository Rename

The system name is `Universal Artichoke`.

The repository slug is:

```text
pineapplesour/universal-artichoke
```

After a rename, update local clones:

```bash
git remote set-url origin https://github.com/pineapplesour/universal-artichoke.git
```
