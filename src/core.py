from __future__ import annotations

import json
import random
from dataclasses import dataclass
import os
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import base64
import mimetypes
import requests


@dataclass(frozen=True)
class MemeTemplate:
    id: str
    name: str
    lines: int
    overlays: int
    styles: List[str]
    blank: str
    example: Dict[str, Any]
    source: Optional[str]
    keywords: List[str]
    self_url: str


class TemplateRepository:
    _templates: List[MemeTemplate]

    def __init__(self, templates_path: Optional[Path] = None) -> None:
        self._templates = []
        self._templates = self._load_templates(templates_path)

    def all(self) -> List[MemeTemplate]:
        return self._templates

    def unique_by_id(self) -> List[MemeTemplate]:
        # Preserve first occurrence for each template id
        seen: Dict[str, MemeTemplate] = {}
        for template in self._templates:
            if template.id not in seen:
                seen[template.id] = template
        return list(seen.values())

    def all_unique(self) -> List[MemeTemplate]:
        seen: Dict[str, MemeTemplate] = {}
        for template in self._templates:
            if template.id not in seen:
                seen[template.id] = template
        return list(seen.values())

    def _load_templates(self, templates_path: Optional[Path]) -> List[MemeTemplate]:
        import json

        base_path = (
            templates_path
            if templates_path is not None
            else Path(__file__).resolve().parents[1] / "meme_templates.json"
        )
        with base_path.open("r", encoding="utf-8") as f:
            raw_list: List[Dict[str, Any]] = json.load(f)

        parsed: List[MemeTemplate] = []
        for item in raw_list:
            parsed.append(
                MemeTemplate(
                    id=item.get("id", ""),
                    name=item.get("name", ""),
                    lines=int(item.get("lines", 0)),
                    overlays=int(item.get("overlays", 0)),
                    styles=list(item.get("styles", [])),
                    blank=str(item.get("blank", "")),
                    example=dict(item.get("example", {})),
                    source=item.get("source"),
                    keywords=list(item.get("keywords", [])),
                    self_url=str(item.get("_self", "")),
                )
            )
        return parsed


class TemplateMatch:
    template: MemeTemplate
    score: float

    def __init__(self, template: MemeTemplate, score: float) -> None:
        self.template = template
        self.score = score


class TemplateMatcher:
    def rank(self, situation: str, candidates: Iterable[MemeTemplate]) -> List[TemplateMatch]:
        raise NotImplementedError


class SimpleTemplateMatcher(TemplateMatcher):
    _keywords_weight: float
    _name_weight: float

    def __init__(self, keywords_weight: float = 1.0, name_weight: float = 0.5) -> None:
        self._keywords_weight = keywords_weight
        self._name_weight = name_weight

    def rank(self, situation: str, candidates: Iterable[MemeTemplate]) -> List[TemplateMatch]:
        situation_lc = situation.lower().strip()
        results: List[TemplateMatch] = []
        for t in candidates:
            score = 0.0
            if situation_lc:
                for kw in t.keywords:
                    if kw and kw.lower() in situation_lc:
                        score += self._keywords_weight
                if t.name and any(part in situation_lc for part in t.name.lower().split()):
                    score += self._name_weight
            results.append(TemplateMatch(template=t, score=score))

        results.sort(key=lambda m: m.score, reverse=True)
        return results


class TemplatePicker:
    _repo: TemplateRepository
    _matcher: TemplateMatcher

    def __init__(self, repo: TemplateRepository, matcher: Optional[TemplateMatcher] = None) -> None:
        self._repo = repo
        self._matcher = matcher or SimpleTemplateMatcher()

    def pick_top_k(self, situation: str, k: int = 3, unique_ids: bool = True) -> List[TemplateMatch]:
        candidates = self._repo.unique_by_id() if unique_ids else self._repo.all()
        ranked = self._matcher.rank(situation=situation, candidates=candidates)
        return ranked[: max(0, k)]

    def pick_best(self, situation: str, unique_ids: bool = True) -> Optional[TemplateMatch]:
        top = self.pick_top_k(situation=situation, k=1, unique_ids=unique_ids)
        return top[0] if top else None


