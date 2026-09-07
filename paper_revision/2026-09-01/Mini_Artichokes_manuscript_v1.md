# Mini Artichokes: Selective Arbitration of Repeated LLM Disagreement

## Abstract

Repeated inference can improve large-language-model (LLM) reasoning, but
correlated agreement is not proof and unconstrained self-correction can damage
an initially correct answer. We study whether answer overlap can instead serve
as a narrow, gold-free trigger for selective arbitration. Mini Artichokes draws
three independent complete-file solutions. It retains the first draw by
default and invokes an anonymous judge only when the second and third draws
agree with each other and disagree with the first. The judge chooses between
the two existing candidates and cannot synthesize a new answer. Our
support-aware variant shows the same candidates and anonymous rotation as a
matched generic judge, adding only the mechanical one-versus-two support count
and a warning that consensus is not proof.

We froze the policy before evaluation on two disjoint, category-proportional
1,000-question samples from MMLU-Pro. The first sample was scored before the
second was generated; no policy, prompt, model, fallback, or statistic changed
between samples. Pooled over 2,000 questions, support-aware Mini Artichokes
scored 1,214/2,000 (60.70%) versus 1,187/2,000 (59.35%) for a direct Luna draw:
+27 correct, 33 rescues, 6 harms, one-sided exact McNemar p=7.15e-6, and a
20,000-sample paired-bootstrap 95% confidence interval of +0.75 to +1.95
percentage points. This passes the pre-frozen two-look alpha=.025 boundary.
The method was numerically highest but not significantly better than
three-draw majority voting (1,209/2,000; p=.0898) or a compute-matched generic
judge (1,211/2,000; p=.2539). It required four complete-file model calls and
3.53 times the tokens of direct Luna. A separate 464-case Korean legal-outcome
reserve produced the opposite result, identifying a boundary where answer
agreement was not informative. The evidence supports selective arbitration as
a statistically reliable improvement over direct inference on the tested
multiple-choice benchmark, while leaving the incremental value and
cross-domain generality of support annotation unresolved.

**Keywords:** large language models; test-time compute; self-consistency;
selective prediction; arbitration; multiple-choice reasoning

## 1 Introduction

Language models often revise their own answers at inference time. Such
revision is appealing because it needs neither additional training nor an
external verifier. Self-Refine, for example, alternates feedback and revision
with the same underlying model [1]. Yet intrinsic self-correction is unreliable
on reasoning tasks: models can fail to locate their own mistakes, accept false
criticisms, or replace a correct answer with an incorrect one [2-4]. The
central problem is therefore not merely how to spend more inference, but how
to decide when internally generated evidence is strong enough to authorize a
change.

Repeated sampling provides a different source of information. Standard
self-consistency samples multiple reasoning paths and returns the modal answer
[5]. Universal Self-Consistency (USC) replaces answer extraction with an LLM
selector for free-form outputs [6]. Multi-agent debate and verifier reranking
also compare several candidates before selecting an answer [7, 8]. These
methods show that diversity and selection can outperform a single trajectory.
They do not, however, make agreement infallible. Same-model samples share
training data, inductive biases, prompts, and systematic misconceptions;
several agents may confidently repeat the same error.

Mini Artichokes tests a conservative use of agreement. It does not replace a
base answer whenever a majority appears. It first uses a mechanical overlap
event to identify a small conflict set: two independent auxiliary draws agree
with one another and disagree with a preassigned base draw. Only those cases
are sent to an anonymous judge, and all other cases retain the base. This
separates two possible roles for overlap:

1. **routing:** agreement identifies cases worth re-examining; and
2. **evidence:** the judge may use the number of supporting draws when choosing
   between the candidates.

The distinction matters. A generic judge can benefit from seeing the question
and two alternatives even without support counts. A fair mechanism test must
therefore compare support-aware arbitration with both majority voting and a
judge that has the same model calls, candidate identities, anonymous rotation,
and conflict set.

We ask three research questions.

