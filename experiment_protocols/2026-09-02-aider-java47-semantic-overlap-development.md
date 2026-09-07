# Frozen development protocol: Aider Java47 Try–Semantic-Overlap–Verify

Status: frozen before the first model call. This is a development experiment,
not a confirmatory result.

## Question

Can a semantic-overlap adjudicator produce a large whole-track improvement
over Plain Codex and a positive improvement over a compute- and
evidence-matched generic adjudicator on an official coding benchmark where
direct Luna is not at ceiling?

The proposed mechanism is **Try–Semantic-Overlap–Verify (TOV)**. It treats
overlap as agreement about fault location, violated invariant, counterexample
class, and edit intent. It does not require literal line intersection and does
not use missing overlap as a veto. A mandatory task-level decision ledger and
two completion audits make every final decision accountable to the candidate
patches, specification, and observed execution evidence.

## Complete benchmark and freeze

- Official source: `Aider-AI/polyglot-benchmark`, commit
  `7e0611e77b54e2dea774cdc0aa00cf9f7ed6144f`.
- Benchmark: all 47 exercises in the official Java track, alphabetically
  ordered. No exercise is selected, removed, replaced, or topped up.
- Primary denominator: 47. Any per-exercise analysis retains all 47 rows.
- Agent workspaces exclude `.meta` and every official test file. The private
  evaluator restores the frozen official tests and enables all progressive
  JUnit tests by removing only `@Disabled` annotations in a temporary copy.
- Gold implementations are absent from both agent and evaluator workspaces.
- Freeze SHA-256:
  `5d353e095fd7056c1d6085d12726a7b4a4ead3092c37d25d13768db711fc1be6`.
- Public task SHA-256:
  `e4b7c79ab39c0b130c8102582bc8e43055384360c989ed9a9d7d37cbb33772f7`.
- Manifest SHA-256:
  `e4b91e08ead2772b0194a54dac7011af7a007990d2b42791e21d8cf10e3471fa`.
- Evaluator SHA-256:
  `997e254b413c4ca248cf68162541843a9a92c0c561539649ab3fc9d681d1475c`.
- Runner SHA-256:
  `d4cfd48e385f5232736d844cb26796f1a53d1c9e0ba1fbf557f6dd50b4f38395`.

## Model, account, and unit of work

Every call uses `gpt-5.6-luna`, medium reasoning, web disabled, and
`CODEX_HOME=/home/pineapple/.codex-new-account`. Each call receives and is
responsible for the entire 47-exercise track at once. There are no per-task
model calls. Agent timeout is 30 minutes and evaluation timeout is 30 minutes.

Exactly five development calls are allowed, in this order:

1. **Plain**: direct one-pass repair from instructions and starter code, with
   tests hidden.
2. **Graph**: one-pass requirement/edge-case/invariant reasoning graph, with
   tests hidden.
3. **Ordinary repair**: starts from Graph and receives Graph's complete
   official failure output. This represents a short Reflexion/Self-Refine
   execution-feedback baseline.
4. **Generic adjudicator**: starts from ordinary repair and receives the
   complete Plain, Graph, and ordinary patches plus identical task-level
   official outcomes and bounded failure tails.
5. **TOV adjudicator**: starts from the same ordinary repair patch and receives
   the byte-identical candidate evidence packet. It additionally must create
   the semantic-overlap/falsification decision ledger for all 47 tasks and
   perform two completion audits.

The generic and TOV adjudicators therefore have the same model, effort, number
of calls, starting patch, task packet, candidate patches, official outcomes,
and failure evidence. Their prompt-level decision procedure is the intended
treatment contrast. TOV is evaluated in a fresh workspace and cannot read the
generic adjudicator's output.

No result-led rerun, prompt repair, missing-task top-up, task deletion, or
candidate replacement is allowed. An incomplete call and all of its 47 task
outcomes remain in the record.

## Frozen analysis and development promotion rule

Report exact task pass vectors and paired rescues/harms for all arms. The
primary development contrasts, in fixed order, are:

1. TOV minus Plain;
2. TOV minus ordinary repair;
3. TOV minus generic adjudication.

Report percentage-point differences, paired exact McNemar/binomial tests, and
paired task bootstrap intervals, while labeling task-level inference as
developmental because the benchmark track is a single realized suite.

Promote the mechanism to prospective evaluation on additional complete
official tracks only if all of these hold:

- TOV improves over Plain by at least 10/47 tasks (21.3 percentage points);
- TOV has more rescues than harms versus ordinary repair;
- TOV improves over generic adjudication by at least 2/47 tasks (4.3 points),
  with more rescues than harms;
- the 47-entry decision ledger is complete and every changed path is an
  allowed solution file.

The 20-point threshold applies to the main Plain comparison. A positive
matched-adjudicator contrast is separately required so that a large gain
cannot be attributed merely to extra calls, candidate access, or execution
feedback.

If promoted, the prompts and decision policy are frozen unchanged before
running complete additional language tracks. The final paper may describe a
coding domain in which semantic overlap is especially observable, but may not
represent benchmark-running machinery as the contribution.

## Relation to prior evidence

The earlier Java20 and Rust/Python task batches are subset diagnostics and are
not pooled into the 47-task primary score. QuixBugs Python40 is retained as a
whole-suite ceiling diagnostic because Plain Luna solved 40/40; no TOV effect
can be estimated there. Prior strict two-of-three change authorization lost to
ordinary repair, so this protocol replaces that veto with semantic overlap as
a confidence/routing signal plus explicit falsification.
