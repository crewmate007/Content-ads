#!/usr/bin/env python3
"""Pull yesterday's ad insights, upsert them, and produce content suggestions.

In stub mode insights are synthetic but deterministic, so the feedback loop runs
fully offline. Writes ad_insights + content_suggestions when Supabase is present.

Usage:
  python scripts/run_daily_insights.py --region ph [--date YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adsmvp import db, pipeline  # noqa: E402
from adsmvp.config import load_config, log_diagnostics  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Pull insights + suggest content.")
    ap.add_argument("--region", default="ph")
    ap.add_argument("--date", default=None,
                    help="insight date (default: yesterday)")
    args = ap.parse_args(argv)

    cfg = load_config()
    log_diagnostics(cfg)
    client = db.get_client(cfg)
    genai_client = pipeline.make_genai(cfg)
    date = args.date or (dt.date.today() - dt.timedelta(days=1)).isoformat()

    print(f"[INFO] run_daily_insights region={args.region} date={date} "
          f"fb_mode={cfg.facebook_mode} supabase={'yes' if client else 'no'}")

    summary = pipeline.run_insights(cfg, args.region, date, client=client,
                                    genai_client=genai_client)
    print(f"[INFO] ads={summary['ads']} insights={summary['insights']} "
          f"suggestions={summary['suggestions']} "
          f"written={summary['suggestions_written']}")
    for s in summary["suggestion_rows"]:
        if s["scope"] in ("topic_type", "angle_type"):
            print(f"  {s['signal'].upper():9} {s['scope']}={s['subject']} "
                  f"w={s['weight']}  {s['rationale']}")
        elif s["scope"] == "overall":
            print(f"  SUMMARY  {s['rationale']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