- **RQ1:** Does the frozen support-aware policy improve full-denominator
  accuracy over a preassigned direct Luna draw on fresh, disjoint MMLU-Pro
  samples?
- **RQ2:** Does it outperform strong multi-call controls: three-draw majority
  voting and a compute-matched generic judge?
- **RQ3:** How often does the policy rescue or harm the base answer, what does
  it cost, and where does its overlap signal stop being useful?

The contributions are empirical and deliberately bounded. First, we define an
executable selective-arbitration policy with a gold-free trigger, anonymous
candidate rotation, no-synthesis judge, and base-preserving fallback. Second,
we evaluate it with two disjoint 1,000-question samples, a policy-unchanged
replication, paired exact tests, confidence intervals, and an explicit
multiplicity boundary. Third, we isolate the effects of consensus and generic
judgment, disclose the complete compute asymmetry, and report a negative legal
boundary condition. Infrastructure receipts and hashes support provenance;
they are not treated as a scientific contribution.

## 2 Related work

### 2.1 Intrinsic self-correction

Self-Refine showed that a single model can generate feedback and iteratively
revise its output across diverse tasks without additional training [1]. This
positive result motivated many inference-time feedback loops. Reasoning tasks
also expose a serious limitation. Huang et al. found that models generally did
not improve reasoning through intrinsic self-correction without external
feedback and sometimes degraded [2]. Stechly et al. reported limitations in
self-verification across reasoning and planning [3], while Valmeekam et al.
found that LLM self-critique could reduce planning performance relative to
sound external verification [4]. Mini Artichokes does not ask a model to revise
its own rationale repeatedly. It limits correction to a discrete choice
between two already generated answers and defaults to no change.

### 2.2 Sampling and consistency

Self-consistency samples diverse chain-of-thought paths and marginalizes over
their final answers [5]. It is a natural strong baseline for stable-answer
reasoning tasks. USC generalizes selection to outputs for which deterministic
answer extraction is difficult by asking an LLM to select the most consistent
candidate [6]. Mini Artichokes shares their use of repeated samples but differs
in its asymmetric operating point: D1 is fixed as the base, D2 and D3 only
trigger review when they agree against D1, and a judge may still retain D1.
Thus, consensus authorizes review rather than automatically authorizing a
switch.

### 2.3 Debate, verifiers, and candidate selection

Multi-agent debate lets several model instances exchange arguments before a
final answer is selected [7]. Training verifiers to rank many sampled
solutions can also improve mathematical reasoning [8]. Our setting uses no
trained reward model, debate transcript, external execution result, or gold
feedback. The arbitration judge sees the original multiple-choice question and
two anonymous candidate answers. The matched GJ3/OJ3 comparison is intended to
separate ordinary candidate judgment from the additional support annotation.

### 2.4 Positioning

The closest interpretation of Mini Artichokes is a selective ensemble with an
LLM tie-breaker. Its novelty claim is not that multiple samples or LLM judges
are new. The contribution is the preassigned-base conflict policy and its
controlled evidence: same conflict set, same anonymous candidates, same judge
budget, full-denominator paired statistics, unchanged replication, and an
explicit negative domain boundary. The experiments also revise the original
mechanistic intuition. Agreement is supported as a routing signal on MMLU-Pro;
its incremental value as judge-side evidence is not statistically established.

## 3 Method

### 3.1 Setting and notation

Let a multiple-choice problem be x=(q,A), where q is the question and
A=(a1,...,aK) contains K≤10 answer options. A model session
returns free text, which is mapped deterministically to one option index. An
unmapped response is invalid and is counted wrong in evaluation.

Three independent sessions of the same solver and configuration produce
D1(x), D2(x), and D3(x). The draw roles are fixed before any answer is scored:
D1 is the base, and D2/D3 are auxiliary draws. No draw is selected as
the base after inspecting its quality.

Define the eligible conflict indicator as C(x)=1 when D1, D2, and D3 are all
valid and D2=D3≠D1; otherwise C(x)=0.

