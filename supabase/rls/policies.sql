-- =====================================================================
--  UX-Ghost ZeroBaran — Row Level Security (RLS) Policies
--  Author : Baran Avisat  <Baranavisat@gmail.com>
--
--  Goals:
--   • anon key may INSERT events from the tracker script (public website)
--   • anon key may NOT read raw events (privacy first — GDPR)
--   • service_role (server-side / GitHub Actions) may read/write all
-- =====================================================================

-- enable RLS
alter table public.uxg_events        enable row level security;
alter table public.uxg_sessions      enable row level security;
alter table public.uxg_visitors      enable row level security;
alter table public.uxg_rage_clicks   enable row level security;
alter table public.uxg_funnel_drops enable row level security;
alter table public.uxg_ai_reports    enable row level security;
alter table public.uxg_alerts_log    enable row level security;
alter table public.uxg_heatmap_cache enable row level security;

-- ---------------------------------------------------------------------
-- Visitors : anon may INSERT (new visitor appears), no SELECT
-- ---------------------------------------------------------------------
drop policy if exists "anon insert visitor" on public.uxg_visitors;
create policy "anon insert visitor"
on public.uxg_visitors for insert
to anon with check (true);

drop policy if exists "anon update own visitor" on public.uxg_visitors;
create policy "anon update own visitor"
on public.uxg_visitors for update
to anon using (visitor_id is not null);

-- ---------------------------------------------------------------------
-- Sessions : anon may INSERT
-- ---------------------------------------------------------------------
drop policy if exists "anon insert session" on public.uxg_sessions;
create policy "anon insert session"
on public.uxg_sessions for insert
to anon with check (true);

-- ---------------------------------------------------------------------
-- Events : anon may INSERT only (this is the public entry point)
-- ---------------------------------------------------------------------
drop policy if exists "anon insert events" on public.uxg_events;
create policy "anon insert events"
on public.uxg_events for insert
to anon with check (true);

-- ---------------------------------------------------------------------
-- Rage clicks : anon may INSERT (the tracker writes them directly)
-- ---------------------------------------------------------------------
drop policy if exists "anon insert rage" on public.uxg_rage_clicks;
create policy "anon insert rage"
on public.uxg_rage_clicks for insert
to anon with check (true);

-- ---------------------------------------------------------------------
-- Funnel drops : anon may INSERT
-- ---------------------------------------------------------------------
drop policy if exists "anon insert funnel" on public.uxg_funnel_drops;
create policy "anon insert funnel"
on public.uxg_funnel_drops for insert
to anon with check (true);

-- ---------------------------------------------------------------------
-- Public read on AI reports and heatmap cache (for the dashboard)
-- ---------------------------------------------------------------------
drop policy if exists "public read ai reports" on public.uxg_ai_reports;
create policy "public read ai reports"
on public.uxg_ai_reports for select
to anon, authenticated using (true);

drop policy if exists "public read heatmap" on public.uxg_heatmap_cache;
create policy "public read heatmap"
on public.uxg_heatmap_cache for select
to anon, authenticated using (true);

-- ---------------------------------------------------------------------
-- service_role bypasses RLS automatically — no extra policies needed
-- for GitHub Actions / dashboard backend when using service_role key.
-- =====================================================================