class OpenRouterTemplateMatcher(TemplateMatcher):
    _model: str
    _client: Any
    _max_candidates: int

    def __init__(
        self,
        model: str = "google/gemini-2.5-flash-image-preview:free",
        client: Optional[Any] = None,
        max_candidates: int = 207,
    ) -> None:
        from .clients import OpenRouterClient, GoogleClient

        self._model = model
        if client is not None:
            self._client = client
        else:
            provider_raw = os.getenv("MEMEGEN_PROVIDER", "").strip().strip("\"'").lower()
            use_openrouter = provider_raw.startswith("openrouter")
            self._client = OpenRouterClient() if use_openrouter else GoogleClient()
        self._max_candidates = max_candidates

    def rank(self, situation: str, candidates: Iterable[MemeTemplate]) -> List[TemplateMatch]:
        candidate_list: List[MemeTemplate] = list(candidates)
        if self._max_candidates > 0:
            candidate_list = candidate_list[: self._max_candidates]

        prompt = self._build_prompt(situation=situation, candidates=candidate_list)

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful meme template selection assistant."
                    " Respond ONLY with JSON when asked to return rankings."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        content = self._client.chat(messages=messages, model=self._model, temperature=0.8, max_tokens=512)

        rankings = self._parse_rankings_text(content)

        id_to_template: Dict[str, MemeTemplate] = {t.id: t for t in candidate_list}
        matches: List[TemplateMatch] = []
        for item in rankings:
            template = id_to_template.get(item["id"])  # type: ignore[index]
            score = float(item.get("score", 0.0))  # type: ignore[assignment]
            if template is not None:
                matches.append(TemplateMatch(template=template, score=score))

        matches.sort(key=lambda m: m.score, reverse=True)
        return matches

    def _build_prompt(self, situation: str, candidates: List[MemeTemplate]) -> str:
        candidates = candidates.copy()
        random.shuffle(candidates)
        compact = [
            {
                "id": t.id,
                "name": t.name,
            }
            for t in candidates
        ]

        return (
            "Given a situation description and a list of meme templates, rank the most suitable templates.\n\n"
            f"Situation: {situation}\n\n"
            f"Templates: {json.dumps(compact, ensure_ascii=False)}\n\n"
            'Return ONLY JSON in this exact shape: [{"id": "<template_id>", "score": <0..1>}].\n'
            "Include up to 5 items."
        )

    def _parse_rankings_text(self, text: str) -> List[Dict[str, Any]]:

        data: List[Dict[str, Any]] = []
        if not text:
            return data
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [x for x in parsed if isinstance(x, dict) and "id" in x]
        except Exception:
            pass
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            snippet = text[start : end + 1]
            try:
                parsed = json.loads(snippet)
                if isinstance(parsed, list):
                    return [x for x in parsed if isinstance(x, dict) and "id" in x]
            except Exception:
                pass
        return data


