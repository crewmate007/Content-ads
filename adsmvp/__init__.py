"""Content-ads: turn phnews prediction-market topics into PAUSED Facebook ad
drafts, pull daily insights, and feed content-iteration suggestions back to the
content team.

Design mirrors phnews conventions: lazy imports of heavy deps (google-genai,
supabase, requests) so the package runs offline; never-raise / no-op-without-
credentials discipline; a channel-adapter abstraction so Google/Twitter slot in
later without touching orchestration.
"""

__all__ = ["__version__"]
__version__ = "0.1.0"
