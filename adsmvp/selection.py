"""Daily candidate selection.

Pure functions over plain dicts (the shapes db.py returns from Supabase) so the
ranking/de-dupe logic is unit-testable without a database. The orchestrator
wires db -> selection -> creative.

Pipeline: screen (guardrails) -> filter (bettable + TOP/CANDIDATE) -> de-dupe
(already-advertised topics) -> rank (reuse R/S/T/U/H + prob + disposition +
density, plus a bounded feedback bonus) -> top N.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set

from . import guardrails

ALLOWED_DISPOSITIONS = {"top", "candidate"}
FEEDBACK_CLAMP = 1.0  # bound the per-candidate feedback adjustment


def _norm_name(name: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


@dataclass
class Candidate:
    topic: Dict
    primary_angle: Optional[Dict]
    source_examples: List[Dict] = field(default_factory=list)
    rank: float = 0.0
    rank_parts: Dict[str, float] = field(default_factory=dict)

    @property
    def topic_id(self) -> Optional[str]:
        return self.topic.get("id")

    @property
    def topic_type(self) -> str:
        return (self.topic.get("topic_type") or "").lower()

    @property
    def angle_type(self) -> str:
        return (self.primary_angle or {}).get("angle_type", "serious_candidate")


def _pick_primary_angle(angles: Sequence[Dict]) -> Optional[Dict]:
    if not angles:
        return None
    serious = [a for a in angles if a.get("angle_type") == "serious_candidate"]
    pool = serious or list(angles)
    primary = [a for a in pool if a.get("is_primary")]
    return (primary or pool)[0]


def feedback_bonus(suggestions: Sequence[Dict], topic_type: str,
                   angle_type: str) -> float:
    """Convert recent content_suggestions into a bounded +/- ranking nudge.

    A 'make_more' suggestion for this topic_type/angle_type adds weight; a
    'make_less' subtracts. Clamped so one noisy day can't dominate.
    """
    score = 0.0
    for s in suggestions or []:
        subject = (s.get("subject") or "").lower()
        scope = (s.get("scope") or "").lower()
        if scope == "topic_type" and subject != topic_type:
            continue
        if scope == "angle_type" and subject != angle_type:
            continue
        if scope not in ("topic_type", "angle_type", "overall"):
            continue
        w = float(s.get("weight") or 0.0)
        signal = (s.get("signal") or "").lower()
        if signal == "make_more":
            score += w
        elif signal == "make_less":
            score -= w
    return max(-FEEDBACK_CLAMP, min(FEEDBACK_CLAMP, score))


def _rank(cand: Candidate, weights: Dict[str, float],
          suggestions: Sequence[Dict]) -> None:
    t = cand.topic
    rstuh = sum((t.get(k) or 0) for k in ("R", "S", "T", "U", "H")) / 25.0
    prob = t.get("prob")
    prob_centrality = (1.0 - abs((prob or 50) - 50) / 50.0) if prob is not None else 0.5
    disp = (t.get("disposition") or "").lower()
    disp_score = 1.0 if disp == "top" else 0.5 if disp == "candidate" else 0.0
    density = t.get("density") or 0
    density_norm = min(density / 10.0, 1.0)
    fb = feedback_bonus(suggestions, cand.topic_type, cand.angle_type)

    parts = {
        "rstuh": weights["rstuh"] * rstuh,
        "prob": weights["prob"] * prob_centrality,
        "disposition": weights["disposition"] * disp_score,
        "density": weights["density"] * density_norm,
        "feedback": weights["feedback"] * fb,
    }
    cand.rank_parts = parts
    cand.rank = round(sum(parts.values()), 6)


def select_candidates(
    topics: Sequence[Dict],
    angles_by_topic: Dict[str, List[Dict]],
    source_examples_by_topic: Dict[str, List[Dict]],
    *,
    weights: Dict[str, float],
    advertised_topic_ids: Optional[Set[str]] = None,
    advertised_names: Optional[Set[str]] = None,
    suggestions: Optional[Sequence[Dict]] = None,
    limit: int = 3,
) -> List[Candidate]:
    advertised_topic_ids = advertised_topic_ids or set()
    advertised_names = {_norm_name(n) for n in (advertised_names or set())}
    suggestions = suggestions or []

    out: List[Candidate] = []
    seen_names: Set[str] = set()
    for t in topics:
        if not t.get("bettable"):
            continue
        if (t.get("disposition") or "").lower() not in ALLOWED_DISPOSITIONS:
            continue
        if not guardrails.screen_topic(t).allowed:
            continue
        tid = t.get("id")
        if tid in advertised_topic_ids:
            continue
        nm = _norm_name(t.get("name"))
        if nm and (nm in advertised_names or nm in seen_names):
            continue
        if nm:
            seen_names.add(nm)

        angles = angles_by_topic.get(tid, [])
        cand = Candidate(
            topic=t,
            primary_angle=_pick_primary_angle(angles),
            source_examples=source_examples_by_topic.get(tid, [])[:2],
        )
        _rank(cand, weights, suggestions)
        out.append(cand)

    out.sort(key=lambda c: c.rank, reverse=True)
    return out[:limit]
