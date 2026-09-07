# Plain Codex visible-options rerun protocol (pre-freeze)

Status: manifests, file contracts, structural tests, and process-isolation
dry-runs are prepared. No solver or grader model call has been made. The real
grader packet is generated only after the complete solver answer file exists.

## Scope

The new baseline is not a continuation of the sealed 619-case choice-hidden
run. It is a new matched campaign with these public inputs:

- original multiple-choice question and every original option;
- the model must return the content of the selected option, not only its label;
- already-open-response official questions remain open response;
- no subject database, Universal/Beta6 engine, evaluated memory, or custom
  skill;
- optional native web search and short calculation/code are allowed;
- direct or near-direct exam/question/quiz/answer-key lookup is forbidden;
- all 3 legal end-to-end families and all 10 public variants are required.

The source-folder re-audit is
`benchmarks/islam_official_source_audit.json`. It currently establishes 1,299
scorable exam cases: the legacy registered 1,235 after replacing AQA4 with
AQA20, plus BYU16 and Cambridge32. The legal 10 variants are reported
separately and are not added to the exam denominator.

## Historical outputs and resume

Do not omit a case merely because some older campaign executed the same source
question. Historical answers have different prompts, output contracts, tool
boundaries, batching, or scorer contracts and cannot be mixed into this score.

There is one solver invocation rather than a set of independently resumable
question batches. An old answer file may count as the completed result of this
new campaign only when it binds all of the following exactly:

- campaign freeze ID and freeze SHA-256;
- case IDs and their order;
- public manifest and public prompt hashes;
- model, reasoning effort, verbosity, and Codex transport identity;
- tool policy and anti-cheating policy;
- public-bundle builder and runner implementation hashes;
- a completed trace, positive token telemetry, valid response schema, and
  accepted policy audit.

A file that merely exists is not resumable evidence. A changed input or policy
creates a new campaign ID and the whole solver job must run again. A
quota/transport failure may move to another authenticated Codex home only
before any semantically valid complete answer file is accepted. Do not call a
model again for only the missing or malformed rows.

## One-call file-oriented solver

Make exactly one Plain Codex invocation responsible for the complete public
suite: 1,299 exam cases and all ten legal variants. This is one agent job, not
1,309 independent completion requests. The agent may iterate through the
public files and use local code to manage its work, but it may not spawn model
workers or delegate subsets to other agents.

Do not inline the whole suite into the final-response channel. Build an
isolated public-only workspace containing a frozen `questions.jsonl` and run
instructions. Require the solver to append or checkpoint its work locally and
atomically finish `answers.jsonl`. Each row has exactly the public case ID and
the answer text; MCQ rows contain the selected option's content rather than
only its label. The final chat message is only a completion notice and is not
the scored answer source.

The solver workspace must not expose private manifests, answer keys, grader
rubrics, historical predictions, previous benchmark outputs, evaluated
memory, custom skills, subject databases, Universal/Beta6 code, or the source
folder that contains official keys. Native web research and local calculation
code remain available under the anti-cheating policy below.

After the invocation exits, deterministic local validation requires:

- exactly 1,309 distinct rows: 1,299 exam IDs plus ten legal-variant IDs;
- every expected ID exactly once and no unknown ID;
- non-empty answer text for every row and valid UTF-8 JSONL;
- an unchanged public input hash, completed Codex trace, positive token
  telemetry, and a passing tool/anti-cheating audit.

Local validation may reject a file but may not fill or semantically alter it.
Failure of any condition marks the one-call solver run `INCOMPLETE`. Do not
top up selected rows with later solver calls; a deliberate whole-suite rerun
is a separate trial with a new run ID.

## Tool and cheating boundary

The solver invocation may use native web search and local calculation/code
when useful. The campaign records every query, URL/open action, command, token
count, and elapsed time. No database or subject MCP is mounted.

For exam questions, forbidden targets include the exact or near-exact stem,
distinctive option phrases, exam/paper name combined with the tested content,
benchmark/case IDs, answer keys, mirrors, and historical answers. General
concept or fact research is allowed.

For legal end-to-end questions, researching the public facts, legal issue, and
precedents named or implied by the user's query is part of the task and is
allowed. Local/private grader targets, benchmark files, historical run output,
and answer artifacts remain forbidden.

## One-call grading

After the complete accepted `answers.jsonl` is frozen, build one grader packet
containing every case ID, public question, original options when any, solver
answer, official correct option content or official mark scheme, and the
private legal rubric for the ten end-to-end variants.

Invoke one separate Codex grader exactly once for the complete packet. It may
read the staged packet and write its output file locally, but has no web,
database, benchmark history, or additional semantic model calls. It must write
every supplied ID exactly once to `grades.jsonl`. Use compact per-case verdicts
and award official raw marks for constructed-response questions. Local code
may validate IDs, ranges, totals, and JSON shape, but it may not make a second
semantic judgment. If the sole grade file is missing, truncated, or invalid,
the grading campaign is unresolved; do not silently shard it or call a
consensus panel.

Report the score without hiding the mixed task shapes:

- 1,251 binary exam cases as pass/fail/unresolved accuracy;
- 48 official constructed-response parts as raw marks out of 338;
- the official-points exam aggregate as binary passes plus constructed raw
  marks, out of 1,589;
- the ten legal E2E variants separately as pass/fail/unresolved.

Do not call a case-normalized 1,299 denominator an accuracy score for the
constructed responses; that would discard their official multi-mark schemes.

## Preparation status and completed execution

The first five preparation gates now pass without a model call:

- AQA20, BYU16, and Cambridge32 public/private manifests were rebuilt from the
  hash-verified local official sources.
- The visible-options registry resolves to exactly 1,299 exam cases plus ten
  legal variants.
- The deterministic public `questions.jsonl` has 1,309 rows and is about
  0.94 MB.
- A placeholder-only structural grader packet also has 1,309 rows and is about
  1.29 MB; the real packet will differ with solver-answer length.
- Bubblewrap probes prove that the staged input is read-only, output is
  writable, and `/home`, `/mnt`, `/root`, `/tmp`, and `/var/tmp` host content is
  masked from both agent roles.

The initial `runs/plain-codex-visible-options-one-agent-20260724-v1/` preflight
bundle is historical preparation only. The accepted default campaign is
`runs/plain-codex-visible-options-one-agent-luna-high-20260724-v2/`, with
embedded solver freeze SHA-256 `6faa70a9...b2fb9b87`. It used the user-selected
`gpt-5.6-luna`, high reasoning, low verbosity, default service tier, native web
plus local code for the solver, and no DB, skills, plugins, memory, or
multi-agent delegation.

The one solver call and one Luna/high grader call both passed isolation,
policy, schema, count, ID-order, and hash validation. The default score is
721/1,251 binary exam points plus 55/338 constructed marks, or 776/1,589
official exam points, with legal E2E 0/10. A separate Sol/xhigh one-call grade
audit of the identical answer file scored 794/1,589 and 0/10 legal. Luna/high
remains the recurring grader default; the Sol result is a sensitivity audit.

The byte-identical Luna/low solver control completed its file contract but
collapsed into mass copied and templated answers, scoring 14/1,589 under the
Luna/high grader. It is evidence against that whole-file/low execution shape,
not a normal Luna/low capability baseline. Exact public-safe artifacts and
machine-readable results are published in
`benchmark_reports/2026-07-24-visible-options-one-call/`.
