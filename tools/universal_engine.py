#!/usr/bin/env python3
"""Universal engine — one mechanism for every legal task in this repo.

The principle, made executable:

    분해 → 독립 시도/검증 → 원장 종결 → 결정적 합성 + 완결 게이트

Every prior benchmark taught the same lesson: a single model call that must
both analyse and conclude collapses, and majority voting over such calls does
not repair it (three independent framings of the same case agree 84% of the
time and are still only 75% accurate; where they split, majority voting scores
exactly chance). The fix is never "vote harder" — it is to take the final
aggregation OUT of the model and put it in code:

  stage 1  DECOMPOSE   one call turns the task into a list of atomic,
                       independently checkable propositions (claim elements,
                       affirmative defenses, sub-questions, checklist items).
  stage 2  VERIFY      one ISOLATED call per proposition. Each call sees only
                       the case material and its own proposition, and answers
                       충족 / 불충족 / 불명 with a confidence. No call ever
                       sees another call's verdict, so errors cannot cascade.
  stage 3  LEDGER      every verdict is written to a per-case ledger with its
                       evidence quote, so the decision is auditable.
  stage 4  SYNTHESIZE  a DETERMINISTIC rule (pure Python, no model) combines
                       the verdicts into the final answer, and derives the
                       confidence from the bottleneck proposition.
  stage 5  GATE        completion gates check the output is well formed and
                       every required proposition was decided; a case failing
                       a gate is re-run for the missing piece only, never
                       silently accepted.

Domains are plug-in profiles that differ only in (a) what a proposition is,
(b) the deterministic synthesis rule, and (c) the gates. The engine code is
shared, which is the point: the same mechanism must serve tax-consequence
prediction, judgment-outcome prediction, and legal question answering.

Backends: `openrouter` (any model id) or `codex` (bwrap-isolated Codex CLI).
Both are per-case and stateless; concurrency is bounded.

usage:
  universal_engine.py run --bench B.jsonl --out RUNDIR [--profile auto]
                          [--model anthropic/claude-opus-5] [--jobs 5]
  universal_engine.py score --run RUNDIR --private P.jsonl
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import sys
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[1]
KEY_PATH = Path(
    os.environ.get(
        "OPENROUTER_KEY_FILE",
        "/tmp/claude-1000/-home-pineapple/57426e87-6333-45bf-8da9-73507afe2b2e/scratchpad/or_key.txt",
    )
)

# --------------------------------------------------------------------------
# backend
# --------------------------------------------------------------------------


class OpenRouterBackend:
    def __init__(self, model: str, max_tokens: int = 4000, effort: str = "high") -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.effort = effort
        self.key = KEY_PATH.read_text().strip()
        self._lock = threading.Lock()
        self.calls = 0

    def __call__(self, prompt: str, *, max_tokens: int | None = None) -> str:
        body = {
            "model": self.model,
            "reasoning": {"effort": self.effort},
            "max_tokens": max_tokens or self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        for attempt in range(3):
            try:
                req = urllib.request.Request(
                    "https://openrouter.ai/api/v1/chat/completions",
                    data=json.dumps(body).encode(),
                    headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
                )
                data = json.load(urllib.request.urlopen(req, timeout=900))
                text = data["choices"][0]["message"]["content"] or ""
                with self._lock:
                    self.calls += 1
                if not text and attempt < 2:
                    body["max_tokens"] = min(int(body["max_tokens"]) * 2, 32000)
                    continue
                return text
            except Exception:
                if attempt == 2:
                    return ""
                time.sleep(6 * (attempt + 1))
        return ""


class CodexBackend:
    """Free-tier backend: one bwrap-isolated `codex exec` per call.

    Same contract as OpenRouterBackend (prompt in, text out), so the engine is
    backend-agnostic: an experiment can be prototyped on a metered API and then
    re-run at scale on the subscription runner without touching engine logic.
    Each call is a fresh sandbox with no network tools and no shared state,
    which is exactly the isolation the VERIFY stage requires.
    """

    def __init__(self, codex_home: Path, model: str = "gpt-5.6-luna",
                 effort: str = "medium", timeout_seconds: int = 420) -> None:
        import subprocess  # noqa: F401  (imported lazily; used in __call__)

        self.codex_home = Path(codex_home)
        self.model = model
        self.effort = effort
        self.timeout_seconds = timeout_seconds
        self._lock = threading.Lock()
        self.calls = 0
        self._seq = 0
        self.workdir = Path(os.environ.get("ENGINE_CODEX_WORK", "/tmp/engine-codex"))
        self.workdir.mkdir(parents=True, exist_ok=True)

    def __call__(self, prompt: str, *, max_tokens: int | None = None) -> str:
        import shutil
        import subprocess

        sys.path.insert(0, str(REPO_ROOT))
        from tools.run_plain_codex_file_agent import base_bwrap_command, DISABLED_FEATURES

        with self._lock:
            self._seq += 1
            seq = self._seq
        role = self.workdir / f"call-{seq:06d}"
        input_dir, output_dir = role / "input", role / "output"
        input_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        (input_dir / "TASK.md").write_text(prompt, encoding="utf-8")
        command, _ = base_bwrap_command(input_dir=input_dir, output_dir=output_dir,
                                        codex_home=self.codex_home)
        command.extend([
            "/tmp/codex-node/bin/node",
            "/tmp/codex-node/lib/node_modules/@openai/codex/bin/codex.js",
            "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "--skip-git-repo-check", "--sandbox", "danger-full-access",
            "--cd", "/tmp/work", "--model", self.model,
            "--config", f'model_reasoning_effort="{self.effort}"',
            "--config", 'model_verbosity="low"',
            "--config", 'web_search="disabled"',
        ])
        for feature in DISABLED_FEATURES:
            command.extend(["--config", f"features.{feature}=false"])
        command.extend(["--config", "features.shell_tool=true",
                        "--output-last-message", "/tmp/work/output/last_message.txt", "-"])
        instruction = ("Read input/TASK.md and answer it exactly in the format it requires. "
                       "Your final chat message must contain the answer itself and nothing else.")
        try:
            proc = subprocess.run(command, input=instruction, text=True, capture_output=True,
                                  timeout=self.timeout_seconds)
        except subprocess.TimeoutExpired:
            return ""
        answer_path = output_dir / "last_message.txt"
        text = answer_path.read_text(encoding="utf-8").strip() if answer_path.is_file() else ""
        with self._lock:
            self.calls += 1
        if not text and proc.stdout:
            text = proc.stdout.strip()[-2000:]
        shutil.rmtree(role, ignore_errors=True)
        return text


# --------------------------------------------------------------------------
# profiles
# --------------------------------------------------------------------------

VERDICT_RE = re.compile(r"판정\s*[::]\s*(충족|불충족|불명)")
CONF_RE = re.compile(r"확신도\s*[::]?\s*([01](?:\.\d+)?)")
EVIDENCE_RE = re.compile(r"근거\s*[::]\s*(.+)")


@dataclass
class Proposition:
    key: str
    text: str
    kind: str  # "element" (plaintiff must prove) | "defense" (defendant must prove)


@dataclass
class Profile:
    name: str
    decompose_prompt: str
    verify_prompt: str
    synthesize: Callable[[list[Proposition], dict[str, dict]], tuple[str, float, str]]
    classes: tuple[str, ...]
    adjudicate_prompt: str = ""
    needs_evidence: bool = False
    max_propositions: int = 6
    min_propositions: int = 2


def parse_propositions(text: str, limit: int) -> list[Proposition]:
    """Deterministic parse of the decomposition output.

    Expected lines: `요건|<명제>` or `항변|<명제>`. Anything else is ignored,
    which is a gate: a malformed decomposition yields too few propositions and
    the caller re-runs it.
    """
    props: list[Proposition] = []
    for line in text.splitlines():
        line = line.strip().lstrip("-*0123456789. \t")
        if "|" not in line:
            continue
        head, body = line.split("|", 1)
        head = head.strip()
        body = re.sub(r"\s+", " ", body).strip()
        if head not in ("요건", "항변") or not (8 <= len(body) <= 110):
            continue
        # atomicity gate: a proposition that bundles several facts cannot be
        # judged with one verdict — "불충족" would be ambiguous about which
        # conjunct failed. Reject compounds and let the caller re-decompose.
        if len(re.findall(r"(?:,|및|그리고|이고|하며|또한)", body)) >= 2:
            continue
        kind = "element" if head == "요건" else "defense"
        props.append(Proposition(key=f"p{len(props) + 1}", text=body, kind=kind))
        if len(props) >= limit:
            break
    return props


def parse_verdict(text: str) -> dict | None:
    verdict = VERDICT_RE.search(text or "")
    if not verdict:
        return None
    conf = CONF_RE.search(text or "")
    evidence = EVIDENCE_RE.search(text or "")
    return {
        "status": verdict.group(1),
        "confidence": float(conf.group(1)) if conf else 0.5,
        "evidence": (evidence.group(1).strip()[:300] if evidence else ""),
    }


def synthesize_claim(props: list[Proposition], verdicts: dict[str, dict]) -> tuple[str, float, str]:
    """Deterministic aggregation — no model involvement.

    First design used a hard bottleneck (any element 불충족 → 기각). Measured
    on 13 cases it failed for a concrete reason: with a strict verifier 62% of
    propositions come back 불명, so the bottleneck almost never fires and every
    case escalates to one holistic call — i.e. the decomposition bought nothing.

    The civil standard is not "each element proven beyond doubt" but the
    court's free evaluation of the whole record, so the aggregation mirrors it:
    each element contributes SIGNED mass (+conf if established, −conf if
    contradicted, 0 if the record is silent), each established defense
    subtracts mass, and the sign of the total decides. Confidence scales with
    the margin, so a near-tie is honestly reported as a near-tie instead of
    being laundered into a decisive-looking answer. Only a genuine tie
    escalates, and the escalation sees the full ledger.
    """
    elements = [p for p in props if p.kind == "element"]
    defenses = [p for p in props if p.kind == "defense"]
    judged = [(p, verdicts[p.key]) for p in elements if p.key in verdicts]
    if not judged:
        return "ESCALATE", 0.5, "요건 판정 없음"

    signed = []
    for _, verdict in judged:
        if verdict["status"] == "충족":
            signed.append(+verdict["confidence"])
        elif verdict["status"] == "불충족":
            signed.append(-verdict["confidence"])
        else:
            signed.append(0.0)
    element_score = sum(signed) / len(signed)

    defense_mass = 0.0
    for prop, verdict in ((p, verdicts[p.key]) for p in defenses if p.key in verdicts):
        if verdict["status"] == "충족":
            defense_mass = max(defense_mass, verdict["confidence"])
    score = element_score - defense_mass

    weakest = min(judged, key=lambda pair: (pair[1]["status"] != "불충족", -pair[1]["confidence"]))
    if abs(score) < 0.10:
        return "ESCALATE", 0.5, f"요건 우열 미확정 (score={score:+.2f})"
    if score > 0:
        return "인용됨", min(0.95, 0.5 + score / 2), f"요건 우세 (score={score:+.2f})"
    reason = f"요건 열세 (score={score:+.2f})"
    if weakest[1]["status"] == "불충족":
        reason += f" — 결정적 결여: {weakest[0].text[:60]}"
    return "기각", min(0.95, 0.5 + abs(score) / 2), reason


DECOMPOSE_CIVIL = """다음은 대한민국 제1심 민사사건의 자료입니다. 결론을 예측하지 마십시오.
이 단계의 임무는 오직 '무엇이 증명되어야 하는가'를 분해하는 것입니다.

