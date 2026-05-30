import json
import types
from pathlib import Path

from adsmvp import images, pipeline, review
from adsmvp.sample_data import sample_inputs
from adsmvp.selection import select_candidates
from adsmvp.config import DEFAULT_WEIGHTS
from tests.conftest import make_cfg


def test_angle_variants_expand_drafts(tmp_path):
    # fuel topic has a primary serious angle + a reddit alt angle.
    cfg = make_cfg(tmp_path, variants_per_topic=2)
    results = pipeline.run_ads(cfg, "ph", "2026-05-30", langs=["en"],
                               client=None, genai_client=None)
    drafted = [r for r in results if r.ad_id]
    fuel = [r for r in drafted if r.topic_id == "t-fuel-001"]
    # primary (serious) + 1 alt (reddit) = 2 variants for the en lang
    assert len(fuel) == 2
    assert {r.angle_type for r in fuel} == {"serious", "reddit"}
    # variants must be distinct ads, not collapsed onto one id/artifact
    assert len({r.ad_id for r in fuel}) == 2
    draft_files = list((Path(cfg.artifacts_dir) / "drafts" / "2026-05-30").glob("*.json"))
    assert len(draft_files) == len(drafted)


def test_variant_default_is_one(tmp_path):
    cfg = make_cfg(tmp_path, variants_per_topic=1)
    results = pipeline.run_ads(cfg, "ph", "2026-05-30", langs=["en"],
                               client=None, genai_client=None)
    fuel = [r for r in results if r.ad_id and r.topic_id == "t-fuel-001"]
    assert len(fuel) == 1
    assert fuel[0].angle_type == "serious"


def test_review_digest_renders(cfg):
    pipeline.run_ads(cfg, "ph", "2026-05-30", langs=["en"], client=None,
                     genai_client=None)
    out = review.write_review(cfg.artifacts_dir, "2026-05-30")
    assert out.exists()
    htmltext = out.read_text()
    assert "PAUSED drafts" in htmltext
    rows = review.collect_drafts(cfg.artifacts_dir, "2026-05-30")
    assert rows and all(r["status"] == "PAUSED" for r in rows)
    assert all(r["countries"] == ["PH"] for r in rows)


def test_supabase_upload_sets_url(tmp_path):
    # Fake supabase storage client.
    uploaded = {}

    class _Storage:
        def upload(self, path, data, opts=None):
            uploaded["path"] = path
            uploaded["bytes"] = len(data)
        def get_public_url(self, path):
            return f"https://cdn.example/{path}"

    class _Client:
        storage = types.SimpleNamespace(from_=lambda bucket: _Storage())

    img = Path(tmp_path) / "x.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nFAKE")
    url = images.upload_to_supabase(_Client(), "ad-creatives", "ph/x.png", img)
    assert url == "https://cdn.example/ph/x.png"
    assert uploaded["bytes"] > 0


def test_supabase_upload_noop_without_client():
    assert images.upload_to_supabase(None, "b", "p", Path("/nope")) is None
