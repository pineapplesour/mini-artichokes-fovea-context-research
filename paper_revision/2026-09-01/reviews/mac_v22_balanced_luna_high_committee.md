# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper presents Mini Artichokes, a five-call program-repair system that freezes complete task states passing official tests, restricts further repair to unresolved tasks, and recursively promotes passing outputs from heterogeneous repair routes. The evidence supports substantial bounded-call effectiveness over Plain and ordinary repair, but does not yet establish a stable causal advantage for semantic overlap or the proposed portfolio over a carefully matched generic alternative.

## Strengths

- The preservation mechanism is clearly specified and formally justified. Under assumptions A1–A5, “the recursively promoted output passes every task in `A union (union_k S_k)`,” because only complete, previously verified task states are copied.

- The evaluation retains complete benchmark inventories. The authors report “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” later adding all 39 Go and all 49 JavaScript tasks, rather than screening or topping up favorable examples.

- The paper includes meaningful controls beyond Plain. The semantic-free control uses “the same ledger fields, counterexample-based falsification, and two audits as TOV,” while withholding only the semantic relation field.

- The system-level gains are substantial in several settings. Mini reaches 59/90 versus 45/90 for ordinary repair and 15/90 for Plain; it reaches 33/39 on Go versus 25/39 and 17/39; and 47/49 on JavaScript versus 42/49 and 27/49.

- The authors report negative evidence and deviations candidly. They state that the Go Generic call was “transport-null,” that HumanEvalFix used “Python 3.13.11 rather than the protocol’s predeclared 3.13.5,” and that the motivating Java result did not repeat in five new pairs.

- The evidential claims are often appropriately qualified. The paper explicitly says that “the best-supported object is Mini Artichokes as a five-call effectiveness system, not semantic overlap as an isolated causal treatment.”

## Weaknesses

- The cleanest prospective equal-call comparison does not show an advantage for Mini. On JavaScript49, “Mini and Direct∪Generic are an exact tie: 0 rescues, 0 harms.” The headline 139/178 versus 132/178 comparison is mixed-stage, includes a post hoc Go replacement, and has only a track-level sign value of `p=.125`.

- The semantic-overlap contribution is not causally established. The original semantic-free control was frozen only after “all TOV outcomes and the MAC v9 critique were known,” while the independent paired replications produced wide, inconclusive session-level intervals: `[-2.35,+8.24]` pp for Python and `[-6.92,+11.54]` pp for C++.

- The large gains over Plain and ordinary repair bundle several interventions. The authors acknowledge that “Candidate diversity, external execution, the verified floor, and both final routes contribute,” and that the recursive rule is “algebraically identical” to a task-wise verifier union. Thus these results demonstrate a useful system, but do not identify anchoring, unresolved-only branching, semantic relations, or recursion as the load-bearing cause.

- Task-level significance is easy to overinterpret because “all task rows within one arm share one whole-track model call.” The reported task-level values such as `p=5.68e-14` and `p=.01953` therefore provide limited evidence about independent sessions or broader benchmark populations; the paper’s own track- and session-level analyses are more appropriate but underpowered.

- The semantic-free intervention is only a prompt-level ablation. The paper concedes that it “cannot make latent model trajectories identical,” and TOV and control also differ in realized tokens and latency. Observed differences may therefore reflect stochastic trajectories, attention allocation, or effort rather than semantic overlap specifically.

- The preservation theorem is conditional on strong practical assumptions. It requires “no cross-task test dependency,” isolated workspaces, complete allowlisted file tuples, and stable verification. Finite tests certify observed labels, not correctness beyond the suite, as the authors themselves state: “byte-exact anchors preserve benchmark passes, not proof of correctness beyond those tests.”

- Generalization remains limited. All semantic calls use “one model and runtime,” and the study focuses on modular, test-available tasks with informative failure output. The five-session replications are valuable, but “still do not estimate a broad language, model, or benchmark population.”

## Questions for the Authors

1. Can Mini and Direct∪Generic be compared prospectively across several unseen tracks and independently sampled sessions under matched realized output tokens, reasoning tokens, and wall-clock budgets?

2. What is the contribution of immutable anchoring, candidate diversity, unresolved-only branching, semantic relations, completion locking, and the second final route in a factorial ablation?

3. Can the semantic intervention be isolated by giving both agents identical diagnoses and varying only access to candidate relations?

4. How does the method detect or handle violations of A1–A5, including shared files, cross-task build state, nondeterministic tests, weak verifiers, and unavailable tests?

5. Does the fixed harness and promotion rule retain its benefit with a different model and runtime, as required by the claimed model-progress leverage?

## Scores

Soundness: 3/4 — The preservation construction is sound under explicit assumptions, but empirical causal attribution and prospective superiority remain limited.

Presentation: 3/4 — The paper is unusually transparent and well organized, although its many stages and evidential qualifications make the central claim difficult to prioritize.

Significance: 3/4 — Verified multi-route repair is practically useful in the test-available setting, but broader applicability is not demonstrated.

Originality: 3/4 — The enforced composition of immutable task anchors, unresolved-only repair, and heterogeneous route promotion is meaningful, although the underlying union operation is simple.

Overall recommendation: 3/6 — Borderline: the system result is credible and promising, but the proposed mechanism’s stable advantage over generic alternatives is not established.

Confidence: 4/5 — The paper provides sufficient methodological and numerical detail for assessment, though the underlying execution artifacts cannot be independently rerun here.

## Ethics and Limitations

The study uses public programming tasks and no human participants. It appropriately discusses licensing, inference cost, possible information leakage through failure output, benchmark contamination, and the distinction between test-available repair and ordinary code generation. The main limitations are substantive: one model and runtime, correlated whole-track trajectories, post hoc and protocol-deviating comparisons, nominal rather than realized compute matching, finite test suites, and dependence on task modularity and verifier stability.

## Comment

I recommend borderline acceptance. The most convincing contribution is the fail-closed preservation architecture, which prevents later repair from discarding already verified task successes. The authors should make this bounded verified-multi-route effectiveness claim central and provide prospective, session-level, compute-matched evidence before claiming that semantic overlap itself provides a reproducible advantage.