The conflict is computed without access to gold labels. On C(x)=0, both
judge arms return D1. On C(x)=1, the two candidate answers are the
base b=D1 and consensus candidate c=D2=D3.

### 3.2 Baseline arms

**D1 (direct Luna).** Return the preassigned first draw.

**SC3 (three-draw self-consistency).** Return any valid option supported by at
least two draws; if there is no majority, return D1. When all three draws are
valid, SC3 differs from D1 exactly on eligible conflicts. It can also differ
when D1 is invalid and valid D2 and D3 agree. A post hoc boundary audit found
no such row in confirmation 1 and two in replication 2; the consensus answer
was wrong on both, as was invalid D1, so strict all-valid gating would leave
every reported score and comparison unchanged.

**GJ3 (matched generic judge).** On eligible conflicts, rotate (b) and (c)
deterministically into anonymous labels C1/C2. A fourth independent Luna
session receives the question and the two candidates and must return one
candidate exactly. It is not told which is the base or how many draws support
either candidate. Invalid output retains D1.

### 3.3 Support-aware selective arbitration (OJ3)

OJ3 uses the same eligible IDs, anonymous candidate strings, rotation, model,
reasoning effort, call count, and fallback as GJ3. It adds only a mechanical
support record stating that one anonymous candidate has one complete-file draw
and the other has two. Its instruction explicitly says that independent
agreement is a fallible signal rather than proof. The judge must solve or
check the question, may use the support count as a prior, and cannot create a
third answer.

The policy is:

```text
Input: question x; independent mapped answers D1, D2, D3
if D1, D2, or D3 is invalid:
    return D1
if not (D2 == D3 and D2 != D1):
    return D1
rotate candidates {base: D1, consensus: D2} into anonymous {C1, C2}
show the judge x, C1, C2, and their mechanical support counts (1 or 2)
if the judge returns exactly C1 or C2:
    return the corresponding existing answer
return D1
```

This design prevents three common confounds. It does not search thresholds
after scoring, it does not expose candidate provenance, and it does not let
the judge improve an answer by synthesizing new content. Comparing OJ3 with
GJ3 isolates the support annotation conditional on the same trigger and
candidate-selection opportunity.

### 3.4 Claim and safety boundary

OJ3 is not described as a validated proof system. “Support-aware” refers only
to the number of independent complete-file draws producing an answer. The
system makes no claim that the draws are statistically independent at the
model level; they are separate sessions of the same model and can share
systematic errors. The base-preserving fallback is a policy choice whose net
value must be measured through paired rescues and harms.

## 4 Experimental design

### 4.1 Benchmark and disjoint sampling

MMLU-Pro is a 14-category, up-to-ten-option benchmark designed to contain more
reasoning-focused and discriminative questions than MMLU [9]. We used the
official TIGER-Lab test parquet at Git commit
`b189ec765aa7ed75c8acfea42df31fdae71f97be`. Its SHA-256 was
`0e24a191...c1ecb9ad8` and it contained 12,032 rows.

Question selection was deterministic, category proportional, and independent
of the answer and chain-of-thought fields. Within category, rows were ranked
by a fixed-seed SHA hash. Confirmation 1 used ranks 0-999. After that cohort
was completely scored, replication 2 was frozen as the immediately following
category-proportional allocation, equivalent to cumulative ranks 1,000-1,999.
The two public ID sets have intersection zero and union size 2,000. Public
question files and private gold files were stored separately, and private gold
was not mounted into any model workspace.

### 4.2 Model sessions

Every semantic arm used `gpt-5.6-luna` with high reasoning effort through the
Codex command-line runtime. Each D1-D3 draw processed all 1,000 public rows in
one isolated complete-file session. Sessions could read the immutable input
file and use a local shell for parsing and arithmetic, but network access, web
search, retrieval, memories, plugins, applications, MCP services, and
multi-agent delegation were disabled. Candidate sessions could not read one
another's outputs. GJ3 and OJ3 were each one additional complete-file session
over the frozen conflict set. Provider temperature was neither exposed nor
user-configurable in this runtime. No model training or fine-tuning occurred,
so training hyperparameters are not applicable.

