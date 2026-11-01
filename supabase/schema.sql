-- =====================================================================
--  UX-Ghost ZeroBaran — Database Schema
--  Target : Supabase (PostgreSQL Free Tier)
--  Author : Baran Avisat  <Baranavisat@gmail.com>
--  License: MIT (attribution required)
--
--  Run this in: Supabase Dashboard → SQL Editor → New Query → Run
-- =====================================================================

-- ---------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------
create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------
-- 1) Visitors  (anonymous user profiles)
-- ---------------------------------------------------------------------
create table if not exists public.uxg_visitors (
  visitor_id      text primary key,
  user_agent      text,
  language        text,
  country         text,
  device_type     text,           -- mobile | tablet | desktop
  first_seen      timestamptz default now(),
  last_seen       timestamptz default now(),
  total_events    integer default 0,
  total_sessions  integer default 0
);

-- ---------------------------------------------------------------------
-- 2) Sessions
-- ---------------------------------------------------------------------
create table if not exists public.uxg_sessions (
  session_id   text primary key,
  visitor_id   text references public.uxg_visitors(visitor_id) on delete cascade,
  page_url     text,
  referer      text,
  started_at   timestamptz default now(),
  ended_at     timestamptz,
  event_count  integer default 0,
  scroll_max   integer default 0,
  dwell_ms     integer default 0
);

-- ---------------------------------------------------------------------
-- 3) Raw events  (clicks, scrolls, drops, exits, tab_hidden)
-- ---------------------------------------------------------------------
create table if not exists public.uxg_events (
  id            bigint generated always as identity primary key,
  session_id    text references public.uxg_sessions(session_id) on delete cascade,
  visitor_id    text references public.uxg_visitors(visitor_id) on delete set null,
  type          text not null,    -- click | scroll | form_drop | rage_click | exit | tab_hidden
  x             integer,
  y             integer,
  w             integer,          -- viewport width
  h             integer,          -- viewport height
  selector      text,
  field         text,             -- for form_drop
  depth         integer,          -- scroll depth %
  count         integer,          -- for rage_click
  page_url      text,
  ts            bigint not null,
  ingested_at   timestamptz default now()
);

create index if not exists idx_uxg_events_session on public.uxg_events(session_id);
create index if not exists idx_uxg_events_type_ts  on public.uxg_events(type, ts);
create index if not exists idx_uxg_events_page     on public.uxg_events(page_url);
create index if not exists idx_uxg_events_ts       on public.uxg_events(ts desc);

-- ---------------------------------------------------------------------
-- 4) Rage clicks aggregation
-- ---------------------------------------------------------------------
create table if not exists public.uxg_rage_clicks (
  id            bigint generated always as identity primary key,
  session_id    text,
  visitor_id    text,
  page_url      text,
  selector      text,
  x             integer,
  y             integer,
  count         integer,
  occurred_at   timestamptz default now(),
  ai_flagged    boolean default false
);
create index if not exists idx_uxg_rage_page on public.uxg_rage_clicks(page_url);
create index if not exists idx_uxg_rage_at   on public.uxg_rage_clicks(occurred_at desc);

-- ---------------------------------------------------------------------
-- 5) Funnel bottlenecks
-- ---------------------------------------------------------------------
create table if not exists public.uxg_funnel_drops (
  id            bigint generated always as identity primary key,
  visitor_id    text,
  session_id    text,
  funnel_step   text,            -- e.g. "product_view", "add_to_cart", "checkout", "payment"
  page_url      text,
  scroll_depth  integer,
  dwell_ms      integer,
  dropped_at    timestamptz default now()
);
create index if not exists idx_uxg_funnel_step on public.uxg_funnel_drops(funnel_step);

-- ---------------------------------------------------------------------
-- 6) AI reports
-- ---------------------------------------------------------------------
create table if not exists public.uxg_ai_reports (
  id              bigint generated always as identity primary key,
  report_type     text,          -- daily | realtime | on_demand
  page_url        text,
  severity        text,          -- critical | warning | info
  summary         text,
  analysis        jsonb,
  recommendations jsonb,
  generated_at    timestamptz default now(),
  model           text,
  token_usage     integer
);
create index if not exists idx_uxg_reports_url   on public.uxg_ai_reports(page_url);
create index if not exists idx_uxg_reports_sev    on public.uxg_ai_reports(severity);
create index if not exists idx_uxg_reports_gen    on public.uxg_ai_reports(generated_at desc);

-- ---------------------------------------------------------------------
-- 7) Alert log (Telegram)
-- ---------------------------------------------------------------------
create table if not exists public.uxg_alerts_log (
  id              bigint generated always as identity primary key,
  alert_type      text,          -- rage_spike | funnel_drop | daily_digest
  message         text,
  severity        text,
  telegram_msg_id bigint,
  sent_at         timestamptz default now(),
  status          text default 'sent'    -- sent | failed | queued
);
create index if not exists idx_uxg_alerts_sent on public.uxg_alerts_log(sent_at desc);

-- ---------------------------------------------------------------------
-- 8) Heatmap cache (pre-aggregated per page/url)
-- ---------------------------------------------------------------------
create table if not exists public.uxg_heatmap_cache (
  id          bigint generated always as identity primary key,
  page_url    text,
  grid_x      integer,    -- 0..99  (viewport cell column)
  grid_y      integer,    -- 0..99  (viewport cell row)
  clicks      integer,
  scrolls     integer,
  rage        integer,
  updated_at  timestamptz default now()
);
create index if not exists idx_uxg_heatmap_url on public.uxg_heatmap_cache(page_url);

-- ---------------------------------------------------------------------
-- Helper: bump visitor last_seen and event count on every insert
-- ---------------------------------------------------------------------
create or replace function public.uxg_touch_visitor()
returns trigger as $$
begin
  if new.visitor_id is not null then
    update public.uxg_visitors
       set last_seen = now(), total_events = total_events + 1
     where visitor_id = new.visitor_id;
  end if;
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_uxg_touch_visitor on public.uxg_events;
create trigger trg_uxg_touch_visitor
after insert on public.uxg_events
for each row execute function public.uxg_touch_visitor();

-- ---------------------------------------------------------------------
-- Aggregation helper: refresh heatmap cache for a page (callable)
-- ---------------------------------------------------------------------
create or replace function public.uxg_refresh_heatmap(p_url text)
returns void as $$
begin
  delete from public.uxg_heatmap_cache where page_url = p_url;
  insert into public.uxg_heatmap_cache (page_url, grid_x, grid_y, clicks, scrolls, rage)
  select
    p_url,
    least(99, greatest(0, (x * 100 / nullif(w, 0))::int))   as grid_x,
    least(99, greatest(0, (y * 100 / nullif(h, 0))::int))   as grid_y,
    count(*) filter (where type = 'click')                   as clicks,
    count(*) filter (where type = 'scroll')                  as scrolls,
    count(*) filter (where type = 'rage_click')              as rage
  from public.uxg_events
  where page_url = p_url
    and type in ('click','scroll','rage_click')
  group by 1, 2;
end;
$$ language plpgsql;
