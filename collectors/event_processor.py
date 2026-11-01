"""
=====================================================================
 UX-Ghost ZeroBaran — Event Processor (aggregation layer)
 Author : Baran Avisat  <Baranavisat@gmail.com>

 Reads raw events from Supabase, aggregates per-page metrics,
 refreshes the heatmap cache, and produces PageAggregates ready
 for the AI brain to consume.
=====================================================================
"""

from __future__ import annotations
import os, logging
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import httpx

from ai_core.ux_analyzer import PageAggregates   # re-export

log = logging.getLogger("uxghost.processor")


class EventProcessor:
    def __init__(self,
                 supabase_url: Optional[str] = None,
                 service_key: Optional[str] = None):
        self.url = supabase_url or os.environ["SUPABASE_URL"]
        self.key = service_key  or os.environ["SUPABASE_SERVICE_KEY"]
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json"
        }

    # ------------------------------------------------------------------
    # Low-level REST helper
    # ------------------------------------------------------------------
    def _select(self, table: str, params: dict, limit: int = 5000) -> list:
        url = f"{self.url}/rest/v1/{table}?limit={limit}"
        for k, v in params.items():
            url += f"&{k}={v}"
        with httpx.Client(timeout=30) as c:
            r = c.get(url, headers=self.headers)
            r.raise_for_status()
            return r.json()

    def _rpc(self, fn: str, params: dict) -> None:
        url = f"{self.url}/rest/v1/rpc/{fn}"
        with httpx.Client(timeout=30) as c:
            r = c.post(url, headers=self.headers, json=params)
            r.raise_for_status()

    # ------------------------------------------------------------------
    # Pull all distinct page_urls touched in the last `hours`
    # ------------------------------------------------------------------
    def list_active_pages(self, hours: int = 24) -> list:
        cutoff_ms = int((datetime.now(timezone.utc) -
                         timedelta(hours=hours)).timestamp() * 1000)
        rows = self._select(
            "uxg_events",
            {"select": "page_url", "ts": f"gte.{cutoff_ms}"},
            limit=5000
        )
        return sorted({r["page_url"] for r in rows if r.get("page_url")})

    # ------------------------------------------------------------------
    # Aggregate a single page
    # ------------------------------------------------------------------
    def aggregate_page(self, page_url: str, hours: int = 24) -> PageAggregates:
        cutoff_ms = int((datetime.now(timezone.utc) -
                         timedelta(hours=hours)).timestamp() * 1000)
        # encode URL for filter
        import urllib.parse
        enc = urllib.parse.quote(page_url, safe="")
        rows = self._select(
            "uxg_events",
            {"select": "*",
             "page_url": f"eq.{enc}",
             "ts":       f"gte.{cutoff_ms}"},
            limit=10000
        )
        if not rows:
            log.warning("No events for %s in last %dh", page_url, hours)

        total_events   = len(rows)
        unique_visitors = len({r.get("visitor_id") for r in rows
                                if r.get("visitor_id")})

        rage_rows = [r for r in rows if r.get("type") == "rage_click"]
        rage_count = len(rage_rows)
        rage_sel_counter = Counter(r.get("selector") or "?" for r in rage_rows)
        rage_selectors = [{"selector": s, "count": c}
                          for s, c in rage_sel_counter.most_common(10)]

        click_rows = [r for r in rows if r.get("type") == "click"]
        clk_counter = Counter(r.get("selector") or "?" for r in click_rows)
        top_click = [{"selector": s, "count": c}
                     for s, c in clk_counter.most_common(10)]

        # scroll depth average
        scroll_rows = [r for r in rows if r.get("type") == "scroll"
                       and r.get("depth") is not None]
        avg_scroll = (sum(r["depth"] for r in scroll_rows) / len(scroll_rows)
                      if scroll_rows else 0.0)

        exit_rows = [r for r in rows if r.get("type") == "exit"
                     and r.get("dwell_ms") is not None]
        avg_dwell = int(sum(r["dwell_ms"] for r in exit_rows) / len(exit_rows)
                        if exit_rows else 0)

        # funnel drop (lookup from uxg_funnel_drops)
        drops = self._select("uxg_funnel_drops",
                             {"page_url": f"eq.{enc}",
                              "order": "dropped_at.desc",
                              "limit": "1"})
        funnel_step = drops[0]["funnel_step"] if drops else None
        funnel_pct  = None
        if drops:
            # crude drop %: visitors who exited at this page vs total
            funnel_pct = round(
                len({d["visitor_id"] for d in drops}) /
                max(1, unique_visitors) * 100, 1)

        # hotspots (top 25 cells from raw clicks)
        from collections import defaultdict
        cells = defaultdict(lambda: {"clicks": 0, "rage": 0})
        for r in rows:
            if not r.get("x") or not r.get("w"): continue
            gx = min(99, max(0, int(r["x"] * 100 / max(1, r["w"]))))
            gy = min(99, max(0, int(r["y"] * 100 / max(1, r["h"] or 1))))
            key = (gx, gy)
            if r["type"] == "click":
                cells[key]["clicks"] += 1
            elif r["type"] == "rage_click":
                cells[key]["rage"]   += 1
        hotspots = sorted(
            [{"grid_x": gx, "grid_y": gy, **v} for (gx, gy), v in cells.items()],
            key=lambda d: d["clicks"] + d["rage"] * 5,
            reverse=True
        )[:25]

        return PageAggregates(
            page_url=page_url,
            total_events=total_events,
            unique_visitors=unique_visitors,
            rage_click_count=rage_count,
            rage_selectors=rage_selectors,
            top_click_selectors=top_click,
            funnel_drop_step=funnel_step,
            funnel_drop_pct=funnel_pct,
            avg_scroll_depth=avg_scroll,
            avg_dwell_ms=avg_dwell,
            hotspots=hotspots
        )

    # ------------------------------------------------------------------
    # Refresh heatmap cache via stored procedure
    # ------------------------------------------------------------------
    def refresh_heatmap(self, page_url: str) -> None:
        try:
            self._rpc("uxg_refresh_heatmap", {"p_url": page_url})
            log.info("Heatmap cache refreshed for %s", page_url)
        except Exception as e:
            log.error("Heatmap refresh failed for %s: %s", page_url, e)