The whole-file design measures an agentic batch-solving regime rather than
independent per-question API calls. It permits cache reuse and within-session
context effects. We therefore report actual calls, input, cached input,
output/reasoning tokens, elapsed time, invalid mappings, and all accepted
receipts. These execution records establish what ran but do not count as
scientific performance. The two cohorts used independently initialized
whole-file sessions on different questions; they do not constitute repeated
executions on the same items. Consequently, the paired tests below quantify
item-level uncertainty conditional on the realized sessions, not
between-session variance of the complete pipeline.

### 4.3 Freezing and replication

Confirmation 1 contained 1,000 questions and 14 eligible conflicts. It showed
OJ3 601 versus D1 597 (5 rescues, 1 harm; one-sided p=.1094). Because the
direction was favorable but underpowered, we froze exactly one disjoint
1,000-question replication. We did not change any policy, prompt, model,
effort, role mapping, conflict rule, fallback, or statistic. No third cohort is
allowed under the protocol.

The first cohort constitutes an interim look. To bound the two-look familywise
error at .05, the pooled 2,000-question headline test uses conservative
one-sided alpha=.025. The first look did not cross .025.

### 4.4 Outcomes and statistical analysis

Accuracy is computed on the full 1,000- or 2,000-question denominator;
unmapped outputs are wrong. For a candidate arm (S) and reference (R), a
rescue is (S) correct and (R) wrong, while a harm is (S) wrong and (R)
correct. The primary p-value is the exact one-sided McNemar/binomial upper tail
on discordant pairs. We also report two-sided exact p-values and 20,000-sample
paired-bootstrap confidence intervals. The cumulative bootstrap resamples
within `(cohort, category)` strata.

The pre-frozen cumulative fixed sequence at alpha=.025 is:

1. OJ3 > D1;
2. OJ3 > SC3;
3. OJ3 > GJ3.

Formal rejection stops after the first unrejected comparison. We report all
point estimates and p-values regardless of sequence reach. Category-specific
policies, row exceptions, post-score remapping, and item-level retries are
prohibited.

### 4.5 Prior development and domain-boundary data

The policy family was developed on a separate 941-row Universal Artichoke
multiple-choice set. Those data were repeatedly inspected and are not
confirmation evidence. The strict V3 development arm improved 566 to 587
(30 rescues, 9 harms; p=.0005325).

We also froze a 464-case, class-balanced Korean civil/tax outcome reserve from
a local 526-case precedent corpus. The selected records comprised 384 entries
labelled as Korean Law Open Data precedents, 75 from LBox Open, and five with
the local source label `lawlaw` [12-14]. Public model packets omitted the
holding and replaced source court, case number, and decision date with fixed
placeholders when present; this affected 116 selected records (288 court, 91
case-number, and 100 date-field replacements, with multiple fields possible
per record). This is metadata minimization, not a claim of comprehensive
de-identification. Each packet contained a partial fact pattern, and the
target was whether the court granted or dismissed the claim. The preassigned
plain-instruction Luna arm was named P1; D1-D3 were separate structured draws
used by the multi-draw policies. The legal reserve is reported separately and
is never pooled with MMLU-Pro.

## 5 Results

### 5.1 Accuracy by cohort

Table 1 gives full-denominator accuracy. OJ3 had the highest count in both
cohorts, although it tied SC3 in replication 2. D2 was an extreme low outlier
in confirmation 1 (145/1,000) but recovered to 607/1,000 in replication 2;
this instability is considered in the limitations.

**Table 1. Full-denominator MMLU-Pro accuracy.**

| Arm | Confirmation 1 correct | Replication 2 correct | Pooled correct | Pooled accuracy |
|---|---:|---:|---:|---:|
| D1 direct Luna | 597 | 590 | 1,187 | 59.35% |
| D2 | 145 | 607 | 752 | 37.60% |
| D3 | 587 | 586 | 1,173 | 58.65% |
| SC3 majority | 596 | 613 | 1,209 | 60.45% |
| GJ3 generic judge | 600 | 611 | 1,211 | 60.55% |
| **OJ3 support-aware judge** | **601** | **613** | **1,214** | **60.70%** |