{case}

위 사건에서 원고 청구가 인용되기 위해 반드시 충족되어야 하는 법적 요건사실과,
피고가 증명하면 청구를 배척시키는 항변을 각각 나열하십시오.

규칙:
- 각 줄은 정확히 `요건|<명제>` 또는 `항변|<명제>` 형식.
- 명제는 사실 자료로 참/거짓을 판정할 수 있는 단일 진술이어야 합니다.
  (나쁜 예: "원고의 청구가 정당한가" / 좋은 예: "피고가 2019.3.1. 계약상 인도의무를 이행하지 않았다")
- 요건 2-4개, 항변 0-2개. 총 6줄을 넘기지 마십시오.
- 결론, 승패, 확률에 대한 언급을 절대 포함하지 마십시오.
- 다른 설명 없이 목록만 출력하십시오."""

VERIFY_CIVIL = """다음은 대한민국 제1심 민사사건의 자료입니다.

{case}

이 자료만 근거로, 아래 명제 하나만 판정하십시오. 사건의 최종 승패는 판단하지 말고,
오직 이 명제가 자료에 의해 증명되는지만 보십시오.

명제: {proposition}

출력 형식 (정확히 세 줄):
판정: <충족|불충족|불명>
확신도: <0.00-1.00>
근거: <자료에서 인용한 한두 문장>

