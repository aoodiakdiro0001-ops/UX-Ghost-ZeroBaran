"""
=====================================================================
 UX-Ghost ZeroBaran — Daily Analysis Runner
 Author : Baran Avisat  <Baranavisat@gmail.com>

 Used by:
   • GitHub Actions (cron = daily 09:00 UTC)
   • Manual execution  (python scripts/run_daily_analysis.py)

 Pipeline:
   1) EventProcessor → list active pages from last 24h
   2) For each page → aggregate + refresh heatmap cache
   3) UXBrain       → analyze page → recommendations
   4) Persist AI report to Supabase
   5) Telegram      → push daily digest
=====================================================================
"""

from __future__ import annotations
import os, sys, logging, time
from pathlib import Path

# Bootstrap path so imports work from anywhere
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from collectors.event_processor import EventProcessor
from ai_core.ux_analyzer import UXBrain, analyze_and_save
from telegram_bot.bot import send_daily_digest

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
log = logging.getLogger("uxghost.daily")


def main():
    log.info("=== UX-Ghost ZeroBaran — Daily Analysis ===")

    # Missing Supabase credentials are a configuration state, not a defect:
    # report honestly and exit 0 until the secrets exist (keeps cron green).
    if not (os.getenv("SUPABASE_URL") or "").strip() or \
       not (os.getenv("SUPABASE_SERVICE_KEY") or "").strip():
        log.warning("Supabase not configured (SUPABASE_URL / SUPABASE_SERVICE_KEY) "
                    "- skipping cycle, exit 0")
        return

    proc = EventProcessor()
    brain = UXBrain()

    pages = proc.list_active_pages(hours=24)
    log.info("Found %d active page(s) in last 24h.", len(pages))

    all_stats = {"visitors": 0, "events": 0, "rage": 0, "avg_scroll": 0.0}
    reports_sent = []

    for page_url in pages:
        try:
            agg = proc.aggregate_page(page_url, hours=24)
            proc.refresh_heatmap(page_url)

            all_stats["visitors"] += agg.unique_visitors
            all_stats["events"]    += agg.total_events
            all_stats["rage"]     += agg.rage_click_count

            if agg.total_events < 5:
                log.info("Skip %s — too few events (%d)", page_url, agg.total_events)
                continue

            report = analyze_and_save(brain, agg,
                                      supabase_url=proc.url,
                                      supabase_service_key=proc.key,
                                      report_type="daily")
            reports_sent.append(report)
            log.info("✓ %s  severity=%s", page_url, report.get("severity"))

            # If page has critical rage clicks → instant alert
            if agg.rage_click_count >= 10:
                from telegram_bot.bot import send_rage_alert
                top = agg.rage_selectors[0] if agg.rage_selectors else {}
                send_rage_alert(
                    page_url=page_url,
                    selector=top.get("selector","(unknown)"),
                    count=agg.rage_click_count,
                    visitors=agg.unique_visitors
                )

            time.sleep(1.0)  # be polite to AI providers
        except Exception as e:
            log.exception("Failed to analyze %s: %s", page_url, e)

    # Daily digest to Telegram
    if all_stats["visitors"] > 0:
        try:
            send_daily_digest(all_stats, reports_sent[:5])
        except Exception as e:
            log.error("Failed to send daily digest: %s", e)

    log.info("=== Done. Reports saved: %d ===", len(reports_sent))


if __name__ == "__main__":
    main()