Each cohort contains 1,000 questions; the pooled denominator is 2,000.

### 5.2 Confirmatory paired results

OJ3 improved over D1 by 27 correct answers (+1.35 percentage points), with 33
rescues and 6 harms (Table 2). The one-sided exact p-value was 7.15e-6 and the
paired-bootstrap interval excluded zero. This rejects the first fixed-sequence
hypothesis at alpha=.025.

The second comparison did not reject: OJ3 exceeded SC3 by five answers, but
p=.0898 and the confidence interval crossed zero. The third comparison was
therefore not formally reached. OJ3 exceeded GJ3 by three answers, with p=.2539.
Consequently, the supported superiority claim is OJ3 over direct Luna, not
over either strong multi-call control.

**Table 2. Pooled paired comparisons over 2,000 questions.**

| Comparison | Rescues | Harms | Net correct | One-sided exact McNemar p | CI lower pp | CI upper pp |
|---|---:|---:|---:|---:|---:|---:|
| **OJ3 vs D1** | **33** | **6** | **+27** | **7.15e-6** | **+0.75** | **+1.95** |
| OJ3 vs SC3 | 7 | 2 | +5 | .08984 | -0.05 | +0.55 |
| OJ3 vs GJ3 | 6 | 3 | +3 | .25391 | -0.15 | +0.45 |
| SC3 vs D1 | 35 | 13 | +22 | .001044 | +0.45 | +1.80 |
| GJ3 vs D1 | 29 | 5 | +24 | 1.93e-5 | +0.65 | +1.80 |

Replication 2 independently showed OJ3 613/1,000 versus D1 590/1,000: 28
rescues, 5 harms, +2.3 percentage points, one-sided exact p=3.31e-5, and paired
bootstrap 95% CI [+1.2,+3.5] percentage points. Confirmation 1 was
directionally consistent (+4) but contained only 14 conflicts and was not
significant by itself.

### 5.3 Descriptive mechanism analysis

The gold-free trigger fired on 68/2,000 questions (3.4%). Table 3 decomposes
these conflicts. D1/base was correct on 13; the two-draw consensus was correct
on 35; both candidates were wrong on 20. Thus, agreement was informative on
MMLU-Pro but far from sufficient.

SC3 always selected consensus and scored 35/68 conflicts. OJ3 selected
consensus 52 times and base 16 times, scoring 40/68. Among the 16 base-retention
decisions, accuracy differed on nine: base won seven and consensus won two;
both candidates were wrong on seven. Selective retention therefore added five
correct answers over always following consensus.

GJ3 selected consensus 47 times and base 21 times, scoring 37/68. OJ3 and GJ3
chose different candidates on 13 conflicts; OJ3 won six, GJ3 won three, and
both candidates were wrong on four. This +3 pattern explains OJ3's higher point
estimate but is not statistically conclusive.

**Table 3. Descriptive conflict-set decomposition.**

| Policy or event | Count correct / 68 | Selection detail |
|---|---:|---|
| D1/base | 13 | Preassigned first draw |
| D2=D3 consensus / SC3 | 35 | Consensus on all 68 conflicts |
| GJ3 | 37 | 47 consensus; 21 base |
| OJ3 | **40** | 52 consensus; 16 base |
| Both candidates wrong | 20 | No judge could synthesize a third answer |

These diagnostics support two limited conclusions. Agreement identified a
subset where switching was often beneficial, and arbitration filtered some
consensus harms. They do not prove that displaying support counts caused the
increment over GJ3.

### 5.4 Compute and latency

