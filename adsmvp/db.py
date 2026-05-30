"""Supabase access for Content-ads.

Reads phnews content tables (topics/angles/source_examples) and writes the new
ad tables (ad_creatives/ad_campaigns/ad_insights/content_suggestions). Mirrors
phnews/mvp/db.py discipline: lazy-import supabase, no-op when creds/package are
absent, and NEVER raise to the caller (log to stderr, return a safe default).
"""
from __future__ import annotations

import datetime as dt
import sys
from typing import Dict, List, Optional, Sequence, Set


def get_client(cfg):
    if not cfg.has_supabase:
        return None
    try:
        from supabase import create_client  # lazy
    except ImportError:
        print("[WARN] supabase package not installed; DB disabled", file=sys.stderr)
        return None
    try:
        return create_client(cfg.supabase_url, cfg.supabase_key)
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] supabase client init failed: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return None


def _safe(fn, default):
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] supabase op failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return default


# --------------------------------------------------------------------- reads
def latest_run_date(client, region: str) -> Optional[str]:
    if client is None:
        return None
    def q():
        r = (client.table("runs").select("run_date").eq("region", region)
             .eq("status", "done").order("run_date", desc=True).limit(1).execute())
        return r.data[0]["run_date"] if r.data else None
    return _safe(q, None)


def fetch_topics(client, region: str, run_date: str) -> List[Dict]:
    if client is None:
        return []
    def q():
        r = (client.table("topics").select("*").eq("region", region)
             .eq("run_date", run_date).eq("bettable", True).execute())
        return r.data or []
    return _safe(q, [])


def fetch_angles(client, topic_ids: Sequence[str]) -> Dict[str, List[Dict]]:
    out: Dict[str, List[Dict]] = {}
    if client is None or not topic_ids:
        return out
    def q():
        r = (client.table("angles").select("*").in_("topic_id", list(topic_ids))
             .order("position").execute())
        return r.data or []
    for a in _safe(q, []):
        out.setdefault(a["topic_id"], []).append(a)
    return out


def fetch_source_examples(client, topic_ids: Sequence[str]) -> Dict[str, List[Dict]]:
    out: Dict[str, List[Dict]] = {}
    if client is None or not topic_ids:
        return out
    def q():
        r = (client.table("source_examples").select("*")
             .in_("topic_id", list(topic_ids)).order("position").execute())
        return r.data or []
    for s in _safe(q, []):
        out.setdefault(s["topic_id"], []).append(s)
    return out


def fetch_advertised_topic_ids(client, since_date: str) -> Set[str]:
    if client is None:
        return set()
    def q():
        r = (client.table("ad_campaigns").select("topic_id")
             .gte("run_date", since_date).execute())
        return {row["topic_id"] for row in (r.data or []) if row.get("topic_id")}
    return _safe(q, set())


def fetch_recent_suggestions(client, region: str, since_date: str) -> List[Dict]:
    if client is None:
        return []
    def q():
        r = (client.table("content_suggestions").select("*").eq("region", region)
             .gte("run_date", since_date).execute())
        return r.data or []
    return _safe(q, [])


def fetch_campaigns_for_insights(client, region: str) -> List[Dict]:
    """Campaigns whose ads we should pull metrics for (launched, or all in stub)."""
    if client is None:
        return []
    def q():
        r = (client.table("ad_campaigns")
             .select("id,external_ad_id,topic_id,creative_id,region")
             .eq("region", region).execute())
        return r.data or []
    return _safe(q, [])


def fetch_creatives_by_id(client, creative_ids: Sequence[str]) -> Dict[str, Dict]:
    out: Dict[str, Dict] = {}
    if client is None or not creative_ids:
        return out
    def q():
        r = (client.table("ad_creatives").select("*")
             .in_("id", list(creative_ids)).execute())
        return r.data or []
    for c in _safe(q, []):
        out[c["id"]] = c
    return out


