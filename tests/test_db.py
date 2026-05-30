"""db.py must no-op (never raise) without Supabase credentials."""
from adsmvp import db
from adsmvp.channels.base import CreativeSpec, DraftResult


def test_get_client_none_without_creds(cfg):
    assert db.get_client(cfg) is None


def test_reads_return_empty_without_client():
    assert db.latest_run_date(None, "ph") is None
    assert db.fetch_topics(None, "ph", "2026-05-30") == []
    assert db.fetch_angles(None, ["t1"]) == {}
    assert db.fetch_source_examples(None, ["t1"]) == {}
    assert db.fetch_advertised_topic_ids(None, "2026-05-01") == set()
    assert db.fetch_recent_suggestions(None, "ph", "2026-05-01") == []


def test_writes_noop_without_client():
    spec = CreativeSpec(topic_id="t", angle_id=None, region="ph", lang="en",
                        primary_text="x", headline="y", description="z",
                        cta="LEARN_MORE", landing_url="https://x")
    draft = DraftResult(channel="facebook", mode="stub", status="PAUSED",
                        external_campaign_id="c", external_adset_id="s",
                        external_creative_id="cr", external_ad_id="a",
                        budget_cap_cents=2000)
    assert db.write_creative(None, spec, "ph", "2026-05-30") is None
    assert db.write_campaign(None, draft, spec, None, "ph", "2026-05-30") is None
    assert db.upsert_insights(None, [{"external_ad_id": "a"}]) == 0
    assert db.write_suggestions(None, [{"region": "ph"}]) == 0
