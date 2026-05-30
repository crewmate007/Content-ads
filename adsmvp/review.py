"""Human-review digest for PAUSED ad drafts (the approval gate).

Reads the stub draft artifacts written by FacebookChannel (artifacts/drafts/
<date>/*.json) and renders a single self-contained HTML page so a human can eye
the image, copy, targeting, and budget before launching. Offline-first; no DB or
network needed. (In live mode, drafts are also visible in Ads Manager.)
"""
from __future__ import annotations

import csv
import html
import json
import os
from pathlib import Path
from typing import Dict, List, Optional


def collect_drafts(artifacts_dir, date: str) -> List[Dict]:
    """Load and flatten every draft graph for a date into review-friendly rows."""
    draft_dir = Path(artifacts_dir) / "drafts" / date
    rows: List[Dict] = []
    if not draft_dir.exists():
        return rows
    for f in sorted(draft_dir.glob("*.json")):
        try:
            g = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        eps = g.get("endpoints", {})
        ld = (eps.get("adcreative", {}).get("payload", {})
              .get("object_story_spec", {}).get("link_data", {}))
        adset = eps.get("adset", {}).get("payload", {})
        campaign = eps.get("campaign", {}).get("payload", {})
        rows.append({
            "ad_id": eps.get("ad", {}).get("returns") or g.get("ad_id"),
            "topic_id": g.get("topic_id"),
            "region": g.get("region"),
            "lang": g.get("lang"),
            "copy_style": g.get("copy_style"),
            "policy_status": g.get("policy_status"),
            "objective": campaign.get("objective"),
            "status": campaign.get("status"),
            "daily_budget": adset.get("daily_budget"),
            "countries": (adset.get("targeting", {})
                          .get("geo_locations", {}).get("countries")),
            "headline": ld.get("name"),
            "primary_text": ld.get("message"),
            "description": ld.get("description"),
            "cta": (ld.get("call_to_action") or {}).get("type"),
            "link": ld.get("link"),
            "image_path": g.get("image_path"),
            "image_url": g.get("image_url"),
            "_file": str(f),
        })
    return rows


# Facebook Ads bulk-import column order (Ads Manager CSV import).
_CSV_COLUMNS = [
    "Campaign Name", "Ad Set Name", "Ad Name", "Campaign Objective",
    "Ad Set Daily Budget", "Bid Strategy", "Countries", "Ad Status",
    "Title", "Body", "Link Description", "Call to Action",
    "Image Hash", "Website URL",
]


def _csv_row(r: Dict) -> Dict[str, object]:
    ad_id = r.get("ad_id") or ""
    budget = r.get("daily_budget")
    countries = r.get("countries") or []
    return {
        "Campaign Name": f"phnews-{r.get('region')}-{r.get('topic_id')}",
        "Ad Set Name": f"{ad_id} / adset",
        "Ad Name": ad_id,
        "Campaign Objective": r.get("objective") or "",
        "Ad Set Daily Budget": (budget / 100.0) if isinstance(budget, (int, float)) else "",
        "Bid Strategy": "LOWEST_COST_WITHOUT_CAP",
        "Countries": ",".join(countries) if isinstance(countries, list) else (countries or ""),
        "Ad Status": r.get("status") or "PAUSED",
        "Title": r.get("headline") or "",
        "Body": r.get("primary_text") or "",
        "Link Description": r.get("description") or "",
        "Call to Action": r.get("cta") or "",
        "Image Hash": r.get("image_url") or r.get("image_path") or "",
        "Website URL": r.get("link") or "",
    }


def export_csv(artifacts_dir, date: str, out_path: Optional[Path] = None) -> Path:
    """Export PAUSED drafts as a Facebook-bulk-import-ready CSV (Lau workflow)."""
    rows = collect_drafts(artifacts_dir, date)
    out_dir = Path(out_path or artifacts_dir) / "csv"
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"{date}_facebook_bulk.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_COLUMNS)
        writer.writeheader()
        for r in rows:
            writer.writerow(_csv_row(r))
    return csv_path