def fetch_winning_creatives(client, region: str, lang: Optional[str] = None,
                            limit: int = 3, lookback_days: int = 7) -> List[Dict]:
    """Top-performing past creatives by CTR, for few-shot copy priming.

    Joins ad_insights -> ad_campaigns -> ad_creatives in Python (the client lacks
    rich joins). Returns [{headline, primary_text, description, ctr, copy_style}]
    for `region` (and `lang` if given), best first. No-op -> [] without a client.
    """
    if client is None:
        return []
    since_date = since(lookback_days)

    def q_insights():
        r = (client.table("ad_insights").select("campaign_id,ctr,insight_date")
             .gte("insight_date", since_date).order("ctr", desc=True)
             .limit(max(limit * 8, 40)).execute())
        return r.data or []
    insights = _safe(q_insights, [])
    if not insights:
        return []

    campaign_ids = [i["campaign_id"] for i in insights if i.get("campaign_id")]
    if not campaign_ids:
        return []

    def q_campaigns():
        r = (client.table("ad_campaigns").select("id,creative_id,region")
             .in_("id", list(dict.fromkeys(campaign_ids))).execute())
        return r.data or []
    campaigns = {c["id"]: c for c in _safe(q_campaigns, [])}

    creative_ids = [c.get("creative_id") for c in campaigns.values()
                    if c.get("creative_id")]
    creatives = fetch_creatives_by_id(client, creative_ids)

    out: List[Dict] = []
    seen = set()
    for i in insights:                       # already CTR-desc ordered
        camp = campaigns.get(i.get("campaign_id"))
        if not camp or camp.get("region") != region:
            continue
        cr = creatives.get(camp.get("creative_id"))
        if not cr or (lang and cr.get("lang") != lang):
            continue
        key = cr.get("id")
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "headline": cr.get("headline"),
            "primary_text": cr.get("primary_text"),
            "description": cr.get("description"),
            "copy_style": cr.get("copy_style"),
            "ctr": i.get("ctr"),
        })
        if len(out) >= limit:
            break
    return out


# -------------------------------------------------------------------- writes
def write_creative(client, spec, region: str, run_date: str) -> Optional[str]:
    if client is None:
        return None
    payload = {
        "topic_id": spec.topic_id, "angle_id": spec.angle_id,
        "region": region, "lang": spec.lang, "channel": "facebook",
        "primary_text": spec.primary_text, "headline": spec.headline,
        "description": spec.description, "cta": spec.cta,
        "image_path": spec.image_path, "image_url": spec.image_url,
        "landing_url": spec.landing_url, "copy_style": spec.copy_style,
        "policy_status": spec.policy_status, "policy_notes": spec.policy_notes,
        "model_copy": spec.model_copy, "model_image": spec.model_image,
    }
    def q():
        r = client.table("ad_creatives").insert(payload).execute()
        return r.data[0]["id"]
    return _safe(q, None)


def write_campaign(client, draft, spec, creative_id: Optional[str],
                   region: str, run_date: str) -> Optional[str]:
    if client is None:
        return None
    payload = {
        "creative_id": creative_id, "topic_id": spec.topic_id,
        "region": region, "channel": draft.channel, "mode": draft.mode,
        "status": draft.status,
        "external_campaign_id": draft.external_campaign_id,
        "external_adset_id": draft.external_adset_id,
        "external_creative_id": draft.external_creative_id,
        "external_ad_id": draft.external_ad_id,
        "permalink": draft.permalink,
        "budget_cap_cents": draft.budget_cap_cents,
        "review_state": "pending_review",
        "raw": draft.raw, "run_date": run_date,
    }
    def q():
        r = client.table("ad_campaigns").insert(payload).execute()
        return r.data[0]["id"]
    return _safe(q, None)


def upsert_insights(client, rows: Sequence[Dict]) -> int:
    """Upsert ad_insights idempotently on (external_ad_id, insight_date)."""
    if client is None or not rows:
        return 0
    def q():
        client.table("ad_insights").upsert(
            list(rows), on_conflict="external_ad_id,insight_date").execute()
        return len(rows)
    return _safe(q, 0)


def write_suggestions(client, suggestions: Sequence[Dict]) -> int:
    if client is None or not suggestions:
        return 0
    def q():
        client.table("content_suggestions").insert(list(suggestions)).execute()
        return len(suggestions)
    return _safe(q, 0)


def since(days: int) -> str:
    return (dt.date.today() - dt.timedelta(days=days)).isoformat()