class ImageEditPromptGenerator:
    """
    Generates a concise instruction for an image generation model to edit a meme template
    based on a user description, selected template, and an optional reference image.

    The prompt is created by a text model via OpenRouter. If a reference image path is provided,
    it is attached as an inline image in the user message following OpenAI-compatible schema
    supported by OpenRouter multi-part content.
    """

    _client: Any
    _model: str

    def __init__(
        self,
        client: Optional[Any] = None,
        model: str = "google/gemini-2.5-flash-image-preview:free",
    ) -> None:
        from .clients import OpenRouterClient, GoogleClient

        if client is not None:
            self._client = client
        else:
            provider_raw = os.getenv("MEMEGEN_PROVIDER", "").strip().strip("\"'").lower()
            use_openrouter = provider_raw.startswith("openrouter")
            self._client = OpenRouterClient() if use_openrouter else GoogleClient()
        self._model = model

    def create_prompt(
        self,
        user_description: str,
        template: MemeTemplate,
        template_image: Optional["DownloadedImage"] = None,
        reference_image: Optional["DownloadedImage"] = None,
        safety_soften: bool = False,
    ) -> str:
        system_msg = {
            "role": "system",
            "content": (
                (
                    "You are a prompt engineer for image editing. "
                    "Given a meme template and user's description, output a single, concise, "
                    "imperative instruction that tells an image generation model exactly how to "
                    "edit the template. Keep it under 120 words. Avoid extra commentary. "
                    "If a reference image is attached, the instruction MUST explicitly state how to use it (e.g., replace a face with the reference, match identity/pose/style) and must not ignore the reference. "
                    "When integrating the reference, inspect the template style: if it is a cartoon/comic/illustration, preserve the drawing style and render the inserted face as a stylized version that captures the reference's distinctive facial features (face shape, hairline/color, eyebrow and eye shape, nose, mouth, freckles/moles) while matching line weight, flat shading and palette; if it is a live-action/photo, integrate the face photorealistically and naturally, preserve the emotion/expression, and match lighting, color temperature and camera angle. Keep existing occlusions (hats/glasses) above the new face and do not alter the background or composition."
                )
                if not safety_soften
                else (
                    "You are a prompt engineer for image editing. "
                    "Given a meme template and user's description, output a single, concise, "
                    "imperative instruction for editing the template. Keep it under 120 words. "
                    "If a reference image is attached, treat it strictly as stylistic guidance (colors, pose, expression, vibe). "
                    "Do NOT identify or replicate a real person, do NOT perform face/identity matching, and do NOT imply impersonation. "
                    "Use neutral, generic phrasing and avoid any identity linkage. "
                    "Style rule: if the template is cartoon/comic/illustration, keep the illustrated look and echo generic traits from the reference (hair style/color, expression) in a stylized way; if it is a live-action/photo, keep the face natural and consistent with lighting and angle without implying identity. Preserve occlusions like hats/glasses and do not change the background or framing."
                )
            ),
        }

        user_content: List[Dict[str, Any]] = []

        # Instruction text first (per OpenRouter docs)
        user_content.append(
            {
                "type": "text",
                "text": (
                    (
                        "Create a concise edit instruction for an image generation model.\n"
                        f"Template: {template.name}.\n"
                        f"User description: {user_description}.\n"
                        "Constraints: One short paragraph; specify text lines if applicable; "
                        "mention placement (top/bottom/overlay) based on template lines; "
                        "describe visual changes succinctly; avoid mentioning file paths. "
                        "The first attached image is the blank template; the second (if present) is the reference to be used. If the reference is present, explicitly instruct using it (e.g., 'swap the character's face with the reference face' or 'match the person to the reference'). "
                        "Style-aware guidance: infer the template style from the template image. If the template is a cartoon/comic/illustration, tell the model to keep the original drawing style and render the inserted face as a stylized version that captures the reference's key features (face shape, hairline/color, eyebrows/eyes, nose, mouth) while matching line weight and flat/limited shading; avoid photorealism. If the template is a live-action/photo, instruct to make the new face look photorealistic and natural, preserve the emotion/expression, and match lighting/white balance and camera angle. In all cases, keep hats/glasses/props from the template on top of the new face and do not change the background or composition."
                    )
                    if not safety_soften
                    else (
                        "Create a concise edit instruction for an image generation model.\n"
                        f"Template: {template.name}.\n"
                        f"User description: {user_description}.\n"
                        "Constraints: One short paragraph; specify text lines if applicable; "
                        "mention placement (top/bottom/overlay) based on template lines; "
                        "describe visual changes succinctly; avoid mentioning file paths. "
                        "The first attached image is the blank template; the second (if present) is a stylistic reference only. If the reference is present, instruct to draw a generic, stylized character inspired by its hairstyle/expression/pose/color palette without matching or identifying a real person. "
                        "Style-aware guidance: if the template is a cartoon/comic/illustration, keep the illustrated style and echo generic traits from the reference; if it is a live-action/photo, keep the face natural and consistent with lighting/angle while remaining non-identifying. Preserve occlusions like hats/glasses and do not alter the background or layout."
                    )
                ),
            }
        )

        # Attach provided template image if available
        if template_image is not None:
            try:
                user_content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": template_image.as_data_uri()},
                    }
                )
            except Exception:
                pass

        # Attach provided reference image if available
        if reference_image is not None:
            try:
                user_content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": reference_image.as_data_uri()},
                    }
                )
            except Exception:
                pass

        # No file or network I/O here; images must be provided by caller

        messages = [system_msg, {"role": "user", "content": user_content}]  # type: ignore[dict-item]

        content = self._client.chat(messages=messages, model=self._model, temperature=0.8, max_tokens=256)
        return content.strip()


@dataclass(frozen=True)
class DownloadedImage:
    url: str
    content: bytes
    mime_type: str

    def as_data_uri(self) -> str:
        encoded = base64.b64encode(self.content).decode("utf-8")
        return f"data:{self.mime_type};base64,{encoded}"


