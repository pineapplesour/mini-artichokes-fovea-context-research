# Aider90 online-freeze versus offline-portfolio ablation

Frozen before every new model call on 2026-09-05 KST.

## Question and status

This review-triggered ablation asks whether Mini Artichokes' intermediate
`verify -> freeze -> unresolved-only generation` mechanism improves accuracy,
holding the candidate generators, candidate evidence, final route types, model,
reasoning effort, whole-track call count, and terminal verifier constant.

The existing online outcomes are already known.  Therefore this is a
prospectively frozen *new-control* experiment, not a prospective replication of
the online treatment.  Infrastructure, masking, hashing, and materialization
are evidence QA and are not scientific contributions.

## Complete official tracks

No task may be selected, removed, replaced, or topped up.  The denominator is
all 90 tasks in the three complete Aider tracks already frozen at
`Aider-AI/polyglot-benchmark` commit
`7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`:

- Rust30: `runs/aider-rust30-tov-v2-development-20260902`
- Python34: `runs/aider-python34-tov-v2-confirmation-20260902`
- C++26: `runs/aider-cpp26-tov-v2-extension-20260902`

Each arm remains one whole-track call.  Per-task calls, retries, selective
reruns, and result-dependent replacement calls are forbidden.

## Shared five-call systems

Both systems contain the same three already completed whole-track candidate
calls: Plain, Graph, and ordinary Graph execution-feedback repair.  Both add
exactly two final whole-track routes:

1. a structured semantic-free route; and
2. a Try--Semantic-Overlap--Verify route.

The **online-freeze system** is the existing treatment.  The official evaluator
is run after the shared candidates; for each task, the highest-priority passing
complete file state (`ordinary > Graph > Plain`) is installed as a byte-locked
anchor.  Both final routes start from that union, edit only unresolved tasks,
and have anchors restored after their calls.  A terminal verifier promotes a
passing output from either route.

The **offline-portfolio system** is the new control.  Each final route starts
from the ordinary candidate and receives the same complete task packet, Plain /
Graph / ordinary patches, pass/fail outcomes, and bounded failure tails.  It
must adjudicate all tasks and has no mechanically protected files.  Only after
both routes finish does the same terminal verifier promote a passing output
from either route.  Thus both systems use five semantic model calls; the named
treatment is intermediate verified state installation, byte preservation, and
unresolved-set contraction.

## Frozen new calls and order

All calls use `gpt-5.6-luna`, medium reasoning, low verbosity, the existing
whole-track timeout, hidden official tests, and no web, memories, plugins,
skills, multi-agent execution, or task-wise splitting.

1. Rust30 `semantic_free_structured_offline_portfolio`
2. Rust30 `semantic_overlap_offline_portfolio`
3. Python34 `semantic_free_structured_offline_portfolio`
4. Python34 `semantic_overlap_offline_portfolio`
5. C++26 `semantic_free_structured_offline_portfolio`
6. C++26 `semantic_overlap_offline_portfolio`

The run stops on an integrity failure.  A transport-null event remains missing
and cannot be silently replaced under this protocol.

## Frozen estimands and decision rules

The primary score is the directly materialized terminal-union pass count over
all 90 tasks.  The primary paired contrast is online-freeze union minus
offline-portfolio union.  Report rescues, harms, net percentage-point change,
one- and two-sided exact McNemar values, a 50,000-draw track-stratified paired
bootstrap interval, and the three track differences.

The preregistered strong-mechanism gate requires both at least `+18/90`
(`+20.0` percentage points) and one-sided exact `p < .05`, with a positive
effect in at least two of three tracks.  Falling short is retained as evidence
but cannot be described as a strong or 20-point causal effect.

Secondary contrasts are online TOV versus offline TOV, online semantic-free
versus offline semantic-free, and each system versus the already reported Plain
and ordinary-repair candidates.  These must not replace the primary matched
contrast.  Existing online-versus-Plain results are not new evidence.

## Frozen hashes

Runner SHA-256:
`a682de4e251f7d93855e54570561300cd719d3e2df9245192ee14a9bb1e913bb`.

| Track | Freeze | Task packet | Plain result | Graph result | Ordinary result |
|---|---|---|---|---|---|
| Rust30 | `0e53b43f5c68f48feb3f01c269de8094e480ffc653a474a0d16ff474e4207cce` | `9984a717e82443c239396eb3b167613511051f071080f1ff7e58aa949cacc1c0` | `7d843c32eb24de611d1ca8a66fb36ef2d253f85b98faf822457ea1031df95e8b` | `54f32ad1e3c17349bc4f199fe06d4fa13b8b4ef8834fbc71057a926797a6b46b` | `3324a4b80925570b22481e5e8720e6bf11175c9f10db064270514619a1b2034c` |
| Python34 | `2f0a2c7fabcbfe33a8f91235c3ea135db4e9c38bf496a934e79dac5deebb5c8a` | `7329bda778b0a65194cd10dc91c1be2ae7f46b81aa43bdbf39bcb3934cfe5289` | `969222e9d8a69b3821769b19bbfe9af01c0f5af16596a9ab71330323477ed3c3` | `a7055df476042b667cbf9f8bb8573032529215a9d7468156e1a0958143b107f5` | `a7f50428dd160c74bac30a2fb0a3beaa825369b078884566d587d48873e69fee` |
| C++26 | `a3feff3bc378bf453c4f11d65221a9761c54b50333364350d0b9ca00da1e2e08` | `6febe691e7074c0a3ba31d49494b81907bc9f09957e0ac8ab68335cd9140b5b8` | `f58a5575b86d72a4492857175c58c3709af49708432874cc1ba575a1ae9b98f3` | `fbd3e9c3b0db8856b22d88f33af3090edebe91a5b72e9636c04e775082ee0d86` | `10c53ec4c43a60d1e97c934963df6072f995792075e958bda8ef72f35009f2a9` |

The protocol file's SHA-256 is recorded separately immediately after this file
is closed; it is not self-referential.
