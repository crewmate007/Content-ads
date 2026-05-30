"""Channel-adapter interface + channel-agnostic data structures.

Every advertising platform implements `Channel`. The orchestrator only ever
talks to this interface, so adding Google/Twitter is a new module + a registry
entry, never an orchestration change.

v1 invariant: created objects are ALWAYS status=PAUSED. No method here launches
an ad or spends money; that boundary is enforced in each adapter.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

PAUSED = "PAUSED"

# Facebook-valid call-to-action button enum we allow in v1. Keep conservative.
VALID_CTAS = {"LEARN_MORE", "SEE_MORE", "SIGN_UP", "GET_OFFER", "SUBSCRIBE"}
DEFAULT_CTA = "LEARN_MORE"


@dataclass
class CreativeSpec:
    """Channel-agnostic creative produced by creative.py, consumed by a Channel."""
    topic_id: Optional[str]
    angle_id: Optional[str]
    region: str
    lang: str                       # "en" | "zh"
    primary_text: str
    headline: str
    description: str
    cta: str
    landing_url: str
    image_path: Optional[str] = None    # local path (set by creative.py)
    image_url: Optional[str] = None     # public URL (set after upload, if any)
    image_hash: Optional[str] = None    # channel handle after build_creative()
    policy_status: str = "pass"         # pass | revised | blocked
    policy_notes: Optional[str] = None
    copy_style: Optional[str] = None    # coarse label for the feedback loop
    model_copy: Optional[str] = None
    model_image: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DraftResult:
    """The PAUSED object graph a Channel created for one creative."""
    channel: str
    mode: str                       # "stub" | "live"
    status: str
    external_campaign_id: str
    external_adset_id: str
    external_creative_id: str
    external_ad_id: str
    budget_cap_cents: int
    permalink: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InsightRow:
    """One ad's metrics for one day."""
    external_ad_id: str
    date: str
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0.0
    spend: float = 0.0
    cpc: float = 0.0
    conversions: int = 0
    raw: Dict[str, Any] = field(default_factory=dict)


class Channel(ABC):
    name: str = "base"

    @abstractmethod
    def build_creative(self, spec: CreativeSpec) -> CreativeSpec:
        """Per-channel normalization + asset upload (e.g. FB AdImage -> image_hash)."""

    @abstractmethod
    def create_draft_campaign(
        self,
        spec: CreativeSpec,
        *,
        budget_cap_cents: int,
        campaign_name: str,
    ) -> DraftResult:
        """Create the PAUSED Campaign -> AdSet -> AdCreative -> Ad graph."""

    @abstractmethod
    def fetch_insights(self, ad_ids: List[str], date: str) -> List[InsightRow]:
        """Return per-ad metrics for `date`."""
