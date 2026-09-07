__Mini Artichokes: Validated\-Overlap Feedback for Tool\-Free LLM Self\-Correction__

__Abstract__

We study a tool\-free self\-correction setting in which a large language model \(LLM\) may call an application programming interface \(API\) repeatedly but receives no external feedback beyond its own verification and critique prompts\. We introduce Mini Artichokes, a verification\-and\-refinement loop that turns additional inference into a redundancy\-based correction signal: two independent diagnoses describe a failed solution, their shared error signature is extracted, and that overlap is validated before any correction is fed back to the solver\. The method is designed to make additional calls more informative by organizing them into independent diagnosis, overlap filtering, validation, and targeted revision\. We evaluate Mini Artichokes on heterogeneous Korean and mathematical benchmarks: Public Service Aptitude Test \(PSAT\) Linguistic Logic, a Legal Education Eligibility Test \(LEET\) Analytical Reasoning subset, Putnam 2024, and American Invitational Mathematics Examination \(AIME\) 2026\. Average full\-suite gains are modest, but the effect is concentrated on items that baseline first\-sample accuracy rarely solves\. On PSAT, pass@1 reaches 467/800 \(58\.4%\) whereas Mini Artichokes reaches 491/800 \(61\.4%\); under an oracle best\-of\-20 scoring view, pass@1 solves 25/40 items at least once, while Mini Artichokes solves 37/40\. The method also improves Putnam from 65/240 to 71/240, AIME from 61/300 to 82/300, and the exploratory LEET subset from 6/15 to 7/15\. These results should not be interpreted as evidence of compute efficiency over cost\-matched repeated sampling; instead, they show how structured self\-generated feedback can expand the set of reachable correct trajectories under a larger inference budget\. The evidence supports a narrower use case: Mini Artichokes is a high\-cost fallback loop for hard problems, expanding the set of items a base model can solve at all and offering a reusable harness\-level correction layer for agentic systems when extra inference is acceptable\.

__Keywords __Large language models · Self\-correction · Verification\-and\-refinement · Iterative reasoning · Tool\-free inference · Mathematical reasoning

# 1 Introduction

Large language models are increasingly used on tasks that require multi\-step reasoning, but their failures are not always corrected by simply asking the same model to critique and revise its own output\. In a self\-correction loop, an erroneous critique can be fed back into the next step, causing the model to amplify spurious issues or to replace one plausible but incorrect answer with another\. The difficulty is especially visible when the loop receives no external signal such as a unit test, retrieval result, formal checker, tool output or human intervention\.

This paper studies a constrained but practically relevant regime: pure application programming interface \(API\) repetition\. The model may be called many times and may be assigned different prompting roles, but it receives no information beyond the problem statement and its own verification or critique prompts\. We intentionally keep the method tool\-free to isolate whether internal feedback can be made more reliable, and to make the procedure easy to embed as a lightweight subroutine inside larger agentic systems that may later add external validators\.

Mini Artichokes is related to model\-agnostic verification\-and\-refinement pipelines for hard reasoning \[1\], iterative\-contextual\-refinement implementations \[2\], and broader test\-time improvement methods such as iterative self\-feedback \[4, 5\], self\-consistency \[6\] and Tree\-of\-Thoughts search \[7\]\. The distinguishing design choice is redundancy\-based feedback filtering: the loop does not directly trust a single critique or a larger retry budget\. Instead, it obtains two independent diagnoses, extracts the common core between them, validates that overlap against the current solution, and only then applies a correction\. This design makes extra inference useful as evidence about a shared failure mode rather than as unstructured retrying\.

The contribution is threefold\. First, we frame Mini Artichokes as a capability\-expansion fallback for hard items rather than as a cheap average\-accuracy booster\. Second, we describe a modular redundancy\-based correction layer that can wrap a solver, independent diagnostic passes, overlap filtering, and validation, and that can be combined with other agentic tools\. Third, we report both hard\-item gains and easy\-item regressions, motivating selective routing instead of always\-on deployment, while explicitly treating compute efficiency against cost\-matched repeated sampling as an open question for future work\.

# 2 Methods

## 2\.1 Problem setting and design goals

