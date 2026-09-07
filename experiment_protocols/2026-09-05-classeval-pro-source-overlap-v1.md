# ClassEval-Pro300: source-overlap experiment, v1

This freezes the prospective transfer of the executable source-overlap
operator described in2026-09-05-classeval-source-overlap-v1.md. The original
ClassEval100 model experiment has NOT run: its full reference check was91/100
in this runtime and the author update did not resolve the affected tests.
That feasibility outcome is not a solver score and no task was omitted.

## Different author-released benchmark, full inventory

Use ALL300 ClassEval-Pro tasks, not an outcome-selected domain or67/233
subset. Author repository https://github.com/ian-Kappa/ClassEval-Pro, commit
6ec785c7068e0e7d36374e2890ebf473f88dd306, released data.json SHA256
f6bcb748819f6f2e39f3d6635c76a8310f5cbee55f08154f9dd726522decb2e3.
Data is downloaded unchanged; do not run the benchmark construction pipeline
or generate replacement problems. The repository accompanies AIware2026 /
arXiv2604.26923 and carries MIT licensing. Full300 is larger than the user's
preferred approximate100, but preserves complete official benchmark scope;
each task is a separate bounded invocation, never a giant whole-suite prompt.

All method-composition rules, source-space14-slot cap,16-trial per-policy
budget, A/B independent identical prompt, Luna/medium approved account,
120-second call cap, failure retention, full-program scoring and stronger
ordinary repair follow the preceding protocol. The complete parent phase
has600 maximum model calls. Calls are serial; all actual tokens/time and
invalid outputs count. No selected-parent retries. No new reviewer call until
there is substantive complete-benchmark evidence.

Pre-generation economy amendment (2026-09-05): unlike the unrun original100
protocol, generate A on every task and generate B ONLY when A does not fully
pass. Both policies share exactly that conditional pool. An A full pass is
preserved by both policies; no B result is invented and no task is removed.
Report Plain A /300, adaptive verified best-of-up-to-two /300 and actual call
counts. This stopping rule is fixed before any model result; it cannot choose
which failed tasks get a second try. Every A failure receives B once.

The first implementation runs the shared two-parent and source-only phases.
The stronger identical ordinary feedback-repair phase is predeclared but is
not yet implemented; it must not be reported as already executed. Replication
promotion still requires superiority over that stronger repaired control.

## Native evaluator conventions

The author's common/evaluate.py applies add_static_statement: remove lines
containing @staticmethod and add it before exactly-four-space def lines not
containing self or cls. Reproduce that preprocessing for EVERY source and
record raw generation separately. The author concatenates candidate + tests,
imports a registered module, and reloads it before each declared test class;
the isolated runner follows those conventions, including5-second class
timeouts. Code runs in a network-isolated fresh writable task directory with
read-only host and no user files/accounts. Parent generation receives ONLY
the skeleton, not any gold source/test/dependency metadata. Case traces and
feedback are available only to the post-generation source operator.

Execute all300 reference programs once before spending the model budget.
Report all failures with denominator300; no silent benchmark edits. A claim
of a clean confirmation requires resolving reference failures through an
official release/environment, not excluding tasks or modifying solutions.

Reference feasibility result (before generation):291/300 complete passes,
session2913 exit0. Tasks24,80,124,133,147,157,201,227 declare empty unittest
classes, which the author's own get_test_answer maps to error. Task102 differs
on the Python HTTP422 reason phrase. Preserve every task in the300 denominator
and report these known limitations; do not repair these test sources or use
reference implementations to guide solvers. Proceed as DEVELOPMENT, not a
clean confirmatory result. All other references pass the same runner.
