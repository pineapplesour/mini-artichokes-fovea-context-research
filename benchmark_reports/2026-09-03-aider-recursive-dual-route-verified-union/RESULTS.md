# Recursive dual-route verified-union analysis

## Mechanism

The repeated final-stage studies show that the overlap-aware TOV route and the
semantic-free direct route have complementary, trajectory-dependent successes.
The derived mechanism applies the existing anchor rule a second time:

1. build the verified union of Plain, Graph, and ordinary repair;
2. run an overlap-aware final route and a direct structured final route from
   the identical anchored state;
3. execute the official per-task verifier on both final outputs; and
4. promote every passing task from either route into a recursive byte-exact
   verified union.

This is not an LLM vote or hidden-label-trained selector. It is valid only in
the paper's explicitly test-available repair setting. The analysis was devised
after the branch crossovers were observed and is therefore exploratory.

## Equal-call original comparison

The overlap system uses five calls: shared Plain, Graph, ordinary repair,
semantic-free direct repair, and TOV. Its matched non-overlap system uses the
same first three candidates and direct repair, replacing TOV with the generic
Critic. Each system takes the task-wise verified union of its two final routes.

| Track | Generic + direct verified union | TOV + direct verified union | Difference | Overlap-system rescues / harms |
|:---|---:|---:|---:|---:|
| Rust30 | 19/30 | 19/30 | 0 | 0 / 0 |
| Python34 | 21/34 | **23/34** | +2 | 2 / 0 |
| C++26 | 14/26 | **17/26** | +3 | 3 / 0 |
| **All90** | **54/90** | **59/90** | **+5 (+5.56 pp)** | **5 / 0** |

The five TOV-route rescues over the equal-call non-overlap union are Python
`forth` and `go-counting`, and C++ `complex-numbers`, `robot-name`, and
`yacht`. There are no harms. The one-sided exact discordance p-value is
`.03125`; the two-sided value is `.0625`. A 50,000-draw within-track paired
bootstrap with seed 20260902 gives `[+1.11,+10.00]` percentage points. Track
differences are `[0,+2,+3]`; the sign value over the two nonzero tracks is
`.25`, so this remains conditional on the realized calls.

This comparison addresses nominal call-count confounding between the two
five-call systems. Realized tokens and latency are not exactly matched, and
the choice to form the recursive union is post hoc.

## Repeated-session stabilization

No additional model calls are used here. Each repeated pair already contains a
TOV output and a semantic-free direct output from the same anchored state. The
recursive union retains every task passed by either output.

| Track | TOV session scores | Direct session scores | Recursive-union session scores | TOV total | Direct total | Recursive total |
|:---|:---|:---|:---|---:|---:|---:|
| Python34 | `24,21,23,23,22` | `20,23,21,23,20` | `24,24,24,24,22` | 113/170 | 107/170 | **118/170** |
| C++26 | `16,15,18,19,17` | `15,16,18,14,20` | `16,17,19,19,21` | 85/130 | 83/130 | **92/130** |
| **Combined** | -- | -- | -- | **198/300** | **190/300** | **210/300** |

Relative to TOV alone, the recursive union adds 12 repeated task-session
passes and loses none. It exceeds TOV in six of ten whole-track sessions and
ties in four, giving an exact one-sided sign value of `.015625` over the six
nonzero session differences. Relative to direct repair, it adds 20 passes and
is higher in all ten sessions. These dominance statements are mechanical: the
recursive union runs an extra final route and selects only verifier-passing
tasks. They establish stabilization in a test-available setting, not a
compute-matched causal benefit over a single route.

## Interpretation and boundary

The data support a stronger system principle than unconditional semantic
overlap:

- verified anchors make every accepted unit monotone;
- heterogeneous direct and overlap-aware routes create useful complementary
  errors;
- recursive verification converts those crossovers into additional anchors;
  and
- overlap is one productive route, not a certificate or universal gate.

The equal-call 59-versus-54 comparison is the relevant overlap-containing
system contrast in the original data. The 210/300 repeated result shows why the
recursive union is robust to branch trajectory. Both analyses are post hoc and
need a new complete track with the dual-route rule frozen before branch calls
for confirmatory status.

Infrastructure that stages patches, runs tests, and copies verified bytes is
experimental provenance, not the contribution. The contribution candidate is
the recursive verified-redundancy principle and its separation of stable
anchoring from conditional semantic reasoning.
