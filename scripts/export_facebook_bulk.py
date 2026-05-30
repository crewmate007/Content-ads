#!/usr/bin/env python3
"""Export PAUSED ad drafts as a Facebook-bulk-import CSV for a date.

Usage:
  python scripts/export_facebook_bulk.py [--date YYYY-MM-DD]

Reads artifacts/drafts/<date>/*.json and writes artifacts/csv/<date>_facebook_bulk.csv.
A human reviews and uploads it via Facebook Ads Manager's bulk import.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adsmvp import review  # noqa: E402
from adsmvp.config import load_config  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Export Facebook bulk-import CSV.")
    ap.add_argument("--date", default=dt.date.today().isoformat())
    args = ap.parse_args(argv)

    cfg = load_config()
    rows = review.collect_drafts(cfg.artifacts_dir, args.date)
    out = review.export_csv(cfg.artifacts_dir, args.date)
    print(f"[INFO] wrote {out} ({len(rows)} drafts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
