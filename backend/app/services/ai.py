"""Model adapter for narrative synthesis.

The analyzer builds a fully deterministic, evidence-backed report on its own. When
a provider is configured the adapter asks the model to *rewrite the prose* of the
headline, summary, and insight explanations for polish — it never invents new
claims or confidence values. With no API key it returns a deterministic synthesis
so the entire pipeline works offline and in tests.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class Synthesis:
    headline: str
    summary: str
    model_name: str


_SYSTEM_PROMPT = (
    "You are Orbit's Software Intelligence Engine — a senior reverse engineer performing software "
    "forensics on an unknown system WITHOUT source access. You investigate; you do not guess.\n"
    "STRICT RULES:\n"
    "- Never invent evidence. Never hallucinate technologies. Every statement must be backed by the "
    "observable evidence provided in the user message (network hosts, headers, DOM/script markers, "
    "TLS, DNS, robots, detected technologies).\n"
    "- Do NOT assert private implementation details as fact. Frame inferences as likelihoods.\n"
    "- If the evidence is insufficient, say so plainly rather than fabricating.\n"
    "- Optimize for being correct, not for sounding confident. Credibility matters more than "
    "completeness.\n"
    "Write a neutral, precise report voice. Return STRICT JSON with exactly two keys: "
    '"headline" (one factual sentence grounded in the strongest observed evidence) and "summary" '
    "(2-3 sentences: what the product appears to be and who it is for, then the most defensible "
    "observations, explicitly noting where evidence is thin). Reference only what the evidence "
    "supports. Do not add fields."
)


class ModelAdapter:
    def __init__(self, api_key: str | None, model: str, base_url: str) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")

    async def synthesize(self, context: dict) -> Synthesis:
        fallback = _fallback_synthesis(context)
        if not self._api_key:
            return fallback
        try:
            payload = {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.2,
            }
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload,
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                data = json.loads(content)
            return Synthesis(
                headline=str(data.get("headline") or fallback.headline).strip(),
                summary=str(data.get("summary") or fallback.summary).strip(),
                model_name=self._model,
            )
        except Exception:  # provider failures must never break report generation
            logger.warning("model synthesis failed; using deterministic fallback", exc_info=True)
            return fallback


def _fallback_synthesis(context: dict) -> Synthesis:
    name = context.get("product_name", "This product")
    host = context.get("host", "")
    techs = [t["name"] for t in context.get("technologies", [])][:4]
    categories = context.get("categories", [])
    pages = context.get("pages_explored", 0)
    evidence = context.get("evidence_count", 0)

    if len(techs) > 2:
        tech_phrase = ", ".join(techs[:-1]) + f", and {techs[-1]}"
    elif len(techs) == 2:
        tech_phrase = f"{techs[0]} and {techs[1]}"
    elif techs:
        tech_phrase = techs[0]
    else:
        tech_phrase = "a modern web stack"
    surface = "a rich, application-style product surface" if categories else "a public marketing and product surface"

    headline = f"{name} presents {surface} built on {tech_phrase}."
    summary = (
        f"Orbit explored {pages} public page(s) on {host} and captured {evidence} evidence point(s). "
        f"Observable signals point to {tech_phrase}"
        + (f", spanning {', '.join(categories[:4])}." if categories else ".")
        + " Architecture and data-model details below are inferred from public behavior and carry per-claim confidence."
    )
    return Synthesis(headline=headline, summary=summary, model_name="heuristic")