Given a problem x, the goal is to return a candidate answer y using only repeated language\-model calls\. The reported experiments exclude external tools, internet access, human feedback and task\-specific validators\. This restriction is not intended as a claim that tool\-free reasoning is preferable to tool\-augmented reasoning; rather, it defines a controlled setting for measuring whether self\-generated feedback can be filtered strongly enough to become useful\.

The architecture is designed around three principles\. The first is modularity: each role can be implemented as a prompt template and therefore reused with different base models\. The second is conservatism: the system should update a solution only when the alleged error is supported by independent diagnoses and a validation step\. The third is bounded exploration: the loop should restart rather than continue indefinitely when a trajectory becomes stagnant\.

## 2\.2 Mini Artichokes architecture

The method decomposes self\-correction into six roles, as summarized in Fig\. 1\. The Solver proposes an answer and, when useful, a supporting solution\. The Verifier checks the current candidate\. If the verifier accepts the candidate repeatedly, the loop terminates\. If the verifier rejects the candidate, two independent Diagnosers are asked to explain the failure\. An Overlap extractor then identifies the shared error signature between the two diagnoses, an Overlap validator checks whether the signature actually explains the failure, and a Corrector applies a targeted revision conditioned on the validated signature\.

The validated\-overlap step is the central mechanism\. Unfiltered self\-critiques can be verbose, contradictory or hallucinated, and repeated calls by themselves do not guarantee a useful correction signal\. Mini Artichokes therefore feeds back only a small error signature that is both agreed upon by two independent diagnoses and explicitly validated against the problem and the current candidate answer\. This redundancy makes unsupported critiques less likely to destabilize the solver, while still preserving actionable information about a shared failure mode\.

## 2\.3 Solver quality floor and stopping rules

In the implementation used here, the Solver is not a single API call\. A short iterative\-contextual\-refinement\-style inner loop is used inside Solve to establish a minimum solution quality before downstream verification begins\. Development runs compared this inner loop with single\-shot solving, longer direct prompts and alternative role prompts; the inner loop was the most consistently reliable choice under comparable cost budgets \[2\]\.

To reduce false positives from the verifier, a solution is accepted only after p consecutive successful verifications\. Conversely, the loop applies early stopping after f consecutive failed verifications\. The reported gemma\-3\-27b\-it runs use p = 3 and f = 10, following the same general heuristic family used in the IMO25 pipeline \[1\]\. These values should be treated as model\-specific hyperparameters rather than universal constants\.

## 2\.4 Anti\-stagnation call cap

A per\-round call cap, denoted rcap, is introduced for both cost control and algorithmic efficacy\. In development runs, once a trajectory remained in a refinement loop for many calls, it often began to recycle earlier mistakes or to generate increasingly elaborate but unsupported repairs\. Terminating such a round and restarting from a fresher trajectory increased the chance of finding a different reasoning path\. The reported gemma\-3\-27b\-it configuration uses rcap = 35, although this threshold is expected to require retuning for other models\.

## 2\.5 Algorithmic procedure

Algorithm 1 summarizes the procedure\. The loop alternates verification and overlap\-based correction for at most M rounds, while the pass streak, fail streak and per\-round call cap provide acceptance and stopping safeguards\.

Algorithm 1  Mini Artichokes \(validated\-overlap verification\-and\-refinement\)  
Require: problem x, max rounds M, pass streak p, fail streak f, per\-round call cap rcap  
 1: y <\- Solve\(x\)  
 2: passes <\- 0; fails <\- 0  
 3: for r = 1 to M do  
 4:     \(ok, report\) <\- Verify\(x, y\)  
 5:     if ok then  
 6:         passes <\- passes \+ 1; fails <\- 0  
 7:         if passes >= p then return y  
 8:     else  
 9:         fails <\- fails \+ 1; passes <\- 0  
10:         d1 <\- Diagnose\(x, y, report\)  
11:         d2 <\- Diagnose\(x, y, report\)      // independent  
12:         o  <\- ExtractOverlap\(d1, d2\)  
13:         o  <\- ValidateOverlap\(x, y, report, o\)  
14:         y  <\- Correct\(x, y, o\)  
15:         if fails >= f then return y  
16:     end if  
17:     AntiStagnation\(rcap\)  
18: end for  
19: return y

