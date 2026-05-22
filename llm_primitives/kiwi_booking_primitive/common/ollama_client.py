from __future__ import annotations
import json
import re
from typing import Any
import requests

class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "qwen3:8b", timeout: int = 120):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def chat(self, messages: list[dict[str, str]]) -> str:
        r = requests.post(
            f"{self.base_url}/api/chat",
            json={"model": self.model, "messages": messages, "stream": False},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()["message"]["content"].strip()

    def generate_json(self, system_prompt: str, user_prompt: str, history: list[dict[str, str]] | None = None) -> dict[str, Any]:
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_prompt})
        raw = self.chat(messages)
        return self._parse_json(raw)

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any]:
        raw = raw.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            for p in parts:
                p = p.strip()
                if p.startswith("json"):
                    p = p[4:].strip()
                try:
                    return json.loads(p)
                except Exception:
                    pass
        try:
            return json.loads(raw)
        except Exception:
            m = re.search(r"\{.*\}", raw, flags=re.S)
            if not m:
                raise ValueError(f"LLM did not return JSON: {raw[:300]}")
            return json.loads(m.group(0))
