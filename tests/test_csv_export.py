"""Facebook bulk-import CSV export."""
import csv
from pathlib import Path

from adsmvp import pipeline, review


def test_export_csv(cfg):
    pipeline.run_ads(cfg, "ph", "2026-05-30", langs=["en"], client=None,
                     genai_client=None)
    out = review.export_csv(cfg.artifacts_dir, "2026-05-30")
    assert out.exists() and out.name == "2026-05-30_facebook_bulk.csv"
    with open(out, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows, "expected CSV rows"
    assert set(review._CSV_COLUMNS).issubset(rows[0].keys())
    for r in rows:
        assert r["Ad Status"] == "PAUSED"
        assert r["Countries"] == "PH"
        assert r["Campaign Objective"] == "OUTCOME_TRAFFIC"
        assert r["Ad Name"].startswith("stub_ad_")


def test_export_csv_empty_date(cfg):
    out = review.export_csv(cfg.artifacts_dir, "1999-01-01")
    assert out.exists()
    with open(out, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows == []
