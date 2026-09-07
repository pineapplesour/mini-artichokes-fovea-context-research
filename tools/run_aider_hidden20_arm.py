#!/usr/bin/env python3
"""Run hidden-test Aider batch arms with filesystem isolation from private tests."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from harness_research.trace_gated_mini.core import (
    CommandResult,
    TaskSpec,
    attempt_from_payload,
    collect_patch,
    execute_attempt,
    prepare_workspace,
    run_process,
    to_jsonable,
)
from tools.run_plain_codex_file_agent import DISABLED_FEATURES, MASKED_HOST_ROOTS, codex_installation


GRAPH_LEAD = """Solve every official exercise from first principles without access to tests. For each exercise, form a compact reasoning graph covering requirements, implementation choices, edge cases, and invariants. Use supports, contradicts, and depends-on relations, and try to falsify the chosen implementation with at least one derived counterexample. Keep the graph internal and edit only listed solution files."""

ORDINARY_REPAIR = """This is an ordinary second-pass test-feedback repair baseline. Continue from the frozen Graph implementation. Use the supplied official failure output to fix every failing task, without changing tasks that passed unless required by a shared concrete defect. Edit only listed solution files. The hidden tests remain unavailable."""

OVERLAP_REPAIR = """Continue from the exact same frozen Graph implementation and official failure output as the ordinary-repair control. Act as a graph-overlap completion verifier and minimal repairer.

For each task independently reconstruct three views: the original requirement graph, the current implementation/diff, and the observed official test failures or pass. Localize a defect only when at least two views overlap on the same unmet obligation. For failures, derive the smallest counterexample and repair the general obligation instead of memorizing the reported example. Preserve passing tasks unless concrete cross-view evidence shows an incomplete requirement.

Perform a KIRA-inspired completion audit twice before finishing: re-read every original task, check each claimed fix against the supplied actual evidence, inspect the final diff for scope or infrastructure edits, and confirm every observable outcome. If either audit exposes an unsupported item, continue reasoning and repair it. Edit only listed solution files; tests and gold solutions remain unavailable."""

MATCHED_REPAIR_V2 = """Continue from the exact frozen Graph implementation and official failure output. Act as a structured completion verifier and minimal repairer.

For each task independently reconstruct the original requirements, inspect the current implementation and diff, and use the observed official test failure or pass as ordinary evidence. For every proposed defect, derive the smallest counterexample and repair the general obligation instead of memorizing the printed example. Preserve passing tasks unless concrete evidence shows an incomplete requirement.

Perform a KIRA-inspired completion audit twice before finishing: re-read every original task, check each claimed fix against the supplied actual evidence, inspect the final diff for scope or infrastructure edits, and confirm every observable outcome. If either audit exposes an unsupported item, continue reasoning and repair it. Edit only listed solution files; tests and gold solutions remain unavailable."""

OVERLAP_REPAIR_V2 = """Continue from the exact frozen Graph implementation and official failure output. Act as a structured completion verifier and minimal repairer.

For each task independently reconstruct the original requirements, inspect the current implementation and diff, and use the observed official test failure or pass as evidence. For every proposed defect, explicitly record which of three independent views supports it: the original specification, the current implementation/diff, and the observed official test outcome. Authorize a change only when at least two views converge on the same unmet obligation. Then derive the smallest counterexample and repair the general obligation instead of memorizing the printed example. Preserve passing tasks unless the same two-view rule identifies an incomplete requirement.

Perform a KIRA-inspired completion audit twice before finishing: re-read every original task, check each claimed fix against the supplied actual evidence, inspect the final diff for scope or infrastructure edits, and confirm every observable outcome. If either audit exposes an unsupported item, continue reasoning and repair it. Edit only listed solution files; tests and gold solutions remain unavailable."""

GENERIC_ADJUDICATOR = """Act as a strong generic code-repair adjudicator. The workspace starts from the ordinary-repair candidate. You receive the same frozen original task packet, complete patches, and official test outcomes for Plain, Graph, and ordinary repair that the experimental adjudicator receives.

Review every exercise in the complete batch. For each exercise, choose, copy, combine, or repair the best candidate implementation using the official instructions and supplied test evidence. Preserve verified passing work, fix all remaining failures at their general cause, and edit only listed solution files. Tests and gold solutions remain unavailable. Inspect the whole batch before finishing."""

SEMANTIC_OVERLAP_ADJUDICATOR = """Act as a Try–Semantic-Overlap–Verify code adjudicator. The workspace starts from the ordinary-repair candidate. You receive the same frozen original task packet, complete patches, and official test outcomes for Plain, Graph, and ordinary repair as the generic adjudicator.

Process every exercise in the complete batch and write `/tmp/artifacts/decision_ledger.json` with exactly one entry per task. Each entry must record: taskId; the three candidate pass/fail outcomes; fault locations; violated invariants; smallest counterexample classes; edit intents; semantic overlaps and disagreements among candidates, specification, and test evidence; a falsification attempt; the selected source or synthesized repair; and the final action.

Use overlap as evidence and routing, not as a rigid veto. If any candidate passed all supplied official tests for a task, treat its exact implementation as a verified anchor and preserve or copy it unless a concrete specification conflict is demonstrated. If none passed, compare the four semantic fields above. Convergence raises confidence; disagreement triggers an explicit counterexample-based falsification and then a synthesized general repair. Never authorize or reject a change merely because edit lines intersect or fail to intersect.

After the per-task pass, perform two whole-batch completion audits: first reconcile every ledger decision with the actual final diff and supplied outcomes; then reread every task marked unresolved or changed and try to falsify the final implementation. Continue repairing if either audit finds a defect. Edit only listed solution files; tests and gold solutions remain unavailable."""

GENERIC_VERIFIED_UNION = """Act as a strong generic code-repair adjudicator. The workspace starts from a deterministic verified union: for every task passed by Plain, Graph, or ordinary repair, the complete solution files from one passing candidate are installed and will be restored after your call. The frozen anchor map is `/tmp/artifacts/verified-anchors.json`.

You receive the complete original task packet, all three patches, and identical official task outcomes and bounded failure tails. Review every unresolved task, choose, combine, or repair the best available implementation, and fix the general cause of each observed failure. Do not spend time rewriting verified anchors. Tests and gold solutions remain unavailable. Edit only listed solution files and inspect the whole batch before finishing."""

SEMANTIC_OVERLAP_VERIFIED_UNION = """Act as a Try–Semantic-Overlap–Verify code adjudicator. The workspace starts from the same deterministic verified union as the matched generic adjudicator: for every task passed by Plain, Graph, or ordinary repair, the complete solution files from one passing candidate are installed and will be restored after your call. Read `/tmp/artifacts/verified-anchors.json` and do not spend time rewriting those anchors.

Process every unresolved exercise and write `/tmp/artifacts/decision_ledger.json` with exactly one entry per unresolved task. Each entry must record: taskId; candidate outcomes; fault locations; violated invariants; smallest counterexample classes; edit intents; semantic overlaps and disagreements among candidates, specification, and test evidence; a falsification attempt; selected evidence; and final action.

Use overlap as evidence and routing, never as a rigid veto. Compare fault location, violated invariant, counterexample class, and edit intent. Convergence raises confidence. Disagreement triggers a counterexample-based falsification followed by a synthesized general repair. Literal edit-line intersection is neither necessary nor sufficient.

After repairing unresolved tasks, perform two completion audits: reconcile every ledger decision with the final diff and evidence, then reread every unresolved or changed task and try to falsify its final implementation. Continue repairing if either audit finds a defect. Tests and gold solutions remain unavailable. Edit only listed solution files."""

DISCRIMINATIVE_SEMANTIC_OVERLAP_VERIFIED_UNION = """Act as a Discriminative Try–Semantic-Overlap–Verify code adjudicator. The workspace starts from the same deterministic verified union as the matched controls: every task passed by Plain, Graph, or ordinary repair is a byte-locked anchor restored after your call. Read `/tmp/artifacts/verified-anchors.json` and do not rewrite anchors.

Process every unresolved exercise and write `/tmp/artifacts/decision_ledger.json` with exactly one entry per unresolved task. Each entry must record: taskId; candidate outcomes; fault locations; violated invariants; competing semantic hypotheses; semantic overlaps and disagreements; a discriminative witness; the predicted output of each leading hypothesis on that witness; the specification-based resolution; selected evidence; final action; and a post-repair falsification.

Overlap is only a hypothesis generator, never sufficient evidence. In particular, multiple failing candidates may converge on the same wrong interpretation. For every unresolved task:
1. Reconstruct at least two competing hypotheses from the specification, implementation differences, and failure evidence.
2. Identify exact qualifiers that can distinguish them, especially first/last, only/exactly, sign placement, ordering, ties, empty inputs, and boundary values.
3. Construct the smallest specification-grounded witness on which the two leading hypotheses predict different outputs. The witness must discriminate rather than merely confirm the preferred hypothesis. Manually simulate both predictions and resolve them from the wording and examples.
4. Add one structurally different boundary or metamorphic falsification. If the two checks disagree, keep reasoning instead of editing.
5. Implement the smallest general repair supported by the resolved invariant.

After all repairs, perform two completion audits: reconcile every ledger field with the actual diff and evidence; then rerun the discriminative-witness and boundary reasoning for every unresolved task. Continue repairing when either audit exposes a contradiction. Tests and gold solutions remain unavailable. Edit only listed solution files."""

COMPLETION_LOCKED_SEMANTIC_OVERLAP_VERIFIED_UNION = """Act as a Completion-Locked Try–Semantic-Overlap–Verify code adjudicator. The workspace starts from the same deterministic verified union as the matched controls: every task passed by Plain, Graph, or ordinary repair is a byte-locked anchor restored after your call. Read `/tmp/artifacts/verified-anchors.json` and do not rewrite anchors.

Process only unresolved exercises. For each one, write exactly one entry to `/tmp/artifacts/decision_ledger.json` containing: taskId; candidate outcomes; exact observed failure atoms; fault locations; violated invariants; semantic overlaps and disagreements; proposed repair; and a failure-closure map from every observed failure atom to the concrete final-code construct that prevents it.

Use semantic overlap to generate and compare repair hypotheses, but place literal verifier closure last and make it mandatory. A repair is not complete merely because it matches the prose specification. Before finishing each task:
1. Enumerate every distinct compiler, runtime, assertion, expected/actual, timeout, or scope failure visible in the bounded evidence. Do not silently generalize away a literal diagnostic.
2. Choose the smallest general repair supported by the specification and cross-candidate evidence.
3. Re-open the final solution file and prove, atom by atom, that the exact observed failure cannot recur. For a compiler diagnostic, reason about the compiled file and dependency boundary, not only the function's abstract output. If an immutable hidden harness import is reported unused, satisfy it through a legitimate implementation use because tests and infrastructure cannot be edited.
4. Reject the candidate and continue repairing if any failure atom lacks a concrete closure witness in the final code.
5. Perform one concise counterexample check for semantic correctness after literal closure.

After all tasks, perform a KIRA-inspired whole-batch completion audit: ledger count equals unresolved count, every ledger task has a nonempty closure map, every closure witness exists in the final diff, and no unverified file was changed. Tests and gold solutions remain unavailable. Edit only listed solution files."""

EXAMPLE_CONSTRAINED_COMPLETION_LOCKED_SEMANTIC_OVERLAP_VERIFIED_UNION = """Act as an Example-Constrained, Completion-Locked Try–Semantic-Overlap–Verify code adjudicator. The workspace starts from the same deterministic verified union as the matched controls: every task passed by Plain, Graph, or ordinary repair is a byte-locked anchor restored after your call. Read `/tmp/artifacts/verified-anchors.json` and do not rewrite anchors.

Process only unresolved exercises. For each one, write exactly one entry to `/tmp/artifacts/decision_ledger.json` containing: taskId; candidate outcomes; every explicit documentation example as an input/expected-output constraint; at least two competing semantic hypotheses; a manual prediction table for every hypothesis on every explicit example; rejected hypotheses and exact violated constraints; exact observed failure atoms; the selected general invariant; proposed repair; and a failure-closure map from every observed failure atom to the concrete final-code construct that prevents it.

