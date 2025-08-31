from __future__ import annotations

import os
from typing import Dict, List, Optional

import requests


class OpenRouterClient:
    _api_key: str
    _base_url: str
    _timeout: float

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: float = 60.0,
    ) -> None:
        self._api_key = api_key or os.getenv("OPENROUTER_API_KEY", "")
        if not self._api_key:
            raise RuntimeError("OpenRouter API key not provided. Set OPENROUTER_API_KEY or pass api_key.")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> str:
        url = f"{self._base_url}/chat/completions"
        headers = self._build_headers()
        body = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        resp = requests.post(url, headers=headers, json=body, timeout=self._timeout)
        resp.raise_for_status()
        data = resp.json()
        content: str = ""
        try:
            content = data["choices"][0]["message"]["content"]
        except Exception:
            if isinstance(data, dict) and "choices" in data and data["choices"]:
                first = data["choices"][0]
                if isinstance(first, dict):
                    msg = first.get("message") or {}
                    content = str(msg.get("content", ""))
        return content

    def _build_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
