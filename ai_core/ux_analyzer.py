"""
=====================================================================
 UX-Ghost ZeroBaran — AI UX Core
 Author : Baran Avisat  <Baranavisat@gmail.com>
 Mobile : +90 531 326 3722
 License: MIT (attribution required — see LICENSE)

 Role:
   • Read aggregated behavior data from Supabase
   • Send a structured prompt to Gemini (Google) or Groq (free tiers)
   • Detect UX problems  (rage clicks, funnel bottlenecks, dead clicks)
   • Produce actionable, design-level recommendations
   • Persist the report into uxg_ai_reports
=====================================================================
"""

from __future__ import annotations
import json, os, time, logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx

log = logging.getLogger("uxghost.ai")
logging.basicConfig(level=os.getenv("UXG_LOG_LEVEL", "INFO"),
                    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")


# ---------------------------------------------------------------------
# Data classes for behaviour aggregates
# ---------------------------------------------------------------------
@dataclass
class PageAggregates:
    page_url: str
    total_events: int
    unique_visitors: int
    rage_click_count: int
    rage_selectors: List[Dict[str, Any]]
    top_click_selectors: List[Dict[str, Any]]
    funnel_drop_step: Optional[str]
    funnel_drop_pct: Optional[float]
    avg_scroll_depth: float
    avg_dwell_ms: int
    hotspots: List[Dict[str, int]]   # [{grid_x, grid_y, clicks, rage}, ...]


# ---------------------------------------------------------------------
# AI UX Brain — provider-agnostic
# ---------------------------------------------------------------------
class UXBrain:
    """
    Wraps either Google Gemini (default) or Groq (fallback).
    Both have generous free tiers. Provider is chosen by env vars.
    """

    PROVIDERS = ("gemini", "groq")

    def __init__(self,
                 provider: Optional[str] = None,
                 gemini_key: Optional[str] = None,
                 groq_key: Optional[str] = None,
                 gemini_model: str = "gemini-1.5-flash",
                 groq_model: str = "llama-3.1-8b-instant"):
        self.provider = (provider or os.getenv("UXG_AI_PROVIDER") or "gemini").lower()
        if self.provider not in self.PROVIDERS:
            raise ValueError(f"Unknown AI provider: {self.provider}")
        self.gemini_key = gemini_key or os.getenv("GEMINI_API_KEY")
        self.groq_key   = groq_key   or os.getenv("GROQ_API_KEY")
        self.gemini_model = gemini_model
        self.groq_model   = groq_model

    # ---------- public entry ----------
    def analyze(self, agg: PageAggregates) -> Dict[str, Any]:
        """
        Returns:
          {
            "severity": "critical|warning|info",
            "summary": "...",
            "analysis": { ... },
            "recommendations": [ ... ],
            "model": "gemini-1.5-flash",
            "token_usage": 1234
          }
        """
        prompt = self._build_prompt(agg)
        if self.provider == "gemini":
            return self._call_gemini(prompt)
        return self._call_groq(prompt)

    # ---------- prompt engineering ----------
    def _build_prompt(self, agg: PageAggregates) -> str:
        return f"""You are a senior UX researcher and conversion-rate optimizer
named UX-Ghost ZeroBaran. You analyse anonymous behavioral telemetry
collected from a website. You MUST respond in Arabic (العربية الفصحى),
in STRICT JSON only — no prose, no markdown, no code fences.

Return this exact JSON schema:
{{
  "severity": "critical | warning | info",
  "summary": "ملخص موجز للمشكلة الرئيسية (سطر واحد)",
  "analysis": {{
    "primary_problem": "وصف السبب الجذري للمشكلة",
    "affected_visitors_pct": 0.0,
    "evidence": ["نقطة دليل 1", "نقطة دليل 2"]
  }},
  "recommendations": [
    {{
      "priority": "high|medium|low",
      "action": "إجراء محدد لاتخاذه",
      "expected_impact": "أثر متوقع على معدل التحويل"
    }}
  ]
}}

DATA (anonymized, last 24h):
- page_url: {agg.page_url}
- total_events: {agg.total_events}
- unique_visitors: {agg.unique_visitors}
- rage_clicks_total: {agg.rage_click_count}
- rage_click_targets: {json.dumps(agg.rage_selectors[:10], ensure_ascii=False)}
- top_click_targets:  {json.dumps(agg.top_click_selectors[:10], ensure_ascii=False)}
- funnel_drop_step: {agg.funnel_drop_step or "—"}
- funnel_drop_pct:  {agg.funnel_drop_pct}
- avg_scroll_depth: {agg.avg_scroll_depth:.1f}%
- avg_dwell_ms:     {agg.avg_dwell_ms}
- heatmap_hotspots: {json.dumps(agg.hotspots[:25], ensure_ascii=False)}

RULES:
1. Be specific — quote selectors and percentages from the data.
2. Recommend concrete design fixes (text, layout, color, hierarchy).
3. If a clickable-looking element produces rage clicks, flag it as critical.
4. If funnel drop > 40% at a step, flag as critical.
5. Average scroll < 35% means content is failing.
6. Output JSON ONLY.
"""

    # ---------- Gemini ----------
    def _call_gemini(self, prompt: str) -> Dict[str, Any]:
        if not self.gemini_key:
            raise RuntimeError("GEMINI_API_KEY is missing")
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self.gemini_model}:generateContent?key={self.gemini_key}")
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.4,
                "maxOutputTokens": 1500
            }
        }
        t0 = time.time()
        with httpx.Client(timeout=60) as c:
            r = c.post(url, json=body)
            r.raise_for_status()
            data = r.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        usage = data.get("usageMetadata", {}).get("totalTokenCount", 0)
        log.info("Gemini call ok in %.2fs, tokens=%s", time.time() - t0, usage)
        parsed = self._safe_json(text)
        parsed["model"] = self.gemini_model
        parsed["token_usage"] = usage
        return parsed

    # ---------- Groq ----------
    def _call_groq(self, prompt: str) -> Dict[str, Any]:
        if not self.groq_key:
            raise RuntimeError("GROQ_API_KEY is missing")
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.groq_key}"}
        body = {
            "model": self.groq_model,
            "messages": [
                {"role": "system",
                 "content": "You are UX-Ghost ZeroBaran. Reply ONLY with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.4,
            "max_tokens": 1500,
            "response_format": {"type": "json_object"}
        }
        t0 = time.time()
        with httpx.Client(timeout=60) as c:
            r = c.post(url, headers=headers, json=body)
            r.raise_for_status()
            data = r.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {}).get("total_tokens", 0)
        log.info("Groq call ok in %.2fs, tokens=%s", time.time() - t0, usage)
        parsed = self._safe_json(text)
        parsed["model"] = self.groq_model
        parsed["token_usage"] = usage
        return parsed

    @staticmethod
    def _safe_json(text: str) -> Dict[str, Any]:
        try:
            return json.loads(text)
        except Exception:
            # last-resort salvage
            s = text.strip()
            if s.startswith("```"):
                s = s.split("```")[1]
                if s.lower().startswith("json"):
                    s = s[4:]
            try:
                return json.loads(s)
            except Exception as e:
                log.error("AI returned non-JSON: %s", e)
                return {
                    "severity": "info",
                    "summary": "تعذّر تحليل استجابة الذكاء الاصطناعي",
                    "analysis": {"raw": text[:1000]},
                    "recommendations": []
                }


# ---------------------------------------------------------------------
# Convenience: analyze a single page and save the report
# ---------------------------------------------------------------------
def analyze_and_save(brain: UXBrain, agg: PageAggregates,
                     supabase_url: str, supabase_service_key: str,
                     report_type: str = "daily") -> Dict[str, Any]:
    result = brain.analyze(agg)
    row = {
        "report_type": report_type,
        "page_url": agg.page_url,
        "severity": result.get("severity", "info"),
        "summary": result.get("summary", ""),
        "analysis": result.get("analysis", {}),
        "recommendations": result.get("recommendations", []),
        "model": result.get("model", "unknown"),
        "token_usage": result.get("token_usage", 0),
        "generated_at": datetime.now(timezone.utc).isoformat()
    }
    with httpx.Client(timeout=30) as c:
        r = c.post(
            f"{supabase_url}/rest/v1/uxg_ai_reports",
            headers={
                "apikey": supabase_service_key,
                "Authorization": f"Bearer {supabase_service_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            },
            json=row
        )
        r.raise_for_status()
    log.info("Saved AI report for %s (severity=%s)", agg.page_url, row["severity"])
    return row


if __name__ == "__main__":
    # quick self-test
    brain = UXBrain()
    agg = PageAggregates(
        page_url="https://example.com/checkout",
        total_events=1240,
        unique_visitors=180,
        rage_click_count=42,
        rage_selectors=[{"selector": "div.fake-button", "count": 18}],
        top_click_selectors=[{"selector": "#cta-buy", "count": 220}],
        funnel_drop_step="payment",
        funnel_drop_pct=58.3,
        avg_scroll_depth=42.5,
        avg_dwell_ms=38000,
        hotspots=[{"grid_x": 50, "grid_y": 60, "clicks": 88, "rage": 12}]
    )
    print(json.dumps(brain.analyze(agg), ensure_ascii=False, indent=2))
