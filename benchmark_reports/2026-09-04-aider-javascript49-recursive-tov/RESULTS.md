# Aider JavaScript49 Prospective Recursive-TOV Evaluation

## Status and scope

This is a before-call-frozen evaluation on **all 49 JavaScript exercises** at
`Aider-AI/polyglot-benchmark` commit
`7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`. No task was selected, removed,
replaced, or topped up. Each arm was exactly one whole-track
`gpt-5.6-luna`/medium call, with no per-task calls or retries. The two system
comparators each contain five calls and share Plain, Graph, ordinary repair,
and semantic-free Direct; their fifth route is Generic or TOV.

The frozen protocol SHA-256 is
`0db8e0037ecdc4fc376a582a6a4628f2f471a542017141ee6ae610c17b54ea0d`.
The valid freeze, manifest, and task-packet SHA-256 values are respectively
`6abd5a0ee1e4792115bec699485e99d2d39064e435d5f621a70802f0291d55ca`,
`ceced6ab0b227a3505b77a9f89070d69a077e2bc8df609a995d65ada29072fd0`,
and `00677d9332c8fd0b0bb3cfaf7ef82b9f6d1cdacfb696c14943581229dad1a7e3`.
The starter scored 1/49. The model saw no official test source; the private
evaluator restored the complete test suites.

## Results

| Arm or system | Passes / 49 | Accuracy |
|:---|---:|---:|
| Plain | 27 | 55.10% |
| Graph | 27 | 55.10% |
| Ordinary execution-feedback repair | 42 | 85.71% |
| Verified candidate floor | 42 | 85.71% |
| Semantic-free Direct | 45 | 91.84% |
| Generic final route | 47 | 95.92% |
| TOV final route | 47 | 95.92% |
| Direct∪Generic | **47** | **95.92%** |
| **Mini Artichokes (Direct∪TOV)** | **47** | **95.92%** |

| Paired contrast | Rescue:harm | Difference | One-sided exact | Two-sided exact | Paired bootstrap 95% CI |
|:---|---:|---:|---:|---:|:---|
| Mini vs Plain | 20:0 | +20/49 (+40.82 pp) | 9.537e-7 | 1.907e-6 | [+26.53,+55.10] pp |
| Mini vs ordinary repair | 5:0 | +5/49 (+10.20 pp) | .03125 | .06250 | [+2.04,+18.37] pp |
| Mini vs Direct∪Generic | 0:0 | 0/49 | 1.0 | 1.0 | [0,0] pp |
| TOV vs Generic | 0:0 | 0/49 | 1.0 | 1.0 | [0,0] pp |

The five Mini-only gains over ordinary repair are `beer-song`, `food-chain`,
`go-counting`, `killer-sudoku-helper`, and `twelve-days`. The preregistered
strong-effect gate of at least +10/49 (+20.41 pp) was met against Plain but not
against ordinary repair or the equal-call comparator. The prospective
overlap-specific result is an exact tie: this experiment supports the
end-to-end verified-redundancy system, not a causal superiority claim for the
TOV prompt over Generic.

## Realized cost and integrity

| Arm | Input | Cached input | Output | Reasoning output | Agent s |
|:---|---:|---:|---:|---:|---:|
| Plain | 1,666,148 | 1,578,240 | 21,710 | 2,262 | 476.4 |
| Graph | 1,542,883 | 1,455,616 | 20,962 | 2,685 | 450.5 |
| Ordinary | 2,007,987 | 1,907,200 | 15,015 | 5,166 | 354.0 |
| Direct | 1,500,303 | 1,408,512 | 15,226 | 2,050 | 324.9 |
| Generic | 819,905 | 736,000 | 9,736 | 2,209 | 219.5 |
| TOV | 1,147,397 | 1,052,672 | 13,387 | 2,712 | 287.1 |
| Direct∪Generic five-call system | 7,537,226 | 7,085,568 | 82,649 | 14,372 | 1,825.3 |
| Direct∪TOV five-call system | 7,864,718 | 7,402,240 | 86,300 | 14,875 | 1,892.9 |

Both systems are call- and hard-cap-matched, not realized-token-matched. Mini
used 4.35% more input, 4.42% more output, and 3.70% more agent time. All six
calls were agent-complete, safe, and free of retries, timeouts, and forbidden
paths. Direct, Generic, and TOV received byte-identical staged candidates,
failure evidence, evidence index, and anchor map. All 126 route-by-anchor file
comparisons were byte-exact. Both materialized union workspaces were evaluated
directly and scored 47/49.

A post-result stability audit re-evaluated the materialized Mini union twice
more with the same pinned evaluator, tests, Node, Jest, and dependency lock.
Both reruns reproduced 47/49 and the identical normalized task-outcome-vector
SHA-256
`f6eee9417245ba316134fb16875dda1d4fbaa63df2c63fa1714e41c67a52d8ad`.
The evaluator returns process status 1 whenever `allPassed=false`; this is its
documented 47/49 result convention, not an execution failure. A manifest audit
found 49 unique task IDs, 49 distinct task roots, 49 uniquely owned declared
solution paths, no nested task roots, and no multi-owner file.

An initial evaluator smoke test lacked `NODE_PATH`. It occurred before any
scored model call, was invalidated, and remains under
`campaign/invalid-freeze-missing-node-path/`; the valid environment was then
re-frozen. The scored analysis SHA-256 is
`4bfc944623b2d59690ad74aff5ad8814539011df5449c4df8874e5bbfd1b4a20`.
