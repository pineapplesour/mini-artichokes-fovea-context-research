# Aider60 online-freeze versus offline-portfolio ablation

Frozen before every call in this protocol on 2026-09-05 KST.  This is a new
campaign, not a continuation or replacement within the stopped Aider90
protocol.

## Question

Does intermediate official verification followed by byte-locked preservation
and unresolved-only final generation outperform unanchored full-track
portfolio adjudication when candidate calls, evidence, route types, model,
reasoning effort, call count, terminal verifier, and tool exposure are held
constant?

The historical online outcomes are known, so this is a prospectively frozen
new-control study.  It is not a prospective replication of the treatment.
Infrastructure and validity checks are not contributions.

## Complete tracks and fixed calls

The denominator is all 60 official tasks in two complete Aider tracks at
`Aider-AI/polyglot-benchmark` commit
`7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`:

- all Python34 tasks in
  `runs/aider-python34-tov-v2-confirmation-20260902`;
- all C++26 tasks in
  `runs/aider-cpp26-tov-v2-extension-20260902`.

No task selection, deletion, replacement, per-task call, retry, or selective
top-up is permitted.  Each arm is one whole-track call.  No optional language
tool root is added; the offline controls receive exactly the system tool
exposure used by the historical online calls.

Both five-call systems share the frozen Plain, Graph, and ordinary-repair
candidate calls, then use one semantic-free structured route and one semantic
overlap route.  The online system installs and restores the evaluator-passing
candidate union before and after final generation.  The offline system starts
both routes from ordinary repair, supplies the same P/G/R patches and bounded
outcomes, permits full-track adjudication without protected files, and applies
the same verifier only after both final routes finish.  Terminal union means a
task passes when either route supplies an evaluator-passing complete solution;
the materialized priority is overlap, then semantic-free.

All new calls use `gpt-5.6-luna`, medium reasoning, low verbosity, hidden
official tests, the existing time caps, and disabled web, memories, plugins,
skills, and multi-agent execution.

Frozen order:

1. Python34 `semantic_free_structured_offline_portfolio`
2. Python34 `semantic_overlap_offline_portfolio`
3. C++26 `semantic_free_structured_offline_portfolio`
4. C++26 `semantic_overlap_offline_portfolio`

Any transport-null event or unsafe call stops this campaign and stays missing.

## Estimands

The primary paired contrast is the directly materialized online terminal union
minus the directly materialized offline terminal union over all 60 tasks.
Report rescues, harms, net percentage points, exact McNemar values, a
50,000-draw track-stratified paired bootstrap interval, and both track
differences.  The strong-mechanism gate requires `+12/60` (`+20.0` points),
one-sided exact `p < .05`, and a positive direction on both tracks.  A result
below that gate cannot be called a strong or 20-point mechanism effect.

Secondary contrasts are online versus offline for each route and each system
versus the fixed Plain and ordinary candidates.  Known online-versus-Plain
outcomes are not new evidence.

## Frozen hashes

Runner:
`a682de4e251f7d93855e54570561300cd719d3e2df9245192ee14a9bb1e913bb`.

| Track | Freeze | Task packet | Plain result | Graph result | Ordinary result |
|---|---|---|---|---|---|
| Python34 | `2f0a2c7fabcbfe33a8f91235c3ea135db4e9c38bf496a934e79dac5deebb5c8a` | `7329bda778b0a65194cd10dc91c1be2ae7f46b81aa43bdbf39bcb3934cfe5289` | `969222e9d8a69b3821769b19bbfe9af01c0f5af16596a9ab71330323477ed3c3` | `a7055df476042b667cbf9f8bb8573032529215a9d7468156e1a0958143b107f5` | `a7f50428dd160c74bac30a2fb0a3beaa825369b078884566d587d48873e69fee` |
| C++26 | `a3feff3bc378bf453c4f11d65221a9761c54b50333364350d0b9ca00da1e2e08` | `6febe691e7074c0a3ba31d49494b81907bc9f09957e0ac8ab68335cd9140b5b8` | `f58a5575b86d72a4492857175c58c3709af49708432874cc1ba575a1ae9b98f3` | `fbd3e9c3b0db8856b22d88f33af3090edebe91a5b72e9636c04e775082ee0d86` | `10c53ec4c43a60d1e97c934963df6072f995792075e958bda8ef72f35009f2a9` |
