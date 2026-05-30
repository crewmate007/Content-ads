-- Content-ads schema: ad creatives, drafts, daily insights, content suggestions.
-- Applied to the shared phnews Supabase project (spzvyicwdzebowlpxued).
-- All tables RLS-enabled with NO anon policy: only the service role (the daily
-- job) can read/write. FKs to phnews tables use ON DELETE SET NULL so deleting a
-- topic never erases ad history the feedback loop still needs.

-- ad_creatives: one row per generated creative variant (lang x channel).
create table if not exists public.ad_creatives (
  id uuid primary key default gen_random_uuid(),
  topic_id uuid references public.topics(id) on delete set null,
  angle_id uuid references public.angles(id) on delete set null,
  region text not null,
  lang text not null,                       -- en | zh
  channel text not null default 'facebook',
  primary_text text,
  headline text,
  description text,
  cta text,
  image_path text,
  image_url text,
  landing_url text,
  copy_style text,                          -- serious | reddit | tiktok (feedback dim)
  policy_status text default 'pass',        -- pass | revised | blocked
  policy_notes text,
  model_copy text,
  model_image text,
  created_at timestamptz default now()
);

-- ad_campaigns: one row per PAUSED draft pushed to a channel.
create table if not exists public.ad_campaigns (
  id uuid primary key default gen_random_uuid(),
  creative_id uuid references public.ad_creatives(id) on delete cascade,
  topic_id uuid references public.topics(id) on delete set null,
  region text not null,
  channel text not null default 'facebook',
  mode text not null,                       -- stub | live
  status text not null default 'PAUSED',
  external_campaign_id text,
  external_adset_id text,
  external_creative_id text,
  external_ad_id text,
  permalink text,
  budget_cap_cents integer,
  review_state text default 'pending_review', -- pending_review | approved | rejected | launched
  raw jsonb,
  run_date date not null,
  created_at timestamptz default now()
);
create index if not exists ad_campaigns_external_ad_id_idx on public.ad_campaigns (external_ad_id);
create index if not exists ad_campaigns_topic_created_idx on public.ad_campaigns (topic_id, created_at);

-- ad_insights: daily per-ad metrics, idempotent on (external_ad_id, insight_date).
create table if not exists public.ad_insights (
  id uuid primary key default gen_random_uuid(),
  campaign_id uuid references public.ad_campaigns(id) on delete cascade,
  external_ad_id text not null,
  insight_date date not null,
  impressions bigint default 0,
  clicks bigint default 0,
  ctr numeric default 0,
  spend numeric default 0,
  cpc numeric default 0,
  conversions bigint default 0,
  raw jsonb,
  created_at timestamptz default now(),
  unique (external_ad_id, insight_date)
);

-- content_suggestions: LLM/statistical feedback for the content team.
create table if not exists public.content_suggestions (
  id uuid primary key default gen_random_uuid(),
  region text not null,
  run_date date not null,
  scope text not null,                      -- topic_type | angle_type | copy_style | overall
  subject text,
  signal text,                              -- make_more | make_less | maintain
  weight numeric,
  rationale text,
  evidence jsonb,
  created_at timestamptz default now()
);
create index if not exists content_suggestions_region_date_idx on public.content_suggestions (region, run_date);

-- RLS: enable, with no policies => deny-all to anon/auth; service role bypasses.
alter table public.ad_creatives enable row level security;
alter table public.ad_campaigns enable row level security;
alter table public.ad_insights enable row level security;
alter table public.content_suggestions enable row level security;