OJ3 is not compute matched to direct Luna. Across both cohorts, it consumed
45,973,780 tokens versus 13,009,321 for D1, a 3.53-fold ratio (Table 4). It is
closely compute matched to GJ3; the difference was 186,131 tokens (0.41% of
GJ3). The selective OJ3 judge stage added 917,347 tokens over SC3, or 2.04% of
the three-draw total, and processed only 68 conflicts.

**Table 4. Observed compute across both MMLU-Pro cohorts.**

| System | Semantic calls | Total tokens | Token ratio to D1 |
|---|---:|---:|---:|
| D1 | 1 | 13,009,321 | 1.00x |
| SC3 | 3 | 45,056,433 | 3.46x |
| GJ3 | 4 | 45,787,649 | 3.52x |
| OJ3 | 4 | 45,973,780 | 3.53x |

If D1-D3 are parallelized, observed OJ3 critical paths were 1,820.7 seconds
and 1,935.3 seconds for the two cohorts, compared with 1,375.1 and 1,101.9
seconds for D1. These measurements depend on the whole-file runtime and do not
establish deployment efficiency.

### 5.5 Development result and negative legal boundary

The Universal development result was directionally consistent with the fresh
MMLU-Pro evidence: a stricter overlap policy improved 566/941 to 587/941 (+21;
30 rescues, 9 harms; p=.0005325). Because the policy family was selected on
that set, the result is hypothesis-generating only.

The legal reserve did not transfer. The direct plain-instruction P1 arm scored
284/464 (61.21%); structured D1 scored 259/464 (55.82%), GJ3 263/464
(56.68%), and OJ3 255/464 (54.96%). Relative to P1, OJ3 produced 30 rescues
but 59 harms, a net loss of 29. On 65 cases carrying the mechanical support
signal, the supported outcome was correct only 32 times (49.2%). This negative
result contradicts a domain-general advantage. It is consistent with shared
assumptions becoming harmful under partial observation, but it does not
isolate underdetermination from concurrent changes in domain, task, prompt,
and label structure.

## 6 Discussion

### 6.1 What the experiment establishes

The strongest result is straightforward: the unchanged OJ3 policy improved
direct Luna on two disjoint MMLU-Pro samples, and the pooled paired effect
passed a conservative two-look threshold. The result is not driven by deleting
invalid rows, choosing a better direct draw after scoring, or evaluating only
the triggered subset. It is a full-denominator comparison against the
preassigned D1 draw.

The experiment also establishes that most of the gain is not uniquely
attributable to the support annotation. SC3 and GJ3 both significantly improved
over D1. OJ3 was numerically highest, and its decisions were favorable in the
small set where it differed from GJ3, but the incremental comparison lacked
power. This is scientifically more informative than treating “validated
overlap” as a monolithic mechanism: answer agreement is useful for routing,
generic question-level judgment is useful for arbitration, and the additional
support count remains a candidate mechanism rather than a confirmed one.

### 6.2 When selective arbitration is appropriate

The tested policy is most plausible for discrete tasks with stable answer
mapping, a unique keyed answer, and enough value per question to justify
roughly 3.5 times the inference tokens. It may be useful when an existing base
answer should be preserved unless a reproducible conflict appears. It is less
appropriate for cheap, high-volume inference; tasks where answers cannot be
mapped reliably; or outcome prediction from incomplete evidence.

The legal result is not an incidental null. One plausible explanation is that,
for a partial fact pattern, two sessions agree because they make the same
unstated assumption rather than because the latent court outcome is
determined. The present contrast cannot identify that mechanism, because
domain, task, prompt, and label structure changed together. Future routing
rules should separately manipulate answer determinacy while holding those
factors fixed.

### 6.3 Relationship to self-correction

Mini Artichokes avoids a long critique-rewrite loop. Its correction is a
selection between fixed candidates, which prevents a judge from introducing a
novel third error. The design therefore converts self-correction into selective
arbitration. This does not solve the general self-verification problem
identified in prior work [2-4], but it reduces the surface on which false
critique can act.

### 6.4 Practical trade-off

