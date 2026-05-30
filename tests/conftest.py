"""Shared fixtures. Mirrors phnews/tests/conftest.py: install fake google.genai
so the LLM + Imagen paths run offline, force Facebook stub mode, and hand tests
a config pointed at a tmp artifacts dir.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for sub in (".", "scripts"):
    p = str((ROOT / sub).resolve())
    if p not in sys.path:
        sys.path.insert(0, p)

from adsmvp.config import DEFAULT_WEIGHTS, AdsConfig  # noqa: E402


def make_cfg(tmp_path, **overrides) -> AdsConfig:
    base = dict(
        gemini_api_key=None, gemini_model="gemini-test", imagen_model="imagen-test",
        supabase_url=None, supabase_key=None,
        facebook_mode="stub", fb_access_token=None, fb_ad_account_id=None,
        fb_page_id=None, fb_pixel_id=None, channels=["facebook"],
        landing_base_url="https://phnews.example/ph", daily_ad_budget_cap=2000,
        daily_ad_limit=3, ads_dedupe_days=14, variants_per_topic=1,
        image_store="local",
        artifacts_dir=Path(tmp_path), weights=dict(DEFAULT_WEIGHTS),
    )
    base.update(overrides)
    return AdsConfig(**base)


@pytest.fixture
def cfg(tmp_path):
    return make_cfg(tmp_path)


class _FakeResp:
    def __init__(self, text):
        self.text = text


class _FakeImage:
    image_bytes = b"\x89PNG\r\n\x1a\nFAKEIMAGEBYTES"


class _FakeGenImagesResp:
    generated_images = [types.SimpleNamespace(image=_FakeImage())]


class _FakeModels:
    def __init__(self, state):
        self.state = state

    def generate_content(self, model=None, contents=None):
        self.state.setdefault("copy_calls", []).append(contents)
        canned = self.state.get("copy", '{"primary_text":"Track the forecast",'
                                '"headline":"Will prices rise?","description":"See more",'
                                '"cta":"LEARN_MORE"}')
        return _FakeResp(canned)

    def generate_images(self, model=None, prompt=None, config=None):
        self.state.setdefault("image_calls", []).append(prompt)
        return _FakeGenImagesResp()


@pytest.fixture
def fake_genai(monkeypatch):
    """Install a fake google.genai; returns the fake client instance."""
    state = {"copy_calls": [], "image_calls": []}
    client = types.SimpleNamespace(models=_FakeModels(state))
    fake_types = types.SimpleNamespace(
        GenerateImagesConfig=lambda **kw: types.SimpleNamespace(**kw))
    fake_genai_mod = types.SimpleNamespace(
        Client=lambda api_key=None: client, types=fake_types)
    fake_google = types.ModuleType("google")
    fake_google.genai = fake_genai_mod
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai_mod)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types)
    client._state = state
    return client


# A 1x1 PNG, base64-encoded — what OpenAI images.generate returns (b64_json).
_PNG_B64 = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMA"
            "ASsJTYQAAAAASUVORK5CYII=")


class _FakeImages:
    def __init__(self, state):
        self.state = state

    def generate(self, model=None, prompt=None, n=1, size=None):
        self.state.setdefault("image_calls", []).append({"prompt": prompt, "size": size})
        datum = types.SimpleNamespace(b64_json=_PNG_B64, url=None)
        return types.SimpleNamespace(data=[datum])


@pytest.fixture
def fake_openai(monkeypatch):
    """Install a fake `openai.OpenAI`; returns the fake client instance."""
    state = {"image_calls": []}
    client = types.SimpleNamespace(images=_FakeImages(state))
    fake_openai_mod = types.ModuleType("openai")
    fake_openai_mod.OpenAI = lambda api_key=None: client
    monkeypatch.setitem(sys.modules, "openai", fake_openai_mod)
    client._state = state
    return client
