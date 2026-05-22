from __future__ import annotations

import json
import re
from typing import Any

import requests


def extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in model output: {text[:500]}")
    return json.loads(match.group(0))


class OllamaClient:
    def __init__(self, base_url: str, model: str = "qwen3:8b", timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def chat(self, messages: list[dict[str, str]]) -> str:
        response = requests.post(
            f"{self.base_url}/api/chat",
            json={"model": self.model, "messages": messages, "stream": False, "options": {"temperature": 0}},
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        return str(data.get("message", {}).get("content", "")).strip()

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        if history:
            messages = [{"role": "system", "content": system_prompt.strip()}]
            messages.extend(history)
            messages.append({"role": "user", "content": user_prompt.strip()})
            return extract_json(self.chat(messages))

        prompt = f"""{system_prompt.strip()}

User query:
{user_prompt.strip()}

Return only valid JSON."""
        response = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0},
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()
        return extract_json(data.get("response", ""))
