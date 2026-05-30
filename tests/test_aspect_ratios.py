"""Multi-aspect-ratio images + Facebook asset_feed_spec."""
import json
from pathlib import Path

from adsmvp import creative, images
from adsmvp.channels.registry import get_channel
from adsmvp.config import DEFAULT_WEIGHTS
from adsmvp.sample_data import sample_inputs
from adsmvp.selection import select_candidates
from tests.conftest import make_cfg


def _cand():
    topics, angles, se = sample_inputs("ph", "2026-05-30")
    return select_candidates(topics, angles, se, weights=DEFAULT_WEIGHTS, limit=1)[0]


def test_size_for_aspect():
    assert images.size_for_aspect("1:1") == "1024x1024"
    assert images.size_for_aspect("9:16") == "1024x1536"
    assert images.size_for_aspect("16:9") == "1536x1024"
    assert images.size_for_aspect("weird") == "1024x1024"  # default


def test_generate_creative_makes_one_image_per_ratio(tmp_path):
    cfg = make_cfg(tmp_path, image_aspect_ratios=["1:1", "9:16"])
    spec = creative.generate_creative(_cand(), "ph", "en", cfg, client=None,
                                      image_client=None, run_date="2026-05-30",
                                      aspect_ratios=["1:1", "9:16"])
    paths = spec.meta["image_paths"]
    assert set(paths) == {"1:1", "9:16"}
    assert all(Path(p).exists() for p in paths.values())
    assert spec.image_path == paths["1:1"]   # primary prefers 1:1


def test_openai_image_client_path(tmp_path, fake_openai):
    cfg = make_cfg(tmp_path, openai_api_key="sk-test", image_aspect_ratios=["9:16"])
    spec = creative.generate_creative(_cand(), "ph", "en", cfg, client=None,
                                      image_client=fake_openai, run_date="2026-05-30",
                                      aspect_ratios=["9:16"])
    assert spec.model_image == cfg.openai_image_model
    assert fake_openai._state["image_calls"][-1]["size"] == "1024x1536"
    assert Path(spec.image_path).exists()


def test_asset_feed_spec_in_draft(tmp_path):
    cfg = make_cfg(tmp_path, image_aspect_ratios=["1:1", "9:16"],
                   fb_placements=["FEED", "STORY"])
    spec = creative.generate_creative(_cand(), "ph", "en", cfg, client=None,
                                      image_client=None, run_date="2026-05-30",
                                      aspect_ratios=["1:1", "9:16"])
    ch = get_channel("facebook", cfg)
    spec = ch.build_creative(spec)
    assert set(spec.meta["image_hashes"]) == {"1:1", "9:16"}
    draft = ch.create_draft_campaign(spec, budget_cap_cents=2000,
                                     campaign_name="phnews-ph-2026-05-30-t-x-en-v0")
    assert draft.status == "PAUSED"
    afs = draft.raw["endpoints"]["adcreative"]["payload"]["asset_feed_spec"]
    assert len(afs["images"]) == 2
    labels = {i["adlabels"][0]["name"] for i in afs["images"]}
    assert labels == {"1:1", "9:16"}
    assert "ACTIVE" not in json.dumps(draft.raw)


def test_single_ratio_has_no_asset_feed_spec(tmp_path):
    cfg = make_cfg(tmp_path, image_aspect_ratios=["1:1"])
    spec = creative.generate_creative(_cand(), "ph", "en", cfg, client=None,
                                      image_client=None, run_date="2026-05-30")
    ch = get_channel("facebook", cfg)
    spec = ch.build_creative(spec)
    draft = ch.create_draft_campaign(spec, budget_cap_cents=2000,
                                     campaign_name="phnews-ph-2026-05-30-t-x-en-v0")
    assert "asset_feed_spec" not in draft.raw["endpoints"]["adcreative"]["payload"]
