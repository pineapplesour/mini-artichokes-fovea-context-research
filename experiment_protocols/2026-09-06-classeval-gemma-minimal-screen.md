# ClassEval-Pro Gemma minimal-thinking screen

Status: implementation ready; launch approval is pending root review. This is
a development screen, not evidence of superiority or a paper/MAC result.

This variant delegates all behavior to the frozen
`tools.run_classeval_dependency_separator_mixed` runner at base commit
`212368e`. The only solver-configuration change is
`thinkingLevel=minimal`; model `gemma-4-26b-a4b-it`, temperature `0.6`,
`maxOutputTokens=16384`, timeout `120s`, no tools, no retries, fixed task
ordinal modulo 10 key assignment, prompts, source handling, evaluator,
selector, and screen gate remain unchanged. The wrapper contract records
`wrapperSha`, `baseCommit`, and `variant`.

The input gate is the complete official ClassEval-Pro 300-task ordinary parent
(268 passed and exactly U32 unresolved) plus the same validated cached Luna
E/A artifacts. Every U32 task receives one fresh minimal Gemma E/B call;
partial artifacts from the stopped high-thinking screen are never reused, and
no failure-selected subset or high B answer is retried. The denominator stays
300 and all failures remain counted. Cached E/A and fresh B are a screen only;
there are no O/C/follow-up calls in this runner.

Default invocation is dry-run; `--execute` is the sole execution switch. Use
an independent sibling output root:

```text
python -m tools.run_classeval_gemma_minimal_screen \
  --parent-root runs/classeval-pro300-text-overlap-20260905-development-v2 \
  --e-cache-root runs/classeval-pro300-overlap-repair-tail-20260905-development-v1 \
  --run-root runs/classeval-pro300-gemma-minimal-screen-20260906-development-v1 \
  --keys-file /home/pineapple/bunjum2/work27/yt-predict/gemini_keys.txt
```

Adding `--execute` requires separate root approval. Tests use mocked
delegation only; no API, evaluator, secret, benchmark, or model call is part
of this authoring change.
