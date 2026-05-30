"""Environment-driven configuration.

Mirrors phnews's load_gemini_api_key pattern (shell env first, then a repo-root
.env fallback) and its shape-only diagnostic logging (never prints secret
values). Every field is optional: with nothing set, the tool runs in stub mode
with fallback copy + placeholder images and no Supabase writes.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = REPO_ROOT / "artifacts"


def _read_dotenv() -> Dict[str, str]:
    """Parse repo-root .env into a dict. Missing file -> empty dict."""
    env_path = REPO_ROOT / ".env"
    out: Dict[str, str] = {}
    if not env_path.exists():
        return out
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        out[name.strip()] = value.strip().strip('"').strip("'")
    return out


_DOTENV = _read_dotenv()


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Shell env first, then repo .env, then default. Empty string -> default."""
    v = os.environ.get(name)
    if v is None or v == "":
        v = _DOTENV.get(name)
    if v is None or v == "":
        return default
    return v.strip()


def _env_int(name: str, default: int) -> int:
    v = _env(name)
    try:
        return int(v) if v is not None else default
    except ValueError:
        return default


# Default ranking weights for selection. Env-overridable (e.g. ADS_W_RSTUH).
DEFAULT_WEIGHTS: Dict[str, float] = {
    "rstuh": 1.0,        # (R+S+T+U+H)/25 normalized
    "prob": 0.4,         # centrality of prob around 50
    "disposition": 0.5,  # TOP=1 / CANDIDATE=0.5
    "density": 0.3,      # normalized story density
    "feedback": 0.6,     # bounded bonus from content_suggestions
}


@dataclass
class AdsConfig:
    gemini_api_key: Optional[str]
    gemini_model: str
    imagen_model: str
    supabase_url: Optional[str]
    supabase_key: Optional[str]
    facebook_mode: str          # "stub" | "live"
    fb_access_token: Optional[str]
    fb_ad_account_id: Optional[str]
    fb_page_id: Optional[str]
    fb_pixel_id: Optional[str]
    channels: List[str]
    landing_base_url: str
    daily_ad_budget_cap: int    # cents
    daily_ad_limit: int
    ads_dedupe_days: int
    variants_per_topic: int     # A/B creatives per (topic, lang): 1 = primary only
    image_store: str            # "local" | "supabase"
    artifacts_dir: Path = ARTIFACTS_DIR
    weights: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))

    @property
    def has_supabase(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)


def load_config() -> AdsConfig:
    weights = dict(DEFAULT_WEIGHTS)
    for key in weights:
        weights[key] = float(_env(f"ADS_W_{key.upper()}") or weights[key])

    mode = (_env("FACEBOOK_MODE", "stub") or "stub").lower()
    if mode not in ("stub", "live"):
        print(f"[WARN] FACEBOOK_MODE={mode!r} invalid; defaulting to 'stub'",
              file=sys.stderr)
        mode = "stub"

    channels = [c.strip() for c in (_env("CHANNELS", "facebook") or "facebook").split(",") if c.strip()]

    return AdsConfig(
        gemini_api_key=_env("GEMINI_API_KEY"),
        gemini_model=_env("GEMINI_MODEL", "gemini-3.5-flash"),
        imagen_model=_env("IMAGEN_MODEL", "imagen-4.0-generate-001"),
        supabase_url=_env("SUPABASE_URL"),
        supabase_key=_env("SUPABASE_SERVICE_KEY"),
        facebook_mode=mode,
        fb_access_token=_env("FB_ACCESS_TOKEN"),
        fb_ad_account_id=_env("FB_AD_ACCOUNT_ID"),
        fb_page_id=_env("FB_PAGE_ID"),
        fb_pixel_id=_env("FB_PIXEL_ID"),
        channels=channels,
        landing_base_url=_env("LANDING_BASE_URL", "https://phnews.example/ph"),
        daily_ad_budget_cap=_env_int("DAILY_AD_BUDGET_CAP", 2000),
        daily_ad_limit=_env_int("DAILY_AD_LIMIT", 3),
        ads_dedupe_days=_env_int("ADS_DEDUPE_DAYS", 14),
        variants_per_topic=max(1, _env_int("VARIANTS_PER_TOPIC", 1)),
        image_store=(_env("IMAGE_STORE", "local") or "local").lower(),
        weights=weights,
    )


def log_diagnostics(cfg: AdsConfig) -> None:
    """Shape-only diagnostics (lengths/prefixes), never secret values.
    Copied in spirit from phnews/mvp/db.py."""
    url = cfg.supabase_url or ""
    key = cfg.supabase_key or ""
    gk = cfg.gemini_api_key or ""
    print(
        f"[INFO] cfg: fb_mode={cfg.facebook_mode} channels={cfg.channels} "
        f"gemini={'yes' if gk else 'no'}(len={len(gk)}) "
        f"supabase_url_len={len(url)} supabase_key_len={len(key)} "
        f"budget_cap_cents={cfg.daily_ad_budget_cap} ad_limit={cfg.daily_ad_limit}",
        file=sys.stderr,
    )