판정 기준 (법원의 자유심증과 동일한 기준으로 판단하십시오):
- `충족`: 자료 전체에 비추어 이 명제가 참일 개연성이 더 높다.
- `불충족`: 자료 전체에 비추어 이 명제가 거짓일 개연성이 더 높다.
- `불명`: 자료가 이 쟁점에 대해 사실상 아무 정보도 제공하지 않는다. 다투어지고 있다는 이유만으로
  `불명`을 쓰지 마십시오 — 다툼이 있어도 자료로 우열을 가릴 수 있으면 우세한 쪽으로 판정합니다.
확신도는 그 우열 판단의 강도입니다(0.5=간신히 우세, 0.9=명백)."""

DECOMPOSE_TAX = """다음은 대한민국 조세 행정소송 제1심 사건의 자료입니다. 결론을 예측하지 마십시오.
이 단계의 임무는 오직 '무엇이 증명되어야 하는가'를 분해하는 것입니다.

{case}

납세자(원고)가 이 부과처분의 취소를 받으려면 반드시 성립해야 하는 명제(요건)와,
과세관청(피고)이 증명하면 처분이 유지되는 명제(항변)를 각각 나열하십시오.

규칙:
- 각 줄은 정확히 `요건|<명제>` 또는 `항변|<명제>` 형식.
- 명제는 처분 경위와 주장으로 참/거짓 판정이 가능한 단일 진술이어야 합니다.
  (예: `요건|이 사건 거래는 실질과세원칙상 원고에게 귀속되지 않는다`)
