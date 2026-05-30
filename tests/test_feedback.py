from adsmvp import feedback


def _rows():
    # disaster outperforms economy on CTR.
    return [
        {"topic_type": "economy", "angle_type": "serious", "lang": "en",
         "impressions": 1000, "clicks": 10, "spend": 1.0, "conversions": 2},
        {"topic_type": "economy", "angle_type": "serious", "lang": "zh",
         "impressions": 1000, "clicks": 12, "spend": 1.2, "conversions": 3},
        {"topic_type": "disaster", "angle_type": "reddit", "lang": "en",
         "impressions": 1000, "clicks": 40, "spend": 1.0, "conversions": 8},
    ]


def test_aggregate_metrics():
    agg = feedback.aggregate(_rows())
    eco = agg["topic_type"]["economy"]
    assert eco["impressions"] == 2000 and eco["clicks"] == 22
    assert round(eco["ctr"], 2) == 1.10


def test_build_suggestions_signals():
    agg = feedback.aggregate(_rows())
    sugg = feedback.build_suggestions(agg, "ph", "2026-05-30")
    by_subject = {(s["scope"], s["subject"]): s for s in sugg}
    assert by_subject[("topic_type", "disaster")]["signal"] == "make_more"
    assert by_subject[("topic_type", "economy")]["signal"] == "make_less"


def test_analyze_offline_no_llm(cfg):
    sugg = feedback.analyze(_rows(), "ph", "2026-05-30", cfg, client=None)
    assert sugg                       # produced statistical suggestions
    assert all("rationale" in s for s in sugg)
    # no LLM -> no 'overall' narration row
    assert not any(s["scope"] == "overall" for s in sugg)
