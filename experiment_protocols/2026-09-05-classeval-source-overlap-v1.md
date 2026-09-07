# ClassEval100: executable overlap-preserving source composition, v1

Frozen before any ClassEval model generation. This is a new Mini Artichokes
coding experiment, not the older Universal exam suite's whole-file contract.

## Inventory and information

Use all100 tasks of the author's ClassEval v1.0.0, commit
90825141e640418ae6dc8257397345ee3ac36cbc. Dataset SHA256:
d13f5e3bac96f57c1cc9bfa282cf6c0cca4605d4748d621b83a0dae72d08ed2f.
The actual release contains410 methods. Code is MIT; data CC BY-NC4.0.
ClassEval-TDD is NOT this dataset: its linked anonymous repository returned401
on2026-09-05. Do not claim that variant's cleaned specifications/public-private
split or compare directly with its published scores.

Generation sees only the released skeleton and import statements. Official
test source, reference implementations and reference-derived dependency
annotations are excluded. Evaluation uses every declared test class and case.
This is test-feedback-available synthesis/repair, not original blind pass@k
after the feedback stages. No test subset or domain is selected by outcomes.
Reference implementations may be executed by the isolated evaluator solely
to check runtime feasibility; they never enter model inputs or composition.

## Shared candidates and controls

For each task in release order, generate two separate holistic class candidates
A and B with the SAME prompt, approved gpt-5.6-luna/medium account,120-second
cap each, isolated native-code-editing CLI adapter. Each call sees only its
own task, never another task's answer or the other parent's code/outcomes.
Both calls are made for every task (200 calls maximum; no answer-led retries).
An incomplete/timed-out/unsafe call is a failed candidate, retained in logs.
Exact terminal receipts, tokens and wall time are recorded.

Evaluate A/B, retaining full test vectors and which candidate class methods
each individual test executed. Methods are obtained from candidate ASTs, not
gold dependencies. Test traces are observed support, never votes or proof of
general correctness. Whole passing parents are retained by every system.

Compare Plain A, verified best-of-two, and two source-composition policies:

1. Generic: uniform random method-source crossover, fixed task seed, up to16
   distinct new executable programs from the same A/B source space.
2. Overlap: rank the SAME source space by predicted passing-test coverage.
   A passing test supports a mixture only if every method executed by that
   test retains that donor's AST (identical methods are compatible with both).
   Shared methods therefore constrain overlapping test-supported fragments.
   Prefer larger support unions, then fewer conflicting shared-field edges,
   then fewer source changes and a fixed lexical mask order. Test at most16
   distinct new programs. Predictions never count as observed passes.

The source space replaces complete same-name class methods, including the
constructor, between two parsed implementations, with either parent's module
as the surrounding context. Non-method context differences constrain donor
support. Duplicate definitions or more than14 differing method/context slots
make a task non-composable under this bounded implementation; the task stays
in the denominator with its actual parent result. No hand-authored task rules.
Both searches retain the best actual complete-test vector, tie-breaking by
earlier candidate order. If a full pass is found, both may stop early and must
report actual evaluator calls/time. Equal caps are not equal realized costs.

After the source-only comparison, a predeclared stronger comparison permits
one ordinary feedback-repair call from each policy's best executable state
on unresolved tasks, with identical prompt template, model and120-second cap.
Its input includes both original parents and the selected candidate's bounded
failure feedback. It may freely copy/combine/synthesize code. Full-pass states
need no repair and remain in the complete100-task endpoint. Report actual
physical and logical calls; no selective retries or replacements. The source
operator, not a special repair prompt, is the treatment.

## Evaluation and decision

Use Python3.13.11 and record dependency versions; this differs from the old
paper's environment and is shared by all arms. The upstream evaluator's
unrestricted working-directory cleanup MUST NOT run. Use its declared unittest
classes and success rule in a network-isolated, read-only-host process with a
fresh task-local writable directory. Preserve the5-second per-test-class
timeout; errors, zero tests, missing cases and timeouts are not passes.
Reference failures prevent claims of clean benchmark confirmation; they are
reported without dropping tasks or silently editing gold/tests.

Primary endpoint: fully passing classes /100, including invalid/missing model
outputs as failures. Also report task-paired rescues/harms, conditional exact
tests, complete test-case vectors, calls, uncached/cached input/output tokens,
elapsed model time and evaluator work. Task calls are separate here, unlike
the prior Java whole-track calls. The first complete run is development.
Only an actual advantage over the stronger generic repaired system warrants
fresh session replication with the same frozen algorithm and full inventory.
No paper score claim is made from a partial run or predicted coverage.