## 2\.6 Implementation and attribution

The implementation is documented in a blinded repository entry \[3\]\. It is a lightweight runner that orchestrates the roles above through prompt templates and API calls\. The runner reuses and adapts ideas, and some scaffolding code, from the open\-source repositories associated with the IMO25 pipeline \[1, 13\] and iterative\-contextual\-refinement patterns \[2\]\. The reported experiments intentionally avoid tool integrations so that the results reflect the internal verification\-and\-refinement mechanism\.

## 2\.7 Experimental protocol

Most experiments use gemma\-3\-27b\-it because of cost constraints\. A small Legal Education Eligibility Test \(LEET\) subset was additionally run with gemini\-3\-flash\-preview to test whether the loop remains useful on a different commercial API model; the official model documentation is cited for reproducibility \[14\]\. The goal is not a vendor comparison, but a portability check\.

The evaluation uses four benchmark suites: Putnam 2024 problems A1\-A6 and B1\-B6 \[8, 9\], American Invitational Mathematics Examination \(AIME\) 2026 problems 1\-15 \[10\], 40 Public Service Aptitude Test \(PSAT\) 2025 Linguistic Logic items from the Korean National Civil Service Open Competitive Examination \[11\], and a small Legal Education Eligibility Test \(LEET\) 2026 Analytical Reasoning subset \[12\]\. Identifiers in the logs follow the numbering of each source\.

For each item, independent trials are repeated, typically 20 times and only 3 times for the LEET subset because of cost\. We report full\-suite accuracy as the primary aggregate metric\. We also report hard\-item lift, defined by items that pass@1 solves at most once in 20 trials on PSAT, because average accuracy alone can hide large improvements on low\-baseline items\. For answer\-choice or numeric suites with 20 repeated direct trials, we additionally report a conservative direct self\-consistency estimate: an item is counted as correct only when the correct answer appears in a strict majority of the 20 pass@1 samples\. The development tables additionally compare Mini Artichokes against direct solving, simple verifier\-guided critique\-and\-revise, and iterative contextual\-refinement baselines\.

Baseline comparisons are reported at two levels\. The main benchmark tables compare Mini Artichokes against direct first\-sample solving \(pass@1\) under repeated independent trials\. This comparison is intentionally not cost\-matched: pass@1 serves as a low\-cost direct\-solving reference, whereas Mini Artichokes is evaluated as a high\-cost fallback procedure\. Therefore, the main comparison measures whether the fallback loop can change the distribution of reachable correct solutions, not whether it is more compute\-efficient than direct repeated sampling under the same call budget\. The development tables position Mini Artichokes relative to simpler repeated\-inference baselines through a combination of matched spot\-checks and feature ablations, including a verifier\-guided critique\-and\-revise loop, an iterative contextual\-refinement loop, and a verifier loop without validated\-overlap feedback\. These development comparisons are not intended as fully powered suite\-level baselines, but they identify whether the validated\-overlap component changes behavior relative to simpler self\-correction loops\.

We distinguish repeated direct sampling from self\-consistency\. Repeated sampling asks whether at least one independent trajectory reaches a correct answer under a fixed budget; self\-consistency instead aggregates several direct samples, usually by majority vote over a stable final\-answer representation\. In this manuscript, the PSAT and AIME results support a conservative strict\-majority self\-consistency estimate from the repeated pass@1 trials, while best\-of\-20 is reported separately as an oracle repeated\-sampling view\. Because Putnam is proof\-style and does not reduce reliably to normalized answer strings, we do not report proof\-task answer\-vote self\-consistency as a main result\.

Self\-consistency\-style internal variants are treated as Mini Artichokes ablations rather than as standalone direct self\-consistency baselines\.

As a post\-hoc stronger\-model sanity check rather than a full model comparison, we ran one Gemma 4 31B minimal\-thinking check on six prior Mini\-below\-pass@1 items; the Gemini API documentation lists the Gemma 4 model identifiers used here \[15\]\. The selected items included proof and legal\-reasoning formats: Putnam A1, A3, A6 and B3, plus LEET 13 and 23\. Each item was run for 20 independent trials with pass@1 and Mini Artichokes\. LEET was graded by exact option match\. Putnam proof responses were graded after generation with an independent Gemma 4 26B judge given the official statement and rubric; official answers were not shown to the solvers\.

