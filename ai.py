from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import httpx

from validator import fallback_blueprint


def _build_prompt(goal: str) -> str:
    return f"""
You are generating a Discord server setup blueprint.
Return ONLY valid JSON. No markdown. No explanation.

Goal:
{goal}

Required JSON schema:
{{
  "roles": [
    {{
      "name": "string",
      "permissions": ["permission_name"],
      "color": "#RRGGBB or omitted",
      "hoist": true,
      "mentionable": false
    }}
  ],
  "categories": [
    {{
      "name": "string",
      "channels": [
        {{
          "name": "string",
          "type": "text|voice",
          "topic": "optional for text",
          "nsfw": false,
          "slowmode": 0,
          "bitrate": 64000,
          "user_limit": 0
        }}
      ]
    }}
  ]
}}

Rules:
- Keep names realistic and community-friendly.
- Use Discord permission flag names.
- Include 3-8 roles.
- Include 2-8 categories.
- Include 2-12 channels per category.
- Ensure text channel names are kebab-case.
- Ensure output is strict JSON only.
""".strip()


async def generate_blueprint(goal: str) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return fallback_blueprint(goal)

    base_url = os.getenv("OPENAI_BASE_URL", "https://ai.riko.my/v1").strip().rstrip("/")
    model = os.getenv("OPENAI_MODEL", "gpt-5.4").strip() or "gpt-5.4"
    instructions = os.getenv("OPENAI_INSTRUCTIONS", "You are a helpful assistant.").strip()
    timeout_seconds = _read_timeout_seconds()

    payload = {
        "model": model,
        "instructions": instructions,
        "input": [
            {
                "role": "user",
                "content": _build_prompt(goal),
            }
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(f"{base_url}/responses", headers=headers, json=payload)
            response.raise_for_status()
            response_json = response.json()
    except Exception:
        return fallback_blueprint(goal)

    raw_text = _extract_text(response_json)
    if not raw_text:
        return fallback_blueprint(goal)

    parsed = _try_parse_json(raw_text)
    if isinstance(parsed, dict):
        return parsed

    return fallback_blueprint(goal)


async def generate_blueprint_with_timeout(goal: str) -> dict[str, Any]:
    timeout_seconds = _read_timeout_seconds(default=30.0)

    try:
        return await asyncio.wait_for(generate_blueprint(goal), timeout=timeout_seconds)
    except asyncio.TimeoutError:
        return fallback_blueprint(goal)


def _read_timeout_seconds(default: float = 30.0) -> float:
    value = os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "").strip()
    if not value:
        return default

    try:
        parsed = float(value)
    except ValueError:
        return default

    return max(5.0, min(120.0, parsed))


def _extract_text(response_json: Any) -> str:
    if not isinstance(response_json, dict):
        return ""

    output_text = response_json.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    output = response_json.get("output")
    if isinstance(output, list):
        chunks: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue

            content = item.get("content")
            if isinstance(content, str) and content.strip():
                chunks.append(content.strip())
                continue

            if isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    text = part.get("text")
                    if isinstance(text, str) and text.strip():
                        chunks.append(text.strip())

        if chunks:
            return "\n".join(chunks).strip()

    choices = response_json.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()

    return ""


def _try_parse_json(raw_text: str) -> Any:
    text = raw_text.strip()
    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    candidate = text[start : end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None
