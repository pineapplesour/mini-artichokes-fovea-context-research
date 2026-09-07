# QuixBugs development smoke protocol

Purpose: validate live Codex execution, patch capture, public-test selection,
and receipt production before choosing a repository-level confirmation suite.
This smoke set is not eligible for the paper's headline claim because QuixBugs
is old, small, public, and may be present in model training data.

- Upstream: `jkoppel/QuixBugs`
- Upstream frozen commit: `4257f44b0ff1181dedaedee6a447e133219fcebf`
- Local sanitized snapshot commit:
  `61985e690803a41f3a3519934d631da775d1f9ec`
- Sanitization: retained buggy `python_programs`, Python tests, root pytest
  configuration, and JSON test cases; excluded all supplied corrected programs,
  Java translations, repository history, and unrelated files.
- Model: `gpt-5.6-luna`, medium reasoning.
- Agent timeout: 180 seconds per attempt for smoke only.
- Test timeout: 60 seconds.
- The targeted public tests are also used for smoke evaluation. A later
  confirmation benchmark must keep evaluation-only tests inaccessible until
  after candidate selection.
