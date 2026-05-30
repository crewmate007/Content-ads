# Content-ads

Turns **phnews** prediction-market topics into **PAUSED Facebook ad drafts**,
pulls daily ad insights, and produces **content-iteration suggestions** for the
content team — a closed optimization loop, built channel-extensible so Google /
Twitter slot in later.

> **Safety (v1):** nothing is ever launched or charged. Every Facebook object is
> created `PAUSED`; a human reviews and launches. `FACEBOOK_MODE=stub` by
> default, so the whole pipeline runs end-to-end with **no credentials**.

## How it works

```
phnews ──writes──▶ Supabase (topics/angles/source_examples)
                        │  read
                        ▼
   selection ─▶ creative (Gemini copy + Imagen image) ─▶ guardrails
                        │
                        ▼
   FacebookChannel ─▶ PAUSED Campaign▸AdSet▸AdCreative▸Ad  (stub or live)
                        │
   run_daily_insights ─▶ ad_insights ─▶ feedback ─▶ content_suggestions
                        └────────── re-weights tomorrow's selection ◀──────┘
```

The Facebook **stub** records the exact live-shaped request payload for every
object to `artifacts/drafts/<date>/<ad_id>.json`, so you can verify the live
calls are correct before any token exists. Flip `FACEBOOK_MODE=live` + secrets
to target the real Marketing API (still PAUSED, still zero spend).

## Quick start (offline, stub)

```bash
pip install -r requirements-dev.txt
cp .env.example .env            # all values optional; leave FB_* blank

python scripts/run_daily_ads.py --region ph --mode stub
python scripts/run_daily_insights.py --region ph

ls artifacts/drafts/            # PAUSED draft graphs (JSON)
ls artifacts/images/            # generated / placeholder PNGs
python -m pytest                # 26 tests, fully offline
```

With no Gemini key the tool uses deterministic fallback copy + placeholder
images. With no Supabase it falls back to bundled sample content
(`adsmvp/sample_data.py`). Add `GEMINI_API_KEY` and Supabase creds in `.env` to
use real LLM copy/images and real phnews content.

## Configuration

See `.env.example`. Key vars: `GEMINI_API_KEY`, `GEMINI_MODEL`, `IMAGEN_MODEL`,
`SUPABASE_URL`, `SUPABASE_SERVICE_KEY` (CI maps it from the secret
`SUPABASE_SERVICE_ROLE_KEY`), `FACEBOOK_MODE`, `FB_*`, `LANDING_BASE_URL`,
`DAILY_AD_BUDGET_CAP`, `DAILY_AD_LIMIT`, `ADS_DEDUPE_DAYS`.

## Database

`migrations/0001_ads_schema.sql` adds `ad_creatives`, `ad_campaigns`,
`ad_insights`, `content_suggestions` to the shared phnews Supabase project
(RLS-enabled, service-role only). Apply via the Supabase MCP `apply_migration`
or the SQL editor. Content-ads only **reads** phnews's tables.

## Going live (later)

Real-money / prediction-market ads on Facebook require prior FB permission,
licensing, and geo-eligibility, plus a Business-verified app with
`ads_management` + `ads_read` through App Review. The stub path lets all
engineering proceed in parallel meanwhile. See `AGENTS.md` for the architecture.
