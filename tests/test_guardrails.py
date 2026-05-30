from adsmvp import guardrails
from adsmvp.channels.base import CreativeSpec


def _spec(**kw):
    base = dict(topic_id="t", angle_id=None, region="ph", lang="en",
                primary_text="", headline="", description="", cta="LEARN_MORE",
                landing_url="https://x")
    base.update(kw)
    return CreativeSpec(**base)


def test_screen_topic_blocks_election():
    assert not guardrails.screen_topic({"topic_type": "election"}).allowed
    assert not guardrails.screen_topic(
        {"topic_type": "politics", "name": "Impeachment vote nears"}).allowed
    assert guardrails.screen_topic(
        {"topic_type": "economy", "name": "Fuel prices"}).allowed


def test_soften_marks_revised():
    spec = _spec(primary_text="Bet on the outcome and follow betting trends.")
    guardrails.enforce_creative(spec)
    assert spec.policy_status == "revised"
    assert "bet" not in spec.primary_text.lower()
    assert "forecast" in spec.primary_text.lower()


def test_hard_deny_blocks():
    spec = _spec(headline="Guaranteed win, easy money!")
    guardrails.enforce_creative(spec)
    assert spec.policy_status == "blocked"
    assert spec.policy_notes and "deny-lexicon" in spec.policy_notes


def test_clean_copy_passes():
    spec = _spec(primary_text="Follow the live forecast for fuel prices.")
    guardrails.enforce_creative(spec)
    assert spec.policy_status == "pass"


def test_chinese_gambling_blocked():
    spec = _spec(primary_text="包赢，快速致富！")
    guardrails.enforce_creative(spec)
    assert spec.policy_status == "blocked"
