import json
from pathlib import Path

import pytest

from adsmvp.channels.base import CreativeSpec
from adsmvp.channels.facebook import FacebookPolicyError, _assert_paused
from adsmvp.channels.registry import get_channel


def _spec(tmp_path):
    img = Path(tmp_path) / "img.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nFAKE")
    return CreativeSpec(
        topic_id="t-fuel-001", angle_id="a1", region="ph", lang="en",
        primary_text="Follow the forecast", headline="Will prices rise?",
        description="See more", cta="LEARN_MORE",
        landing_url="https://phnews.example/ph?topic=t-fuel-001",
        image_path=str(img), meta={"run_date": "2026-05-30"})


def test_build_creative_sets_image_hash(cfg, tmp_path):
    ch = get_channel("facebook", cfg)
    spec = ch.build_creative(_spec(tmp_path))
    assert spec.image_hash and spec.image_hash.startswith("stub_img_")


def test_draft_graph_is_paused_and_faithful(cfg):
    ch = get_channel("facebook", cfg)
    spec = ch.build_creative(_spec(cfg.artifacts_dir))
    draft = ch.create_draft_campaign(spec, budget_cap_cents=2000,
                                     campaign_name="phnews-ph-2026-05-30-t-fuel-001-en")
    assert draft.status == "PAUSED"
    eps = draft.raw["endpoints"]
    # every created object is PAUSED
    assert eps["campaign"]["payload"]["status"] == "PAUSED"
    assert eps["adset"]["payload"]["status"] == "PAUSED"
    assert eps["ad"]["payload"]["status"] == "PAUSED"
    # faithful FB fields present
    assert eps["adset"]["payload"]["daily_budget"] == 2000
    assert eps["adset"]["payload"]["targeting"]["geo_locations"]["countries"] == ["PH"]
    ld = eps["adcreative"]["payload"]["object_story_spec"]["link_data"]
    assert ld["image_hash"] == spec.image_hash
    assert ld["call_to_action"]["type"] == "LEARN_MORE"
    # NEVER an ACTIVE status anywhere in the graph
    assert "ACTIVE" not in json.dumps(draft.raw)


def test_draft_artifact_written(cfg):
    ch = get_channel("facebook", cfg)
    spec = ch.build_creative(_spec(cfg.artifacts_dir))
    draft = ch.create_draft_campaign(spec, budget_cap_cents=2000,
                                     campaign_name="phnews-ph-2026-05-30-t-fuel-001-en")
    art = Path(cfg.artifacts_dir) / "drafts" / "2026-05-30" / f"{draft.external_ad_id}.json"
    assert art.exists()
    saved = json.loads(art.read_text())
    assert saved["endpoints"]["ad"]["returns"] == draft.external_ad_id


def test_insights_synthetic_deterministic(cfg):
    ch = get_channel("facebook", cfg)
    a = ch.fetch_insights(["stub_ad_x"], "2026-05-30")
    b = ch.fetch_insights(["stub_ad_x"], "2026-05-30")
    assert a[0].impressions == b[0].impressions > 0
    assert a[0].clicks >= 1


def test_assert_paused_guard():
    with pytest.raises(FacebookPolicyError):
        _assert_paused("ACTIVE")
