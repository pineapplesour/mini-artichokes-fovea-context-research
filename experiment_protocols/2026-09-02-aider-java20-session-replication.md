# Frozen protocol: Aider Java20 session-level replication

Status: frozen before any model call in the five replication sessions and
before inspecting any replication outcome.

## Scientific question

Does the frozen Graph-plus-matched-structured-repair policy improve the same
official hidden-test Java20 task set over direct Luna and Graph alone across
independently initialized whole-batch sessions?

This experiment measures session-level repeatability of the coding effect. It
does not test an infrastructure contribution, and it does not claim that
overlap metadata causes the gain. The prior Java20 observation (7/20 matched
repair, 3/20 Plain, 3/20 Graph) motivated this replication but is excluded from
its confirmatory statistics.

## Frozen benchmark and policy

- Official source: `Aider-AI/polyglot-benchmark` at commit
  `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`.
- Task set: the same 20 SHA-ranked Java exercises frozen in
  `runs/aider-hidden-java20-luna-medium-20260902-v1`.
- Freeze SHA-256:
  `b12e7d7a4904084b35cae8bca1f492d9173a46d7ee6c8dcfe8165cd3a27111c0`.
- Public task SHA-256:
  `69e2e1d2220ff21651d7ac266ab0828695a769c4740dbc2b85baa0b0a9981942`.
- Public manifest SHA-256:
  `102cb6e1631dc33c7f59f118991c87c77554f468a2acc26cb2173151a0418e84`.
- Private evaluator SHA-256:
  `997e254b413c4ca248cf68162541843a9a92c0c561539649ab3fc9d681d1475c`.
- Arm runner SHA-256:
  `e0a51ce1c743f74760eb7f7c47104299d2ac1564b34e9e86d6594ca2a5a8236a`.
- Frozen Graph instruction SHA-256:
  `40ed476feae75f8bf0c0dbb1af271dace9a14846c14a9ed56b183c9dd98246ba`.
- Frozen matched-repair instruction SHA-256:
  `67f9af88529cd845cf06225d0e3df88861cbaa18104ae8f3a0275184bec51346`.

All calls use `gpt-5.6-luna`, medium reasoning, the approved Codex account,
and one whole-batch invocation. Tests and gold implementations remain hidden.
The repair call starts from its own session's frozen Graph patch and receives
that Graph attempt's complete official failure stdout. Thus the repair policy
is identical across sessions while the observed evidence is appropriately
session-specific.

## Predeclared sessions and order

Exactly five new sessions are allowed:

1. `aider-hidden-java20-session-replication-01`: Plain, Graph, matched repair.
2. `aider-hidden-java20-session-replication-02`: Graph, Plain, matched repair.
3. `aider-hidden-java20-session-replication-03`: Plain, Graph, matched repair.
4. `aider-hidden-java20-session-replication-04`: Graph, Plain, matched repair.
5. `aider-hidden-java20-session-replication-05`: Plain, Graph, matched repair.

The Plain/Graph order alternates to reduce a simple temporal-order confound;
matched repair necessarily follows Graph. No result-led rerun, task deletion,
prompt change, top-up, or additional session is allowed. An incomplete or
unsafe arm remains in the record and contributes 0/20 for its session rather
than being selectively replaced.

## Frozen analysis

For each session report full-denominator correct counts for Plain, Graph, and
matched repair. The primary fixed-sequence tests are:

1. matched repair has a positive session-level accuracy difference over Plain;
2. only if (1) rejects at one-sided alpha .05, matched repair has a positive
   session-level accuracy difference over Graph.

Each test uses the exact one-sided sign test over the five independently
initialized session differences, discarding exact zero differences. Report
positive/tied/negative sessions, the mean and median percentage-point
difference, and a paired session bootstrap interval. Also report task-session
rescues and harms over 100 repeated outcomes, explicitly labeled descriptive
because the same 20 tasks recur in every session.

The prior Java20 session and the earlier Python/Rust batches are not pooled
into either confirmatory test. No infrastructure property is a paper claim.