Use semantic overlap only to generate hypotheses. Documentation examples are executable specification constraints, not illustrations that may be discarded when prose admits another interpretation. Before editing each unresolved task:
1. Extract every explicit input/output example and simulate each leading hypothesis on every example. Reject any hypothesis that violates even one example. If prose and an example appear inconsistent, infer the smallest uniform rule that satisfies both as far as possible; never hard-code an example input or output.
2. Prefer the smallest local repair to the observed implementation defect over a broad semantic rewrite when both can satisfy all constraints. Candidate convergence cannot override a violated example.
3. Add one non-example boundary or metamorphic witness and manually simulate the selected invariant. Recheck arithmetic, sign placement, ordering, ties, and boundaries independently.
4. Enumerate every compiler, runtime, assertion, expected/actual, timeout, or scope failure atom in the bounded evidence. Re-open the final solution file and map every atom to a concrete present code construct that prevents recurrence. Continue repairing if any atom lacks a witness.
5. Re-simulate every documentation example against the actual final code, not the proposed intent. Reject and repair any final file that violates an example, hard-codes example values, or contradicts its ledger.

After all tasks, perform a whole-batch completion audit: ledger IDs exactly equal unresolved IDs; every example has predictions for all leading hypotheses; every rejected hypothesis names a violated constraint; every failure atom has a nonempty closure witness present in the final diff; all final implementations satisfy every explicit example under manual simulation; and no unverified file was changed. Tests and gold solutions remain unavailable. Edit only listed solution files."""

MINIMAL_DELTA_EXAMPLE_CLOSURE_VERIFIED_UNION = """Act as a Minimal-Delta Example-Closure semantic adjudicator. The workspace starts from the same deterministic verified union as the matched controls: every task passed by Plain, Graph, or ordinary repair is a byte-locked anchor restored after your call. Read `/tmp/artifacts/verified-anchors.json` and do not rewrite anchors.

Process only unresolved exercises and write exactly one `/tmp/artifacts/decision_ledger.json` entry per unresolved task. Each entry must contain: taskId; candidate outcomes; original-seed fault localization; explicit documentation examples; violated invariants; competing repair hypotheses; candidate semantic overlaps/disagreements; edits ordered by structural footprint; selected minimal edit and why every smaller edit fails; exact observed failure atoms; final-code example simulations; one non-example counterexample; and a failure-closure map.

Apply these gates in order:
1. Start from the actual unresolved seed and localize a concrete expression, branch, data dependency, boundary, or interface defect before proposing a rewrite. Compare candidate patches as fallible hypotheses, not templates.
2. Extract every documentation example as a mandatory input/output constraint. Manually execute the actual language semantics, operator by operator, for each leading hypothesis. Recheck every numerical sum, sign, tie, and ordering calculation once independently. Reject any hypothesis that misses any example.
3. Enumerate constraint-satisfying edits from smallest to largest structural footprint: token/term deletion or substitution, one expression, one branch, one function, then algorithm replacement. If a smaller edit restores the localized invariant, makes data dependencies legitimate, and satisfies all examples plus the non-example check, select it. A broader rewrite is forbidden unless the ledger exhibits a concrete counterexample against every smaller eligible edit.
4. Enforce dependency separation: a value, score, key, or decision for one independent entity may not depend on another entity unless the specification explicitly couples them. Prefer removing an unsupported dependency over inventing a new semantic rule.
5. Never hard-code example values or introduce a special case that exists only to reproduce one example. Preserve the original algorithm and its documented conventions outside the smallest proven defect.
6. Re-open the final diff against the unresolved seed. Verify that it is the selected minimal edit, manually simulate all examples against the actual final code, and map every compiler, runtime, assertion, expected/actual, timeout, or scope failure atom to a concrete present code witness. Continue repairing if any check fails.

Finally audit ledger IDs against unresolved IDs, anchor preservation, changed paths, example simulations, minimality justifications, dependency separation, and failure-closure witnesses. Tests and gold solutions remain unavailable. Edit only listed solution files."""

EXECUTED_EXAMPLE_MINIMAL_DELTA_VERIFIED_UNION = """Act as an Executed-Example Minimal-Delta semantic adjudicator. Start from the deterministic verified union; all passing tasks are byte-locked anchors restored after the call. Read `/tmp/artifacts/verified-anchors.json` and process only unresolved tasks.

For each unresolved task, write one compact entry to `/tmp/artifacts/decision_ledger.json` with: taskId, outcomes, localized seed defect, mandatory documentation examples, competing hypotheses ordered by edit size, scratch-check command and stdout, selected minimal edit, one non-example check, exact failure atoms, and final-code closure witnesses.

The procedure is mandatory:
1. Localize the smallest suspicious expression, branch, dependency, boundary, or interface in the actual unresolved seed. Enumerate deletion/substitution repairs before rewrites. A per-entity value may not depend on another independent entity unless the specification explicitly couples them.
2. Treat every documentation example as a hard constraint. Do not trust mental arithmetic. Before editing, run a tiny scratch calculator/program under `/tmp` (never inside the repository, never importing or invoking the solution, and never using hidden tests) that computes each leading hypothesis's keys/intermediate values and final output for every explicit example. Record the exact command and stdout in the ledger. Correct the scratch program if its modeled operator semantics do not match the source language.
3. Select the smallest edit whose executed example outputs all match and whose invariant passes one separately constructed non-example check. If deleting one unsupported term suffices, broader formula changes, special tie-breakers, example cases, and algorithm rewrites are forbidden. Never hard-code example values.
4. Apply only that edit. Re-open the final diff, compile or syntax-check the solution when the toolchain permits, and rerun the scratch model of the final expression on every example. The final ledger must quote the second stdout and identify the exact changed code witness.
5. Map every observed compiler, runtime, assertion, expected/actual, timeout, or scope failure atom to a concrete construct present in the final file. Continue repairing if a witness is absent, the scratch output misses an example, the final edit is broader than the selected minimum, or ledger and code differ.

Finish with one concise whole-batch audit: ledger IDs equal unresolved IDs, scratch checks have exit code zero, every example is satisfied, anchors are untouched, only allowlisted solution files changed, and every failure atom is closed. Tests and gold solutions remain unavailable. Edit only listed solution files."""

EXECUTED_DIFF_EXAMPLE_CLOSURE_VERIFIED_UNION = """Act as an Executed-Diff Example-Closure adjudicator. Start from the deterministic verified union; passing tasks are byte-locked anchors restored after the call. Read `/tmp/artifacts/verified-anchors.json` and process only unresolved tasks.

For each unresolved task, localize the smallest concrete defect in the actual seed and enumerate candidate diffs from smallest to largest: term/token deletion or substitution, one expression, one branch, then broader rewrites. Independent entities' keys or values may not depend on one another unless the documentation explicitly couples them.

