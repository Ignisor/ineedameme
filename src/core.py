from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


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
        from .clients import OpenRouterClient

        self._model = model
        self._client = client or OpenRouterClient()
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
