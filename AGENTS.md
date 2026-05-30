# AGENTS.md — Content-ads architecture

Notes for Claude Code / Codex collaborators. Sibling repo: **phnews** (the
content source). This repo turns that content into Facebook ad drafts and a
content-feedback loop.

## Principles (inherited from phnews)
- **Lazy-import heavy deps** (`google-genai`, `supabase`, `requests`) inside
  functions so the package imports and tests run with none of them installed.
- **Never raise across boundaries** for I/O: `db.py` and channel HTTP swallow +
  log to stderr and return safe defaults. A Supabase/FB outage must not crash a
  daily run.
- **No-op without credentials**: missing Gemini → fallback copy + placeholder
  images; missing Supabase → bundled `sample_data` + writes skipped; missing FB
  creds → stub.
- **v1 invariant — PAUSED only.** No code path launches or spends. `facebook.py`
  `_assert_paused()` hard-fails any non-PAUSED status; tests assert "ACTIVE"
  never appears in a draft graph.

## Module map (`adsmvp/`)
| File | Role |
|---|---|
| `config.py` | env/.env loading, `AdsConfig`, shape-only diagnostics |
| `llm.py` | genai client + `parse_json_response` + retry (copied from phnews) |
| `regions.py` | ph/id config incl. FB geo country code |
| `db.py` | Supabase read (content) + write (ad tables); no-op without creds |
| `sample_data.py` | offline content fixtures matching Supabase shape |
| `selection.py` | pure filter/de-dupe/rank → `Candidate`; `feedback_bonus` |
| `guardrails.py` | `screen_topic` (election/sensitive) + `enforce_creative` (gambling lexicon) |
| `images.py` | **single image backend boundary**: OpenAI `gpt-image-2` (aspect→size) or stdlib placeholder PNG; Supabase Storage upload |
| `creative.py` | topic+angle → `CreativeSpec` (Gemini copy + OpenAI image), bilingual, few-shot priming, multi-aspect-ratio |
| `feedback.py` | statistical aggregate → suggestions; LLM only narrates |
| `eval.py` | scrappy creative-quality eval (LLM copy vs baseline); pure functions |
| `review.py` | PAUSED-draft → human-review HTML (`render_html`) + Facebook bulk CSV (`export_csv`) |
| `pipeline.py` | orchestration glue (selection→creative→draft, A/B + multi-aspect, few-shot fetch, optional eval + Supabase upload) |
| `channels/base.py` | `Channel` ABC + `CreativeSpec`/`DraftResult`/`InsightRow` |
| `channels/facebook.py` | stub + live Marketing API graph (Campaign▸AdSet▸AdCreative▸Ad) |
| `channels/stub.py` | deterministic IDs, synthetic insights, artifact writer |
| `channels/registry.py` | `get_channel(name, cfg)` — add Google/Twitter here |

## Adding a channel
1. New `channels/<name>.py` implementing `Channel` (build_creative,
   create_draft_campaign → PAUSED, fetch_insights).
2. Register it in `channels/registry.py`.
3. Orchestration is unchanged (`pipeline.run_ads` is channel-agnostic).

## Data flow
`runs/topics/angles/source_examples` (phnews, read-only) → `selection` →
`creative` → `guardrails` → `FacebookChannel` → `ad_creatives` + `ad_campaigns`
(PAUSED) → `run_daily_insights` → `ad_insights` → `feedback` →
`content_suggestions` → `selection.feedback_bonus` re-weights tomorrow.

## Tests
`python -m pytest` — 46 offline tests. `tests/conftest.py` fakes `google.genai`
(copy), `openai` (`fake_openai`, images), and pins a tmp artifacts dir; Facebook
runs in stub mode.

## Done in Phase 2
- A/B creative variants from reddit/tiktok angles (`VARIANTS_PER_TOPIC`).
- Supabase Storage image hosting (`IMAGE_STORE=supabase`).
- `review.py` + `scripts/export_review.py` human-approval HTML digest.

## Done in Phase 3 (Austin Lau playbook, Facebook)
- Image backend switched to OpenAI `gpt-image-2` (`images.py`).
- Performance-data-informed copy: few-shot winning headlines
  (`db.fetch_winning_creatives` → `creative` prompt), `FEW_SHOT_*`.
- Multi-aspect-ratio images per FB placement via `asset_feed_spec`
  (`IMAGE_ASPECT_RATIOS`, `FB_PLACEMENTS`).
- Facebook bulk-import CSV (`review.export_csv` + `scripts/export_facebook_bulk.py`).
- Creative-quality eval harness (`adsmvp/eval.py`, `CREATIVE_QUALITY_EVAL_ENABLED`).

## Known follow-ups
- Live FB path needs App Review + `ads_management`/`ads_read` + page/business
  perms; gambling/prediction-market ads need FB written permission + geo
  eligibility. Position as "forecasting", not "betting".
- Persisted review_state workflow (approve → launch) once live creds exist.