Every explicit documentation example is mandatory. Validate candidate diffs by replaying documentation, not by mental arithmetic or a reimplemented formula: under a temporary `/tmp` directory, copy the actual unresolved solution source, apply exactly one candidate diff to that copy, add only the smallest external driver needed to invoke the documented examples, and compile/run that actual modified source. This is a temporary documentation replay, not a repository test; never inspect or reproduce hidden tests. Record the command, candidate diff, exit code, and exact stdout. A key-only calculator, pseudocode simulation, or separately reimplemented algorithm is invalid evidence.

Reject any diff that fails an example, violates an explicit invariant, leaves an unsupported cross-entity dependency, or needs an example-specific special case. Select the smallest remaining diff; a broader rewrite is forbidden unless actual-source replay or a concrete non-example counterexample rejects every smaller diff. Apply the selected diff to the repository solution, then copy that final repository file back to a fresh `/tmp` replay directory and rerun all documentation examples. Compile or syntax-check it and add one non-example boundary/metamorphic check.

Write exactly one compact `/tmp/artifacts/decision_ledger.json` row per unresolved task containing: taskId; outcomes; localized defect; ordered candidate diffs; actual-source replay commands and stdout; rejected diffs; selected minimal diff; final-source replay stdout; non-example check; exact observed failure atoms; and a map from every atom to concrete final-code witnesses. Finish only when ledger IDs equal unresolved IDs, actual-source replay passes every example, the final diff equals the selected minimum, anchors are untouched, and only allowlisted solution files changed. Gold solutions and hidden test source remain unavailable."""

CONSERVATIVE_FIRST_CLOSURE_VERIFIED_UNION = """Act as a Conservative-First Closure semantic adjudicator. Start from the deterministic verified union; passing tasks are byte-locked anchors restored after the call. Read `/tmp/artifacts/verified-anchors.json` and process only unresolved tasks.

For each unresolved task, localize the smallest concrete defect in the actual seed. An unsupported dependency between otherwise independent entities, an off-by-one boundary, a wrong operator, a missing guard, or a literal compiler diagnostic is a concrete defect when supported by the specification and candidate/failure evidence. Enumerate candidate diffs strictly from smallest structural footprint to largest: token or term deletion/substitution, one expression, one branch, then rewrite.

Replay every explicit documentation example against the actual candidate source: copy the solution and a minimal documentation-example driver under `/tmp`, apply exactly one candidate diff, compile/run, and record the command, exit code, and stdout. Do not inspect hidden tests and do not substitute a separately reimplemented formula for the actual candidate source.

Use a fail-closed stopping rule. Select and apply the FIRST smallest candidate diff that simultaneously (a) removes the localized concrete defect, (b) preserves every documented convention not implicated by that defect, (c) compiles or syntax-checks, and (d) passes every explicit documentation example under actual-source replay. Once such a diff exists, STOP searching and do not replace it with a broader or more elegant rule. A smaller eligible diff may be rejected only by a quoted documentation constraint, the observed failure atom, a compile/runtime error, or a direct logical contradiction; an invented semantic convention, speculative hidden case, aesthetic preference, or broader rewrite is not valid rejection evidence.

After selection, add one non-example check derived only from explicit documented invariants. When documentation is ambiguous beyond its examples, preserve the seed's unaffected semantics rather than inventing a new convention. Re-open the final diff, confirm it equals the selected minimum, rerun the actual final source on every documentation example, and map every observed compiler/runtime/assertion/expected/timeout/scope atom to concrete final-code witnesses. Continue only if one of these mandatory checks fails.

Write exactly one compact `/tmp/artifacts/decision_ledger.json` row per unresolved task with: taskId; outcomes; localized defect and evidence; ordered diffs tried; actual-source replay commands/stdout; explicit reason for each smaller rejection; selected first closure; final-source replay; documented-invariant non-example check; failure atoms; and closure witnesses. Finish when ledger IDs equal unresolved IDs, anchors are untouched, and only allowlisted solution files changed. Gold solutions and hidden test source remain unavailable."""

EXECUTABLE_CLAIM_CLOSURE_VERIFIED_UNION = """Act as an Executable Claim-Closure semantic adjudicator. Start from the deterministic verified union; passing tasks are byte-locked anchors restored after the call. Read `/tmp/artifacts/verified-anchors.json` and process only unresolved tasks.

For every unresolved task, compare the specification, actual seed source, all candidate diffs, and every bounded observed failure atom. Align candidate hypotheses by fault location, violated invariant, counterexample class, and edit intent. Agreement raises priority but is never proof; disagreement must produce the smallest discriminating witness grounded in the specification or observed evidence.

A natural-language assertion that a check passed is not evidence. Before accepting a repair, create a temporary driver under `/tmp` that imports, includes, or invokes the ACTUAL repository solution file at its absolute `/tmp/work/...` path. Never paste or reimplement the function under test in the driver. The driver must exercise every explicit documentation example that can be executed and every fully specified observed failure atom, including expected/actual assertions. Run a syntax or compile check when available. Immediately before and after the replay, compute SHA-256 of the repository solution file; both hashes must match. Record the exact source path, both hashes, driver path, command, exit code, and stdout/stderr in `/tmp/artifacts/decision_ledger.json`.

Use the smallest general repair that closes the documented postcondition and all observed atoms. A minimal edit is preferred, but do not stop merely because a local defect disappeared: the actual-source replay and the complete behavioral obligation must close. Do not invent hidden cases, hard-code examples, modify tests, or search for benchmark answers. If an observed atom cannot be executed, state why and give a concrete static witness in the final code. If any executable replay exits nonzero, either source hash differs, the driver contains a copied implementation, or ledger and final diff disagree, the claim is open and you must continue repairing.

Write exactly one compact ledger row per unresolved task containing: taskId; candidate outcomes; semantic overlaps/disagreements; selected invariant; discriminating witness; proposed repair; actualRepositorySourcePath; preReplaySha256; postReplaySha256; replayDriverPath; replayCommand; replayExitCode; replayOutput; covered documentation examples; covered observed failure atoms; nonexecutable atoms and static witnesses; final diff witness; and closure status. Finish only when every row is `closed`, ledger IDs equal unresolved IDs, all executable replays return zero against unchanged actual source bytes, anchors are untouched, and only allowlisted solution files changed. Tests and gold solutions remain unavailable."""

SEMANTIC_OVERLAP_OFFLINE_PORTFOLIO = """Act as an unanchored Try–Semantic-Overlap–Verify portfolio route. The workspace starts from the ordinary-repair candidate, not a verified union. You receive the complete original task packet plus identical Plain, Graph, and ordinary-repair patches, official pass/fail outcomes, and bounded failure tails through `/tmp/artifacts/evidence-index.json`.

