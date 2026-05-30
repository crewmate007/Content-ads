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
   selection ─▶ creative (Gemini copy + OpenAI gpt-image-2) ─▶ guardrails
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
python scripts/export_review.py                 # human-review HTML digest
python scripts/export_facebook_bulk.py          # Facebook bulk-import CSV

ls artifacts/drafts/            # PAUSED draft graphs (JSON)
ls artifacts/images/            # generated / placeholder PNGs
open artifacts/review/*.html    # review the drafts before launching
cat artifacts/csv/*_facebook_bulk.csv
python -m pytest                # 46 tests, fully offline
```

Adapted from Anthropic growth-marketer **Austin Lau**'s Claude playbook:

### Performance-data-informed copy (few-shot)
Copy is primed with the **top-performing past headlines** (by CTR, last
`FEW_SHOT_LOOKBACK_DAYS`) as in-prompt examples — closing the loop on *creative*,
not just selection. Toggle `FEW_SHOT_ENABLED`; needs Supabase history (no-ops
offline). See `db.fetch_winning_creatives` + `creative._format_few_shot_examples`.

### Multi-aspect-ratio images (Facebook placements)
`IMAGE_ASPECT_RATIOS=1:1,9:16,4:5` generates one image per ratio (OpenAI
`gpt-image-2`, mapped to the nearest supported size) and serves them per
placement via Facebook **`asset_feed_spec`**. `FB_PLACEMENTS=FEED,STORY,REELS`.

### A/B creative variants
`VARIANTS_PER_TOPIC=2`+ also builds creatives from a topic's reddit/tiktok
angles; each variant is a distinct ad whose angle style the feedback loop
compares and re-weights.

### Facebook bulk CSV + review digest
`export_review.py` renders a PAUSED-draft HTML for human approval;
`export_facebook_bulk.py` writes an Ads-Manager bulk-import CSV.

### Creative-quality eval
`CREATIVE_QUALITY_EVAL_ENABLED=true` scores LLM copy vs the fallback baseline
(length/CTA validity, divergence, specificity) and flags low-divergence copy for
review — non-blocking ("cheap evals first"). See `adsmvp/eval.py`.

### Image hosting
`IMAGE_STORE=local` (default) keeps PNGs as files. `IMAGE_STORE=supabase`
uploads all aspect ratios to the `ad-creatives` Storage bucket.

With no Gemini key → fallback template copy; no OpenAI key → placeholder PNGs;
no Supabase → bundled sample content (`adsmvp/sample_data.py`). Add the keys in
`.env` to use real LLM copy, real `gpt-image-2` images, and real phnews content.

## Configuration

See `.env.example`. Key vars: `GEMINI_API_KEY`/`GEMINI_MODEL` (copy),
`OPENAI_API_KEY`/`OPENAI_IMAGE_MODEL` (images), `IMAGE_ASPECT_RATIOS`,
`SUPABASE_URL`, `SUPABASE_SERVICE_KEY` (CI maps it from the secret
`SUPABASE_SERVICE_ROLE_KEY`), `FACEBOOK_MODE`, `FB_*`, `FB_PLACEMENTS`,
`LANDING_BASE_URL`, `DAILY_AD_BUDGET_CAP`, `DAILY_AD_LIMIT`, `ADS_DEDUPE_DAYS`,
`VARIANTS_PER_TOPIC`, `FEW_SHOT_*`, `CREATIVE_QUALITY_EVAL_ENABLED`.

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
