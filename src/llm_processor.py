from __future__ import annotations

import json
from typing import Any

from ollama import chat

from src.config import SETTINGS

PROMPT_TEMPLATE = """
Extract current employment details from the public profile text.

Return JSON only.
Do not include markdown.
Do not include explanation.
Use exactly these keys:
company
role
location
evidence
confidence

Rules:
- Use only the provided text.
- Do not guess.
- If a field is unclear, return an empty string.
- confidence must be a number from 0 to 1.
- evidence must be a short quote or short summary from the text.
- If the profile only shows a professional headline and location, extract those.
- If no clear employment evidence exists, return empty strings and confidence 0.

Person name: {name}

Profile text:
{text}
""".strip()


def _empty_result() -> dict[str, Any]:
    return {
        "company": "",
        "role": "",
        "location": "",
        "evidence": "",
        "confidence": 0.0,
    }


def extract_with_llm(name: str, text: str) -> dict[str, Any]:
    clean_name = str(name or "").strip()
    clean_text = str(text or "").strip()

    if not clean_name or not clean_text:
        return _empty_result()

    prompt = PROMPT_TEMPLATE.format(
        name=clean_name,
        text=clean_text[: SETTINGS.max_text_for_llm],
    )

    try:
        response = chat(
            model=SETTINGS.ollama_model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            format="json",
        )
    except Exception as exc:
        print(f"   Ollama request failed: {exc}")
        return _empty_result()

    raw_response = str(response.message.content or "").strip()
    if not raw_response:
        return _empty_result()

    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError:
        print("   Ollama returned non-JSON output")
        return _empty_result()

    result = {
        "company": str(parsed.get("company", "") or "").strip(),
        "role": str(parsed.get("role", "") or "").strip(),
        "location": str(parsed.get("location", "") or "").strip(),
        "evidence": str(parsed.get("evidence", "") or "").strip(),
        "confidence": 0.0,
    }

    try:
        result["confidence"] = float(parsed.get("confidence", 0) or 0)
    except (TypeError, ValueError):
        result["confidence"] = 0.0

    if result["confidence"] < 0:
        result["confidence"] = 0.0
    if result["confidence"] > 1:
        result["confidence"] = 1.0

    return result