"""Ad-policy guardrails for a prediction-market product.

Two gates:
1. screen_topic(topic)   -> decide if a topic is eligible to advertise at all
   (filter election/political-issue content that triggers FB special_ad_categories,
   and sensitive criminal-naming topics).
2. enforce_creative(spec) -> scrub/grade ad copy against a gambling-solicitation
   lexicon. Blocked creatives are SKIPPED by callers (fail safe), never shipped.

This reduces — but cannot eliminate — Facebook ad-policy risk for real-money
betting. Live launch may still require FB written permission + licensing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional

# Explicit gambling solicitation / unrealistic-outcome promises (EN + ZH + TL/ID).
# Matching copy is auto-revised where possible, else blocked.
DENY_COPY = [
    r"\bbet now\b", r"\bplace your bet\b", r"\bguaranteed win\b", r"\bsure win\b",
    r"\beasy money\b", r"\bget rich\b", r"\bwin big\b", r"\bcash ?out\b",
    r"\bdeposit now\b", r"\bfree bet\b", r"\bodds\b", r"\bpayout\b", r"\bjackpot\b",
    # Chinese
    r"包赢", r"稳赢", r"必赢", r"轻松赚", r"快速致富", r"下注", r"赔率", r"投注",
    # Tagalog / Bahasa common gambling terms
    r"\bpusta\b", r"\btaya\b", r"\bjudi\b", r"\btaruhan\b", r"\bpasti menang\b",
]
_DENY_RE = [re.compile(p, re.IGNORECASE) for p in DENY_COPY]

# Soft replacements that keep copy compliant ("forecasting", not "betting").
SOFTEN = {
    re.compile(r"\bbet on\b", re.IGNORECASE): "forecast",
    re.compile(r"\bbetting\b", re.IGNORECASE): "forecasting",
    re.compile(r"\bbet\b", re.IGNORECASE): "predict",
}

# Topic types we never advertise in v1 (election/authorization + sensitive).
BLOCKED_TOPIC_TYPES = {"election", "elections", "political_campaign"}
SENSITIVE_MARKERS = [
    r"\belection\b", r"\bvote for\b", r"\bcandidate\b", r"\bimpeach",
    r"\bballot\b", r"选举", r"弹劾", r"\bpemilu\b", r"\bhalalan\b",
]
_SENS_RE = [re.compile(p, re.IGNORECASE) for p in SENSITIVE_MARKERS]


@dataclass
class TopicScreen:
    allowed: bool
    reason: Optional[str] = None


def screen_topic(topic: Dict) -> TopicScreen:
    """Gate a raw topic dict (from Supabase) for advertisability."""
    ttype = (topic.get("topic_type") or "").strip().lower()
    if ttype in BLOCKED_TOPIC_TYPES:
        return TopicScreen(False, f"blocked topic_type={ttype!r} (special ad category)")
    haystack = " ".join(str(topic.get(k) or "") for k in
                        ("name", "name_zh", "narrative", "suggested_question"))
    for rx in _SENS_RE:
        if rx.search(haystack):
            return TopicScreen(False, f"sensitive/election marker: {rx.pattern}")
    return TopicScreen(True)


def _scan(text: str) -> List[str]:
    return [rx.pattern for rx in _DENY_RE if rx.search(text or "")]


def _soften(text: str) -> str:
    out = text or ""
    for rx, repl in SOFTEN.items():
        out = rx.sub(repl, out)
    return out


def enforce_creative(spec) -> "object":
    """Grade + scrub a CreativeSpec in place. Sets policy_status to
    pass | revised | blocked and returns the same spec.

    - First soften known phrasings ("bet" -> "predict").
    - Then re-scan; if hard-deny terms remain, mark blocked (caller skips it).
    """
    fields = ("primary_text", "headline", "description")
    revised = False
    for f in fields:
        original = getattr(spec, f, "") or ""
        soft = _soften(original)
        if soft != original:
            setattr(spec, f, soft)
            revised = True

    remaining: List[str] = []
    for f in fields:
        remaining.extend(_scan(getattr(spec, f, "")))

    if remaining:
        spec.policy_status = "blocked"
        spec.policy_notes = "deny-lexicon: " + ", ".join(sorted(set(remaining)))
    elif revised:
        spec.policy_status = "revised"
        spec.policy_notes = "softened gambling phrasing"
    else:
        spec.policy_status = "pass"
    return spec
