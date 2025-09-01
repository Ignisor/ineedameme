from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

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
        messages: List[Dict[str, Any]],
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

    def chat_raw(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
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
        if not isinstance(data, dict):
            raise RuntimeError("Unexpected response format from OpenRouter")
        return data

    def _build_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }


class GoogleClient:
    _api_key: str
    _base_url: str
    _timeout: float

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout: float = 60.0,
    ) -> None:
        self._api_key = api_key or os.getenv("GOOGLE_API_KEY", "")
        if not self._api_key:
            raise RuntimeError("Google API key not provided. Set GOOGLE_API_KEY or pass api_key.")
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def _normalize_model(self, model: str) -> str:
        # Accept OpenRouter-style ids and map to Google format
        # e.g., "google/gemini-2.5-flash-image-preview:free" -> "models/gemini-2.5-flash-image-preview"
        m = model
        if "/" in m:
            parts = m.split("/", 1)[1]
            m = parts
        if ":" in m:
            m = m.split(":", 1)[0]
        if not m.startswith("models/"):
            m = f"models/{m}"
        return m

    def chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 512,
    ) -> str:
        url = f"{self._base_url}/{self._normalize_model(model)}:generateContent?key={self._api_key}"
        headers = {"Content-Type": "application/json"}
        body = self._convert_messages_to_google_payload(messages, temperature, max_tokens)
        resp = requests.post(url, headers=headers, json=body, timeout=self._timeout)
        resp.raise_for_status()
        data = resp.json()
        # Extract first text part
        try:
            cands = data.get("candidates") or []
            if cands:
                parts = ((cands[0] or {}).get("content") or {}).get("parts") or []
                for p in parts:
                    if isinstance(p, dict) and "text" in p:
                        return str(p.get("text") or "").strip()
        except Exception:
            pass
        return ""

    def chat_raw(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        url = f"{self._base_url}/{self._normalize_model(model)}:generateContent?key={self._api_key}"
        headers = {"Content-Type": "application/json"}
        body = self._convert_messages_to_google_payload(messages, temperature, max_tokens)
        resp = requests.post(url, headers=headers, json=body, timeout=self._timeout)
        resp.raise_for_status()
        data = resp.json()
        # Convert Google response to OpenRouter-like structure our parser expects
        converted = self._convert_google_to_openrouter_like(data)
        return converted

    def _convert_messages_to_google_payload(
        self, messages: List[Dict[str, Any]], temperature: float, max_tokens: int
    ) -> Dict[str, Any]:
        system_instruction: Optional[Dict[str, Any]] = None
        contents: List[Dict[str, Any]] = []
        for msg in messages:
            role = str(msg.get("role") or "user")
            content = msg.get("content")
            if role == "system":
                text = content if isinstance(content, str) else ""
                if not text and isinstance(content, list):
                    # Concatenate text parts if provided as list
                    texts: List[str] = []
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            texts.append(str(item.get("text") or ""))
                    text = "\n".join(texts)
                system_instruction = {"role": "system", "parts": [{"text": text}]}
                continue

            parts: List[Dict[str, Any]] = []
            if isinstance(content, str):
                parts.append({"text": content})
            elif isinstance(content, list):
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") == "text":
                        parts.append({"text": str(item.get("text") or "")})
                    elif item.get("type") == "image_url":
                        image_url = (item.get("image_url") or {}).get("url")
                        mime, b64 = self._parse_data_uri(str(image_url or ""))
                        if b64:
                            parts.append({"inline_data": {"mime_type": mime or "image/png", "data": b64}})
            if parts:
                contents.append({"role": "user", "parts": parts})

        payload: Dict[str, Any] = {
            "contents": contents or [{"role": "user", "parts": [{"text": ""}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_instruction is not None:
            payload["systemInstruction"] = system_instruction
        return payload

    def _parse_data_uri(self, data_uri: str) -> Tuple[str, str]:
        # returns (mime, base64)
        try:
            if not data_uri.startswith("data:"):
                return "image/png", ""
            header, b64 = data_uri.split(",", 1)
            mime = "image/png"
            rest = header[5:]
            semi = rest.find(";")
            if semi != -1:
                mime = rest[:semi] or mime
            else:
                mime = rest or mime
            return mime, b64
        except Exception:
            return "image/png", ""

    def _convert_google_to_openrouter_like(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # Detect safety / refusal
        refusal: Optional[str] = None
        finish_reason = "stop"

        # Global prompt feedback
        pf = data.get("promptFeedback") or {}
        br = pf.get("blockReason")
        if br:
            refusal = str(br)
            finish_reason = "content_filter"

        images: List[Dict[str, Any]] = []
        texts: List[str] = []

        cands = data.get("candidates") or []
        if cands:
            # Read candidate-level finish reason if present
            try:
                cand_finish = str((cands[0] or {}).get("finishReason") or "").lower()
                if cand_finish:
                    # Map some known reasons
                    if cand_finish in {"safety", "blocked", "recitation", "prohibited_content", "blocklist"}:
                        finish_reason = "content_filter"
                    elif cand_finish in {"length", "max_tokens"}:
                        finish_reason = "length"
                    else:
                        finish_reason = cand_finish
                    if (
                        cand_finish
                        and not refusal
                        and cand_finish in {"prohibited_content", "blocked", "safety", "blocklist"}
                    ):
                        refusal = cand_finish
            except Exception:
                pass

            parts = ((cands[0] or {}).get("content") or {}).get("parts") or []
            for p in parts:
                if not isinstance(p, dict):
                    continue
                # inlineData (camelCase)
                if "inlineData" in p:
                    inline = p.get("inlineData") or {}
                    mime = str(inline.get("mimeType") or "image/png")
                    b64 = str(inline.get("data") or "")
                    if b64:
                        images.append({"image_url": {"url": f"data:{mime};base64,{b64}"}})
                        continue
                # inline_data (snake_case) - just in case
                if "inline_data" in p:
                    inline = p.get("inline_data") or {}
                    mime = str(inline.get("mime_type") or "image/png")
                    b64 = str(inline.get("data") or "")
                    if b64:
                        images.append({"image_url": {"url": f"data:{mime};base64,{b64}"}})
                        continue
                # fileData with fileUri
                if "fileData" in p:
                    fd = p.get("fileData") or {}
                    mime = str(fd.get("mimeType") or "image/png")
                    uri = str(fd.get("fileUri") or "")
                    if uri:
                        images.append({"image_url": {"url": uri}})
                        continue
                if "file_data" in p:
                    fd = p.get("file_data") or {}
                    mime = str(fd.get("mime_type") or "image/png")
                    uri = str(fd.get("file_uri") or "")
                    if uri:
                        images.append({"image_url": {"url": uri}})
                        continue
                # Text parts (often contain refusal/explanations)
                if "text" in p and isinstance(p.get("text"), str):
                    t = str(p.get("text") or "").strip()
                    if t:
                        texts.append(t)
                        continue

        # If no images but we received text or block reason details, surface it as refusal
        if not images:
            br_msg = str((pf.get("blockReasonMessage") or "")).strip()
            if br_msg:
                texts.append(br_msg)
            if texts and not refusal:
                refusal = " ".join(texts)[:500]
            if finish_reason == "stop" and (refusal or br_msg):
                finish_reason = "content_filter"
            if not refusal:
                refusal = "no_image_returned"

        data = {
            "choices": [
                {
                    "finish_reason": finish_reason,
                    "message": {
                        "content": "",
                        "images": images,
                        "refusal": refusal,
                    },
                }
            ]
        }

        return data
