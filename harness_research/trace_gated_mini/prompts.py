"""Prompt policies used by the pre-registered harness arms."""

from __future__ import annotations


KIRA_STYLE_CHECKLIST = """

Before you finish, perform a completion audit:
1. Re-read the original request and list the required observable outcomes.
2. Run the most relevant tests and inspect their actual output.
3. Inspect the final Git diff and remove unrelated files or side effects.
4. Check edge cases, robustness, and the result from tester and user perspectives.
5. If any item is not supported by evidence, continue working; otherwise finish.
""".strip()


INDEPENDENT_VARIANTS = {
    "a": "Solve the task directly. Inspect the repository, implement the smallest correct change, and run relevant tests.",
    "b": (
        "Solve independently from first principles. Inspect the failing behavior and tests, form your own diagnosis, "
        "seek a counterexample to the first plausible fix, and then implement and verify the smallest correct change."
    ),
    "c": (
        "Take an adversarial debugging approach. Reproduce the failure, consider at least one competing root-cause "
        "hypothesis, and treat named examples as potentially illustrative rather than exhaustive. Derive the full "
        "relevant input class from the local code, contracts, and applicable specification; probe its boundaries or "
        "properties with temporary checks. Implement the best-supported minimal repair and try to falsify it before "
        "finishing."
    ),
}


def build_prompt(instruction: str, policy: str, candidate_id: str = "a") -> str:
    """Build a policy prompt without benchmark- or domain-specific routing."""

    if policy == "direct":
        lead = INDEPENDENT_VARIANTS["a"]
        suffix = ""
    elif policy == "kira":
        lead = INDEPENDENT_VARIANTS["a"]
        suffix = "\n\n" + KIRA_STYLE_CHECKLIST
    elif policy == "mini":
        lead = INDEPENDENT_VARIANTS[candidate_id]
        suffix = "\n\n" + KIRA_STYLE_CHECKLIST
    else:
        raise ValueError(f"unknown policy: {policy}")

    return f"{lead}\n\nOriginal task:\n{instruction.strip()}{suffix}\n"


def build_repair_prompt(
    instruction: str,
    current_candidate: str,
    evidence: str,
    trigger_reason: str,
    critic_memo: str | None = None,
) -> str:
    """Create the bounded disagreement repair prompt.

    The repair agent begins from the strongest observed workspace. It receives
    public traces and anonymous patches only; evaluation-only tests are never
    included.
    """

    if trigger_reason == "all_public_fail":
        situation = "None of the independent attempts passed the public verifier."
    elif trigger_reason == "patch_disagreement":
        situation = (
            "Multiple independent attempts passed the public verifier but produced different patches, so the public "
            "suite cannot discriminate their requirement coverage."
        )
    else:
        raise ValueError(f"unknown repair trigger: {trigger_reason}")

    critic_section = ""
    if critic_memo:
        critic_section = f"""

An independent counterexample critic inspected the same public repository state. It had no evaluation-only tests or
gold patch. Treat its memo as fallible evidence and verify it yourself. For every reported false accept, false reject,
uncovered ingress path, and concrete counterexample, either make the final implementation satisfy the critic's
source-backed oracle or cite stronger local evidence that the item is outside the intended contract. The issue's named
regressions are not sufficient grounds to ignore a broader source-defined language. A pre-change test that directly
asserts behavior the issue and stronger local contract are changing is evidence of the old behavior, not by itself a
compatibility veto. Before finishing, rerun the critic's finite-domain/equivalence-class oracle against the final patch
and obtain zero unexplained mismatches. State that closure evidence in the final response.

Critic claim certificate:

{critic_memo.strip()}
"""

    return f"""The original task is below. Three independent attempts were made. {situation}
You are starting from anonymous candidate {current_candidate}, the strongest deterministic trace so far. Compare the
anonymous patches against every part of the issue, identify what each candidate may have missed, and actively try to
falsify the current implementation with temporary or one-off checks. Treat named examples as potentially illustrative,
not exhaustive: derive the relevant input class from local code, contracts, and applicable specifications, then probe
its boundaries or properties. You may keep, revise, or replace the current patch. Do not assume that a candidate is
correct merely because it made progress or passed existing tests. Run the public tests yourself, keep the final
repository change minimal, do not modify evaluator-owned tests, and do not leave review notes or temporary evidence
files in the repository.

Original task:
{instruction.strip()}

Anonymous candidate evidence:
{evidence}
{critic_section}

{KIRA_STYLE_CHECKLIST}
"""