The absolute pooled improvement was 1.35 percentage points at 3.53 times D1's
tokens. Whether that trade is worthwhile depends on application value and
latency. OJ3's judge stage was relatively small once three draws had already
been purchased, but the three-draw candidate cost dominated the system. Thus,
the method is a fallback or batch-quality policy, not a general efficiency
claim. A future system should route before generating all auxiliary draws if a
reliable pre-inference uncertainty signal is available.

## 7 Limitations

First, confirmation covers one model, one runtime, and one primary benchmark.
MMLU-Pro spans 14 disciplines but remains multiple choice, and benchmark
questions may have been present in model training. “Fresh” here means not used
for policy development and disjoint between the two samples; it does not mean
post-training or contamination-free.

Second, each 1,000-question draw was generated in one complete-file agent
session. Answers can be affected by within-session context, cache behavior,
file parsing, and local computation. The anomalous D2 result in confirmation 1
(14.5%) demonstrates session-level instability. Although D1 was fixed before
scoring and replication 2 recovered on a disjoint question set, no full
pipeline was rerun on identical items. The reported paired p-values and
bootstrap intervals therefore condition on the realized sessions and do not
estimate between-session repeatability. Per-question independent inference may
produce different variance and conflict rates.

Third, the three candidate sessions and the judge use the same model family.
Separate sessions do not create model-level independence. Correlated errors
remain, as shown by 20/68 MMLU-Pro conflicts where both candidates were wrong
and by the legal boundary result.

Fourth, only 68/2,000 questions triggered arbitration. This was sufficient for
the direct-Luna comparison but not for a precise OJ3-versus-GJ3 estimate. The
support annotation's incremental causal effect is unresolved.

Fifth, compute matching is approximate in tokens rather than exact in cached
and uncached cost, wall time, or monetary price. OJ3 and GJ3 have equal
semantic call counts and nearly equal observed tokens, but their prompts are
not byte-identical because the support record is the treatment.

Sixth, the legal reserve is a useful negative boundary but not a comprehensive
domain study. It contains Korean civil and tax cases, uses partial fact
patterns, and predicts a binary judicial outcome. It simultaneously changes
domain, task, prompt, and label structure relative to MMLU-Pro, so it cannot
identify why transfer failed. Five selected records retain a legacy local
source label for which reuse metadata was not recoverable. The result should
not be generalized to legal question answering with complete statutes and
facts.

Finally, the protocol allowed one replication after an interim look and used a
Bonferroni-style alpha=.025 boundary. No further cohort can be interpreted as
part of the same confirmatory family without a new protocol.

## 8 Ethics and environmental considerations

This study evaluates public benchmark questions and locally curated Korean
precedent text; it does not recruit human participants. The legal pipeline
removed outcome text from model input and minimized direct source metadata,
but it did not establish full de-identification of facts. Court decisions can
remain re-identifiable through distinctive events, and five selected records
have no recoverable reuse metadata beyond a legacy source label. We therefore
report only aggregate legal results and do not release those item texts or
model outputs pending a separate governance review. The method also increases
inference compute by design, consuming 45.97 million tokens across the two OJ3
cohorts. Reporting that cost is necessary because modest accuracy gains can be
misleading when their resource burden is hidden. The negative legal result
cautions against deploying same-model agreement as a reliability signal in
high-stakes decision support without external evidence and domain-specific
validation.

## 9 Conclusion

Mini Artichokes turns repeated-answer overlap into a selective review trigger
rather than a claim of truth. On two disjoint MMLU-Pro samples, the frozen
support-aware policy significantly improved a preassigned direct Luna draw and
had the highest pooled point estimate among the tested arms. Three-draw
majority voting and a compute-matched generic judge captured most of the gain,
however, and the incremental support annotation was not statistically
established. A negative legal reserve further showed that agreement can become
uninformative when the input does not determine a unique outcome. The useful
result is therefore narrow: selective arbitration can improve repeated LLM
reasoning on the tested multiple-choice regime, provided its compute cost and
domain boundary are made explicit.

## Data and code availability

