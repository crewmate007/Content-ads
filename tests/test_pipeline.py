"""End-to-end pipeline in stub/offline mode (no Supabase, no Gemini)."""
import json
from pathlib import Path

from adsmvp import pipeline


def test_run_ads_offline_creates_paused_drafts(cfg):
    results = pipeline.run_ads(cfg, "ph", "2026-05-30", client=None,
                               genai_client=None)
    drafted = [r for r in results if r.ad_id]
    assert drafted, "expected at least one draft"
    # 3 selected topics x 2 langs = 6 (election/non-bettable filtered out)
    assert len(drafted) == 6
    assert all(r.policy_status in ("pass", "revised") for r in drafted)
    # artifacts written and every graph is PAUSED-only
    draft_dir = Path(cfg.artifacts_dir) / "drafts" / "2026-05-30"
    files = list(draft_dir.glob("*.json"))
    assert len(files) == 6
    for f in files:
        assert "ACTIVE" not in f.read_text()
        graph = json.loads(f.read_text())
        assert graph["endpoints"]["campaign"]["payload"]["status"] == "PAUSED"


def test_run_insights_offline_produces_suggestions(cfg):
    summary = pipeline.run_insights(cfg, "ph", "2026-05-30", client=None,
                                    genai_client=None)
    assert summary["ads"] == 6
    assert summary["insights"] == 6
    assert summary["suggestions"] >= 1
    signals = {s["signal"] for s in summary["suggestion_rows"]}
    assert signals & {"make_more", "make_less", "maintain"}
