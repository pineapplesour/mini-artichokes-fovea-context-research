# Review: Mini Artichokes: Recursive Verified Redundancy for Test-Available Program Repair

## Summary

This paper presents Mini Artichokes, a test-available program-repair system that preserves complete verifier-passing task states as immutable anchors and applies heterogeneous repair routes only to unresolved tasks. Its strongest contribution is a carefully specified verified-union composition: Mini reaches 139/178 Aider tasks versus 132/178 for a nominally five-call Generic-plus-Direct portfolio. However, the evidence for semantic overlap and completion locking as causal improvements is limited, and the clean prospective matched comparisons are mostly ties or single-task differences.

## Strengths

- The preservation mechanism is clearly formalized under explicit assumptions. Under A1–A5, “no unverified merged state is created,” and the output “passes every task in `A union (union_k S_k)`.”

- The evaluation retains complete benchmark inventories. The paper evaluates “all 30 official Rust tasks, all 34 Python tasks, and all 26 C++ tasks,” followed by complete Go39, JavaScript49, and HumanEvalFixDocs populations, with “No task ... ranked, screened, removed, replaced, or topped up.”

- The system produces substantial effectiveness gains over cheaper baselines. On the original Aider tracks it reaches “59/90,” compared with “45/90” for ordinary repair and “15/90” for Plain; on JavaScript it reaches “47/49” versus “42/49” and “27/49.”

- The controls are stronger than a simple one-pass baseline. The semantic-free control uses “the same ledger fields, counterexample-based falsification, and two audits as TOV,” while withholding candidate relations.

- The paper is unusually candid about evidential boundaries and failures. It states that a “repeatable standalone semantic-relation effect” is “Not established,” retains the Rust `fizzy` harm, and explicitly identifies the five-track comparison as “mixed-stage.”

- The artifact and protocol reporting is detailed, including hashes, byte audits, transport failures, runtime deviations, token counts, and latency. This makes the experimental claims substantially more auditable.

## Weaknesses

- The strongest matched-system result is not sufficiently prospective or robust. The five-track comparison is 139/178 versus 132/178, but the paper acknowledges that it is “mixed-stage,” that Go uses a post-result replacement, and that the clean prospective JavaScript comparison is an exact tie at 47/49. The prospective Java result is only one rescue, with “one-sided `p=.5`.” Thus the evidence supports a bounded realized-portfolio advantage, but not a reliable general superiority claim.

- The semantic-overlap effect is underidentified. The semantic-free control “was frozen only after all TOV outcomes and the MAC v9 critique were known,” and the paper calls the original +7/90 contrast “review-triggered and post hoc.” The later replications yield means of only +1.2/34 and +0.4/26, with intervals `[-2.35,+8.24]` and `[-6.92,+11.54]` percentage points. This leaves open whether the original gain reflects semantic relations, prompt differences, or trajectory variance.

- Recursive promotion is formally useful but algorithmically simple. The authors state that “a minimal task-wise verifier union is algebraically identical to this promotion rule” and make “no claim a new selector beyond that max operation.” Consequently, the scientific novelty rests mainly on the composition and route construction, while much of the gain may come from adding another repair call and taking a verifier-wise union.

- Equal nominal call counts do not imply equal resource usage. The paper reports that TOV takes “29.6 more seconds” than the semantic-free control, and on JavaScript uses “4.35% more input tokens and 3.70% more time.” The comparisons therefore establish bounded-call effectiveness, not superiority under matched latency, tokens, or cost.

- The task-level statistical tests provide limited evidence about generalization. “All task rows within one arm share one whole-track model call,” and the paper says the tests “condition on the realized calls.” The five-pair replications on only two tracks are informative about trajectory variance but too small to establish performance across models, sessions, languages, or benchmark populations.

- The proposed semantic representation is not independently validated. Integrity checks “do not score the natural-language diagnoses for semantic correctness,” and the interface-ambiguity explanation is explicitly “a hypothesis for prospective testing.” The ledgers therefore document intended reasoning structure, but do not demonstrate that semantic overlap is measured accurately or predicts successful repairs.

- Applicability is narrower than the title and broader framing may suggest. The guarantee requires “tasks [to be] partitioned into task units” with isolated workspaces, complete file ownership, and stable verifiers. The paper concedes that anchors preserve “benchmark passes, not proof of correctness beyond those tests.” Real repositories with shared build state, flaky tests, weak tests, or no tests remain untested.

- Comparisons to external repair systems are limited. The paper states that Graph and the other methods are “bounded prompt-level realizations” and that it does not compare “a full contemporary repository agent such as KIRA under matched verifier access, calls, and tokens.” The results therefore establish an internally controlled systems comparison rather than state-of-the-art competitiveness.

## Questions for the Authors

1. Can the authors run a preregistered multi-session comparison between Mini and Direct∪Generic with matched realized token, reasoning, or wall-clock budgets?

2. Can anchoring, recursive promotion, semantic relations, and completion locking be isolated through a factorial or sequential ablation using independently generated candidate artifacts?

3. Can blinded annotators score TOV ledger fields and failure-closure witnesses before outcome inspection, then test whether their quality predicts rescues or harms?

4. Can the Java164 completion-lock rescue be replicated on additional independently frozen languages or benchmark families?

5. How does the preservation rule behave with shared files, cross-task dependencies, nondeterministic tests, and incomplete or flaky verifiers?

## Scores

Soundness: 3/4 — The construction and reporting are careful, but causal attribution and generalization remain limited.

Presentation: 3/4 — The paper is transparent and well organized, though the many stages and caveats obscure the central evidence hierarchy.

Significance: 3/4 — Verifier-backed redundancy is practically useful in test-available repair, but broader impact and efficiency are not demonstrated.

Originality: 3/4 — The composition of immutable anchors, unresolved-only branching, heterogeneous routes, and recursive promotion is meaningful, although the union operation itself is simple.

Overall recommendation: 3/6 — Borderline; the system is promising, but superiority over matched alternatives is not yet convincingly established.

Confidence: 4/5 — The paper is sufficiently self-contained for a substantive assessment, although the underlying executions cannot be independently rerun here.

## Ethics and Limitations

The study uses public programming tasks and no human participants. It appropriately notes that “Models never receive private test source or gold implementations,” while recognizing that failure output can reveal behavioral expectations. Compute consumption, latency, token usage, and upstream licensing are disclosed.

The authors candidly acknowledge the main limitations: one model and runtime, correlated whole-track trajectories, limited independent sessions, post-hoc components, incomplete resource matching, runtime deviations for Python and Java, finite test specifications, prompt-level baselines, and dependence on modular stable verifiers. These limitations materially constrain claims beyond test-available benchmark repair.

## Comment

I recommend borderline reject. The paper makes a credible case for a useful verifier-backed portfolio construction and a sound conditional preservation property. The decisive missing evidence is a prospective, independently repeated, resource-matched comparison that separates the mechanical benefit of verified union and extra routes from the claimed benefit of semantic overlap and completion locking.