These comparisons are preliminary and not cost\-matched\. The key controlled distinction is whether extra calls are spent as unstructured retrying or as a validated redundancy loop: an unfiltered verifier critique is fed back directly in simple critique\-and\-revise, whereas Mini Artichokes uses only a short error signature supported by independent diagnoses and validated before correction\.

# 3 Results

## 3\.1 Overall performance

Table 1 reports suite\-level accuracy and average API calls per trial\. Mini Artichokes improves average accuracy on all four reported suites, but the aggregate gains are modest: PSAT improves from 467/800 \(58\.4%\) to 491/800 \(61\.4%\), Putnam from 65/240 \(27\.1%\) to 71/240 \(29\.6%\), AIME from 61/300 \(20\.3%\) to 82/300 \(27\.3%\), and the LEET subset from 6/15 \(40\.0%\) to 7/15 \(46\.7%\)\. Table 3 adds conservative direct\-sampling baselines for the stable\-answer 20\-trial suites: strict\-majority direct self\-consistency and best\-of\-20 repeated sampling\. These gains come with substantially higher inference cost, ranging from 24\.40 average calls per trial on the LEET subset to 121\.07 on Putnam\.

## 3\.2 Hard\-item lift

The most visible effect appears on hard items where pass@1 rarely succeeds\. Table 2 summarizes representative cases\. On PSAT, Mini Artichokes obtains 20/20 successes on question identifiers \(QIDs\) 38 and 28 while pass@1 obtains 0/20 and 1/20, respectively\. Similar hard\-item gains appear on Putnam B2, Putnam A4, Putnam A2 and AIME problem 5\.

The complete PSAT table is given in Supplementary Table 1\. Under a best\-of\-20 scoring view, where an item is counted if it is solved at least once over 20 trials and each item is worth 2\.5 points, pass@1 reaches 62\.5/100 by solving 25/40 items at least once\. Mini Artichokes reaches 92\.5/100 by solving 37/40 items at least once\. Across the 40 PSAT items, 25 are solved at least once by both methods, 12 are solved at least once only by Mini Artichokes, and 3 are never solved by either method\. No item in this run is solved at least once by pass@1 while having zero Mini Artichokes successes\. This best\-of\-20 view is repeated\-sampling evidence, not self\-consistency majority voting\.

## 3\.3 Results on the remaining suites

The LEET subset results are shown in Supplementary Table 2\. Because only five items were tested and each item used three trials, the subset should be interpreted as a small portability check rather than a full exam\-level benchmark\. Two of the three LEET items with zero pass@1 successes, QID 2 and QID 24, were solved at least once by Mini Artichokes; QID 6 remained unsolved by both methods\.

Supplementary Tables 3 and 4 report Putnam and AIME results, respectively\. These suites show the same pattern as PSAT: Mini Artichokes can substantially improve difficult zero\-success baseline items, but it can also regress on items that pass@1 already solves reliably\. For example, Putnam B2 improves from 0/20 to 10/20, whereas Putnam B3 drops from 20/20 to 1/20\. AIME problem 5 improves from 0/20 to 19/20, whereas AIME problem 3 drops from 18/20 to 4/20\.

Post\-hoc Gemma 4 sanity check on selected negative\-delta cases\. Supplementary Table 9 reports the six\-item follow\-up on Putnam A1, A3, A6, B3 and LEET 13, 23\. Under Gemma 4 31B solving, Mini Artichokes scored 112/120, whereas pass@1 scored 92/120\. Mini Artichokes matched or exceeded pass@1 on every item in this subset: Putnam A1 20/20 versus 19/20, A3 17/20 versus 16/20, A6 16/20 versus 12/20, B3 19/20 versus 12/20, LEET 13 20/20 versus 13/20, and LEET 23 20/20 versus 20/20\. This result is auxiliary evidence, not a replacement for the main benchmark tables: it shows that several severe earlier negative\-delta cases, including Putnam B3, are not stable failures under the stronger model and current Mini Artichokes configuration\.

