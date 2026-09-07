# Working method section: contrast-guided overlap recombination

Status: a proposed replacement/extension for the experimental-method section,
not a revised submission or a claim of established superiority. The current
submitted-style manuscript and committee result remain v26 and 3/6. Complete
ClassEval-Pro results and fresh matched replication are still pending.

## Scientific question

Can a model's repair be useful even when the repaired program is no more
correct than its predecessor? A repair may fix one behavior while damaging
another. Selecting either complete program discards one of these improvements.
Mini Artichokes instead tests whether their complementary fragments can form
a better executable program, without another model invocation.

This question concerns problem-solving accuracy under a fixed model-call and
verification budget. Trace collection, isolation and artifact checks support
the experiment; they are not the proposed scientific contribution.

## Shared generation and repair history

All compared systems receive the same problem specification and model history.
Generate a complete implementation A. If A passes the full supplied verifier,
preserve it. Otherwise generate B once from the same specification, and select
the stronger observed original program P, preferring complete success and
then passing-case count, with stable A-first ties. If neither original passes,
make one ordinary feedback-repair call R. The repair sees both original
programs, their observed feedback and the selected starting program; it is not
given an overlap-specific reasoning instruction.

Thus each compared system uses at most three model calls. The ordinary system
selects between P and R using their actual outcomes. Post-repair systems use
the same history and may additionally evaluate a bounded number of code
mixtures. They preserve an already fully passing ordinary result unchanged.

## Overlapping traces as transplant hypotheses

Let E_c(X) be the method names executed by program X while running test c.
Let D be the methods whose implementations differ between P and R. For a
test that fails or errors in an anchor X but passes in the other program Y,
form the overlap

I_c(X,Y) = E_c(X) ∩ E_c(Y) ∩ D.

An observed contrast provides a donor direction; the intersection narrows
the methods whose implementations are exchanged. Neither contrast nor overlap
is a correctness certificate. Setup methods and correlated calls can remain
in the intersection, and the same method can participate in several unrelated
behaviors. Accordingly, I_c proposes executable transplants rather than
authorizing an untested final answer.

For every nonempty I_c, first copy its methods from Y into X while retaining
the anchor's surrounding module context; also consider the donor context when
it differs. Multi-method intersections additionally propose individual-method
transplants. Process witnesses by increasing intersection size, then stable
test identifier and anchor order. Exclude duplicate ASTs and intact parents.
If the trial budget is not filled, use the pre-existing conservative overlap
ranking as a fallback. Constructors are ordinary exchangeable methods, and
candidate-exclusive helper methods are retained in the common source space.

The implementation imposes the same fourteen differing-slot bound on both
policies. Non-composable problems remain in the benchmark denominator and
retain the ordinary baseline; they are not removed from evaluation.

## Actual verification and the strong comparator

Every proposed complete program is executed against the unchanged supplied
test suite. Only an actual full pass counts as a solved problem. Predicted
coverage, agreement between candidates and the union of their passing tests
are never added to the score. Before a full solution is found, retain the
observed candidate with the strongest actual passing-case count.

The principal algorithmic comparator samples mixtures uniformly from the same
source space with the same program-trial cap. It uses the same original and
repaired programs, helper enrichment and preservation rule. The ordinary
repair comparator establishes whether recombination adds useful behavior;
random recombination tests whether the overlap ordering earns its complexity.
Equal caps do not imply identical realized time. Report model calls/tokens,
actual verifier executions and available timings separately; do not omit
exploratory calls made for other systems in the parent campaign.

Because these comparisons reuse the exact same model outputs, the model cost
is shared, not merely matched by an invocation limit. The ordinary comparator
does not spend the extra recombination-verification budget and is therefore
not the equal-total-resource control. That role belongs to random recombination.
Recorded trial-suite timings exclude host-side candidate construction and
ranking overhead; they must not be described as total system latency.

## Relation to prior class-generation strategies

ClassEval-Pro evaluates independent fragment generation as its Compositional
strategy, and dependency-ordered generation as Bottom-Up and Top-Down.
[Chen et al., section 4.2](https://arxiv.org/html/2604.26923v1#S4.SS2).
Our proposed extension is a post-generation operation: it reuses complete
implementations and their observed execution contrasts to prioritize donor
transplants. It does not claim to introduce class decomposition or to
replicate those generation strategies. Published scores from different models
and inference protocols are related-work context, not matched control results.

## Verified motivating case, not aggregate evidence

In ClassEval-Pro task 43, original code passes 11 of 12 tests but omits a required
asset-metadata field. The ordinary repair adds that field, yet changes a
previously passing fulfillment state to Rejected rather than Delivered; it
also passes 11 of 12. The contrast-guided program combines the repaired
stock_asset implementation with the original request_fulfillment and
track_fulfillment implementations. A separate execution confirms 12 of 12.

The contrast-guided ordering finds this program on its first trial; uniform
recombination finds a successful program on trial 12. This is a concrete example
of recovering useful work from a regressive repair. Because the case motivated
the ordering, it is development evidence, not an independent confirmation.
At the sixteen-trial cap the two methods tie in the initial 58-task diagnostic.

## Required evaluation before a strong claim

The official 300-task inventory is the evaluation unit; no favorable task
subset is presented as a benchmark. Report the entire predeclared trial-budget
curve K ∈ {1,2,4,8,16}, rescues and harms against both comparators, and realized
resource use. Conditional task-level statistics and multiplicity correction
describe development outcomes but do not remove method-selection bias.
Fresh complete-inventory paired sessions are needed to establish repeatability.

The study is explicitly test-available program repair. Passing the supplied
verifier does not establish semantic correctness on all possible inputs.
Known benchmark/reference issues stay in the denominator and are disclosed;
they are not repaired into favorable scores. Until full results and replication
support it, the paper must not assert general overlap superiority, a 20-point
accuracy gain, or a committee score of 4/6.
