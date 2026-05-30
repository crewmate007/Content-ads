"""Shared helpers for the stub (sandbox) path.

The stub records the *full live-shaped request payload* for every object so a
reviewer can confirm the live API would receive correct fields before any token
exists. IDs and synthetic metrics are deterministic (seeded by content) so runs
are reproducible and tests can assert exact values.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict


def deterministic_id(prefix: str, *parts: str) -> str:
    """Stable fake external id, e.g. stub_campaign_ab12cd34."""
    seed = "|".join(str(p) for p in parts)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8]
    return f"stub_{prefix}_{digest}"


def synthetic_insights(ad_id: str, date: str) -> Dict[str, Any]:
    """Plausible, deterministic metrics so the feedback loop is exercised.

    Seeded by hash(ad_id+date). Values are in realistic ranges; spend stays
    modest so aggregates look sane. This is the ONLY place fake metrics are
    invented; the live path returns real Graph API numbers instead.
    """
    h = int(hashlib.sha256(f"{ad_id}|{date}".encode("utf-8")).hexdigest(), 16)
    impressions = 800 + (h % 4200)              # 800 - 5000
    ctr = 0.6 + ((h >> 8) % 240) / 100.0        # 0.6% - 3.0%
    clicks = max(1, int(impressions * ctr / 100.0))
    cpc = 4.0 + ((h >> 16) % 1600) / 100.0      # 4.00 - 20.00 (cents)
    spend = round(clicks * cpc / 100.0, 2)      # dollars
    conversions = (h >> 24) % max(1, clicks // 4 + 1)
    return {
        "impressions": impressions,
        "clicks": clicks,
        "ctr": round(ctr, 4),
        "spend": spend,
        "cpc": round(cpc / 100.0, 4),
        "conversions": int(conversions),
    }


def write_draft_artifact(artifacts_dir: Path, date: str, ad_id: str,
                         payload: Dict[str, Any]) -> Path:
    """Persist the intended request graph for human review."""
    out_dir = Path(artifacts_dir) / "drafts" / date
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{ad_id}.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    return out_path