- 요건 2-4개, 항변 0-2개, 총 6줄 이내.
- 결론, 승패, 확률 언급 금지. 목록만 출력."""

VERIFY_TAX = """다음은 대한민국 조세 행정소송 제1심 사건의 자료입니다.

{case}

이 자료만 근거로 아래 명제 하나만 판정하십시오. 처분의 최종 적법 여부는 판단하지 말고,
오직 이 명제가 자료에 의해 뒷받침되는지만 보십시오.

명제: {proposition}

판정 기준 (법원의 자유심증과 동일한 기준):
- `충족`: 자료 전체에 비추어 이 명제가 참일 개연성이 더 높다.
- `불충족`: 자료 전체에 비추어 이 명제가 거짓일 개연성이 더 높다.
- `불명`: 자료가 이 쟁점에 사실상 아무 정보도 주지 않는다(다툼이 있다는 이유만으로는 불명이 아님).
확신도는 우열 판단의 강도입니다(0.5=간신히 우세, 0.9=명백).

출력 형식 (정확히 세 줄):
판정: <충족|불충족|불명>
확신도: <0.00-1.00>
근거: <자료에서 인용한 한두 문장>"""



ADJUDICATE = """아래는 한 사건에 대해 독립적으로 수행된 요건별 판정 원장입니다.
당신의 임무는 사건을 처음부터 다시 푸는 것이 아니라, 이 원장을 검토하여 어느 결론이
증거상 실제로 뒷받침되는지 판정하는 것입니다.

[사건 자료]
{case}

[요건별 판정 원장]
{ledger}

원장에서 `불명`으로 남은 쟁점이 실제로 결론을 좌우하는지, 아니면 나머지 확정된 판정만으로
결론이 정해지는지 검토하십시오. 증명책임은 원고(납세자)에게 있으나, 법원은 정황 전체로
사실을 인정할 수 있습니다.

첫 줄에 결론 한 단어(인용됨 또는 기각), 둘째 줄에 `확신도: 0.xx`,
셋째 줄에 한 문장 이유를 쓰십시오."""


# --------------------------------------------------------------------------
# legal retrieval-answer profile
# --------------------------------------------------------------------------

DECOMPOSE_LEGAL = """다음은 대한민국 법률 실무 질의입니다. 아직 답하지 마십시오.

[질의]
{case}

이 질의에 제대로 답하기 위해 반드시 확인되어야 할 사실 명제를 나열하십시오.
각 명제는 판례 데이터베이스 검색으로 참/거짓을 확인할 수 있는 단일 진술이어야 합니다.