# 4 Discussion

Among the 16 PSAT items with pass@1 of 0/20 or 1/20, Mini Artichokes reached 17\-20/20 on three items and produced smaller or no gains on the others\. Across this subset, Mini Artichokes recorded 103/320 successful trials versus 1/320 for pass@1\. Under the tested structured loop and larger call budget, some low\-base\-rate items entered the set of reachable correct trajectories; the present experiments do not isolate the effect of structure from the effect of additional calls\. This observed pattern motivates evaluating validated overlap as a high\-cost fallback for hard or low\-confidence trajectories\.

At the aggregate level, the largest regressions occur on items that direct solving handles reliably\. This is consistent with, but does not establish, destabilization of initially correct solutions; trace\-level analysis is needed to distinguish false criticism, poor repair, and answer\-format instability\.

The post\-hoc Gemma 4 check provides auxiliary evidence on selected negative\-delta cases\. The six\-item Putnam/LEET follow\-up yielded 112/120 successful trials for Mini Artichokes versus 92/120 for pass@1, with the severe B3 case recovering to 19/20\. This selected\-case result is not a new main model regime\.

Development sweeps, baseline\-style spot checks, and feature ablations are reported in Supplementary Tables 5\-8\. In the two\-item feature ablations \(Supplementary Tables 7 and 8\), the overlap\-only configuration \(O\) achieved 8/10 and 9/9 successful trials, showing the highest observed success proportion among the tested configurations on both items\. Because these ablations cover only two items with small and sometimes unequal trial counts and mixed module interactions, they do not isolate O as the principal component\. The later Gemma 4 follow\-up evaluates the full procedure rather than O in isolation and therefore does not resolve component attribution\. These results are descriptive development checks, not powered causal evidence, statistical superiority, or proof that any configuration is universally optimal\.

Mini Artichokes deliberately targets a different operating regime from pass@1\. It is meant for cases where solving a hard item at least once is more valuable than minimizing calls\. Average accuracy is still useful as a sanity check, but the main signal is capability expansion: moving near\-zero\-base\-rate items into the solvable set\. The important engineering distinction is not one call versus many calls; it is unstructured extra inference versus a correction harness in which each additional call has a role\. In harness and agentic engineering, the same overlap\-filtered correction layer can wrap direct sampling, self\-consistency, verifier reranking, retrieval\-augmented solving, unit tests, proof checkers, or other verification signals\. A cost\-matched comparison remains necessary before making compute\-efficiency claims\.

# 5 Limitations

A key limitation is the absence of a fully cost\-matched comparison against direct repeated sampling or self\-consistency\. Because Mini Artichokes uses substantially more calls than pass@1, the present results should be interpreted as evidence for capability expansion under a structured fallback loop, not as evidence of superior compute efficiency\. The experiments are also limited in breadth, especially for the exploratory LEET subset, and use cost\-constrained repeated trials\. The reported model choices were constrained by API cost and availability, so the results should not be interpreted as a comprehensive model comparison\. The tool\-free regime is intentionally restrictive: it isolates the internal self\-correction mechanism but does not represent the strongest possible agentic harness\. The development ablations are informative but not exhaustive, and they do not replace a powered comparison against cost\-matched direct sampling or self\-consistency\. The targeted Gemma 4 Putnam follow\-up relies on an LLM judge rather than formal or human grading, so Supplementary Table 9 should be treated as auxiliary sanity\-check evidence rather than as a main benchmark result\. Because stronger\-model follow\-ups are post hoc and use benchmark items that may be known to later models, they should be read as robustness checks rather than as uncontaminated estimates of benchmark performance\.

# 6 Conclusion

Mini Artichokes shows that structured extra inference can expand the set of reachable correct solutions under the tested fallback loop; whether it is more useful or efficient than cost\-matched repeated sampling remains unresolved\. Redundant diagnosis and validated overlap can turn large inference budgets into a correction signal that expands the set of hard problems a base model can solve\. The method is not an always\-on replacement for direct prompting and does not claim compute efficiency against matched sampling budgets\. Its best\-supported use is as a high\-cost fallback and as a reusable harness\-level layer: a solver, independent diagnostic passes, an overlap filter, and a validator can be combined with other agentic tools and verification signals\. The next step is to test routing and cost\-matched baselines directly\.

