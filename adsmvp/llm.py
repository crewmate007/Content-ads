"""Thin Gemini access layer.

Copied/adapted from phnews/mvp/angles/base.py + run_daily.py so Content-ads has
no cross-repo import. `get_client` lazy-imports google-genai (absent in some
environments) and returns None when no key is configured, letting callers fall
back to deterministic offline behaviour.
"""
from __future__ import annotations

import json
import re
import sys
import time
from typing import Dict, Optional

_TRAILING_COMMA_RE = re.compile(r",(\s*[}\]])")


def get_client(api_key: Optional[str]):
    """Return a google-genai Client, or None if no key / package unavailable."""
    if not api_key:
        return None
    try:
        from google import genai  # lazy: package may be absent
    except ImportError:
        print("[WARN] google-genai not installed; LLM disabled", file=sys.stderr)
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception as exc:  # noqa: BLE001
        print(f"[WARN] genai client init failed: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return None


def parse_json_response(text: str) -> Dict:
    """Parse LLM JSON output, tolerating code fences and trailing commas."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = text[3:]
        if text[:4].lower() == "json":
            text = text[4:]
        text = text.lstrip("\r\n")
        end = text.rfind("```")
        if end != -1:
            text = text[:end]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(_TRAILING_COMMA_RE.sub(r"\1", text))


def generate_content_with_retry(client, model: str, prompt: str, attempts: int = 4):
    """Retry transient Gemini overloads/disconnects without hiding real failures.

    Mirrors phnews's matcher: network disconnects surface as exception *types*,
    not HTTP codes, so we match both status codes and type/message markers.
    """
    last_exc = None
    for attempt in range(attempts):
        try:
            return client.models.generate_content(model=model, contents=prompt)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            message = str(exc).lower()
            status_code = getattr(exc, "status_code", None)
            exc_type = type(exc).__name__.lower()
            transient = status_code in (429, 500, 502, 503, 504) or any(
                m in message for m in (
                    "503", "429", "unavailable", "high demand", "timeout",
                    "disconnected", "connection reset", "connection aborted",
                    "remote protocol", "server disconnected", "read error",
                )
            ) or any(
                m in exc_type for m in (
                    "remoteprotocol", "connecterror", "readerror",
                    "connecttimeout", "readtimeout", "protocolerror",
                )
            )
            if not transient or attempt == attempts - 1:
                raise
            time.sleep(5 * (2 ** attempt))
    raise last_exc


def generate_json(client, model: str, prompt: str) -> Dict:
    """Convenience: generate + parse JSON. Raises on persistent failure."""
    resp = generate_content_with_retry(client, model, prompt)
    return parse_json_response(getattr(resp, "text", "") or "")
