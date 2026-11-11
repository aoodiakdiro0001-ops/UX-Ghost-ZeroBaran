"""
=====================================================================
 UX-Ghost ZeroBaran — Telegram Alert Bot
 Author : Baran Avisat  <Baranavisat@gmail.com>

 Two modes:
   1) Long-polling bot — interactive commands (/status, /latest, /report)
   2) Send-only mode    — used by GitHub Actions to push alerts
=====================================================================
"""

from __future__ import annotations
import os, sys, json, logging, argparse
from datetime import datetime, timedelta, timezone
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

log = logging.getLogger("uxghost.bot")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

TG_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
HEADERS = {"apikey": SUPABASE_KEY,
           "Authorization": f"Bearer {SUPABASE_KEY}"}


# ---------------------------------------------------------------------
def send(text: str, parse_mode: str = "HTML",
         chat_id: str | None = None, disable_preview: bool = True) -> dict:
    """Send a message via Telegram Bot API."""
    if not TG_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")
    chat = chat_id or TG_CHAT_ID
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    body = {
        "chat_id": chat,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_preview
    }
    with httpx.Client(timeout=20) as c:
        r = c.post(url, json=body)
        r.raise_for_status()
        return r.json()


# ---------------------------------------------------------------------
def log_alert(alert_type: str, severity: str, message: str) -> None:
    """Persist alert in uxg_alerts_log table."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return
    try:
        with httpx.Client(timeout=10) as c:
            c.post(f"{SUPABASE_URL}/rest/v1/uxg_alerts_log",
                   headers={**HEADERS, "Prefer": "return=minimal"},
                   json={"alert_type": alert_type,
                         "severity": severity,
                         "message": message[:2000]})
    except Exception as e:
        log.error("Failed to log alert: %s", e)


# ---------------------------------------------------------------------
def send_rage_alert(page_url: str, selector: str, count: int,
                    visitors: int) -> None:
    text = (
        "🚨 <b>تنبيه سلوكي حرج — UX-Ghost ZeroBaran</b>\n\n"
        f"<b>الصفحة:</b> <code>{page_url}</code>\n"
        f"<b>العنصر:</b> <code>{selector}</code>\n"
        f"<b>عدد نقرات الغضب:</b> {count}\n"
        f"<b>عدد الزوار المتأثرين:</b> {visitors}\n\n"
        "👤 مؤلف النظام: Baran Avisat\n"
        "📧 Baranavisat@gmail.com"
    )
    send(text)
    log_alert("rage_spike", "critical",
              f"{page_url} :: {selector} :: {count} rage clicks")


# ---------------------------------------------------------------------
def send_funnel_alert(funnel_step: str, drop_pct: float,
                      page_url: str) -> None:
    text = (
        "⚠️ <b>تسرب في قمع التحويل — UX-Ghost ZeroBaran</b>\n\n"
        f"<b>المرحلة:</b> {funnel_step}\n"
        f"<b>الصفحة:</b> <code>{page_url}</code>\n"
        f"<b>نسبة التسرب:</b> {drop_pct}%\n\n"
        "<i>اقتراح: راجع التصميم في هذه المرحلة فوراً.</i>"
    )
    send(text)
    log_alert("funnel_drop", "warning",
              f"{funnel_step} :: {page_url} :: {drop_pct}%")


# ---------------------------------------------------------------------
def send_daily_digest(stats: dict, top_reports: list) -> None:
    text = (
        "📊 <b>التقرير اليومي — UX-Ghost ZeroBaran</b>\n\n"
        f"<b>التاريخ:</b> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC\n\n"
        f"<b>إجمالي الزوار:</b> {stats.get('visitors',0):,}\n"
        f"<b>إجمالي الأحداث:</b> {stats.get('events',0):,}\n"
        f"<b>نقرات الغضب:</b> {stats.get('rage',0):,}\n"
        f"<b>متوسط عمق التمرير:</b> {stats.get('avg_scroll',0):.1f}%\n\n"
    )
    if top_reports:
        text += "<b>أبرز التوصيات الذكية:</b>\n"
        for r in top_reports[:5]:
            text += (f"• <b>[{r.get('severity','?').upper()}]</b> "
                     f"{r.get('summary','—')}\n"
                     f"  <code>{r.get('page_url','—')[:80]}</code>\n")
    text += "\n— <i>Baran Avisat</i>"
    send(text)
    log_alert("daily_digest", "info", text[:2000])


# ---------------------------------------------------------------------
# Interactive bot (long-polling)
# ---------------------------------------------------------------------
def run_bot():
    """Run an interactive bot with commands: /status /latest /report."""
    if not TG_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN missing — cannot start bot")
    log.info("UX-Ghost Telegram bot is starting…")
    last_update_id = 0
    while True:
        try:
            url = (f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates"
                   f"?offset={last_update_id}&timeout=30")
            with httpx.Client(timeout=40) as c:
                r = c.get(url)
                r.raise_for_status()
                data = r.json()
            for upd in data.get("result", []):
                last_update_id = upd["update_id"] + 1
                msg = upd.get("message", {})
                text_in = msg.get("text","").strip()
                chat_id = msg["chat"]["id"]
                if not text_in: continue
                log.info("Incoming: %s from %s", text_in, chat_id)
                if text_in == "/start":
                    send("👻 <b>أهلاً بك في UX-Ghost ZeroBaran</b>\n\n"
                         "الأوامر المتاحة:\n"
                         "/status — حالة النظام\n"
                         "/latest — آخر تقرير ذكاء اصطناعي\n"
                         "/stats — إحصائيات آخر 24 ساعة\n"
                         "/author — معلومات المؤلف",
                         chat_id=str(chat_id))
                elif text_in == "/status":
                    send("✅ النظام يعمل.\n"
                         f"Supabase: {'مرتبط' if SUPABASE_URL else 'غير مرتبط'}\n"
                         f"التوقيت: {datetime.now(timezone.utc).isoformat()[:19]}",
                         chat_id=str(chat_id))
                elif text_in == "/author":
                    send("👤 <b>Baran Avisat</b>\n"
                         "📧 Baranavisat@gmail.com\n"
                         "📱 +90 531 326 3722\n\n"
                         "© 2026 — UX-Ghost ZeroBaran v1.0.0",
                         chat_id=str(chat_id))
                elif text_in == "/latest":
                    if not SUPABASE_URL:
                        send("⚠️ Supabase غير مهيأ.", chat_id=str(chat_id))
                    else:
                        with httpx.Client(timeout=15) as c:
                            r = c.get(
                                f"{SUPABASE_URL}/rest/v1/uxg_ai_reports"
                                "?order=generated_at.desc&limit=1",
                                headers=HEADERS)
                            r.raise_for_status()
                            rows = r.json()
                        if not rows:
                            send("لا توجد تقارير بعد.", chat_id=str(chat_id))
                        else:
                            r = rows[0]
                            send(
                                f"📋 <b>أحدث تقرير</b>\n"
                                f"<b>الصفحة:</b> <code>{r.get('page_url','')}</code>\n"
                                f"<b>الخطورة:</b> {r.get('severity','')}\n"
                                f"<b>الملخص:</b> {r.get('summary','')}\n"
                                f"<b>النموذج:</b> {r.get('model','')}",
                                chat_id=str(chat_id))
                elif text_in == "/stats":
                    send("للحصول على الإحصائيات الكاملة، راجع لوحة Streamlit.",
                         chat_id=str(chat_id))
                else:
                    send("غير معروف. جرّب: /status /latest /stats /author",
                         chat_id=str(chat_id))
        except KeyboardInterrupt:
            log.info("Bot stopped by user.")
            break
        except Exception as e:
            log.error("Bot loop error: %s — retrying in 5s", e)
            import time; time.sleep(5)


# ---------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UX-Ghost ZeroBaran Telegram bot")
    parser.add_argument("--mode", choices=["poll","send-test"],
                        default="poll",
                        help="poll = run long-polling bot; "
                             "send-test = send a single test message")
    args = parser.parse_args()
    if args.mode == "poll":
        run_bot()
    else:
        send("👻 <b>اختبار اتصال من UX-Ghost ZeroBaran</b>\n\n"
             "تم الاستلام بنجاح. النظام جاهز.\n\n— Baran Avisat")
        log.info("Test message sent.")