# Data Availability

The per\-item summaries needed to interpret the reported results are included in Tables 1\-3 and Supplementary Tables 1\-9\. Code and log access are represented by the blinded repository entry in \[3\] for double\-blind review\.

# Statements and Declarations

The authors declare that they have no conflicts of interest\.

# References

1\. Huang Y, Yang LF \(2025\) Winning gold at IMO 2025 with a model\-agnostic verification\-and\-refinement pipeline\. arXiv:2507\.15855\. https://arxiv\.org/abs/2507\.15855

2\. ryoiki\-tokuiten\. Iterative\-Contextual\-Refinements\. GitHub repository \(Apache\-2\.0\)\. https://github\.com/ryoiki\-tokuiten/Iterative\-Contextual\-Refinements\. Accessed 15 Feb 2026

3\. Anonymous\. Repository omitted for double\-blind review\. Accessed 15 Feb 2026

4\. Madaan A, Tandon N, Gupta P, Hallinan S, Gao L, Wiegreffe S, Alon U, Dziri N, Prabhumoye S, Yang Y, Gupta S, Majumder BP, Hermann K, Welleck S, Yazdanbakhsh A, Clark P \(2023\) Self\-Refine: iterative refinement with self\-feedback\. arXiv:2303\.17651

5\. Shinn N, Cassano F, Berman E, Gopinath A, Narasimhan K \(2023\) Reflexion: language agents with verbal reinforcement learning\. arXiv:2303\.11366

6\. Wang X, Wei J, Schuurmans D, Le Q, Chi E, Narang S, Chowdhery A, Zhou D \(2022\) Self\-consistency improves chain of thought reasoning in language models\. arXiv:2203\.11171

7\. Yao S, Yu D, Zhao J, Shafran I, Griffiths TL, Cao Y, Narasimhan K \(2023\) Tree of thoughts: deliberate problem solving with large language models\. arXiv:2305\.10601

8\. Mathematical Association of America \(2024\) The 85th William Lowell Putnam mathematical competition \(2024\): problems for session A\. https://maa\.org/wp\-content/uploads/2025/02/2024Putnam\_A\-1\.pdf\. Accessed 15 Feb 2026

9\. Mathematical Association of America \(2024\) The 85th William Lowell Putnam mathematical competition \(2024\): problems for session B\. https://maa\.org/wp\-content/uploads/2025/02/2024Putnam\_B\-1\.pdf\. Accessed 15 Feb 2026

10\. Art of Problem Solving Wiki \(2026\) 2026 AIME I problems\. https://artofproblemsolving\.com/wiki/index\.php/2026\_AIME\_I\_Problems\. Accessed 15 Feb 2026

11\. Ministry of Personnel Management \(Republic of Korea\)\. Cyber State Examination Center: multiple\-choice exam problems and answer keys\. https://www\.gosi\.kr/cop/bbs/gosiQnaChoiceExam\.do\. Accessed 15 Feb 2026

12\. Association of Korean Law Schools\. \(2025\)\. Explanations of Law School Admission Test Problems: LEET Analytical Reasoning \(2026 Academic Year\)\. ISBN 978\-89\-200\-5488\-4\. \(in Korean\)\.

13\. Yang L, Huang Y\. IMO25: IMO 2025 problem solver\. GitHub repository \(MIT\)\. https://github\.com/lyang36/IMO25\. Accessed 15 Feb 2026

14\. Google Cloud Documentation\. Gemini 3 Flash\. https://docs\.cloud\.google\.com/gemini\-enterprise\-agent\-platform/models/gemini/3\-flash\. Accessed 2 June 2026\.

15\. Google AI for Developers\. Run Gemma with the Gemini API\. https://ai\.google\.dev/gemma/docs/core/gemma\_on\_gemini\_api\. Accessed 2 June 2026\.

__Table 1 Suite\-level accuracy and average API calls per trial__

__Suite__

__pass@1__

__Mini Artichokes__

__pass@1 calls__

__Mini calls__

