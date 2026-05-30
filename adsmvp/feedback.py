"""Insights -> content suggestions (the optimization half of the loop).

Numbers are computed deterministically (statistics, never LLM-invented); the
LLM only narrates the rationale. Output `content_suggestions` rows feed back
into selection.feedback_bonus() to re-weight tomorrow's topic/angle choice.
"""
from __future__ import annotations

import statistics
import sys
from typing import Dict, List, Optional, Sequence

from . import llm

# Thresholds for turning a group's CTR vs. the cohort median into a signal.
OVER = 1.10
UNDER = 0.90
MAX_WEIGHT = 1.0


def _ctr(clicks: float, impressions: float) -> float:
    return (clicks / impressions * 100.0) if impressions else 0.0


def _cpc(spend: float, clicks: float) -> float:
    return (spend / clicks) if clicks else 0.0


def aggregate(rows: Sequence[Dict]) -> Dict[str, Dict[str, Dict]]:
    """Roll up metric rows by topic_type / angle_type / lang.

    Each row needs: topic_type, angle_type, lang, impressions, clicks, spend,
    conversions. Returns {scope: {subject: {metrics...}}}.
    """
    scopes = ("topic_type", "angle_type", "lang")
    acc: Dict[str, Dict[str, Dict]] = {s: {} for s in scopes}
    for r in rows:
        for s in scopes:
            subj = (r.get(s) or "unknown")
            g = acc[s].setdefault(subj, {"impressions": 0, "clicks": 0,
                                         "spend": 0.0, "conversions": 0, "n": 0})
            g["impressions"] += int(r.get("impressions") or 0)
            g["clicks"] += int(r.get("clicks") or 0)
            g["spend"] += float(r.get("spend") or 0.0)
            g["conversions"] += int(r.get("conversions") or 0)
            g["n"] += 1
    for s in scopes:
        for subj, g in acc[s].items():
            g["ctr"] = round(_ctr(g["clicks"], g["impressions"]), 4)
            g["cpc"] = round(_cpc(g["spend"], g["clicks"]), 4)
    return acc


def _signal(ctr: float, median: float) -> tuple:
    if median <= 0:
        return ("maintain", 0.0)
    ratio = ctr / median
    if ratio >= OVER:
        return ("make_more", min(MAX_WEIGHT, ratio - 1.0))
    if ratio <= UNDER:
        return ("make_less", min(MAX_WEIGHT, 1.0 - ratio))
    return ("maintain", 0.0)


def build_suggestions(aggregates: Dict[str, Dict[str, Dict]], region: str,
                      run_date: str) -> List[Dict]:
    """Pure statistical suggestions (no LLM). One row per (scope, subject)."""
    out: List[Dict] = []
    for scope in ("topic_type", "angle_type"):
        groups = aggregates.get(scope, {})
        ctrs = [g["ctr"] for g in groups.values() if g["n"]]
        if len(ctrs) < 2:
            continue
        median = statistics.median(ctrs)
        for subj, g in groups.items():
            if not g["n"]:
                continue
            signal, weight = _signal(g["ctr"], median)
            out.append({
                "region": region,
                "run_date": run_date,
                "scope": scope,
                "subject": subj,
                "signal": signal,
                "weight": round(float(weight), 4),
                "rationale": (f"{scope}={subj}: CTR {g['ctr']:.2f}% vs cohort "
                              f"median {median:.2f}% over {g['n']} ad(s), "
                              f"CPC {g['cpc']:.3f}, conv {g['conversions']}."),
                "evidence": g,
            })
    return out


NARRATE_PROMPT = """You are a growth analyst advising a news content team. Given \
these ad-performance rollups for {region} on {date}, write a 2-4 sentence plain \
recommendation of what content to make MORE and LESS of. Be specific about \
topic types and angle styles. Do not invent numbers; only use those given.

DATA (JSON):
{data}

Return ONLY JSON: {{"summary": "...", "make_more": ["..."], "make_less": ["..."]}}
"""


def narrate(aggregates: Dict, region: str, run_date: str, cfg, client) -> Optional[Dict]:
    """Optional LLM narration enriching the statistical suggestions."""
    if client is None:
        return None
    import json
    prompt = NARRATE_PROMPT.format(region=region, date=run_date,
                                   data=json.dumps(aggregates, ensure_ascii=False))
    try:
        return llm.generate_json(client, cfg.gemini_model, prompt)
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] narration failed ({type(exc).__name__}: {exc})", file=sys.stderr)
        return None


def analyze(rows: Sequence[Dict], region: str, run_date: str, cfg, *,
            client=None) -> List[Dict]:
    """Full path: aggregate -> statistical suggestions -> attach LLM narration."""
    aggregates = aggregate(rows)
    suggestions = build_suggestions(aggregates, region, run_date)
    narration = narrate(aggregates, region, run_date, cfg, client)
    if narration:
        suggestions.append({
            "region": region, "run_date": run_date, "scope": "overall",
            "subject": "summary", "signal": "maintain", "weight": 0.0,
            "rationale": narration.get("summary", ""),
            "evidence": narration,
        })
    return suggestions
