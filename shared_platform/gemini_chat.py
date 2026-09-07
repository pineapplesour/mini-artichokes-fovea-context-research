from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from .gemma_keyring import first_available_gemini_key


GEMMA4_26B_MODEL = "gemma-4-26b-a4b-it"
GEMINI_GENERATE_CONTENT_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


@dataclass(frozen=True)
class GeminiChatMessage:
    role: str
    text: str


class GeminiDirectChatClient:
    def __init__(
        self,
        *,
        api_key: str,
        timeout_seconds: float = 120.0,
        default_model: str = GEMMA4_26B_MODEL,
    ) -> None:
        cleaned_key = str(api_key or "").strip()
        if not cleaned_key:
            raise ValueError("Gemini API key is not configured")
        self.api_key = cleaned_key
        self.timeout_seconds = float(timeout_seconds)
        self.default_model = default_model

    def generate(
        self,
        messages: list[GeminiChatMessage],
        *,
        system_instruction: str = "",
        model: str = "",
        temperature: float = 0.6,
        max_output_tokens: int = 1024,
        thinking_level: str = "",
    ) -> dict[str, Any]:
        active_model = _normalize_model(model or self.default_model)
        payload = {
            "contents": [_content_payload(message) for message in _clean_messages(messages)],
            "generationConfig": {
                "temperature": float(temperature),
                "maxOutputTokens": max(32, min(int(max_output_tokens), 4096)),
            },
        }
        if system_instruction.strip():
            payload["systemInstruction"] = {"parts": [{"text": system_instruction.strip()}]}
        if thinking_level.strip():
            payload["generationConfig"]["thinkingConfig"] = {"thinkingLevel": thinking_level.strip()}
        parsed = self._post_generate_content(active_model, payload)
        answer = _extract_text(parsed)
        return {
            "model": active_model,
            "answer": answer,
            "usageMetadata": parsed.get("usageMetadata") or {},
        }

    def _post_generate_content(self, model: str, payload: dict[str, Any]) -> dict[str, Any]:
        query = urllib.parse.urlencode({"key": self.api_key})
        url = f"{GEMINI_GENERATE_CONTENT_BASE}/{model}:generateContent?{query}"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = _safe_error_detail(exc)
            raise RuntimeError(f"Gemini API returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Gemini API request failed: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Gemini API returned invalid JSON") from exc


def gemini_api_key_from_env() -> str:
    key = first_available_gemini_key()
    if key:
        return key
    for name in ("RELIGION_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY"):
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _normalize_model(model: str) -> str:
    active = str(model or "").strip()
    if active != GEMMA4_26B_MODEL:
        raise ValueError(f"unsupported Gemma chat model: {active}")
    return active


def _clean_messages(messages: list[GeminiChatMessage]) -> list[GeminiChatMessage]:
    cleaned: list[GeminiChatMessage] = []
    for message in messages[-24:]:
        role = _normalize_role(message.role)
        text = str(message.text or "").strip()
        if text:
            cleaned.append(GeminiChatMessage(role=role, text=text[:12_000]))
    if not cleaned:
        raise ValueError("at least one non-empty chat message is required")
    if cleaned[-1].role != "user":
        raise ValueError("last chat message must be from the user")
    return cleaned


def _normalize_role(role: str) -> str:
    value = str(role or "").strip().lower()
    if value == "assistant":
        return "model"
    if value not in {"user", "model"}:
        raise ValueError("chat message role must be user or model")
    return value


def _content_payload(message: GeminiChatMessage) -> dict[str, Any]:
    return {"role": message.role, "parts": [{"text": message.text}]}


def _extract_text(parsed: dict[str, Any]) -> str:
    parts = (((parsed.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [])
    text = "\n".join(
        str(part.get("text") or "").strip()
        for part in parts
        if part.get("text") and not bool(part.get("thought"))
    )
    if not text.strip():
        raise RuntimeError("Gemini API returned no text candidate")
    return text.strip()


def _safe_error_detail(exc: urllib.error.HTTPError) -> str:
    try:
        raw = exc.read().decode("utf-8", errors="replace")
    except Exception:
        return "no response body"
    if not raw:
        return "empty response body"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw[:500]
    message = (((parsed.get("error") or {}).get("message")) or raw)[:500]
    return str(message)
