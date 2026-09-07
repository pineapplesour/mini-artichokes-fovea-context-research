# Independent executable probes × semantic overlap: Java47 development

Frozen before all new calls. This is exposed-task development, not confirmation.

## Hypothesis and complete population

The preceding Python34 2×2 experiment found no positive overlap effect. Its
C++26 shared fourth candidate timed out, so no 60-task primary contrast exists.
Do not replace that candidate or merge a new experiment into that protocol.

Here the structural change is to generate executable specification probes in a
clean context BEFORE showing the author any failed candidate or test outcome.
The repair stage then compares actual candidate behavior on those probes.
The hypothesis is that independently grounded behavioral witnesses make
cross-candidate overlap useful where prose-only self-verification did not.
Generated probes are fallible auxiliary evidence, never the scoring oracle.

Use ALL 47 tasks in the frozen official Aider Java track, commit
7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f, at
`runs/aider-java47-tov-development-20260902`. No task removal, selection, or
replacement. Java is selected for development because its earlier complete
track results leave headroom; this selection is explicitly result-informed.

## Three new whole-track calls, shared prefix

Reuse the original Plain/Graph/ordinary-repair outputs unchanged. The new calls
are sequential: (1) independent probe author; (2) overlap repair; (3) generic
repair. Both final systems have five logical Codex executions: the same three
old candidate executions, the shared probe-author execution, and one repair.
There are four candidate implementations per system, not five: probe creation
is computation, not another solution candidate. No per-task model calls.

The probe author sees only original public documentation, original source/API
stubs, and task IDs. It receives no candidate patches, outputs, failure labels,
or private test material. It writes one JSON entry for every task with a small
Java `Probe` main program and specification basis, or explicitly marks that
task's probe unavailable. It must not mutate the original source. Incorrect,
uncompilable, missing, or unavailable probes are retained; never repair the
probe packet after seeing a treatment result.

Both repair calls start from the SAME ordinary-repair patch. Both receive
byte-identical P/G/R evidence, original documentation, complete public source
snapshots, frozen probes, and the same small replay helper. Both can execute
and inspect any probe/candidate and derive their own checks. The generic arm
is unrestricted strong code repair, not forbidden to compare candidates.
Only the final decision instruction differs: overlap explicitly aligns
requirement-level behavior vectors to choose discriminating/shared-failure
witnesses; generic chooses its own strategy from the same evidence. Both
record the same compact per-task decisions and perform two completion audits.

Probe compilation/execution takes place only inside the existing isolated
agent sandbox. Compile/runtime failures of a probe are not evidence of a
semantic solution defect. A probe contradicting the specification can be
explicitly rejected by either arm, without changing the frozen probe packet.
The official evaluator remains the sole terminal scoring/selection authority.

## Budgets, terminal selection, and gates

All NEW executions use Luna/medium, default tier, approved account
`/home/pineapple/.codex-new-account`, 900-second agent ceiling; official
evaluation ceiling 1800 seconds. Both final arms expose the identical existing
JDK17 root `/home/pineapple/miniconda3/lib/jvm` read-only. This is not a claim
that historical prefix tool access/caps were identical; that prefix is shared.
Report realized tokens, agent time, and probe coverage; logical call matching
does not imply token matching. This is not an infrastructure contribution.

For each task select a complete official-test-passing snapshot, priority
final > ordinary > graph > plain, else final. Materialize and re-evaluate the
complete 47-task portfolio. Same selection for both arms; it is not novelty.

Primary development contrast: overlap system minus generic system over all47.
Report candidate-only scores, rescues/harms, exact paired tests conditional on
the realized calls, full-system costs, probe availability/execution fidelity,
and gained tasks above the common P/G/R floor. No independent-task population
inference from one whole-track session. Advancement requires positive net
gain with no integrity failure; +10/47 is the ambitious +20pp target, not a
promised result. A winner needs new paired sessions and another full official
track before a general superiority claim or final paper promotion.

An incomplete probe-author call or incomplete inventory invalidates the shared
input and stops both dependent arms without a replacement. An invalid final
arm stays invalid. The other arm may finish; no best-of-retries selection.
No additional prompt variants or altered probe packets in this experiment.
