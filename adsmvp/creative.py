"""Creative generation: topic + angle -> ad copy (Gemini) + image (Imagen).

Bilingual (en/zh). Falls back to deterministic template copy + a placeholder
image when no Gemini key is present, so the pipeline runs fully offline. The
image prompt is editorial/illustrative and explicitly forbids gambling imagery.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import quote

from . import images, llm
from .channels.base import DEFAULT_CTA, VALID_CTAS, CreativeSpec
from .selection import Candidate

COPY_PROMPT = """You are a compliant performance-marketing copywriter for a \
PREDICTION / FORECASTING product (NOT a gambling operator). Write a Facebook \
single-image ad in {lang_name} for {country}.

Topic: {name}
Narrative: {narrative}
Forecasting question: {question}
A grounding news fact: {fact}

Hard rules:
- Frame it as following/forecasting an outcome, never as betting or guaranteed \
winnings. No odds, payouts, "bet", "win big", or money promises.
- Curiosity-driven, factual, concise. No clickbait lies. No targeting minors.
- headline <= 40 chars, description <= 30 chars, primary_text <= 125 chars.

Return ONLY JSON:
{{"primary_text": "...", "headline": "...", "description": "...", "cta": "LEARN_MORE"}}
"""

IMAGE_PROMPT = """Editorial, photo-illustrative square image for a news \
forecasting article about: {name} ({country}). Clean, modern, trustworthy news \
aesthetic; subtle data/chart motif. ABSOLUTELY NO betting slips, casino chips, \
dice, cards, money/cash, or odds. No text overlays, no logos."""

LANG_NAMES = {"en": "English", "zh": "Simplified Chinese"}


def _question_for(cand: Candidate, lang: str) -> str:
    a = cand.primary_angle or {}
    if lang == "zh":
        return (a.get("question_zh") or cand.topic.get("suggested_question_zh")
                or cand.topic.get("name_zh") or "")
    return (a.get("question_en") or cand.topic.get("suggested_question")
            or cand.topic.get("name") or "")


def _fact_for(cand: Candidate, lang: str) -> str:
    if not cand.source_examples:
        return cand.topic.get("narrative") or ""
    se = cand.source_examples[0]
    return (se.get("title_zh") if lang == "zh" else se.get("title_en")) or se.get("title_en") or ""


def _name_for(cand: Candidate, lang: str) -> str:
    if lang == "zh":
        return cand.topic.get("name_zh") or cand.topic.get("name") or ""
    return cand.topic.get("name") or ""


def _narrative_for(cand: Candidate, lang: str) -> str:
    if lang == "zh":
        return cand.topic.get("narrative_zh") or cand.topic.get("narrative") or ""
    return cand.topic.get("narrative") or ""


def _valid_cta(raw: Optional[str]) -> str:
    cta = (raw or "").strip().upper()
    return cta if cta in VALID_CTAS else DEFAULT_CTA


def _clip(text: str, n: int) -> str:
    s = (text or "").strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _fallback_copy(cand: Candidate, lang: str, country: str) -> Dict[str, str]:
    q = _question_for(cand, lang)
    name = _name_for(cand, lang)
    if lang == "zh":
        return {
            "primary_text": _clip(f"{name}：接下来会怎样？跟踪我们的实时预测。", 125),
            "headline": _clip(q or name, 40),
            "description": _clip("查看预测", 30),
            "cta": DEFAULT_CTA,
        }
    return {
        "primary_text": _clip(f"{name}: what happens next? Follow our live forecast.", 125),
        "headline": _clip(q or name, 40),
        "description": _clip("See the forecast", 30),
        "cta": DEFAULT_CTA,
    }


def _gen_copy(cand: Candidate, lang: str, country: str, cfg, client) -> Dict[str, str]:
    if client is None:
        return _fallback_copy(cand, lang, country)
    prompt = COPY_PROMPT.format(
        lang_name=LANG_NAMES.get(lang, "English"),
        country=country,
        name=_name_for(cand, lang),
        narrative=_clip(_narrative_for(cand, lang), 400),
        question=_question_for(cand, lang),
        fact=_clip(_fact_for(cand, lang), 200),
    )
    try:
        data = llm.generate_json(client, cfg.gemini_model, prompt)
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] copy generation failed ({type(exc).__name__}: {exc}); "
              "using fallback", file=sys.stderr)
        return _fallback_copy(cand, lang, country)
    return {
        "primary_text": _clip(str(data.get("primary_text") or ""), 125),
        "headline": _clip(str(data.get("headline") or ""), 40),
        "description": _clip(str(data.get("description") or ""), 30),
        "cta": _valid_cta(data.get("cta")),
    }


def _landing_url(cfg, cand: Candidate) -> str:
    base = (cfg.landing_base_url or "").rstrip("/")
    tid = cand.topic_id or ""
    return f"{base}?topic={quote(str(tid))}" if tid else base


def generate_creative(cand: Candidate, region: str, lang: str, cfg, *,
                      client=None, run_date: str = "undated") -> CreativeSpec:
    """Produce a CreativeSpec (copy + image) for one candidate in one language."""
    from .regions import get_region
    rc = get_region(region)
    copy = _gen_copy(cand, lang, rc.country_name, cfg, client)

    img_dir = Path(cfg.artifacts_dir) / "images" / region / run_date
    img_path = img_dir / f"{cand.topic_id}_{lang}.png"
    image_prompt = IMAGE_PROMPT.format(name=_name_for(cand, "en") or cand.topic.get("name"),
                                       country=rc.country_name)
    images.generate_image(
        image_prompt, img_path,
        client=client if cfg.has_gemini else None,
        model=cfg.imagen_model,
        seed=f"{cand.topic_id}|{lang}",
    )

    spec = CreativeSpec(
        topic_id=cand.topic_id,
        angle_id=(cand.primary_angle or {}).get("id"),
        region=region,
        lang=lang,
        primary_text=copy["primary_text"],
        headline=copy["headline"],
        description=copy["description"],
        cta=copy["cta"],
        landing_url=_landing_url(cfg, cand),
        image_path=str(img_path),
        copy_style="serious" if cand.angle_type == "serious_candidate" else cand.angle_type,
        model_copy=cfg.gemini_model if client is not None else "fallback-template",
        model_image=cfg.imagen_model if cfg.has_gemini else "placeholder",
        meta={"run_date": run_date, "image_prompt": image_prompt},
    )
    return spec
