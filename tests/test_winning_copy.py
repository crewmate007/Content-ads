"""Performance-data-informed copy: few-shot winning headlines (Lau workflow)."""
from adsmvp import creative
from adsmvp.config import DEFAULT_WEIGHTS
from adsmvp.sample_data import sample_inputs
from adsmvp.selection import select_candidates
from tests.conftest import make_cfg


def _cand():
    topics, angles, se = sample_inputs("ph", "2026-05-30")
    return select_candidates(topics, angles, se, weights=DEFAULT_WEIGHTS, limit=1)[0]


def test_format_few_shot_examples():
    out = creative._format_few_shot_examples(
        [{"headline": "Will prices rise next week?", "ctr": 2.4}])
    assert "High-performing past headlines" in out
    assert "Will prices rise next week?" in out
    assert "2.40%" in out
    assert creative._format_few_shot_examples([]) == ""
    assert creative._format_few_shot_examples(None) == ""


def test_winning_examples_injected_into_prompt(tmp_path, fake_genai):
    cfg = make_cfg(tmp_path, few_shot_enabled=True)
    winning = [{"headline": "WINNING_HEADLINE_XYZ", "ctr": 3.1}]
    creative.generate_creative(_cand(), "ph", "en", cfg, client=fake_genai,
                               run_date="2026-05-30", winning_examples=winning)
    prompts = fake_genai._state["copy_calls"]
    assert prompts and "WINNING_HEADLINE_XYZ" in prompts[-1]


def test_few_shot_disabled_suppresses_examples(tmp_path, fake_genai):
    cfg = make_cfg(tmp_path, few_shot_enabled=False)
    winning = [{"headline": "WINNING_HEADLINE_XYZ", "ctr": 3.1}]
    creative.generate_creative(_cand(), "ph", "en", cfg, client=fake_genai,
                               run_date="2026-05-30", winning_examples=winning)
    assert "WINNING_HEADLINE_XYZ" not in fake_genai._state["copy_calls"][-1]


def test_fetch_winning_creatives_noop_without_client():
    from adsmvp import db
    assert db.fetch_winning_creatives(None, "ph") == []
