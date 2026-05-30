#!/usr/bin/env python3
"""Generate creatives and create PAUSED Facebook ad drafts for a region/day.

Never launches or spends. Writes draft payloads to artifacts/ (stub) and, when
Supabase creds are present, rows to ad_creatives / ad_campaigns.

Usage:
  python scripts/run_daily_ads.py --region ph [--date YYYY-MM-DD] [--limit N]
                                  [--mode stub|live] [--langs en,zh]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adsmvp import db, pipeline  # noqa: E402
from adsmvp.config import load_config, log_diagnostics  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Create PAUSED Facebook ad drafts.")
    ap.add_argument("--region", default="ph")
    ap.add_argument("--date", default=None, help="run_date (default: latest run / today)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--mode", choices=["stub", "live"], default=None,
                    help="override FACEBOOK_MODE for this run")
    ap.add_argument("--langs", default="en,zh")
    args = ap.parse_args(argv)

    if args.mode:
        os.environ["FACEBOOK_MODE"] = args.mode
    cfg = load_config()
    log_diagnostics(cfg)

    client = db.get_client(cfg)
    genai_client = pipeline.make_genai(cfg)
    run_date = pipeline.resolve_run_date(cfg, client, args.region, args.date)
    langs = [l.strip() for l in args.langs.split(",") if l.strip()]

    print(f"[INFO] run_daily_ads region={args.region} date={run_date} "
          f"fb_mode={cfg.facebook_mode} supabase={'yes' if client else 'no'} "
          f"gemini={'yes' if genai_client else 'no'}")

    results = pipeline.run_ads(cfg, args.region, run_date, limit=args.limit,
                               langs=langs, client=client, genai_client=genai_client)

    drafted = [r for r in results if r.ad_id]
    blocked = [r for r in results if r.skipped]
    for r in drafted:
        print(f"  DRAFT {r.ad_id}  topic={r.topic_id} lang={r.lang} "
              f"type={r.topic_type} policy={r.policy_status}")
    for r in blocked:
        print(f"  SKIP  topic={r.topic_id} lang={r.lang} reason={r.skipped}")
    print(f"[INFO] drafted={len(drafted)} blocked={len(blocked)} "
          f"(all PAUSED, zero spend). Review artifacts/drafts/{run_date}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
