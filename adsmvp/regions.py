"""Region config for ad targeting. Trimmed from phnews/mvp/regions.py and
extended with the Facebook geo-targeting country code."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RegionConfig:
    slug: str               # "ph" | "id"
    country_code: str       # ISO-2, used for FB targeting.geo_locations.countries
    country_name: str
    country_name_zh: str
    # Default ad language order for the region. We generate "en" + "zh" today;
    # locale_hint guides the LLM toward natural local phrasing (TL/ID in v2).
    locale_hint: str


REGIONS: dict[str, RegionConfig] = {
    "ph": RegionConfig(
        slug="ph",
        country_code="PH",
        country_name="the Philippines",
        country_name_zh="菲律宾",
        locale_hint="Filipino/Taglish-friendly English",
    ),
    "id": RegionConfig(
        slug="id",
        country_code="ID",
        country_name="Indonesia",
        country_name_zh="印尼",
        locale_hint="Bahasa-Indonesia-friendly English",
    ),
}


def get_region(slug: str | None) -> RegionConfig:
    key = (slug or "ph").lower()
    try:
        return REGIONS[key]
    except KeyError as exc:
        valid = ", ".join(sorted(REGIONS))
        raise ValueError(f"unknown region '{slug}'. Valid regions: {valid}") from exc
