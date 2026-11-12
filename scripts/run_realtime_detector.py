"""
=====================================================================
 UX-Ghost ZeroBaran — Real-time Spike Detector
 Author : Baran Avisat  <Baranavisat@gmail.com>

 Used by:
   • GitHub Actions (cron = every 30 minutes)

 Goal:
   Detect short-window behavioural spikes (rage clicks, funnel drops)
   and push instant Telegram alerts — without waiting for the daily run.
=====================================================================
"""

from __future__ import annotations
import os, sys, logging
from pathlib import Path
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import httpx
from telegram_bot.bot import send_rage_alert, send_funnel_alert

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("uxghost.realtime")

# Empty secrets are a configuration state, not a defect: exit 0 (keep CI green)
# until SUPABASE_URL / SUPABASE_SERVICE_KEY are added to Actions secrets.
SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip()
SUPABASE_KEY = (os.getenv("SUPABASE_SERVICE_KEY") or "").strip()
HEADERS = {"apikey": SUPABASE_KEY,
           "Authorization": f"Bearer {SUPABASE_KEY}"}

# Thresholds (tunable via env)
RAGE_THRESHOLD     = int(os.getenv("UXG_RAGE_THRESHOLD", "5"))      # rage clicks in window
RAGE_VISITOR_MIN   = int(os.getenv("UXG_RAGE_VISITOR_MIN", "3"))    # at least N visitors
FUNNEL_DROP_ALERT  = float(os.getenv("UXG_FUNNEL_DROP_ALERT", "40"))  # pct
WINDOW_MINUTES     = int(os.getenv("UXG_WINDOW_MIN", "30"))


def sb_select(table: str, params: dict, limit: int = 1000) -> list:
    url = f"{SUPABASE_URL}/rest/v1/{table}?limit={limit}"
    for k, v in params.items():
        url += f"&{k}={v}"
    with httpx.Client(timeout=20) as c:
        r = c.get(url, headers=HEADERS)
        r.raise_for_status()
        return r.json()


def detect_rage_spikes():
    cutoff_ms = int((datetime.now(timezone.utc) -
                     timedelta(minutes=WINDOW_MINUTES)).timestamp() * 1000)
    rows = sb_select("uxg_events",
                     {"type": "eq.rage_click",
                      "ts": f"gte.{cutoff_ms}",
                      "select": "page_url,selector,visitor_id,count"},
                     limit=2000)
    log.info("Rage events in last %dm: %d", WINDOW_MINUTES, len(rows))
    if not rows: return
    from collections import defaultdict
    by_page = defaultdict(list)
    for r in rows:
        by_page[(r.get("page_url"), r.get("selector"))].append(r)
    for (page, sel), evs in by_page.items():
        visitors = len({e.get("visitor_id") for e in evs})
        total    = sum(e.get("count", 1) or 1 for e in evs)
        if total >= RAGE_THRESHOLD and visitors >= RAGE_VISITOR_MIN:
            try:
                send_rage_alert(page_url=page, selector=sel or "(unknown)",
                                count=total, visitors=visitors)
                log.info("🚨 Rage alert sent for %s :: %s", page, sel)
            except Exception as e:
                log.error("Failed rage alert: %s", e)


def detect_funnel_drops():
    cutoff_iso = (datetime.now(timezone.utc) -
                  timedelta(minutes=WINDOW_MINUTES)).isoformat()
    drops = sb_select("uxg_funnel_drops",
                      {"dropped_at": f"gte.{cutoff_iso}",
                       "select": "funnel_step,page_url,visitor_id,scroll_depth"})
    if not drops: return
    from collections import defaultdict
    by_step = defaultdict(set)
    by_step_page = defaultdict(list)
    for d in drops:
        by_step[d["funnel_step"]].add(d["visitor_id"])
        by_step_page[(d["funnel_step"], d["page_url"])].append(d)
    # crude drop pct: visitors who dropped / visitors in same period (need total — approximate from events)
    cutoff_ms = int((datetime.now(timezone.utc) -
                     timedelta(minutes=WINDOW_MINUTES)).timestamp() * 1000)
    total_visitors_q = sb_select("uxg_events",
        {"ts": f"gte.{cutoff_ms}", "select": "visitor_id"}, limit=5000)
    total_visitors = len({r.get("visitor_id") for r in total_visitors_q})
    for (step, page), evs in by_step_page.items():
        v = len({e["visitor_id"] for e in evs})
        pct = (v / total_visitors * 100) if total_visitors else 0
        if pct >= FUNNEL_DROP_ALERT:
            try:
                send_funnel_alert(funnel_step=step, drop_pct=round(pct,1),
                                  page_url=page)
                log.info("⚠️ Funnel alert sent for %s (%.1f%%)", step, pct)
            except Exception as e:
                log.error("Failed funnel alert: %s", e)


def main():
    log.info("=== UX-Ghost ZeroBaran — Realtime detector (%dm) ===", WINDOW_MINUTES)
    if not SUPABASE_URL or not SUPABASE_KEY:
        log.warning("Supabase not configured (SUPABASE_URL / SUPABASE_SERVICE_KEY) "
                    "- skipping cycle, exit 0")
        return
    try:
        detect_rage_spikes()
    except Exception as e:
        log.error("rage spike detection failed: %s", e)
    try:
        detect_funnel_drops()
    except Exception as e:
        log.error("funnel drop detection failed: %s", e)
    log.info("=== Done ===")


if __name__ == "__main__":
    main()
