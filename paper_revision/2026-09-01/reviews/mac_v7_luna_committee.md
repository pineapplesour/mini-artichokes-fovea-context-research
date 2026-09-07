# Review: Mini Artichokes: Bounded Verification for Selective LLM Arbitration and Program Repair

## Summary

This paper proposes a conservative second-pass framework that freezes an answer or code patch, invokes additional reasoning only after observable conflict or failure, restricts the update, and preserves unaffected work. It reports a significant gain over direct Luna on one disjoint 1,000-question MMLU-Pro replication, but no significant gain over compute-matched generic judging, and a narrow coding gain on “one fixed official task set.” The evidence supports a useful engineering pattern, but not the paper’s stronger mechanism-specific or generality claims.

## Strengths

- The arbitration policy is precise and auditable: “if not `(D2 == D3 and D2 != D1)`, return D1,” and the judge “cannot create a third answer.”

- The study separates routing from evidence and includes an appropriate matched control: OJ3 and GJ3 use the “same eligible IDs, anonymous candidate strings, rotation, model, reasoning effort, call count, and fallback.”

- The primary MMLU-Pro result uses full-denominator paired accounting: OJ3 achieved “28 rescues, 5 harms, +23 correct,” with `p=3.31e-5` and a bootstrap interval of `[+1.2,+3.5]` points.

- The paper is unusually candid about null and negative evidence. It reports that OJ3 “tied SC3 at 613/1,000,” that the legal reserve produced “30 rescues but 59 harms,” and that ordinary repair scored 27/100 versus 25/100 for matched repair.

- The coding analysis correctly treats five whole-batch sessions as the inferential units, explicitly stating: “The inferential result is five positive whole-session differences on one fixed official task set.”

- Protocol provenance is described carefully through frozen commits, hashes, prompts, scorers, and restrictions against “rerun, top-up, task deletion, prompt change, or extra session.”

## Weaknesses

- The main MMLU-Pro comparison is substantially compute-asymmetric. OJ3 used “45,973,780 tokens versus 13,009,321 for D1,” a 3.53-fold ratio. Against the closest compute-matched alternatives, it tied SC3 and achieved only “+2” over GJ3 with `p=.36328`. Thus, the strongest supported claim is that additional sampling plus judgment can improve over one direct draw—not that support-aware arbitration is superior to generic multi-call inference.

- The distinctive support-count mechanism is underpowered and unresolved. Only “68/2,000 questions triggered arbitration,” and OJ3 versus GJ3 differed on just 13 conflicts. The paper itself concedes that “the support annotation's incremental causal effect is unresolved.”

- The MMLU result is conditional on realized whole-file sessions, with notable instability. D2 scored “145/1,000” in confirmation 1 and “607/1,000” in replication 2; the authors state that the anomalous session’s “semantic cause remains unresolved.” The paired tests therefore do not establish robustness across repeated executions on the same items or estimate between-session variance.

- The coding result has limited external validity. All five confirmatory sessions reuse “the same frozen official Java20 set,” and the paper explicitly says this establishes “session repeatability on that fixed set, not new-task generality.” The earlier cross-language evidence also has only “three whole-batch call clusters.”

- The explicit structured-repair mechanism is not supported by the strongest control. Matched repair scored 25/100 versus 27/100 for ordinary repair, with matched-minus-ordinary mean `-2` and interval `[-7,+2]`. Since the matched arm bundles “failure feedback, counterexamples, preservation, and a double completion audit,” no individual component or the bundle is identified as necessary.

- The ordinary-repair control was commissioned “after the five-session matched results” were known. Although the paper correctly labels it secondary, this timing limits its ability to provide an unbiased confirmatory test of the structured intervention.

- The unified “bounded-update contract” is conceptually plausible but theoretically underdeveloped. The paper provides a behavioral contract, yet no expected-gain condition relates trigger precision, candidate correlation, judge error, and rescue/harm rates. Moreover, arbitration uses correlated model agreement while repair uses external hidden-test feedback, so the two experiments demonstrate an analogy rather than a common causal mechanism.

## Questions for the Authors

1. Can the authors provide a prospective, compute-matched evaluation of OJ3 versus GJ3 and SC3 with enough triggered conflicts to estimate the support-count effect?

2. Can the coding policy be evaluated on newly frozen tasks or independent repositories, with the ordinary-repair control specified before outcomes are observed?

3. How sensitive are the MMLU results to whole-file session initialization and context effects, particularly given the D2 result of 145/1,000 followed by 607/1,000?

4. What formal conditions would make the bounded-update policy beneficial, in terms of trigger prevalence, candidate correlation, judge accuracy, and the rescue-to-harm ratio?

5. Which components of structured repair are intended as essential, given that “no accuracy evidence” supports the explicit bundle or any individual component?

## Scores

Soundness: 3/4 — The accounting and caveats are careful, but the principal mechanism and generality claims remain weakly identified.

Presentation: 4/4 — The paper is clear, well organized, and precise about protocols, costs, and inferential boundaries.

Significance: 3/4 — The bounded-update framing and negative results are useful, but demonstrated advantages over strong matched alternatives are limited.

Originality: 3/4 — The framing and rescue/harm accounting are useful syntheses, although the underlying ingredients are largely familiar.

Overall recommendation: 3/6 — Borderline; the paper presents a credible narrow result but does not establish a novel mechanism or broad advantage.

Confidence: 4/5 — The manuscript is self-contained and sufficiently detailed to assess, although the underlying executions cannot be independently rerun here.

## Ethics and Limitations

The paper responsibly reports its compute burden—“45.97 million tokens across the two OJ3 cohorts”—and warns against treating same-model agreement as a reliability certificate in high-stakes settings. Its legal-data discussion is also appropriate: it acknowledges that facts may remain re-identifiable and withholds item texts and outputs pending governance review.

The principal limitations are the single model and runtime, whole-file session dependence, correlated same-model draws, rare arbitration triggers, approximate compute matching, fixed-task Java replication, incomplete Aider coverage, and the post-outcome timing of the ordinary-repair control. These limitations are clearly acknowledged, but they substantially constrain the scope of the conclusions.

## Comment

I recommend borderline acceptance at most. The strongest contribution is a careful demonstration that a separate evidence-informed second pass can improve a realized direct baseline under specific execution regimes, together with honest evidence that support metadata and elaborate repair instructions are not established causes. The authors should narrow the headline claim and prioritize a prospective compute-matched evaluation on newly frozen tasks that distinguishes generic benefit from the proposed bounded-update mechanism.

> Soundness capped at 2/4: 22 proven integrity breach(es). Overall recommendation capped at 2/6: 22 proven integrity breach(es).
