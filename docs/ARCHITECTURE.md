# 🏗️ ARCHITECTURE — UX-Ghost ZeroBaran

**Author**: Baran Avisat · Baranavisat@gmail.com

This document explains the technical architecture in depth.

## 1. Layered view

```
┌──────────────────────────────────────────────────────────────────┐
│  BROWSER (visitor)                                               │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  tracker/ux-ghost-tracker.js   (<2KB, vanilla JS)          │  │
│  │  captures: click, scroll, rage_click, form_drop, exit      │  │
│  └──────────────────────┬─────────────────────────────────────┘  │
└─────────────────────────┼────────────────────────────────────────┘
                          │  HTTPS POST (anon key)
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  SUPABASE (Postgres + PostgREST)                                 │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  uxg_events        (raw events)                             │  │
│  │  uxg_visitors      (anon visitors)                         │  │
│  │  uxg_sessions      (sessions)                               │  │
│  │  uxg_rage_clicks   (rage aggregated)                       │  │
│  │  uxg_funnel_drops  (funnel exits)                          │  │
│  │  uxg_heatmap_cache(pre-aggregated 100×100 grid)            │  │
│  │  uxg_ai_reports    (AI recommendations)                     │  │
│  │  uxg_alerts_log   (telegram audit)                         │  │
│  └──────────────────────┬─────────────────────────────────────┘  │
└─────────────────────────┼────────────────────────────────────────┘
                          │  service_role key (server only)
                          ▼
┌──────────────────────────────────────────────────────────────────┐
│  SERVER (GitHub Actions cron or local)                          │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  collectors/event_processor.py                              │  │
│  │   - aggregate_page() → PageAggregates                       │  │
│  │   - refresh_heatmap() → calls SQL RPC                       │  │
│  └──────────────────────┬─────────────────────────────────────┘  │
│  ┌──────────────────────▼─────────────────────────────────────┐  │
│  │  ai-core/ux_analyzer.py                                    │  │
│  │   - UXBrain.analyze(PageAggregates) → JSON report           │  │
│  │   - Provider: Gemini or Groq (free tier)                    │  │
│  └──────────────────────┬─────────────────────────────────────┘  │
│  ┌──────────────────────▼─────────────────────────────────────┐  │
│  │  telegram_bot/bot.py                                        │  │
│  │   - send_rage_alert(), send_funnel_alert(), daily_digest() │  │
│  └──────────────────────┬─────────────────────────────────────┘  │
└─────────────────────────┼────────────────────────────────────────┘
                          │  Telegram Bot API + HTTPS
                          ▼
              ┌────────────────────────┐
              │  Telegram (operator)   │
              │  dashboard (Streamlit) │
              └────────────────────────┘
```

## 2. Data flow timeline

| t      | Event                                                          |
|--------|----------------------------------------------------------------|
| 0.0s   | Visitor clicks element X. Tracker pushes event to Supabase.    |
| 0.5s   | RLS policy `anon insert events` accepts the row.                |
| ~30m   | GitHub Actions realtime-detector runs.                          |
|        | Detects spike → `send_rage_alert()` to Telegram + logs row.     |
| 09:00  | GitHub Actions daily-analysis runs.                              |
|        | For each active page → aggregate, refresh heatmap, AI analyze.  |
|        | Save report to `uxg_ai_reports`.                                 |
|        | Send daily digest to Telegram.                                   |
| any t  | Operator opens Streamlit dashboard → reads `uxg_ai_reports`.    |

## 3. Why this is GDPR-compliant by design

- **No PII collected**: tracker stores only an anonymous `visitor_id` (random string).
- **No third-party CDN**: tracker is self-hosted by the website owner.
- **RLS = data sovereignty**: anon key can only INSERT. Reads require service_role.
- **Right to erasure**: deleting a row from `uxg_visitors` cascades to all related tables.

## 4. Why this is genuinely free

| Resource          | Free quota                                | Limit reached? |
|-------------------|--------------------------------------------|----------------|
| Supabase Free     | 500 MB DB, 5 GB bandwidth                  | rarely for SMB |
| GitHub Actions    | 2,000 min/month for private repos (unlimited for public) | never |
| Gemini API        | 15 RPM, 1500/day, free tier                | rarely |
| Groq API          | 30 RPM, 14,400/day                         | rarely |
| Telegram Bot API  | unlimited free                             | never |
| Streamlit         | community edition free; deploy via Streamlit Cloud (1 app free) | never |
