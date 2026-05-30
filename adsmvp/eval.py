"""Scrappy creative-quality evals (Austin Lau's 'cheap evals first' principle).

Compares LLM-generated copy against the deterministic fallback baseline on a few
cheap, deterministic heuristics — enough to flag generic/low-effort output
before scaling, without a heavyweight eval framework. Pure functions; no I/O.
"""
from __future__ import annotations

import re
from typing import Dict

from .channels.base import VALID_CTAS

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _tokens(text: str) -> set:
    return {w.lower() for w in _WORD_RE.findall(text or "")}


def _text_divergence(a: str, b: str) -> float:
    """1 - Jaccard(token sets). 1.0 = fully distinct, 0.0 = identical."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb) or 1
    return round(1.0 - inter / union, 4)


def _estimate_specificity(text: str) -> float:
    """Heuristic 0..1: presence of numbers/proper nouns and adequate length
    signal concrete, specific copy rather than vague filler."""
    s = (text or "").strip()
    if not s:
        return 0.0
    words = _WORD_RE.findall(s)
    if not words:
        return 0.0
    has_number = any(any(ch.isdigit() for ch in w) for w in words)
    proper = sum(1 for w in words if w[:1].isupper())
    proper_ratio = proper / len(words)
    length_ok = min(len(s) / 80.0, 1.0)
    score = 0.4 * (1.0 if has_number else 0.0) + 0.3 * min(proper_ratio * 2, 1.0) + 0.3 * length_ok
    return round(min(score, 1.0), 4)


def compare_copy_quality(llm_copy: Dict, baseline_copy: Dict) -> Dict[str, float]:
    """Score LLM copy vs the baseline. Booleans returned as 0.0/1.0 floats."""
    headline = llm_copy.get("headline", "") or ""
    primary = llm_copy.get("primary_text", "") or ""
    description = llm_copy.get("description", "") or ""
    return {
        "headline_length_ok": float(len(headline) <= 40),
        "primary_length_ok": float(len(primary) <= 125),
        "description_length_ok": float(len(description) <= 30),
        "cta_valid": float((llm_copy.get("cta") or "").upper() in VALID_CTAS),
        "baseline_divergence": _text_divergence(headline, baseline_copy.get("headline", "")),
        "specificity": _estimate_specificity(primary),
    }