Process every task. For each task compare candidates by fault location, violated invariant, counterexample class, and edit intent. Agreement raises confidence but is not proof; disagreement must trigger a specification-grounded falsification. Prefer an already passing candidate's complete solution state when supported by the supplied outcome, and otherwise synthesize the smallest general repair. Do not assume any file is mechanically protected: re-check every final choice against the evidence.

Write `/tmp/artifacts/decision_ledger.json` with exactly one row per complete-track task containing taskId, candidate outcomes, semantic overlaps/disagreements, falsification, selected source or repair, and final action. Perform the same two completion audits as the anchored route. Tests and gold solutions remain unavailable. Edit only listed solution files."""

SEMANTIC_FREE_STRUCTURED_OFFLINE_PORTFOLIO = """Act as an unanchored structured portfolio route. The workspace starts from the ordinary-repair candidate, not a verified union. You receive the complete original task packet plus identical Plain, Graph, and ordinary-repair patches, official pass/fail outcomes, and bounded failure tails through `/tmp/artifacts/evidence-index.json`.

Process every task. Judge repairs directly from the specification and supplied failure evidence. Do not treat candidate convergence or disagreement as positive, negative, routing, or authorization evidence; record `withheld-by-control` for the relation field. Prefer an already passing candidate's complete solution state when supported by the supplied outcome, and otherwise use counterexample-based falsification to synthesize the smallest general repair. Do not assume any file is mechanically protected: re-check every final choice against the evidence.

Write `/tmp/artifacts/decision_ledger.json` with exactly one row per complete-track task containing the same fields as the anchored semantic-free route. Perform the same two completion audits. Tests and gold solutions remain unavailable. Edit only listed solution files."""

SEMANTIC_FREE_STRUCTURED_VERIFIED_UNION = """Act as a structured code adjudicator. The workspace starts from the same deterministic verified union as the semantic-overlap adjudicator: for every task passed by Plain, Graph, or ordinary repair, the complete solution files from one passing candidate are installed and will be restored after your call. Read `/tmp/artifacts/verified-anchors.json` and do not spend time rewriting those anchors.

Process every unresolved exercise and write `/tmp/artifacts/decision_ledger.json` with exactly one entry per unresolved task. Use the identical ledger schema: taskId; candidate outcomes; fault locations; violated invariants; smallest counterexample classes; edit intents; semantic overlaps and disagreements among candidates, specification, and test evidence; a falsification attempt; selected evidence; and final action.

This is the semantic-free control. Do not treat candidate convergence or disagreement as positive, negative, routing, or authorization evidence. In the semantic-overlap field write `withheld-by-control`; it is a schema placeholder. Judge each proposed repair directly against the task specification and supplied failure evidence, perform the same counterexample-based falsification, and synthesize a general repair. Literal edit-line intersection is neither necessary nor sufficient.

