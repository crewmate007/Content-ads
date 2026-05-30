"""Channel factory. Adding Google/Twitter = a new module + one line here."""
from __future__ import annotations

from typing import Callable, Dict

from .base import Channel


def _facebook(cfg) -> Channel:
    from .facebook import make_facebook_channel
    return make_facebook_channel(cfg)


# name -> builder. Future: "google": _google, "twitter": _twitter
_BUILDERS: Dict[str, Callable[[object], Channel]] = {
    "facebook": _facebook,
}


def get_channel(name: str, cfg) -> Channel:
    key = (name or "").lower()
    try:
        return _BUILDERS[key](cfg)
    except KeyError as exc:
        valid = ", ".join(sorted(_BUILDERS))
        raise ValueError(f"unknown channel '{name}'. Available: {valid}") from exc


def available_channels() -> list[str]:
    return sorted(_BUILDERS)