def _img_src(row: Dict, out_path: Path) -> Optional[str]:
    if row.get("image_url"):
        return row["image_url"]
    p = row.get("image_path")
    if p and Path(p).exists():
        try:
            return os.path.relpath(p, out_path.parent)
        except ValueError:
            return p
    return None


def render_html(rows: List[Dict], date: str, out_path: Path) -> str:
    cards = []
    for r in rows:
        src = _img_src(r, out_path)
        img = (f'<img src="{html.escape(src)}" alt="creative" '
               f'style="width:120px;height:120px;object-fit:cover;border-radius:8px;'
               f'background:#1a2236">' if src else
               '<div style="width:120px;height:120px;border-radius:8px;'
               'background:#1a2236"></div>')
        badge = {"pass": "#2e7d32", "revised": "#b08900",
                 "blocked": "#b00020"}.get(r.get("policy_status"), "#555")
        cards.append(f"""
        <div class="card">
          {img}
          <div class="body">
            <div class="head">
              <span class="pill" style="background:{badge}">{html.escape(str(r.get('policy_status')))}</span>
              <span class="pill" style="background:#37474f">{html.escape(str(r.get('status')))}</span>
              <span class="meta">{html.escape(str(r.get('region')))} · {html.escape(str(r.get('lang')))} · {html.escape(str(r.get('copy_style')))}</span>
            </div>
            <div class="headline">{html.escape(str(r.get('headline') or ''))}</div>
            <div class="primary">{html.escape(str(r.get('primary_text') or ''))}</div>
            <div class="desc">{html.escape(str(r.get('description') or ''))} · CTA: {html.escape(str(r.get('cta') or ''))}</div>
            <div class="meta">geo {html.escape(str(r.get('countries')))} · budget {html.escape(str(r.get('daily_budget')))}¢/day · {html.escape(str(r.get('objective') or ''))}</div>
            <div class="meta"><a href="{html.escape(str(r.get('link') or '#'))}">{html.escape(str(r.get('link') or ''))}</a></div>
            <div class="meta id">{html.escape(str(r.get('ad_id') or ''))} · topic {html.escape(str(r.get('topic_id') or ''))}</div>
          </div>
        </div>""")
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Ad draft review — {html.escape(date)}</title>
<style>
 body{{background:#0e1320;color:#e6eaf2;font:14px/1.5 system-ui,Segoe UI,Roboto,sans-serif;margin:0;padding:24px}}
 h1{{font-size:18px}} .note{{color:#9fb0c8;margin-bottom:16px}}
 .card{{display:flex;gap:14px;background:#141b2d;border:1px solid #222c44;border-radius:12px;padding:14px;margin-bottom:12px}}
 .body{{flex:1;min-width:0}} .head{{display:flex;gap:8px;align-items:center;margin-bottom:6px;flex-wrap:wrap}}
 .pill{{font-size:11px;padding:2px 8px;border-radius:999px;color:#fff}}
 .headline{{font-weight:700;margin:2px 0}} .primary{{margin:2px 0}}
 .desc{{color:#c7d2e6}} .meta{{color:#8a9bb6;font-size:12px}} .id{{font-family:ui-monospace,monospace}}
 a{{color:#7cc4ff}}
</style></head><body>
<h1>Ad draft review — {html.escape(date)} <span class="note">({len(rows)} PAUSED drafts)</span></h1>
<div class="note">These are PAUSED drafts. Review each, then launch approved ones in Ads Manager (live) or mark review_state=approved. Nothing here has spent money.</div>
{''.join(cards) if cards else '<div class="note">No drafts found for this date.</div>'}
</body></html>"""


def write_review(artifacts_dir, date: str) -> Path:
    rows = collect_drafts(artifacts_dir, date)
    out_dir = Path(artifacts_dir) / "review"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{date}.html"
    out_path.write_text(render_html(rows, date, out_path), encoding="utf-8")
    return out_path
