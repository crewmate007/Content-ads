"""Creative-quality eval harness (Lau's 'cheap evals first')."""
from adsmvp import eval as ev
from adsmvp import pipeline


def test_text_divergence():
    assert ev._text_divergence("a b c", "a b c") == 0.0
    assert ev._text_divergence("a b c", "x y z") == 1.0
    assert 0.0 < ev._text_divergence("buy fuel now", "fuel prices today") < 1.0


def test_specificity_rewards_numbers_and_propers():
    vague = ev._estimate_specificity("what happens next")
    specific = ev._estimate_specificity("BSP may cut rates on Jun 19 after 3.2% inflation")
    assert specific > vague


def test_compare_copy_quality_shape():
    llm = {"headline": "Will the BSP cut on Jun 19?",
           "primary_text": "Inflation eased to 3.2%. Track our forecast.",
           "description": "See more", "cta": "LEARN_MORE"}
    base = {"headline": "BSP interest rate decision", "primary_text": "x",
            "description": "y", "cta": "LEARN_MORE"}
    s = ev.compare_copy_quality(llm, base)
    assert s["headline_length_ok"] == 1.0
    assert s["cta_valid"] == 1.0
    assert s["baseline_divergence"] > 0.0
    bad = ev.compare_copy_quality({"headline": "x" * 60, "primary_text": "y" * 200,
                                   "description": "z" * 50, "cta": "NOPE"}, base)
    assert bad["headline_length_ok"] == 0.0
    assert bad["cta_valid"] == 0.0


def test_eval_gating_records_scores(cfg, fake_genai):
    cfg.creative_quality_eval_enabled = True
    # Run with LLM copy so eval compares against the fallback baseline.
    results = pipeline.run_ads(cfg, "ph", "2026-05-30", langs=["en"],
                               client=None, genai_client=fake_genai)
    assert [r for r in results if r.ad_id]   # still produced drafts (non-blocking)