규칙:
- 각 줄은 `요건|<명제>` 형식 (이 과제에서는 모두 `요건`).
- 첫 번째 명제는 반드시 '어떤 사건/판결을 특정해야 하는가'에 관한 것이어야 합니다.
- 2-4개, 각 110자 이내, 접속사 남발 금지.
- 목록만 출력."""

VERIFY_LEGAL = """다음은 법률 질의와, 그 질의를 위해 판례 데이터베이스에서 결정적 검색기로
가져온 후보 판례 발췌입니다.

[질의]
{case}

[검색된 판례 후보]
{evidence}

아래 명제 하나만, 위 후보 발췌에 실제로 적힌 내용만 근거로 판정하십시오.
추측하지 말고, 발췌에 근거가 없으면 `불명`이라고 하십시오.

중요 — 한국 공개 판결문은 개인정보 보호를 위해 당사자·지명이 이니셜(C, D, H군, I 등)로
비식별 처리되어 있습니다. 따라서 질의의 실명이 발췌에 없는 것은 정상이며, 그 이유만으로
`불명`으로 판정해서는 안 됩니다. 사건 동일성은 **내용 속성의 일치**로 판단하십시오:
직위·선수(選數)·관할 법원·시기·사건 구조·행위 유형이 질의와 일치하면 같은 사건으로 봅니다.

명제: {proposition}

출력 형식 (정확히 네 줄):
판정: <충족|불충족|불명>
확신도: <0.00-1.00>
근거: <후보 발췌에서 그대로 인용한 한두 문장>
출처: <해당 후보의 사건번호 또는 canonical id>"""

SOURCE_RE = re.compile(r"출처\s*[::]\s*(.+)")
IDENTITY_RE = re.compile(r"\((?:남|여)[,\s]*\d+\s*세\)")


def synthesize_legal(props: list[Proposition], verdicts: dict[str, dict]) -> tuple[str, float, str]:
    """Assemble the answer from verified components, with a citation gate.

    Nothing is asserted that a verification call did not establish from a
    retrieved document, and an answer without a source citation fails the gate
    rather than being emitted — the retrieval-era failure mode was exactly a
    fluent answer with no document behind it.
    """
    established = [(p, verdicts[p.key]) for p in props
                   if p.key in verdicts and verdicts[p.key]["status"] == "충족"]
    if not established:
        return "ESCALATE", 0.4, "확인된 명제 없음"
    cited = [v for _, v in established if v.get("source")]
    if not cited:
        return "ESCALATE", 0.4, "출처 없는 확인 — 인용 게이트 실패"
    lines = [f"- {p.text}\n  근거: {v['evidence'][:200]} (출처: {v.get('source', '?')})"
             for p, v in established]
    confidence = min(v["confidence"] for _, v in established)
    return "\n".join(lines), confidence, f"확인 {len(established)}/{len(props)} 명제"


def legal_evidence(query: str, limit: int = 14) -> str:
    """Deterministic retrieval — the model never decides whether to search.

    Uses the question-ladder over the full-body FTS index: stems are extracted
    from the query, every 3- and 2-stem AND combination is run, and ranks are
    fused. A masked or de-identified document still surfaces through the
    surviving role/act stems, which is what made the hardest legal case
    solvable without naming it.
    """
    sys.path.insert(0, str(REPO_ROOT))
    import sqlite3

    from tools.reference_search import ladder_search, MAIN_DB, snippet

    main_db = sqlite3.connect(f"file:{MAIN_DB}?mode=ro", uri=True) if Path(MAIN_DB).is_file() else None
    blocks = []
    for _, row, combo in ladder_search(query, limit=limit):
        rowid, canonical_id, court, case_number, date, title, _ = row
        windows: list[str] = []
        if main_db is not None:
            got = main_db.execute("SELECT full_text FROM precedents WHERE rowid=?", (rowid,)).fetchone()
            if got and got[0]:
                body = got[0]
                # Korean judgments state party identity (initials, sex, age,
                # role) in the caption block; a de-identified case is often
                # identifiable ONLY there, so the head is always included as a
                # deterministic anchor window rather than left to stem luck.
                windows.append(body[:900])
                # Korean judgments annotate a party's sex and age inline as
                # "C(남, 64세)" — usually deep inside the 범죄사실 section, far
                # from both the caption and any query stem. That annotation is
                # the identity fact these queries turn on, so every occurrence
                # is anchored deterministically rather than hoped for.
                for hit in list(IDENTITY_RE.finditer(body))[:3]:
                    windows.append(body[max(0, hit.start() - 400): hit.start() + 200])
                # one window per matched stem: a de-identified document rarely
                # states the answer next to the first hit, so a single snippet
                # around one stem is what made earlier retrieval look empty.
                for stem in combo:
                    text = snippet(body, [stem], width=700)
                    if text and all(text[:80] not in existing for existing in windows):
                        windows.append(text)
                if not windows:
                    windows.append(body[:700])
        blocks.append(f"[{canonical_id} | {court or '?'} {case_number or '?'} {date or '?'}] "
                      f"{(title or '')[:60]}\n" + "\n  …\n".join(windows))
    if main_db is not None:
        main_db.close()
    return "\n\n".join(blocks) if blocks else "(검색 결과 없음)"


def synthesize_assessment(props: list[Proposition], verdicts: dict[str, dict]) -> tuple[str, float, str]:
    """Tax variant: the subject of the trial is the ASSESSMENT's lawfulness.

    The first tax profile asked what the taxpayer must prove, and the verdicts
    came back systematically negative — the engine predicted 기각 for 30/30
    dismissals but only 9/30 grants. That is not a calibration problem: in a
    Korean tax case the court examines whether each element of the assessment
    holds, and the taxpayer wins when ONE element fails. So the propositions
    here are the assessment's own elements, and the sign is inverted: mass in
    favour of the assessment means the claim is dismissed, mass against it
    means the assessment is cancelled (청구 인용).
    """
    answer, confidence, reason = synthesize_claim(props, verdicts)
    if answer == "인용됨":
        return "기각", confidence, "처분 적법요건 우세 → " + reason
    if answer == "기각":
        return "인용됨", confidence, "처분 적법요건 결여 → " + reason
    return answer, confidence, reason


DECOMPOSE_TAX_ASSESSMENT = """다음은 대한민국 조세 행정소송 제1심 사건의 자료입니다. 결론을 예측하지 마십시오.
이 단계의 임무는 오직 '이 부과처분이 적법하려면 무엇이 성립해야 하는가'를 분해하는 것입니다.

