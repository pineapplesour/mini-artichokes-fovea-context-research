# Frozen protocol: Go39 prospective recursive-TOV confirmation

Status: frozen before every model call.

## Scientific objective

Prospectively test the recursive verified-redundancy rule on an untouched
complete official language track. The primary comparison isolates the presence
of an overlap-aware final route at equal nominal call count:

- **Non-overlap dual-route system:** shared `Plain/Graph/ordinary` candidates,
  a generic verified-union Critic, and a semantic-free structured direct route;
  output is the task-wise official-test verified union of the two final routes.
- **Recursive TOV system:** the identical shared candidates and direct route,
  with TOV replacing the generic Critic; output is the same task-wise verified
  union of the two final routes.

Each compared system contains five model calls and shares four of them. The
union copies only declared solution-file bytes from a route that passes the
complete official suite for that task. Fixed provenance priority is direct
route before the replaceable route when both pass; priority cannot affect the
pass label.

## Benchmark and denominator

- Source: `Aider-AI/polyglot-benchmark`, commit
  `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`.
- Track: all 39 official Go exercises, alphabetical frozen order.
- Selection: none; every task is retained regardless of outcome.
- Starter smoke score: 3/39 on the same complete official evaluator.
- Agent workspace contains zero `*_test.go` files; private evaluator contains
  61 official test files. Gold `.meta` and `.approaches` content is absent from
  model and evaluator workspaces.
- Freeze SHA-256:
  `ebbb01078961617728451d80d4837ef98be4a022184952fb965575784779d061`.
- Manifest SHA-256:
  `dc7a21782d577bf243bbb9c3d8602a1cd45c79e13ae6aa0c2543ddb104a3b805`.
- Public task SHA-256:
  `168fa87420866a010523ff4e5a83102a51ba54dc7765b5ab59cea65f6e98819a`.

## Runtime and treatment freeze

- Model: `gpt-5.6-luna`.
- Reasoning effort: medium; low verbosity.
- Approved account: `CODEX_HOME=/home/pineapple/.codex-new-account`.
- One whole-track model call per arm; no per-task calls.
- Agent and evaluator timeouts: 1800 seconds.
- Local fixed toolchain: Ubuntu Go `go1.22.2 linux/amd64`, exposed read-only
  inside the model sandbox and used by the private evaluator.
- Runner SHA-256:
  `d8526504b1ab8c4f6251449bca24df284205142cf8707c3d66cd21a54159dbeb`.
- Evaluator SHA-256:
  `ec44af3735eab61194ddc7ae3b5338303271f22b0a1a88da53d3896d9165f10b`.
- Preparer SHA-256:
  `fa2d938abfc33997706fb6874f0006fdbb705240941e38e58958e44eb7e43917`.

The six new calls occur exactly once in this order:

1. Plain;
2. Graph;
3. ordinary execution-feedback repair from Graph;
4. semantic-free structured direct route from the verified candidate union;
5. generic Critic from the identical verified candidate union;
6. TOV from the identical verified candidate union.

No prompt, evidence-tail cap, anchor priority, ledger schema, output cap,
model, effort, or analysis rule changes after call 1 begins.

## Evidence and isolation

Plain and Graph see only public instructions and starter files. Ordinary repair
sees Graph's per-task pass/fail outcomes and bounded failure tails. The three
final routes receive byte-identical candidate patches, per-task outcomes,
bounded failure tails, evidence index, verified anchor map, task packet, model,
effort, and cap. Every final route starts from the same deterministic
`ordinary > Graph > Plain` candidate union. A post-call adapter restores every
candidate anchor byte before official evaluation.

The semantic-free direct route must write `withheld-by-control` in its semantic
field and cannot use convergence or disagreement as evidence. TOV may use
semantic convergence as support and must route disagreement through explicit
counterexample falsification. The generic Critic has no required ledger.

Models cannot access private tests or gold implementations. Official pass/fail
and bounded failure output are external repair evidence, consistent with the
paper's test-available setting.

## Primary endpoint and gates

Let `Y_T(t)` be one when task `t` passes in the recursive TOV union and `Y_N(t)`
one when it passes in the non-overlap dual-route union.

The primary effect is the full-denominator paired difference

`Delta = sum_t [Y_T(t)-Y_N(t)] / 39`.

Report overlap-system rescues, harms, net tasks, percentage points, and exact
one- and two-sided binomial/McNemar values over discordant tasks. The
directional primary superiority gate is one-sided `p<.05`. A separately named
strong-effect gate requires net at least +8/39 tasks (+20.5 percentage points).
Passing the statistical gate does not imply passing the strong-effect gate.

A 50,000-draw paired task bootstrap with seed 20260903 is descriptive and
conditional on the six realized whole-track calls. With one new language
track, no session- or language-population claim is permitted.

## Secondary outcomes

Report full-denominator scores for starter, Plain, Graph, ordinary repair,
candidate verified union, direct route, generic route, TOV route, non-overlap
dual-route union, and recursive TOV union. Also report:

- each final route's additions above the candidate anchor floor;
- TOV versus generic and TOV versus direct rescue/harm;
- complementarity added by recursive union over TOV alone and over direct
  alone;
- task IDs for every discordance;
- realized input, cached input, output, reasoning-output tokens, and seconds;
  and
- post hoc defect examples only as exploratory explanation.

## Integrity promotion gate

Promotion as prospective confirmation additionally requires:

- all six model calls are agent-complete, with no retry, replacement, or
  top-up;
- all changed paths are declared solution files;
- every final workspace restores all candidate anchor files byte-exactly;
- direct and TOV ledgers contain the exact frozen unresolved ID set and order;
- every direct semantic field is exactly `withheld-by-control`;
- evidence artifacts are byte-identical across direct, generic, and TOV arms;
  and
- recursive unions copy only declared solution files from evaluator-passing
  routes.

Any violation is retained in intention-to-treat scoring, named explicitly, and
causes the integrity promotion gate to fail. There are no reruns for low score,
protocol violation, timeout after a model turn starts, or unfavorable direction.

## Stopping rule

Stop after these six calls. Do not add repetitions, change the track, remove
tasks, or run a favorable follow-up before reporting this primary result.
Infrastructure files and toolchain staging are provenance only, never paper
contributions.
