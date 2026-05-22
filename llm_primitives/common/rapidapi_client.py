from __future__ import annotations

import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()


class RapidAPIClient:
    def __init__(self):
        self.api_key = os.getenv("RAPIDAPI_KEY", "").strip()
        if not self.api_key:
            raise RuntimeError("RAPIDAPI_KEY is missing.")

    def get(self, host: str, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"https://{host}{path}"
        headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": host,
        }
        response = requests.get(url, headers=headers, params=params or {}, timeout=60)
        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text[:2000]}
        return {"status_code": response.status_code, "data": data}