AIME 2026 \(15 items, 20 trials each\)

61/300 \(20\.3%\)

82/300 \(27\.3%\)

1\.0

67\.28

PSAT 2025 Linguistic Logic \(40 items,  20 trials each\)

467/800 \(58\.4%\)

491/800 \(61\.4%\)

1\.0

26\.55

Putnam 2024 \(12 problems, 20 trials each\)

65/240 \(27\.1%\)

71/240 \(29\.6%\)

1\.0

121\.07

LEET 2026 Analytical Reasoning \(5 items, 3 trials each\)

6/15 \(40\.0%\)

7/15 \(46\.7%\)

1\.0

24\.40

Cells are Correct/Attempts or average calls per trial\. Abbreviations: API: application programming interface; AIME: American Invitational Mathematics Examination; PSAT: Public Service Aptitude Test; LEET: Legal Education Eligibility Test; pass@1: first\-sample accuracy\.

__Table 2 Selected hard\-item gains of Mini Artichokes versus pass@1__

__Benchmark__

__QID__

__pass@1__

__Mini Artichokes__

__Δ__

PSAT 2025 \(Linguistic Logic\)

38

0/20

20/20

\+20

PSAT 2025 \(Linguistic Logic\)

28

1/20

20/20

\+19

PSAT 2025 \(Linguistic Logic\)

3

0/20

17/20

\+17

PSAT 2025 \(Linguistic Logic\)

14

0/20

11/20

\+11

PSAT 2025 \(Linguistic Logic\)

34

0/20

8/20

\+8

PSAT 2025 \(Linguistic Logic\)

31

0/20

7/20

\+7

LEET 2026 \(AR subset\)

2

0/3

2/3

\+2

LEET 2026 \(AR subset\)

24

0/3

1/3

\+1

Putnam 2024

B2

0/20

10/20

\+10

Putnam 2024

A4

0/20

7/20

\+7

Putnam 2024

A2

0/20

6/20

\+6

AIME 2026

P5

0/20

19/20

\+19

Cells are Correct/Attempts over repeated trials; Δ is Mini Artichokes minus pass@1\. Abbreviations: AIME: American Invitational Mathematics Examination; AR: Analytical Reasoning; LEET: Legal Education Eligibility Test; pass@1: first\-sample accuracy; PSAT: Public Service Aptitude Test; QID: question identifier\.

__Table 3 Conservative direct self\-consistency and repeated\-sampling baselines from pass@1 trials__

__Suite__

__Direct pass@1 trial accuracy__

__Direct strict SC@20__

__Direct best\-of\-20__

__Mini trial accuracy__

__Mini best\-of\-20__

PSAT 2025 Linguistic Logic

467/800 \(58\.4%\)

24/40 \(60\.0%\)

25/40 \(62\.5%\)

491/800 \(61\.4%\)

37/40 \(92\.5%\)

AIME 2026

61/300 \(20\.3%\)

3/15 \(20\.0%\)

5/15 \(33\.3%\)

82/300 \(27\.3%\)

9/15 \(60\.0%\)

Direct strict SC@20 reports whether the majority\-vote answer extracted from the 20 direct samples matches the gold answer; cases without a strict majority are counted as unresolved/incorrect\. Best\-of\-20 is an oracle repeated\-sampling view, not a deployable baseline without an external answer check\. The table is restricted to stable\-answer 20\-trial suites; LEET has only three trials and Putnam is proof\-style\.

Abbreviations: AIME: American Invitational Mathematics Examination; LEET: Legal Education Eligibility Test; Mini: Mini Artichokes; pass@1: first\-sample accuracy; PSAT: Public Service Aptitude Test; SC: self\-consistency\.

[Figure 1 omitted from the text-only MAC audit; preserved in the original DOCX.]

__Fig\. 1__ System overview of Mini Artichokes\. Independent diagnoses are filtered through overlap extraction and validation before correction\. The acceptance and stopping rules use a pass streak p and fail streak f, and each round is bounded by a per\-round call cap \(rcap\)\. Abbreviations: API: application programming interface; f: fail streak; ICR: iterative contextual refinement; p: pass streak; rcap: per\-round application programming interface call cap

