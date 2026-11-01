# 🚀 DEPLOYMENT — UX-Ghost ZeroBaran

**Author**: Baran Avisat · Baranavisat@gmail.com

This document walks through every deployment step end-to-end.

## A) Supabase

1. Create a free project at <https://supabase.com>.
2. Note three values from **Project Settings → API**:
   - `Project URL` → `SUPABASE_URL`
   - `anon public` key → used by the tracker (`UXGHOST_KEY` in HTML)
   - `service_role` key → `SUPABASE_SERVICE_KEY` (server only — keep secret!)
3. Open **SQL Editor → New Query**.
4. Paste `supabase/schema.sql` → **Run**.
5. Open a second query, paste `supabase/rls/policies.sql` → **Run**.

## B) Google Gemini (or Groq)

1. Go to <https://aistudio.google.com> → **Get API Key**.
2. Copy the key → `GEMINI_API_KEY` in `.env`.
3. (Alternative) Groq at <https://console.groq.com/keys> → `GROQ_API_KEY`.

To switch providers, set `UXG_AI_PROVIDER=groq` (or `gemini`).

## C) Telegram Bot

1. Open <https://t.me/BotFather> → `/newbot` → name it "UX-Ghost ZeroBaran".
2. Copy the bot token → `TELEGRAM_BOT_TOKEN`.
3. Create a private channel, add the bot as admin.
4. Get the channel id (forward a message to `@userinfobot`) → `TELEGRAM_CHAT_ID`.
5. (Optional) Test: `python telegram-bot/bot.py --mode send-test`.

## D) Tracker installation on your website

Copy `tracker/ux-ghost-tracker.js` to your site's static folder, then add the
following snippet **just before `</body>`** on every page you want to track:

```html
<script>
  window.UXGHOST_URL = "https://YOUR-PROJECT.supabase.co";
  window.UXGHOST_KEY = "YOUR-SUPABASE-ANON-KEY";
</script>
<script defer src="/js/ux-ghost-tracker.js?v=1.0.0"></script>
```

Verify by opening DevTools → Network → look for POST requests to
`/rest/v1/events` after clicking around your page.

## E) Streamlit Dashboard (local)

```bash
source .venv/bin/activate
streamlit run dashboard/app.py
```

## F) Streamlit Cloud (free hosting)

1. Push your repo to GitHub.
2. Visit <https://share.streamlit.io>.
3. Select the repo → main file: `dashboard/app.py`.
4. Add **Secrets** (Settings → Secrets):
   ```toml
   SUPABASE_URL = "https://..."
   SUPABASE_SERVICE_KEY = "eyJ..."
   ```
5. Click **Deploy** — free, public URL.

## G) GitHub Actions (scheduling)

1. Push repo to GitHub.
2. **Settings → Secrets and variables → Actions → New repository secret**:
   - `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
   - `GEMINI_API_KEY` (and/or `GROQ_API_KEY`)
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
3. (Variables) **New variable** (optional):
   - `UXG_AI_PROVIDER` = `gemini`
4. Both workflows are already defined in `.github/workflows/` — they will start
   running on schedule automatically once secrets are present.
5. To trigger manually: **Actions tab → "UX-Ghost Daily Analysis" → Run workflow**.

## H) Smoke test

```bash
# 1) Local analytics run (uses .env)
python scripts/run_daily_analysis.py

# 2) Local realtime detector (uses .env)
python scripts/run_realtime_detector.py

# 3) Open dashboard
streamlit run dashboard/app.py
```

If all three succeed and your Telegram receives messages — **you are live**.
