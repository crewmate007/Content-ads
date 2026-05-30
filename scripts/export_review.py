#!/usr/bin/env python3
"""Render a human-review HTML digest of PAUSED ad drafts for a date.

Usage:
  python scripts/export_review.py [--date YYYY-MM-DD]

Reads artifacts/drafts/<date>/*.json and writes artifacts/review/<date>.html.
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
    ap = argparse.ArgumentParser(description="Export PAUSED-draft review digest.")
    ap.add_argument("--date", default=dt.date.today().isoformat())
    args = ap.parse_args(argv)

    cfg = load_config()
    rows = review.collect_drafts(cfg.artifacts_dir, args.date)
    out = review.write_review(cfg.artifacts_dir, args.date)
    print(f"[INFO] wrote {out} ({len(rows)} drafts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