The double-blind artifact contains the MMLU-Pro public benchmark IDs,
deterministic selection code, frozen protocols, exact prompts, accepted
candidate and judge outputs, private-score scripts, aggregate reports, and
tests. Private gold was kept separate from model workspaces. For the legal
reserve, the artifact contains the frozen protocol and aggregate negative
boundary statistics only; item texts and outputs are withheld for the
governance reasons above. The pooled MMLU-Pro score artifact has SHA-256
`bdf7e36abcf05b8a05d921a259590b919f54da2b7a1658dcc4057acabc905fec`.

## References

1. Madaan A, Tandon N, Gupta P, et al. Self-Refine: Iterative Refinement with
   Self-Feedback. Advances in Neural Information Processing Systems 36, 2023.
   https://proceedings.neurips.cc/paper_files/paper/2023/hash/91edff07232fb1b55a505a9e9f6c0ff3-Abstract-Conference.html
2. Huang J, Chen X, Mishra S, et al. Large Language Models Cannot Self-Correct
   Reasoning Yet. International Conference on Learning Representations, 2024.
   https://openreview.net/forum?id=IkmD3fKBPQ
3. Stechly K, Valmeekam K, Kambhampati S. On the Self-Verification Limitations
   of Large Language Models on Reasoning and Planning Tasks. arXiv:2402.08115,
   2024. https://arxiv.org/abs/2402.08115
4. Valmeekam K, Marquez M, Kambhampati S. Can Large Language Models Really
   Improve by Self-critiquing Their Own Plans? arXiv:2310.08118, 2023.
   https://arxiv.org/abs/2310.08118
5. Wang X, Wei J, Schuurmans D, et al. Self-Consistency Improves Chain of
   Thought Reasoning in Language Models. International Conference on Learning
   Representations, 2023. https://openreview.net/forum?id=1PL1NIMMrw
6. Chen X, Aksitov R, Alon U, et al. Universal Self-Consistency for Large
   Language Model Generation. arXiv:2311.17311, 2023.
   https://arxiv.org/abs/2311.17311
7. Du Y, Li S, Torralba A, Tenenbaum JB, Mordatch I. Improving Factuality and
   Reasoning in Language Models through Multiagent Debate. Proceedings of the
   41st International Conference on Machine Learning, PMLR 235:11733-11763,
   2024. https://proceedings.mlr.press/v235/du24e.html
8. Cobbe K, Kosaraju V, Bavarian M, et al. Training Verifiers to Solve Math
   Word Problems. arXiv:2110.14168, 2021.
   https://arxiv.org/abs/2110.14168
9. Wang Y, Ma X, Zhang G, et al. MMLU-Pro: A More Robust and Challenging
   Multi-Task Language Understanding Benchmark. Advances in Neural Information
   Processing Systems 37, Datasets and Benchmarks Track, 2024.
   https://proceedings.neurips.cc/paper_files/paper/2024/hash/ad236edc564f3e3156e1b2feafb99a24-Abstract.html
10. McNemar Q. Note on the Sampling Error of the Difference between Correlated
    Proportions or Percentages. Psychometrika 12:153-157, 1947.
11. Efron B, Tibshirani RJ. An Introduction to the Bootstrap. Chapman & Hall,
    1993.
12. joonhok-exo-ai. Korean Law Open Data Precedents. Hugging Face Datasets,
    dataset revision `b08a068a511d035537a612c5f4d104f0225ef806`, labelled
    OpenRAIL. https://huggingface.co/datasets/joonhok-exo-ai/korean_law_open_data_precedents
13. Hwang W, Lee D, Cho K, Lee H, Seo M. A Multi-Task Benchmark for Korean
    Legal Language Understanding and Judgement Prediction. NeurIPS Datasets
    and Benchmarks, 2022. The LBox Open repository is licensed CC BY-NC 4.0.
    https://github.com/lbox-kr/lbox-open
14. Korea Ministry of Government Legislation. National Law Information Center,
    Law Open Data precedent service. https://open.law.go.kr/LSO/openState/orgList.do
