from pathlib import Path

from adsmvp import creative
from adsmvp.channels.base import VALID_CTAS
from adsmvp.sample_data import sample_inputs
from adsmvp.selection import select_candidates
from adsmvp.config import DEFAULT_WEIGHTS


def _first_candidate():
    topics, angles, se = sample_inputs("ph", "2026-05-30")
    return select_candidates(topics, angles, se, weights=DEFAULT_WEIGHTS, limit=1)[0]


def test_fallback_copy_offline(cfg):
    cand = _first_candidate()
    spec = creative.generate_creative(cand, "ph", "en", cfg, client=None,
                                      run_date="2026-05-30")
    assert spec.cta in VALID_CTAS
    assert spec.primary_text and len(spec.primary_text) <= 125
    assert spec.headline and len(spec.headline) <= 40
    assert Path(spec.image_path).exists()           # placeholder PNG written
    assert spec.model_copy == "fallback-template"


def test_zh_variant(cfg):
    cand = _first_candidate()
    spec = creative.generate_creative(cand, "ph", "zh", cfg, client=None,
                                      run_date="2026-05-30")
    assert spec.lang == "zh"
    assert any("一" <= ch <= "鿿" for ch in spec.primary_text)  # has CJK


def test_llm_copy_path(cfg, fake_genai):
    cand = _first_candidate()
    spec = creative.generate_creative(cand, "ph", "en", cfg, client=fake_genai,
                                      run_date="2026-05-30")
    assert spec.headline == "Will prices rise?"     # from canned fake response
    assert spec.cta in VALID_CTAS
    assert fake_genai._state["copy_calls"]          # LLM was called
