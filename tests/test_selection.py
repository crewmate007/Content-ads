from adsmvp.config import DEFAULT_WEIGHTS
from adsmvp.sample_data import sample_inputs
from adsmvp.selection import feedback_bonus, select_candidates


def test_filters_and_dedupe():
    topics, angles, se = sample_inputs("ph", "2026-05-30")
    cands = select_candidates(topics, angles, se, weights=DEFAULT_WEIGHTS, limit=10)
    ids = {c.topic_id for c in cands}
    # bettable + TOP/CANDIDATE only; election + non-bettable excluded.
    assert "t-impeach-004" not in ids   # guardrails screen_topic
    assert "t-celeb-005" not in ids     # not bettable
    assert ids == {"t-fuel-001", "t-bsp-002", "t-typhoon-003"}


def test_dedupe_already_advertised():
    topics, angles, se = sample_inputs("ph", "2026-05-30")
    cands = select_candidates(topics, angles, se, weights=DEFAULT_WEIGHTS,
                              advertised_topic_ids={"t-fuel-001"}, limit=10)
    assert "t-fuel-001" not in {c.topic_id for c in cands}


def test_ranking_orders_top_above_candidate():
    topics, angles, se = sample_inputs("ph", "2026-05-30")
    cands = select_candidates(topics, angles, se, weights=DEFAULT_WEIGHTS, limit=10)
    ranks = {c.topic_id: c.rank for c in cands}
    # bsp is disposition=candidate with lower scores -> should rank last.
    assert ranks["t-bsp-002"] == min(ranks.values())
    # primary angle picked + is the serious candidate.
    fuel = next(c for c in cands if c.topic_id == "t-fuel-001")
    assert fuel.primary_angle["angle_type"] == "serious_candidate"


def test_feedback_bonus_reweights():
    make_more = [{"scope": "topic_type", "subject": "disaster",
                  "signal": "make_more", "weight": 0.5}]
    assert feedback_bonus(make_more, "disaster", "serious") == 0.5
    assert feedback_bonus(make_more, "economy", "serious") == 0.0
    # clamp
    big = [{"scope": "overall", "subject": "x", "signal": "make_more", "weight": 5}]
    assert feedback_bonus(big, "economy", "serious") == 1.0


def test_feedback_changes_selection_order():
    topics, angles, se = sample_inputs("ph", "2026-05-30")
    base = select_candidates(topics, angles, se, weights=DEFAULT_WEIGHTS, limit=10)
    boosted = select_candidates(
        topics, angles, se, weights=DEFAULT_WEIGHTS,
        suggestions=[{"scope": "topic_type", "subject": "economy",
                      "signal": "make_more", "weight": 1.0}], limit=10)
    base_rank = {c.topic_id: c.rank for c in base}
    boosted_rank = {c.topic_id: c.rank for c in boosted}
    assert boosted_rank["t-fuel-001"] > base_rank["t-fuel-001"]
