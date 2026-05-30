"""Orchestration glue shared by the entry-point scripts.

Keeps scripts thin and the data-source seam testable. Works in three escalating
modes automatically:
  - no Supabase, no Gemini  -> bundled sample content + fallback copy + stub FB
  - Supabase, no Gemini     -> real content, fallback copy
  - Supabase + Gemini       -> real content + LLM copy + Imagen images
The Facebook side is stub unless FACEBOOK_MODE=live with full creds.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from . import creative as creative_mod
from . import db, feedback, guardrails, llm, sample_data
from .channels.registry import get_channel
from .selection import Candidate, select_candidates


@dataclass
class SelectionInputs:
    topics: List[Dict]
    angles_by_topic: Dict[str, List[Dict]]
    source_examples_by_topic: Dict[str, List[Dict]]
    advertised_topic_ids: set = field(default_factory=set)
    advertised_names: set = field(default_factory=set)
    suggestions: List[Dict] = field(default_factory=list)
    source: str = "supabase"


def resolve_run_date(cfg, client, region: str, requested: Optional[str]) -> str:
    if requested:
        return requested
    return (db.latest_run_date(client, region)
            or dt.date.today().isoformat())


def load_selection_inputs(cfg, client, region: str, run_date: str) -> SelectionInputs:
    topics = db.fetch_topics(client, region, run_date)
    if not topics:
        # Offline / empty DB: fall back to bundled sample so the loop still runs.
        t, a, s = sample_data.sample_inputs(region, run_date)
        return SelectionInputs(t, a, s, source="sample")
    ids = [t["id"] for t in topics]
    return SelectionInputs(
        topics=topics,
        angles_by_topic=db.fetch_angles(client, ids),
        source_examples_by_topic=db.fetch_source_examples(client, ids),
        advertised_topic_ids=db.fetch_advertised_topic_ids(
            client, db.since(cfg.ads_dedupe_days)),
        suggestions=db.fetch_recent_suggestions(client, region, db.since(7)),
        source="supabase",
    )


@dataclass
class AdResult:
    topic_id: Optional[str]
    region: str
    lang: str
    topic_type: str
    angle_type: str
    policy_status: str
    ad_id: Optional[str] = None
    skipped: Optional[str] = None


def run_ads(cfg, region: str, run_date: str, *, limit: Optional[int] = None,
            langs: Optional[List[str]] = None, client=None,
            genai_client=None) -> List[AdResult]:
    """Select -> generate -> guardrails -> draft (PAUSED) -> persist."""
    limit = limit or cfg.daily_ad_limit
    langs = langs or ["en", "zh"]
    inputs = load_selection_inputs(cfg, client, region, run_date)
    candidates = select_candidates(
        inputs.topics, inputs.angles_by_topic, inputs.source_examples_by_topic,
        weights=cfg.weights,
        advertised_topic_ids=inputs.advertised_topic_ids,
        advertised_names=inputs.advertised_names,
        suggestions=inputs.suggestions, limit=limit,
    )
    channel = get_channel("facebook", cfg)
    results: List[AdResult] = []
    for cand in candidates:
        for lang in langs:
            spec = creative_mod.generate_creative(
                cand, region, lang, cfg, client=genai_client, run_date=run_date)
            guardrails.enforce_creative(spec)
            if spec.policy_status == "blocked":
                results.append(AdResult(
                    cand.topic_id, region, lang, cand.topic_type, cand.angle_type,
                    spec.policy_status, skipped=spec.policy_notes))
                continue
            spec = channel.build_creative(spec)
            draft = channel.create_draft_campaign(
                spec, budget_cap_cents=cfg.daily_ad_budget_cap,
                campaign_name=f"phnews-{region}-{run_date}-{cand.topic_id}-{lang}")
            assert draft.status == "PAUSED", "v1 must only create PAUSED drafts"
            creative_id = db.write_creative(client, spec, region, run_date)
            db.write_campaign(client, draft, spec, creative_id, region, run_date)
            results.append(AdResult(
                cand.topic_id, region, lang, cand.topic_type, cand.angle_type,
                spec.policy_status, ad_id=draft.external_ad_id))
    return results


def run_insights(cfg, region: str, run_date: str, *, client=None,
                 genai_client=None) -> Dict:
    """Pull yesterday's metrics, upsert, analyze -> content_suggestions.

    Builds the (ad_id -> topic_type/angle_type/lang) meta needed for aggregation
    from Supabase when available, else by reconstructing today's stub drafts so
    the feedback loop is demonstrable fully offline.
    """
    channel = get_channel("facebook", cfg)
    meta_by_ad: Dict[str, Dict] = {}
    campaign_id_by_ad: Dict[str, str] = {}

    campaigns = db.fetch_campaigns_for_insights(client, region)
    if campaigns:
        creative_ids = [c["creative_id"] for c in campaigns if c.get("creative_id")]
        creatives = db.fetch_creatives_by_id(client, creative_ids)
        topic_ids = [c["topic_id"] for c in campaigns if c.get("topic_id")]
        topics = {t["id"]: t for t in db.fetch_topics(client, region, run_date)}
        # topics for run_date may not cover historical; fetch types best-effort.
        for c in campaigns:
            aid = c.get("external_ad_id")
            if not aid:
                continue
            cr = creatives.get(c.get("creative_id"), {})
            topic = topics.get(c.get("topic_id"), {})
            meta_by_ad[aid] = {
                "topic_type": (topic.get("topic_type") or "unknown"),
                "angle_type": (cr.get("copy_style") or "serious"),
                "lang": cr.get("lang") or "en",
            }
            campaign_id_by_ad[aid] = c["id"]
    else:
        # Offline: reconstruct stub drafts to get ad_ids + meta.
        for r in run_ads(cfg, region, run_date, client=None, genai_client=genai_client):
            if r.ad_id:
                meta_by_ad[r.ad_id] = {"topic_type": r.topic_type,
                                       "angle_type": r.angle_type, "lang": r.lang}

    ad_ids = list(meta_by_ad)
    insights = channel.fetch_insights(ad_ids, run_date)

    # Upsert raw insights (DB mode only persists; offline just computes).
    insight_rows = [{
        "campaign_id": campaign_id_by_ad.get(i.external_ad_id),
        "external_ad_id": i.external_ad_id, "insight_date": i.date,
        "impressions": i.impressions, "clicks": i.clicks, "ctr": i.ctr,
        "spend": i.spend, "cpc": i.cpc, "conversions": i.conversions,
        "raw": i.raw,
    } for i in insights]
    db.upsert_insights(client, insight_rows)

    # Build feedback rows and analyze.
    feedback_rows = []
    for i in insights:
        m = meta_by_ad.get(i.external_ad_id, {})
        feedback_rows.append({
            "topic_type": m.get("topic_type", "unknown"),
            "angle_type": m.get("angle_type", "serious"),
            "lang": m.get("lang", "en"),
            "impressions": i.impressions, "clicks": i.clicks,
            "spend": i.spend, "conversions": i.conversions,
        })
    suggestions = feedback.analyze(feedback_rows, region, run_date, cfg,
                                   client=genai_client)
    written = db.write_suggestions(client, suggestions)
    return {
        "ads": len(ad_ids), "insights": len(insights),
        "suggestions": len(suggestions), "suggestions_written": written,
        "rows": feedback_rows, "suggestion_rows": suggestions,
    }


def make_genai(cfg):
    return llm.get_client(cfg.gemini_api_key)
