"""Frozen final-stage instructions for Java47 independent-probe development."""

GENERIC = """Use strong general code repair. Freely inspect and compare any candidates,
probes, and outcomes. Choose your own strategy to localize and fix remaining
defects. Use actual execution where it helps, reconstruct missing requirements,
consider alternative repairs, and preserve working behavior. A probe is a
fallible proposal, not an authoritative answer. Reject an unjustified probe by
giving its concrete specification conflict; never fix code merely to satisfy
an erroneous probe. Prioritize general repairs that close observed failures."""

OVERLAP = """Use executable semantic overlap to guide repair. For unresolved tasks,
run a useful specification probe against the supplied Plain, Graph, and ordinary
source snapshots. Align the resulting behavior vectors by requirement or
invariant, not source-line similarity. A disagreement should identify a small
input on which candidate hypotheses differ. Shared failure should identify an
unsupported assumption to reconsider, not a consensus to obey. Resolve which
behavior is required from the independent probe's basis AND original task;
an incorrect probe must be explicitly rejected with its specification conflict.
Combine complementary supported obligations into a general repair, then replay
the actual final source on the discriminating witness. Preserve supported
behavior. Do not substitute prose predictions for the candidate executions,
and do not treat a compile failure of the probe as a semantic counterexample."""

COMMON = """Repair ALL tasks in the complete official track. The workspace starts from
the ordinary-repair candidate. Identical P/G/R patches and bounded official
outcomes are indexed in /tmp/artifacts/evidence-index.json. Their complete public
Java source snapshots are under /tmp/artifacts/candidates/{plain,graph,ordinary_repair}.
Independent specification probes are in /tmp/artifacts/probes.json; their author
never saw these candidates or official test results. They are auxiliary checks,
not new benchmark questions or private-test answers.

The common replay helper is /tmp/artifacts/probe_replay.py. Usage:
python /tmp/artifacts/probe_replay.py --candidate-root /tmp/work --task-id TASK_ID
Replace /tmp/work with one of the candidate snapshot roots to compare behavior.
The helper compiles a temporary copy of the actual task source plus the Probe
and runs Java with assertions enabled. It prints actual stdout/stderr/status.
Unavailable/incorrect probes and missing dependency/API compilation must be
distinguished from a semantic assertion failure. Both arms may derive and run
their own specification-grounded checks under /tmp. Keep the supplied probe,
candidate, and evidence files unchanged. No hidden test source, gold, network,
benchmark lookup, or external answers are permitted.

{policy}

Previous candidate successes will be preserved by the same terminal official
verifier selector for every arm. Spend effort on unresolved behavior; do not
rewrite already working implementations cosmetically. Edit only allowlisted
solution files. Temporary probes, compiler output, and drivers belong under
/tmp outside the repository. Use only documented APIs/dependencies.

Write /tmp/artifacts/decision_ledger.json, one short row per original task:
taskId, hypothesis, check, observation, action. For preserved tasks record the
supporting official outcome. Identify actual replay commands/results in changed
tasks; explicitly say when no useful executable probe exists. Do not invent
successful executions or produce a lengthy formal certificate. Before ending,
inspect the final diff against the intended fixes, then recheck the original
requirements against actual final source. Correct concrete contradictions found
by either audit. Budget: 900 seconds for the entire track.

Original task:
{instruction}
"""


def make_prompt(instruction: str, policy: str) -> str:
    if policy not in {"generic", "overlap"}:
        raise ValueError(policy)
    return COMMON.replace("{policy}", GENERIC if policy == "generic" else OVERLAP).replace(
        "{instruction}", instruction)
