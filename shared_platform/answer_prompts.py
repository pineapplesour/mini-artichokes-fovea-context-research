from __future__ import annotations


def direct_answer_messages(query: str, *, language: str = "") -> list[dict[str, str]]:
    """Canonical closed-book answer path shared by baselines and no-evidence fallback."""

    return [
        {
            "role": "system",
            "content": (
                "Answer the user's question directly from your pretrained knowledge and reasoning. "
                "No external database or retrieved context is available. Obey the output format requested "
                "in the question. Do not claim to have searched sources."
            ),
        },
        {
            "role": "user",
            "content": f"Answer language hint: {language or 'same as question'}\n\n{query}",
        },
    ]
