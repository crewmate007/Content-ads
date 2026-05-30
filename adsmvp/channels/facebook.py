"""Facebook Marketing API channel adapter.

`FACEBOOK_MODE=stub` (default) and `live` build the SAME Campaign -> AdSet ->
AdCreative -> Ad object graph, so the stub is a faithful dry-run of the live
request payloads. v1 never launches or spends: every object is created PAUSED,
and the live path hard-refuses any ACTIVE status.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any, Dict, List

from .base import (
    PAUSED,
    Channel,
    CreativeSpec,
    DraftResult,
    InsightRow,
)
from . import stub as stubmod

GRAPH_VERSION = "v21.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"


class FacebookPolicyError(RuntimeError):
    """Raised if code ever attempts a non-PAUSED / spend-affecting operation."""


def _assert_paused(status: str) -> None:
    if status != PAUSED:
        raise FacebookPolicyError(
            f"v1 refuses to create a Facebook object with status={status!r}; "
            "only PAUSED drafts are allowed."
        )


class FacebookChannel(Channel):
    name = "facebook"

    def __init__(self, cfg):
        self.cfg = cfg
        self.mode = cfg.facebook_mode
        if self.mode == "live" and not (cfg.fb_access_token and cfg.fb_ad_account_id
                                        and cfg.fb_page_id):
            print("[WARN] FACEBOOK_MODE=live but FB creds incomplete; "
                  "falling back to stub.", file=sys.stderr)
            self.mode = "stub"

    # ------------------------------------------------------------------ build
    def build_creative(self, spec: CreativeSpec) -> CreativeSpec:
        """Upload the image and attach an image_hash (FB AdImage edge)."""
        if not spec.image_path or not Path(spec.image_path).exists():
            # No image -> the creative will be link-only; allowed but flagged.
            spec.meta["image_missing"] = True
            return spec
        data = Path(spec.image_path).read_bytes()
        if self.mode == "stub":
            spec.image_hash = "stub_img_" + hashlib.sha256(data).hexdigest()[:16]
            return spec
        # live: POST /act_{acct}/adimages with raw bytes
        resp = self._post(
            f"/act_{self._acct()}/adimages",
            files={"filename": ("creative.png", data, "image/png")},
        )
        images = resp.get("images", {})
        first = next(iter(images.values()), {})
        spec.image_hash = first.get("hash")
        return spec

    # --------------------------------------------------------- create drafts
    def create_draft_campaign(self, spec: CreativeSpec, *, budget_cap_cents: int,
                              campaign_name: str) -> DraftResult:
        region_cc = _country_code(spec.region)
        campaign_payload = {
            "name": campaign_name,
            "objective": "OUTCOME_TRAFFIC",
            "status": PAUSED,
            "special_ad_categories": [],
        }
        _assert_paused(campaign_payload["status"])

        adset_payload = {
            "name": f"{campaign_name} / adset",
            "status": PAUSED,
            "daily_budget": int(budget_cap_cents),
            "billing_event": "IMPRESSIONS",
            "optimization_goal": "LINK_CLICKS",
            "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
            "targeting": {"geo_locations": {"countries": [region_cc]}},
        }
        _assert_paused(adset_payload["status"])

        link_data: Dict[str, Any] = {
            "message": spec.primary_text,
            "link": spec.landing_url,
            "name": spec.headline,
            "description": spec.description,
            "call_to_action": {
                "type": spec.cta,
                "value": {"link": spec.landing_url},
            },
        }
        if spec.image_hash:
            link_data["image_hash"] = spec.image_hash
        creative_payload = {
            "name": f"{campaign_name} / creative",
            "object_story_spec": {
                "page_id": self.cfg.fb_page_id or "PAGE_ID_PLACEHOLDER",
                "link_data": link_data,
            },
        }
        if self.cfg.fb_pixel_id:
            creative_payload["object_story_spec"]["link_data"].setdefault(
                "tracking_specs", {"action.type": "offsite_conversion",
                                   "fb_pixel": self.cfg.fb_pixel_id})

        ad_payload_status = PAUSED
        _assert_paused(ad_payload_status)

        if self.mode == "stub":
            return self._draft_stub(spec, campaign_name, budget_cap_cents,
                                    campaign_payload, adset_payload,
                                    creative_payload)
        return self._draft_live(spec, budget_cap_cents, campaign_payload,
                                adset_payload, creative_payload)

    def _draft_stub(self, spec, campaign_name, budget_cap_cents,
                    campaign_payload, adset_payload, creative_payload) -> DraftResult:
        seed = f"{spec.topic_id}|{spec.lang}|{spec.region}|{spec.meta.get('angle_key', 'primary')}"
        cid = stubmod.deterministic_id("campaign", seed)
        sid = stubmod.deterministic_id("adset", seed)
        crid = stubmod.deterministic_id("creative", seed)
        aid = stubmod.deterministic_id("ad", seed)
        adset_payload = {**adset_payload, "campaign_id": cid}
        ad_payload = {"name": f"{campaign_name} / ad", "status": PAUSED,
                      "adset_id": sid, "creative": {"creative_id": crid}}
        graph = {
            "channel": self.name,
            "mode": "stub",
            "region": spec.region,
            "lang": spec.lang,
            "topic_id": spec.topic_id,
            "angle_id": spec.angle_id,
            "policy_status": spec.policy_status,
            "copy_style": spec.copy_style,
            "image_path": spec.image_path,
            "image_url": spec.image_url,
            "endpoints": {
                "campaign": {"path": f"/act_{self._acct()}/campaigns",
                             "payload": campaign_payload, "returns": cid},
                "adset": {"path": f"/act_{self._acct()}/adsets",
                          "payload": adset_payload, "returns": sid},
                "adcreative": {"path": f"/act_{self._acct()}/adcreatives",
                               "payload": creative_payload, "returns": crid},
                "ad": {"path": f"/act_{self._acct()}/ads",
                       "payload": ad_payload, "returns": aid},
            },
        }
        stubmod.write_draft_artifact(self.cfg.artifacts_dir, _date_part(spec), aid, graph)
        return DraftResult(
            channel=self.name, mode="stub", status=PAUSED,
            external_campaign_id=cid, external_adset_id=sid,
            external_creative_id=crid, external_ad_id=aid,
            budget_cap_cents=budget_cap_cents, permalink=None, raw=graph,
        )

    def _draft_live(self, spec, budget_cap_cents, campaign_payload,
                    adset_payload, creative_payload) -> DraftResult:
        acct = self._acct()
        camp = self._post(f"/act_{acct}/campaigns", data=_flatten(campaign_payload))
        cid = camp["id"]
        adset_payload = {**adset_payload, "campaign_id": cid}
        adset = self._post(f"/act_{acct}/adsets", data=_flatten(adset_payload))
        sid = adset["id"]
        creative = self._post(f"/act_{acct}/adcreatives", data=_flatten(creative_payload))
        crid = creative["id"]
        ad_payload = {"name": creative_payload["name"].replace("creative", "ad"),
                      "status": PAUSED, "adset_id": sid,
                      "creative": {"creative_id": crid}}
        ad = self._post(f"/act_{acct}/ads", data=_flatten(ad_payload))
        aid = ad["id"]
        return DraftResult(
            channel=self.name, mode="live", status=PAUSED,
            external_campaign_id=cid, external_adset_id=sid,
            external_creative_id=crid, external_ad_id=aid,
            budget_cap_cents=budget_cap_cents,
            permalink=f"https://business.facebook.com/adsmanager/manage/ads?selected_ad_ids={aid}",
            raw={"campaign": camp, "adset": adset, "creative": creative, "ad": ad},
        )

    # -------------------------------------------------------------- insights
    def fetch_insights(self, ad_ids: List[str], date: str) -> List[InsightRow]:
        rows: List[InsightRow] = []
        if self.mode == "stub":
            for aid in ad_ids:
                m = stubmod.synthetic_insights(aid, date)
                rows.append(InsightRow(external_ad_id=aid, date=date, raw=m, **m))
            return rows
        for aid in ad_ids:
            try:
                resp = self._get(
                    f"/{aid}/insights",
                    params={"fields": "impressions,clicks,ctr,spend,cpc,actions",
                            "time_range": f'{{"since":"{date}","until":"{date}"}}',
                            "level": "ad"},
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[WARN] insights fetch failed for {aid}: {exc}", file=sys.stderr)
                continue
            data = (resp.get("data") or [{}])[0]
            rows.append(InsightRow(
                external_ad_id=aid, date=date,
                impressions=int(float(data.get("impressions", 0) or 0)),
                clicks=int(float(data.get("clicks", 0) or 0)),
                ctr=float(data.get("ctr", 0) or 0),
                spend=float(data.get("spend", 0) or 0),
                cpc=float(data.get("cpc", 0) or 0),
                conversions=_count_conversions(data.get("actions")),
                raw=data,
            ))
        return rows

    # ----------------------------------------------------------------- http
    def _acct(self) -> str:
        acct = (self.cfg.fb_ad_account_id or "ACT_PLACEHOLDER").replace("act_", "")
        return acct

    def _post(self, path: str, data=None, files=None) -> Dict[str, Any]:
        import requests  # lazy
        params = {"access_token": self.cfg.fb_access_token}
        resp = requests.post(GRAPH_BASE + path, params=params, data=data,
                             files=files, timeout=60)
        return _raise_or_json(resp)

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        import requests  # lazy
        params = {**params, "access_token": self.cfg.fb_access_token}
        resp = requests.get(GRAPH_BASE + path, params=params, timeout=60)
        return _raise_or_json(resp)


# --------------------------------------------------------------- module utils
def _raise_or_json(resp) -> Dict[str, Any]:
    try:
        body = resp.json()
    except Exception:  # noqa: BLE001
        resp.raise_for_status()
        raise
    if isinstance(body, dict) and body.get("error"):
        raise RuntimeError(f"Graph API error: {body['error']}")
    return body


def _flatten(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Graph API wants nested objects JSON-encoded as form fields."""
    import json
    out: Dict[str, Any] = {}
    for k, v in payload.items():
        out[k] = json.dumps(v) if isinstance(v, (dict, list)) else v
    return out


def _country_code(region: str) -> str:
    from ..regions import get_region
    return get_region(region).country_code


def _date_part(spec: CreativeSpec) -> str:
    return spec.meta.get("run_date") or "undated"


def _count_conversions(actions) -> int:
    if not actions:
        return 0
    total = 0
    for a in actions:
        try:
            total += int(float(a.get("value", 0)))
        except (TypeError, ValueError):
            continue
    return total


def make_facebook_channel(cfg) -> FacebookChannel:
    return FacebookChannel(cfg)
