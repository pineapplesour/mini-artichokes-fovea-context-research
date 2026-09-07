# HumanEvalFix Python164 Prospective Recursive-TOV Evaluation

## Status and scope

This is a before-call-frozen evaluation on **all 164 Python tasks** in the
official BigCode HumanEvalPack `HumanEvalFixDocs` configuration. The Hugging
Face dataset revision is pinned at
`9a41762f73a8cb23bb5811b73d5aab164efcf378`; the source parquet SHA-256 is
`ed5f15d789156e21222bfcd556c425a39042355c84ae1e8b058abd6a3d7f8075`.
No task was selected, removed, replaced, or topped up. Each arm was one
whole-track `gpt-5.6-luna`/medium call with no per-task calls or retries.

The protocol SHA-256 is
`47585a6fb48a96fb4daaf481a30f32d5fab3561fc8be01980288a2fef314c5e5`.
The freeze, manifest, private-case, and task-packet SHA-256 values are
`07c52db96d1017657ac3161e81c9da3606929b7ce18cfea1edb0a7366f392836`,
`be7fb0c0fab142faa2fc0c9022867f6a113676162f8f111a397f8cc971144a06`,
`38d32a2cf88f374f991c571e563a508f7667d321458b4c8e904d96393f60001a`,
and `19d29a475e830825d8eb7093132de8cf1c2f36f7a82493132549c6314ba136ce`.
The starter scored 0/164. Model workspaces contained the buggy solution and
docstring but neither canonical solutions nor private tests.

## Results

| Arm or system | Passes / 164 | Accuracy |
|:---|---:|---:|
| Plain | 157 | 95.73% |
| Graph | 154 | 93.90% |
| Ordinary execution-feedback repair | **164** | **100%** |
| Verified candidate floor | **164** | **100%** |
| Semantic-free Direct | **164** | **100%** |
| Generic final route | **164** | **100%** |
| TOV final route | **164** | **100%** |
| Direct∪Generic | **164** | **100%** |
| **Mini Artichokes (Direct∪TOV)** | **164** | **100%** |

| Paired contrast | Rescue:harm | Difference | One-sided exact | Two-sided exact | Paired bootstrap 95% CI |
|:---|---:|---:|---:|---:|:---|
| Mini vs Plain | 7:0 | +7/164 (+4.27 pp) | .0078125 | .015625 | [+1.22,+7.32] pp |
| Mini vs ordinary repair | 0:0 | 0/164 | 1.0 | 1.0 | [0,0] pp |
| Mini vs Direct∪Generic | 0:0 | 0/164 | 1.0 | 1.0 | [0,0] pp |
| TOV vs Generic | 0:0 | 0/164 | 1.0 | 1.0 | [0,0] pp |

The seven Mini gains over Plain are tasks 038, 050, 093, 120, 132, 140, and
145. Ordinary repair already reached the complete-suite ceiling. Consequently,
this benchmark independently confirms that execution feedback plus verified
preservation can repair all observed Plain failures, but it supplies no
positive information about which final route is better. It fails the
preregistered +33/164 strong-effect gate and is retained as a ceiling boundary.

## Realized cost and integrity

| Arm | Input | Cached input | Output | Reasoning output | Agent s |
|:---|---:|---:|---:|---:|---:|
| Plain | 1,253,558 | 1,174,016 | 16,709 | 4,033 | 374.3 |
| Graph | 1,137,136 | 1,053,696 | 16,552 | 4,383 | 375.4 |
| Ordinary | 196,377 | 170,752 | 3,453 | 782 | 87.1 |
| Direct | 107,339 | 88,320 | 2,898 | 848 | 74.6 |
| Generic | 308,073 | 261,376 | 3,301 | 1,033 | 93.8 |
| TOV | 102,941 | 80,384 | 2,871 | 684 | 75.6 |
| Direct∪Generic five-call system | 3,002,483 | 2,748,160 | 42,913 | 11,079 | 1,005.3 |
| Direct∪TOV five-call system | 2,797,351 | 2,567,168 | 42,483 | 10,730 | 987.1 |

Both systems are call- and hard-cap-matched, not realized-token-matched. All
six calls were agent-complete and safe, with no retry, timeout, or forbidden
path. The three final routes received byte-identical evidence and anchors; all
492 route-by-anchor file comparisons were byte-exact. Both materialized system
unions were evaluated directly at 164/164. The scored analysis SHA-256 is
`197d5c00ea04d3717d20efd8a24202dcce3d421f472017dfa160a72f583641c7`.

The actual freeze manifest and evaluator executable record Python 3.13.11,
rather than the protocol's predeclared Python 3.13.5 or the benchmark paper's
Python 3.9.13 environment. This version mismatch is a protocol deviation, so
the run is used as a complete-suite ceiling/portability evaluation rather than
a strict protocol-confirming endpoint.

A post-result stability audit re-evaluated the materialized Mini union twice
more. Both reruns reproduced 164/164 with byte-identical stdout SHA-256
`c37bd431873259b50d981f631331c5a3672fa385bb50d2f38a5f90b87fc2843a`.
A manifest audit found 164 unique task IDs, 164 distinct task roots, 164
uniquely owned declared solution paths, no nested task roots, and no
multi-owner file.