class SafetyRefusalError(Exception):
    """Raised when the model refuses to generate due to safety/policy."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ImageDownloader:
    _timeout: float

    def __init__(self, timeout: float = 30.0) -> None:
        self._timeout = timeout

    def download(self, url: str) -> DownloadedImage:
        # Single retry on transient failure
        last_error: Optional[Exception] = None
        for attempt in range(2):
            try:
                resp = requests.get(url, timeout=self._timeout)
                resp.raise_for_status()
                content_type = resp.headers.get("Content-Type", "").split(";")[0].strip()
                mime = content_type or self._guess_mime_from_url(url) or "image/png"
                return DownloadedImage(url=url, content=resp.content, mime_type=mime)
            except Exception as e:
                last_error = e
                if attempt == 1:
                    raise
                continue
        # Satisfy type checker; in practice we either returned or raised
        raise RuntimeError(f"Failed to download image from {url}: {last_error}")

    def _guess_mime_from_url(self, url: str) -> str:
        guess, _ = mimetypes.guess_type(url)
        return guess or ""


def _guess_mime_from_path(path: str) -> str:
    guess, _ = mimetypes.guess_type(path)
    return guess or "image/png"


@dataclass(frozen=True)
class GeneratedImage:
    """Holds a single generated image output."""

    mime_type: str
    content: bytes

    def as_data_uri(self) -> str:
        encoded = base64.b64encode(self.content).decode("utf-8")
        return f"data:{self.mime_type};base64,{encoded}"


class MemeImageGenerator:
    """
    Creates a meme image using an image generation model via OpenRouter.

    Input:
    - prompt: text instruction for editing/creating the meme
    - template_image: the meme template image as attachment (required by user request)
    - reference_image: optional face/reference image

    Output: a single image as GeneratedImage
    """

    _client: Any
    _model: str
    _logger: logging.Logger

    def __init__(self, client: Optional[Any] = None, model: str = "google/gemini-2.5-flash-image-preview:free") -> None:
        from .clients import OpenRouterClient, GoogleClient

        if client is not None:
            self._client = client
        else:
            provider_raw = os.getenv("MEMEGEN_PROVIDER", "").strip().strip("\"'").lower()
            use_openrouter = provider_raw.startswith("openrouter")
            self._client = OpenRouterClient() if use_openrouter else GoogleClient()
        self._model = model
        self._logger = logging.getLogger("ai.memegen")

    def generate(
        self,
        prompt: str,
        template_image: DownloadedImage,
        reference_image: Optional[DownloadedImage] = None,
        temperature: float = 0.2,
        max_tokens: int = 256,
    ) -> "GeneratedImage":
        user_content: List[Dict[str, Any]] = []

        # Put prompt text first
        user_content.append({"type": "text", "text": prompt})

        # Template image must be attached
        user_content.append(
            {
                "type": "image_url",
                "image_url": {"url": template_image.as_data_uri()},
            }
        )

        # Optional reference image
        if reference_image is not None:
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": reference_image.as_data_uri()},
                }
            )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an image generation model that outputs exactly one final image. "
                    "Use the provided template image AND, if present, the reference image. "
                    "If a reference image is attached, you MUST incorporate it faithfully (e.g., identity/face swap or stylistic match as implied by the instruction). Do not ignore the reference."
                ),
            },
            {"role": "user", "content": user_content},  # type: ignore[dict-item]
        ]

        # Ask for raw JSON so we can extract image content
        data = self._client.chat_raw(
            messages=messages,
            model=self._model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return self._extract_generated_image(data)

    def _parse_data_uri(self, data_uri: str) -> Tuple[str, bytes]:
        # data:[<mime>];base64,<payload>
        try:
            header, b64 = data_uri.split(",", 1)
            mime = "image/png"
            if header.startswith("data:"):
                rest = header[5:]
                semi = rest.find(";")
                if semi != -1:
                    mime = rest[:semi] or mime
                else:
                    mime = rest or mime
            payload = base64.b64decode(b64)
            return mime, payload
        except Exception as e:
            raise RuntimeError(f"Invalid data URI: {e}")

    def _summarize_openrouter_response(self, data: Dict[str, Any]) -> str:
        """Create a concise, redacted summary of the OpenRouter response for logging/errors."""
        try:
            summary: Dict[str, Any] = {}
            if isinstance(data, dict):
                summary["object"] = data.get("object")
                summary["model"] = data.get("model")
                usage = data.get("usage")
                if isinstance(usage, dict):
                    summary["usage"] = usage
                choices = data.get("choices")
                if isinstance(choices, list) and choices:
                    summary["choices_count"] = len(choices)
                    first = choices[0]
                    if isinstance(first, dict):
                        msg = first.get("message")
                        if isinstance(msg, dict):
                            summary["message_keys"] = list(msg.keys())
                            content = msg.get("content")
                            if isinstance(content, str):
                                summary["content_len"] = len(content)
                            images = msg.get("images")
                            if isinstance(images, list):
                                summary["images_count"] = len(images)
                                if images and isinstance(images[0], dict):
                                    img0 = images[0]
                                    summary["images_0_keys"] = list(img0.keys())
                                    image_url = img0.get("image_url")
                                    if isinstance(image_url, dict):
                                        redacted: Dict[str, Any] = {}
                                        if "url" in image_url:
                                            url_val = image_url.get("url")
                                            if isinstance(url_val, str) and url_val.startswith("data:"):
                                                redacted["url"] = "data:[redacted]"
                                            else:
                                                redacted["url"] = url_val
                                        if "b64_json" in image_url:
                                            b64 = image_url.get("b64_json")
                                            redacted["b64_len"] = len(b64) if isinstance(b64, str) else None
                                        summary["images_0_image_url"] = redacted
            text = json.dumps(summary, ensure_ascii=False)
            if len(text) > 4000:
                text = text[:4000] + "...(truncated)"
            return text
        except Exception:
            try:
                text = json.dumps(data, ensure_ascii=False)
                if len(text) > 4000:
                    text = text[:4000] + "...(truncated)"
                return text
            except Exception:
                return str(type(data))

    def _extract_generated_image(self, data: Dict[str, Any]) -> "GeneratedImage":
        """Protected parser for the OpenRouter JSON response.

        Expects shape with an image in choices[0].message.images[0].image_url.
        Supports data URIs, http(s) URLs, and b64_json.
        """
        try:
            choice = data["choices"][0]
            message = choice["message"]
            refusal = message.get("refusal")
            refusal_present = bool(refusal)
            finish_reason = str(choice.get("finish_reason", "")).lower()
            finish_is_safety = finish_reason in {"content_filter", "safety", "policy_violation"}
            if refusal_present or finish_is_safety:
                reason_parts: List[str] = []
                if isinstance(refusal, str) and refusal:
                    reason_parts.append(refusal)
                elif isinstance(refusal, dict):
                    reason_parts.append(str(refusal.get("reason") or refusal.get("message") or refusal))
                reasoning = message.get("reasoning")
                if isinstance(reasoning, str) and reasoning:
                    reason_parts.append(reasoning)
                if finish_reason:
                    reason_parts.append(f"finish_reason={finish_reason}")
                reason = " ".join([p for p in reason_parts if p]).strip() or "Model refused due to safety policy"
                raise SafetyRefusalError(reason)
            images_field = message.get("images")
            if not isinstance(images_field, list) or not images_field:
                raise RuntimeError("No images in response message")

            first_image = images_field[0]
            if not isinstance(first_image, dict):
                raise RuntimeError("Invalid image entry in response")

            image_spec = first_image.get("image_url")
            url: str = ""
            if isinstance(image_spec, dict):
                url = image_spec.get("url") or image_spec.get("data") or ""
                b64_json = image_spec.get("b64_json")
                if isinstance(b64_json, str) and b64_json:
                    payload = base64.b64decode(b64_json)
                    return GeneratedImage(mime_type="image/png", content=payload)
            elif isinstance(image_spec, str):
                url = image_spec

            if isinstance(url, str) and url.startswith("data:"):
                mime, b = self._parse_data_uri(url)
                return GeneratedImage(mime_type=mime, content=b)

            if isinstance(url, str) and (url.startswith("http://") or url.startswith("https://")):
                downloaded = ImageDownloader().download(url)
                return GeneratedImage(mime_type=downloaded.mime_type, content=downloaded.content)

            raise RuntimeError("Image URL missing or unsupported format in response")
        except Exception as e:
            # Let safety refusals bubble up for API to return 400
            if isinstance(e, SafetyRefusalError):
                raise
            summary = self._summarize_openrouter_response(data)

            # Log full summary once for diagnostics
            try:
                self._logger.warning(f"cid=n/a step=extract_image_error error={e!r} response_summary={summary}")
            except Exception:
                pass
            raise RuntimeError(f"Failed to extract generated image: {e}")