{case}

과세관청의 이 사건 부과처분이 적법하기 위해 반드시 성립해야 하는 명제(요건)와,
납세자가 증명하면 처분을 위법하게 만드는 명제(항변)를 각각 나열하십시오.

규칙:
- 각 줄은 정확히 `요건|<명제>` 또는 `항변|<명제>` 형식.
- `요건`은 과세요건사실·절차적 요건·법령 적용의 정당성 등 처분이 서 있기 위한 전제입니다.
  (예: `요건|이 사건 거래의 실질적 귀속자는 원고이다`, `요건|처분 전 과세예고 통지가 이루어졌다`)
- `항변`은 신의성실·소급과세 금지·제척기간 도과 등 납세자 측 위법사유입니다.
- 요건 2-4개, 항변 0-2개, 총 6줄 이내, 각 110자 이내.
- 결론·승패·확률 언급 금지. 목록만 출력."""


PROFILES: dict[str, Profile] = {
    "outcome_civil": Profile(
        name="outcome_civil",
        decompose_prompt=DECOMPOSE_CIVIL,
        verify_prompt=VERIFY_CIVIL,
        synthesize=synthesize_claim,
        classes=("인용됨", "기각"),
        adjudicate_prompt=ADJUDICATE,
    ),
    "outcome_tax_assessment": Profile(
        name="outcome_tax_assessment",
        decompose_prompt=DECOMPOSE_TAX_ASSESSMENT,
        verify_prompt=VERIFY_TAX,
        synthesize=synthesize_assessment,
        classes=("인용됨", "기각"),
        adjudicate_prompt=ADJUDICATE,
    ),
    "outcome_tax": Profile(
        name="outcome_tax",
        decompose_prompt=DECOMPOSE_TAX,
        verify_prompt=VERIFY_TAX,
        synthesize=synthesize_claim,
        classes=("인용됨", "기각"),
        adjudicate_prompt=ADJUDICATE,
    ),
    "legal_retrieval": Profile(
        name="legal_retrieval",
        decompose_prompt=DECOMPOSE_LEGAL,
        verify_prompt=VERIFY_LEGAL,
        synthesize=synthesize_legal,
        classes=(),
        needs_evidence=True,
        min_propositions=2,
    ),
}


def pick_profile(row: dict, override: str | None) -> Profile:
    if override and override != "auto":
        return PROFILES[override]
    bench = str(row.get("benchmarkId", ""))
    if ".tax_" in bench or "tax" in bench.split(".")[1:2]:
        return PROFILES["outcome_tax"]
    return PROFILES["outcome_civil"]


# --------------------------------------------------------------------------
# engine
# --------------------------------------------------------------------------

CASE_RE = re.compile(r"^(.*?)\n다음 두 가지 중 정확히 하나로 답하십시오\.", re.S)


def case_material(prompt: str) -> str:
    """Strip the answer-format instructions so the sub-calls cannot be steered
    by the original 'predict the outcome' framing."""
    match = CASE_RE.search(prompt)
    body = match.group(1) if match else prompt
    body = re.sub(r"^다음은[^\n]*\n(?:[^\n]*\n)?[^\n]*예측하십시오\.\n+", "", body)
    return body.strip()


def solve_case(row: dict, *, backend, profile: Profile, retries: int = 1) -> dict:
    case = case_material(row["prompt"])
    ledger: list[dict] = []
    props: list[Proposition] = []
    for attempt in range(retries + 1):
        raw = backend(profile.decompose_prompt.format(case=case), max_tokens=1500)
        props = parse_propositions(raw, profile.max_propositions)
        ledger.append({"stage": "decompose", "attempt": attempt, "raw": raw[:1200],
                       "parsed": len(props)})
        if len([p for p in props if p.kind == "element"]) >= profile.min_propositions:
            break
    if not props:
        return {"id": row["id"], "finalAnswer": "", "status": "decompose_failed", "ledger": ledger}

    evidence = ""
    if profile.needs_evidence:
        evidence = legal_evidence(case)
        ledger.append({"stage": "retrieve", "chars": len(evidence)})

    verdicts: dict[str, dict] = {}
    for prop in props:
        for attempt in range(retries + 1):
            prompt = (profile.verify_prompt.format(case=case, proposition=prop.text, evidence=evidence)
                      if profile.needs_evidence
                      else profile.verify_prompt.format(case=case, proposition=prop.text))
            raw = backend(prompt, max_tokens=1200)
            parsed = parse_verdict(raw)
            ledger.append({"stage": "verify", "key": prop.key, "kind": prop.kind,
                           "proposition": prop.text, "attempt": attempt,
                           "verdict": parsed, "raw": raw[:600]})
            if parsed:
                source = SOURCE_RE.search(raw or "")
                if source:
                    parsed["source"] = source.group(1).strip()[:120]
                verdicts[prop.key] = parsed
                break

    missing = [p.key for p in props if p.key not in verdicts]
    answer, confidence, reason = profile.synthesize(props, verdicts)
    if answer == "ESCALATE" and not (profile.adjudicate_prompt and profile.classes):
        answer = "\n".join(
            f"- {p.text} → {verdicts[p.key]['status']} (근거: {verdicts[p.key]['evidence'][:150]})"
            for p in props if p.key in verdicts
        ) or "확인된 사실 없음"
        reason = "확정 실패 — 원장만 반환 (인용 게이트 미통과)"
    if answer == "ESCALATE" and profile.adjudicate_prompt and profile.classes:
        summary = "\n".join(
            f"- [{p.kind}] {p.text} → {verdicts[p.key]['status']} "
            f"(확신도 {verdicts[p.key]['confidence']:.2f}) 근거: {verdicts[p.key]['evidence'][:120]}"
            for p in props if p.key in verdicts
        )
        raw = backend(profile.adjudicate_prompt.format(case=case, ledger=summary), max_tokens=1500)
        picked = re.search(r"(%s)" % "|".join(profile.classes), (raw or "")[:120])
        conf = CONF_RE.search(raw or "")
        ledger.append({"stage": "adjudicate", "raw": (raw or "")[:800],
                       "picked": picked.group(1) if picked else None})
        if picked:
            answer = picked.group(1)
            confidence = float(conf.group(1)) if conf else 0.6
            reason = "원장 종결 판정"
        else:
            answer, confidence, reason = "기각", 0.5, "미확정 — 증명책임 원칙 적용"
    status = "ok" if not missing else "incomplete_verdicts"
    ledger.append({"stage": "synthesize", "answer": answer, "confidence": confidence,
                   "reason": reason, "missing": missing})
    final = f"{answer}\n확신도: {confidence:.2f}\n{reason}"
    return {"id": row["id"], "finalAnswer": final, "answer": answer,
            "confidence": confidence, "reason": reason, "status": status,
            "propositions": [p.__dict__ for p in props], "verdicts": verdicts,
            "ledger": ledger}


def cmd_run(args: argparse.Namespace) -> int:
    rows = [json.loads(l) for l in args.bench.read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.limit:
        rows = rows[: args.limit]
    args.out.mkdir(parents=True, exist_ok=True)
    answers_path = args.out / "answers.jsonl"
    ledger_path = args.out / "ledger.jsonl"
    done = set()
    if answers_path.is_file():
        for line in answers_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                if item.get("finalAnswer"):
                    done.add(item["id"])
    todo = [r for r in rows if r["id"] not in done]
    if args.backend == "codex":
        backend = CodexBackend(Path(args.codex_home), model=args.codex_model, effort=args.effort)
    else:
        backend = OpenRouterBackend(args.model, effort=args.effort)
    lock = threading.Lock()
    counter = {"n": 0}

    def one(row: dict) -> dict:
        profile = pick_profile(row, args.profile)
        result = solve_case(row, backend=backend, profile=profile, retries=args.retries)
        with lock:
            with answers_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({k: v for k, v in result.items() if k != "ledger"},
                                    ensure_ascii=False) + "\n")
            with ledger_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"id": row["id"], "profile": profile.name,
                                     "ledger": result["ledger"]}, ensure_ascii=False) + "\n")
            counter["n"] += 1
            if counter["n"] % 5 == 0:
                print(f"{counter['n']}/{len(todo)} (calls={backend.calls})", flush=True)
        return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        list(pool.map(one, todo))
    receipt = {"bench": str(args.bench), "backend": args.backend,
               "model": args.codex_model if args.backend == "codex" else args.model,
               "rows": len(rows),
               "ran": len(todo), "modelCalls": backend.calls}
    (args.out / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=1))
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    priv = {r["caseId"]: r["label"] for r in
            map(json.loads, args.private.read_text(encoding="utf-8").splitlines())}
    rows = [json.loads(l) for l in (args.run / "answers.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    seen: dict[str, dict] = {}
    for row in rows:
        seen[row["id"]] = row
    total = correct = 0
    by_class: dict[str, list[int]] = {}
    buckets: list[tuple[float, bool]] = []
    for cid, row in seen.items():
        gold = priv.get(cid)
        if gold is None:
            continue
        total += 1
        hit = row.get("answer") == gold
        correct += hit
        by_class.setdefault(gold, [0, 0])
        by_class[gold][1] += 1
        by_class[gold][0] += hit
        buckets.append((float(row.get("confidence") or 0), bool(hit)))
    report = {
        "n": total,
        "accuracy": round(correct / total, 4) if total else None,
        "byClass": {k: f"{v[0]}/{v[1]}" for k, v in by_class.items()},
        "balancedAccuracy": round(sum(v[0] / v[1] for v in by_class.values()) / len(by_class), 4) if by_class else None,
        "confidenceOperatingPoints": {},
    }
    for threshold in (0.7, 0.8, 0.9):
        selected = [hit for conf, hit in buckets if conf >= threshold]
        if selected:
            report["confidenceOperatingPoints"][str(threshold)] = {
                "coverage": round(len(selected) / total, 3),
                "accuracy": round(sum(selected) / len(selected), 4),
                "n": len(selected),
            }
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--bench", type=Path, required=True)
    run.add_argument("--out", type=Path, required=True)
    run.add_argument("--profile", default="auto")
    run.add_argument("--model", default="anthropic/claude-opus-5")
    run.add_argument("--backend", choices=["openrouter", "codex"], default="openrouter")
    run.add_argument("--codex-home", default="/home/pineapple/.codex-7")
    run.add_argument("--codex-model", default="gpt-5.6-luna")
    run.add_argument("--effort", default="high")
    run.add_argument("--jobs", type=int, default=5)
    run.add_argument("--retries", type=int, default=1)
    run.add_argument("--limit", type=int, default=0)
    run.set_defaults(func=cmd_run)
    score = sub.add_parser("score")
    score.add_argument("--run", type=Path, required=True)
    score.add_argument("--private", type=Path, required=True)
    score.set_defaults(func=cmd_score)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