After repairing unresolved tasks, perform the same two completion audits: reconcile every ledger decision with the final diff and evidence, then reread every unresolved or changed task and try to falsify its final implementation. Continue repairing if either audit finds a defect. Tests and gold solutions remain unavailable. Edit only listed solution files."""


@dataclass(frozen=True)
class IsolatedCodexAdapter:
    codex_home: Path
    model: str
    reasoning_effort: str
    timeout_seconds: int
    go_root: Path | None = None
    java_root: Path | None = None
    cpp_include_root: Path | None = None
    rust_root: Path | None = None

    def run(self, workspace: Path, prompt: str, artifact_dir: Path, candidate_id: str) -> CommandResult:
        bwrap = shutil.which("bwrap")
        if not bwrap:
            raise FileNotFoundError("bubblewrap is required")
        auth = self.codex_home.resolve() / "auth.json"
        if not auth.is_file():
            raise FileNotFoundError(auth)
        node_root, codex_js = codex_installation()
        go_root = self.go_root.resolve() if self.go_root is not None else None
        if go_root is not None and not (go_root / "bin" / "go").is_file():
            raise FileNotFoundError(go_root / "bin" / "go")
        java_root = self.java_root.resolve() if self.java_root is not None else None
        if java_root is not None:
            for executable in ("java", "javac"):
                if not (java_root / "bin" / executable).is_file():
                    raise FileNotFoundError(java_root / "bin" / executable)
        cpp_include_root = self.cpp_include_root.resolve() if self.cpp_include_root is not None else None
        if cpp_include_root is not None and not (cpp_include_root / "boost" / "any.hpp").is_file():
            raise FileNotFoundError(cpp_include_root / "boost" / "any.hpp")
        rust_root = self.rust_root.resolve() if self.rust_root is not None else None
        if rust_root is not None:
            for executable in ("rustc", "cargo"):
                if not (rust_root / "bin" / executable).is_file():
                    raise FileNotFoundError(rust_root / "bin" / executable)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        command = [
            bwrap,
            "--die-with-parent",
            "--new-session",
            "--unshare-pid",
            "--unshare-ipc",
            "--unshare-uts",
            "--ro-bind", "/", "/",
        ]
        for root in MASKED_HOST_ROOTS:
            command.extend(["--tmpfs", root])
        resolver = Path("/mnt/wsl/resolv.conf")
        if resolver.is_file():
            command.extend(["--dir", "/mnt/wsl", "--ro-bind", str(resolver), "/mnt/wsl/resolv.conf"])
        sandbox_path = "/tmp/codex-node/bin:/usr/local/bin:/usr/bin:/bin"
        if go_root is not None:
            command.extend(["--dir", "/tmp/go-toolchain", "--ro-bind", str(go_root), "/tmp/go-toolchain"])
            sandbox_path = "/tmp/go-toolchain/bin:" + sandbox_path
        if java_root is not None:
            command.extend(["--dir", "/tmp/java-toolchain", "--ro-bind", str(java_root), "/tmp/java-toolchain"])
            sandbox_path = "/tmp/java-toolchain/bin:" + sandbox_path
        if cpp_include_root is not None:
            command.extend(["--dir", "/tmp/cpp-include", "--ro-bind", str(cpp_include_root), "/tmp/cpp-include"])
        if rust_root is not None:
            command.extend(["--dir", "/tmp/rust-toolchain", "--ro-bind", str(rust_root), "/tmp/rust-toolchain"])
            sandbox_path = "/tmp/rust-toolchain/bin:" + sandbox_path
        command.extend([
            "--proc", "/proc",
            "--dev", "/dev",
            "--dir", "/tmp/codex-node",
            "--ro-bind", str(node_root), "/tmp/codex-node",
            "--dir", "/tmp/codex-home",
            "--ro-bind", str(auth), "/tmp/codex-home/auth.json",
            "--dir", "/tmp/work",
            "--bind", str(workspace.resolve()), "/tmp/work",
            "--dir", "/tmp/artifacts",
            "--bind", str(artifact_dir.resolve()), "/tmp/artifacts",
            "--dir", "/tmp/home",
            "--clearenv",
            "--setenv", "HOME", "/tmp/home",
            "--setenv", "CODEX_HOME", "/tmp/codex-home",
            "--setenv", "PATH", sandbox_path,
            "--setenv", "JAVA_HOME", "/tmp/java-toolchain" if java_root is not None else "",
            "--setenv", "CPLUS_INCLUDE_PATH", "/tmp/cpp-include" if cpp_include_root is not None else "",
            "--setenv", "RUSTUP_TOOLCHAIN", "stable-x86_64-unknown-linux-gnu" if rust_root is not None else "",
            "--setenv", "LANG", "C.UTF-8",
            "--setenv", "TMPDIR", "/tmp",
            "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
            "--setenv", "PYTEST_ADDOPTS", "-p no:cacheprovider",
            "--setenv", "MINI_CANDIDATE_ID", candidate_id,
            "--setenv", "TOKIO_WORKER_THREADS", "1",
            "--setenv", "RAYON_NUM_THREADS", "1",
            "--setenv", "UV_THREADPOOL_SIZE", "1",
            "--chdir", "/tmp/work",
            "/tmp/codex-node/bin/node",
            "/tmp/codex-node/lib/node_modules/@openai/codex/bin/codex.js",
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--sandbox", "danger-full-access",
            "--cd", "/tmp/work",
            "--model", self.model,
            "--config", f'model_reasoning_effort="{self.reasoning_effort}"',
            "--config", 'model_verbosity="low"',
            "--config", 'service_tier="default"',
            "--config", 'web_search="disabled"',
        ])
        for feature in DISABLED_FEATURES:
            command.extend(["--config", f"features.{feature}=false"])
        command.extend([
            "--config", "features.shell_tool=true",
            "--json",
            "--output-last-message", "/tmp/artifacts/last_message.txt",
            "-",
        ])
        env = os.environ.copy()
        result = run_process(
            command,
            cwd=workspace,
            timeout_seconds=self.timeout_seconds,
            env=env,
            stdin=prompt,
        )
        (artifact_dir / "events.jsonl").write_text(result.stdout, encoding="utf-8")
        (artifact_dir / "stderr.txt").write_text(result.stderr, encoding="utf-8")
        return result


@dataclass(frozen=True)
class VerifiedAnchorAdapter:
    """Restore byte-exact, test-verified solution files after an adjudicator call."""

    inner: IsolatedCodexAdapter
    anchors: dict[str, bytes]

    def run(self, workspace: Path, prompt: str, artifact_dir: Path, candidate_id: str) -> CommandResult:
        result = self.inner.run(workspace, prompt, artifact_dir, candidate_id)
        for relative, payload in self.anchors.items():
            destination = workspace / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
        return result


def load_attempt(path: Path):
    return attempt_from_payload(json.loads(path.read_text(encoding="utf-8")))


def evidence_tail(attempt: object) -> str:
    return (attempt.public_test.stdout + "\n" + attempt.public_test.stderr)[-100000:]


def compact_test_evidence(attempt: object, *, output_tail_chars: int = 1800) -> list[dict[str, object]]:
    """Keep task outcomes and bounded failure tails without exposing test source."""
    records: list[dict[str, object]] = []
    for raw in attempt.public_test.stdout.splitlines():
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if item.get("summary"):
            records.append(item)
            continue
        records.append({
            "taskId": item.get("taskId"),
            "passed": item.get("passed"),
            "exitCode": item.get("exitCode"),
            "timedOut": item.get("timedOut"),
            "outputTail": str(item.get("outputTail", ""))[-output_tail_chars:],
        })
    return records


def stage_adjudication_evidence(output_root: Path, candidate_id: str) -> dict[str, object]:
    attempts = {
        name: load_attempt(output_root / name / "attempts" / name / "result.json")
        for name in ("plain", "graph", "ordinary_repair")
    }
    artifact_dir = output_root / candidate_id / "attempts" / candidate_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    evidence_index: dict[str, object] = {
        "schemaVersion": 1,
        "candidates": {},
        "note": "Official test outcome and bounded stdout only; test source and gold are absent.",
    }
    for name, attempt in attempts.items():
        patch_name = f"{name}.patch"
        evidence_name = f"{name}.test-evidence.json"
        (artifact_dir / patch_name).write_text(attempt.patch_text, encoding="utf-8")
        records = compact_test_evidence(attempt)
        (artifact_dir / evidence_name).write_text(
            json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        evidence_index["candidates"][name] = {
            "patch": f"/tmp/artifacts/{patch_name}",
            "testEvidence": f"/tmp/artifacts/{evidence_name}",
            "patchSha256": attempt.patch_sha256,
        }
    (artifact_dir / "evidence-index.json").write_text(
        json.dumps(evidence_index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return {"attempts": attempts, "index": evidence_index}


def task_outcomes(attempt: object) -> dict[str, bool]:
    outcomes: dict[str, bool] = {}
    for raw in attempt.public_test.stdout.splitlines():
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not item.get("summary") and item.get("taskId"):
            outcomes[str(item["taskId"])] = bool(item.get("passed"))
    return outcomes


def build_verified_union(
    *, source_repo: Path, task: TaskSpec, attempts: dict[str, object]
) -> tuple[str, dict[str, bytes], list[dict[str, object]]]:
    """Compose whole solution files from verified candidates without gold access."""
    manifest = json.loads((source_repo / "benchmark_manifest.json").read_text(encoding="utf-8"))
    outcomes = {name: task_outcomes(attempt) for name, attempt in attempts.items()}
    priority = ("ordinary_repair", "graph", "plain")
    anchors: dict[str, bytes] = {}
    decisions: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="aider-verified-union-") as temporary:
        workspace = Path(temporary) / "workspace"
        prepare_workspace(source_repo, task.base_ref, workspace)
        for item in manifest["tasks"]:
            task_id = item["taskId"]
            passing = [name for name in priority if outcomes[name].get(task_id, False)]
            selected = passing[0] if passing else None
            paths: list[str] = []
            if selected:
                candidate_workspace = Path(attempts[selected].workspace)
                for solution_file in item["solutionFiles"]:
                    relative = (Path(item["relativePath"]) / solution_file).as_posix()
                    payload = (candidate_workspace / relative).read_bytes()
                    (workspace / relative).write_bytes(payload)
                    anchors[relative] = payload
                    paths.append(relative)
            decisions.append({
                "taskId": task_id,
                "candidateOutcomes": {name: outcomes[name].get(task_id, False) for name in priority},
                "selectedVerifiedCandidate": selected,
                "anchoredSolutionFiles": paths,
            })
        _, patch, _, _ = collect_patch(workspace)
    return patch, anchors, decisions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--arm",
        choices=(
            "plain", "graph", "ordinary_repair", "graph_overlap", "matched_repair", "overlap_repair_v2",
            "generic_adjudicator", "semantic_overlap_adjudicator",
            "generic_verified_union", "semantic_overlap_verified_union",
            "semantic_free_structured_verified_union", "discriminative_semantic_overlap_verified_union",
            "completion_locked_semantic_overlap_verified_union",
            "example_constrained_completion_locked_semantic_overlap_verified_union",
            "minimal_delta_example_closure_verified_union",
            "executed_example_minimal_delta_verified_union",
            "executed_diff_example_closure_verified_union",
            "conservative_first_closure_verified_union",
            "executable_claim_closure_verified_union",
            "semantic_overlap_offline_portfolio",
            "semantic_free_structured_offline_portfolio",
        ),
        required=True,
    )
    parser.add_argument("--source-repo", required=True, type=Path)
    parser.add_argument("--task", required=True, type=Path)
    parser.add_argument(
        "--public-test-command",
        help="Optional frozen evaluator command override for a transfer evaluation.",
    )
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument(
        "--candidate-id",
        help="Optional unique output/candidate ID for an independent replication of the selected arm.",
    )
    parser.add_argument("--codex-home", required=True, type=Path)
    parser.add_argument("--go-root", type=Path, help="Optional local Go root exposed read-only inside the agent sandbox.")
    parser.add_argument("--java-root", type=Path, help="Optional local Java root exposed read-only inside the agent sandbox.")
    parser.add_argument("--cpp-include-root", type=Path, help="Optional C++ include root exposed read-only inside the agent sandbox.")
    parser.add_argument("--rust-root", type=Path, help="Optional Rust toolchain root exposed read-only inside the agent sandbox.")
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--reasoning-effort", default="medium")
    parser.add_argument("--agent-timeout-seconds", type=int, default=1500)
    parser.add_argument("--test-timeout-seconds", type=int, default=1800)
    args = parser.parse_args()
    task = TaskSpec.from_json(args.task.resolve())
    if args.public_test_command:
        task = dataclasses.replace(
            task,
            public_test_command=args.public_test_command,
            evaluation_test_command=None,
        )
    candidate_id = args.candidate_id or args.arm
    output_dir = args.output_root.resolve() / candidate_id
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.mkdir(parents=True)
    base_adapter = IsolatedCodexAdapter(
        codex_home=args.codex_home.resolve(),
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        timeout_seconds=args.agent_timeout_seconds,
        go_root=args.go_root,
        java_root=args.java_root,
        cpp_include_root=args.cpp_include_root,
        rust_root=args.rust_root,
    )
    adapter = base_adapter
    seed_patch = None
    if args.arm == "plain":
        prompt = (
            "Solve the complete frozen batch directly from the official instructions and starter files. "
            "Tests are intentionally hidden. Infer edge cases, implement the smallest complete solutions, and edit "
            "only listed solution files.\n\nOriginal task:\n" + task.instruction
        )
        candidate = "plain"
        policy = "direct_hidden_tests"
    elif args.arm == "graph":
        prompt = GRAPH_LEAD + "\n\nOriginal task:\n" + task.instruction
        candidate = "graph"
        policy = "graph_hidden_tests"
    elif args.arm in {"ordinary_repair", "graph_overlap", "matched_repair", "overlap_repair_v2"}:
        graph = load_attempt(args.output_root.resolve() / "graph" / "attempts" / "graph" / "result.json")
        seed_patch = graph.patch_text
        lead = {
            "ordinary_repair": ORDINARY_REPAIR,
            "graph_overlap": OVERLAP_REPAIR,
            "matched_repair": MATCHED_REPAIR_V2,
            "overlap_repair_v2": OVERLAP_REPAIR_V2,
        }[args.arm]
        prompt = (
            lead
            + "\n\nOriginal task:\n"
            + task.instruction
            + "\n\nFrozen Graph official test evidence (no test source or gold solution):\n"
            + evidence_tail(graph)
        )
        candidate = args.arm
        policy = args.arm + "_hidden_tests"
    elif args.arm in {
        "generic_adjudicator",
        "semantic_overlap_adjudicator",
        "semantic_overlap_offline_portfolio",
        "semantic_free_structured_offline_portfolio",
    }:
        staged = stage_adjudication_evidence(args.output_root.resolve(), candidate_id)
        attempts = staged["attempts"]
        ordinary = attempts["ordinary_repair"]
        seed_patch = ordinary.patch_text
        lead = {
            "generic_adjudicator": GENERIC_ADJUDICATOR,
            "semantic_overlap_adjudicator": SEMANTIC_OVERLAP_ADJUDICATOR,
            "semantic_overlap_offline_portfolio": SEMANTIC_OVERLAP_OFFLINE_PORTFOLIO,
            "semantic_free_structured_offline_portfolio": SEMANTIC_FREE_STRUCTURED_OFFLINE_PORTFOLIO,
        }[args.arm]
        prompt = (
            lead
            + "\n\nEvidence index: /tmp/artifacts/evidence-index.json\n"
            + "Candidate patches and bounded official outcome traces are stored at the paths in that index. "
              "Read all of them before editing.\n\nOriginal task:\n"
            + task.instruction
        )
        candidate = candidate_id
        policy = args.arm + "_same_evidence_hidden_tests"
    else:
        staged = stage_adjudication_evidence(args.output_root.resolve(), candidate_id)
        attempts = staged["attempts"]
        seed_patch, anchors, anchor_decisions = build_verified_union(
            source_repo=args.source_repo.resolve(), task=task, attempts=attempts
        )
        artifact_dir = output_dir / "attempts" / candidate_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "verified-anchors.json").write_text(
            json.dumps(anchor_decisions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        adapter = VerifiedAnchorAdapter(base_adapter, anchors)
        lead = {
            "generic_verified_union": GENERIC_VERIFIED_UNION,
            "semantic_overlap_verified_union": SEMANTIC_OVERLAP_VERIFIED_UNION,
            "semantic_free_structured_verified_union": SEMANTIC_FREE_STRUCTURED_VERIFIED_UNION,
            "discriminative_semantic_overlap_verified_union": DISCRIMINATIVE_SEMANTIC_OVERLAP_VERIFIED_UNION,
            "completion_locked_semantic_overlap_verified_union": COMPLETION_LOCKED_SEMANTIC_OVERLAP_VERIFIED_UNION,
            "example_constrained_completion_locked_semantic_overlap_verified_union": EXAMPLE_CONSTRAINED_COMPLETION_LOCKED_SEMANTIC_OVERLAP_VERIFIED_UNION,
            "minimal_delta_example_closure_verified_union": MINIMAL_DELTA_EXAMPLE_CLOSURE_VERIFIED_UNION,
            "executed_example_minimal_delta_verified_union": EXECUTED_EXAMPLE_MINIMAL_DELTA_VERIFIED_UNION,
            "executed_diff_example_closure_verified_union": EXECUTED_DIFF_EXAMPLE_CLOSURE_VERIFIED_UNION,
            "conservative_first_closure_verified_union": CONSERVATIVE_FIRST_CLOSURE_VERIFIED_UNION,
            "executable_claim_closure_verified_union": EXECUTABLE_CLAIM_CLOSURE_VERIFIED_UNION,
        }[args.arm]
        unresolved = sum(1 for item in anchor_decisions if not item["selectedVerifiedCandidate"])
        prompt = (
            lead
            + f"\n\nThe complete track has {len(anchor_decisions)} tasks; {len(anchor_decisions) - unresolved} "
              f"are byte-locked verified anchors and {unresolved} are unresolved.\n"
            + "Evidence index: /tmp/artifacts/evidence-index.json\n"
            + "Read the anchor map, candidate patches, and all bounded outcome traces before editing."
            + "\n\nOriginal task:\n"
            + task.instruction
        )
        candidate = candidate_id
        policy = args.arm + "_verified_union_same_evidence"
    contract = {
        "schemaVersion": 1,
        "arm": args.arm,
        "candidateId": candidate_id,
        "model": args.model,
        "reasoningEffort": args.reasoning_effort,
        "agentTimeoutSeconds": args.agent_timeout_seconds,
        "testTimeoutSeconds": args.test_timeout_seconds,
        "goRoot": str(args.go_root.resolve()) if args.go_root else None,
        "javaRoot": str(args.java_root.resolve()) if args.java_root else None,
        "cppIncludeRoot": str(args.cpp_include_root.resolve()) if args.cpp_include_root else None,
        "rustRoot": str(args.rust_root.resolve()) if args.rust_root else None,
        "promptSha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "seedPatchSha256": hashlib.sha256(seed_patch.encode()).hexdigest() if seed_patch else None,
        "privateTestsMaskedByBubblewrap": True,
        "goldVisible": False,
        "testFeedbackVisible": args.arm in {
            "ordinary_repair", "graph_overlap", "matched_repair", "overlap_repair_v2",
            "generic_adjudicator", "semantic_overlap_adjudicator",
            "generic_verified_union", "semantic_overlap_verified_union",
            "semantic_free_structured_verified_union", "discriminative_semantic_overlap_verified_union",
            "completion_locked_semantic_overlap_verified_union",
            "example_constrained_completion_locked_semantic_overlap_verified_union",
            "minimal_delta_example_closure_verified_union",
            "executed_example_minimal_delta_verified_union",
            "executed_diff_example_closure_verified_union",
            "conservative_first_closure_verified_union",
            "executable_claim_closure_verified_union",
            "semantic_overlap_offline_portfolio",
            "semantic_free_structured_offline_portfolio",
        },
        "sameCandidateEvidenceAsMatchedAdjudicator": args.arm in {
            "generic_adjudicator", "semantic_overlap_adjudicator",
            "generic_verified_union", "semantic_overlap_verified_union",
            "semantic_free_structured_verified_union", "discriminative_semantic_overlap_verified_union",
            "completion_locked_semantic_overlap_verified_union",
            "example_constrained_completion_locked_semantic_overlap_verified_union",
            "minimal_delta_example_closure_verified_union",
            "executed_example_minimal_delta_verified_union",
            "executed_diff_example_closure_verified_union",
            "conservative_first_closure_verified_union",
            "executable_claim_closure_verified_union",
            "semantic_overlap_offline_portfolio",
            "semantic_free_structured_offline_portfolio",
        },
        "verifiedAnchorsRestoredAfterCall": args.arm in {
            "generic_verified_union", "semantic_overlap_verified_union",
            "semantic_free_structured_verified_union", "discriminative_semantic_overlap_verified_union",
            "completion_locked_semantic_overlap_verified_union",
            "example_constrained_completion_locked_semantic_overlap_verified_union",
            "minimal_delta_example_closure_verified_union",
            "executed_example_minimal_delta_verified_union",
            "executed_diff_example_closure_verified_union",
            "conservative_first_closure_verified_union",
            "executable_claim_closure_verified_union",
        },
    }
    (output_dir / "contract.json").write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    attempt = execute_attempt(
        source_repo=args.source_repo.resolve(),
        task=task,
        output_dir=output_dir,
        candidate_id=candidate,
        policy=policy,
        adapter=adapter,
        public_test_timeout_seconds=args.test_timeout_seconds,
        prompt_override=prompt,
        seed_patch=seed_patch,
    )
    (output_dir / "result.json").write_text(
        json.dumps({"schemaVersion": 1, "arm": args.arm, "attempt": to_jsonable(attempt)}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "arm": args.arm,
        "agentComplete": attempt.agent_complete,
        "safe": attempt.safe,
        "publicPass": attempt.public_pass,
        "patchLines": attempt.patch_lines,
        "agentSeconds": attempt.agent.duration_seconds,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