def build_counterexample_prompt(
    instruction: str,
    evidence: str,
    perspective: str = "balanced",
) -> str:
    """Build a verification-only prompt that searches for shared candidate blind spots."""

    if perspective == "spec_first":
        perspective_instruction = """
Your independent perspective is SPEC-FIRST. Reconstruct the intended post-change contract from the task and the
strongest normative local source. A pre-change implementation or test that directly preserves the behavior being fixed
is an observation of the old state, not a veto. When named regression examples and a source-defined accepted language
differ, test the complete source-defined language unless stronger local evidence explicitly narrows the new contract.
"""
    elif perspective == "regression_first":
        perspective_instruction = """
Your independent perspective is REGRESSION-FIRST. Enforce every explicit requested change, while aggressively searching
for false rejects, lost compatibility, partial mutation, missed ingress paths, and excessive patch scope. Compatibility
claims must be supported by local code, documentation, or tests and must not be used to excuse an explicit requirement.
"""
    elif perspective == "balanced":
        perspective_instruction = ""
    else:
        raise ValueError(f"unknown critic perspective: {perspective}")

    return f"""Act as a verification-only counterexample critic. Do not implement a fix and do not modify any tracked
repository file. You may run disposable inline commands. Create exactly one untracked artifact at the repository root,
`.mini_claim_oracle.sh`; do not create any other persistent file. The workspace starts from the strongest
public-passing candidate, and the anonymous public evidence for all candidates is below. You have no evaluation-only
tests or gold patch.
{perspective_instruction}

Infer the complete behavioral contract from the issue and local repository evidence. Named examples are a lower bound,
not necessarily the whole contract, even when the issue describes them as the immediate bug. Do not conclude that the
contract is exactly the enumerated examples without positive repository evidence excluding other cases. Distinguish a
regression witness from the full valid-input language. When source code or local documentation defines that language
with a grammar, regular expression, protocol production, schema, type invariant, or authoritative comment, use that
definition as the oracle instead of treating current acceptance as compatibility evidence. Explicitly identify
assumptions shared by all candidates and try to falsify them.
Construct a machine-checkable oracle when possible: derive an allowed language, pre/postcondition, state transition,
algebraic property, or exhaustive set of relevant equivalence classes. If the relevant input domain is finite or has a
small finite projection, enumerate it instead of checking only examples. For a character, token, byte, enum, flag, or
other bounded validator, compare every value in the finite projection against the independently derived oracle and
report both false accepts and false rejects. For validation or parsing behavior, search the local code for grammar,
regular-expression, protocol, type, and normalization definitions and compare the candidate's accepted language with
that source-defined contract. Trace every public ingress path that can reach the behavior.

Return a concise claim certificate with: (1) the behavioral claim, (2) normative local evidence, (3) an explicit
accepted/rejected-set oracle, (4) the enumerated domain or equivalence classes and observed false accepts/false rejects,
(5) ingress-path coverage, (6) the smallest concrete counterexample found, if any, and (7) the general repair
obligation. If no counterexample is found, state the search space you exhausted. Do not merely restate candidate claims.

Encode the same source-derived claim as `.mini_claim_oracle.sh`. It must be a self-contained Bash program runnable from
the repository root, use only repository code and locally available tools, perform no network access, and leave no
persistent repository changes. Exit zero only when the checked-out implementation satisfies the derived contract;
otherwise print concrete mismatches and exit nonzero. Exercise public behavior instead of inspecting a known patch
string. When a finite projection is relevant, enumerate it. The harness will preserve this oracle outside the critic
workspace, discard the critic workspace, and run the oracle independently against the repair workspace.

Original task:
{instruction.strip()}

Anonymous candidate evidence:
{evidence}
"""
