"""
=====================================================================
 UX-Ghost ZeroBaran — Streamlit Dashboard
 Author : Baran Avisat  <Baranavisat@gmail.com>

 Run:
   streamlit run dashboard/app.py

 Features:
   • Live heatmap (click density) per page
   • Rage-click leaderboard
   • Funnel drop analysis
   • AI reports (with recommendations) — read directly from Supabase
   • Daily/weekly KPI cards
=====================================================================
"""

from __future__ import annotations
import os, sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import urllib.parse

import httpx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# allow imports from sibling packages
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------
# Page config — RTL Arabic
# ---------------------------------------------------------------------
st.set_page_config(
    page_title="UX-Ghost ZeroBaran",
    page_icon="👻",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
      .main .block-container {max-width: 1400px; padding-top:1.5rem;}
      h1,h2,h3 {font-family: 'Segoe UI', Tahoma, sans-serif !important;}
      .reportview-container {direction: rtl;}
      section[data-testid="stSidebar"] {direction: rtl;}
      .sev-critical {color:#c0392b; font-weight:700;}
      .sev-warning  {color:#d68910; font-weight:700;}
      .sev-info     {color:#2874a6; font-weight:700;}
      footer {visibility:hidden;}
      .author-badge {
        background: linear-gradient(90deg,#1a1a2e,#16213e);
        color:#fff; padding:.4rem .8rem; border-radius:8px;
        font-size:.8rem; display:inline-block;
      }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------
# Env
# ---------------------------------------------------------------------
SUPABASE_URL  = os.getenv("SUPABASE_URL",  st.secrets.get("SUPABASE_URL",""))
SUPABASE_KEY  = os.getenv("SUPABASE_SERVICE_KEY",
                          st.secrets.get("SUPABASE_SERVICE_KEY",""))
HEADERS = {"apikey": SUPABASE_KEY,
           "Authorization": f"Bearer {SUPABASE_KEY}"}

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def sb_get(table: str, params: dict = None, limit: int = 5000) -> list:
    url = f"{SUPABASE_URL}/rest/v1/{table}?limit={limit}"
    for k, v in (params or {}).items():
        url += f"&{k}={v}"
    with httpx.Client(timeout=20) as c:
        r = c.get(url, headers=HEADERS)
        r.raise_for_status()
        return r.json()

def time_window_ms(hours: int) -> int:
    return int((datetime.now(timezone.utc) -
                timedelta(hours=hours)).timestamp() * 1000)

# ---------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 👻 UX-Ghost ZeroBaran")
    st.caption("المنظومة الذاتية للتحليل السلوكي")
    st.divider()
    window = st.select_slider("النطاق الزمني", options=[1, 6, 24, 72, 168],
                              value=24, format_func=lambda h: f"{h} ساعة")
    page_filter = st.text_input("تصفية حسب الصفحة (يحتوي)", "")
    auto_refresh = st.checkbox("تحديث تلقائي كل دقيقة", False)
    st.divider()
    st.markdown(
        '<span class="author-badge">👤 المؤلف: Baran Avisat</span>',
        unsafe_allow_html=True)
    st.caption("Baranavisat@gmail.com  •  +90 531 326 3722")

if auto_refresh:
    st.experimental_rerun() if hasattr(st, "experimental_rerun") else None
    try:
        st_autorefresh = __import__("streamlit_autorefresh",
                                    fromlist=["st_autorefresh"]).st_autorefresh
        st_autorefresh(interval=60_000, key="uxg_auto")
    except Exception:
        pass

# ---------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------
st.markdown("# 👻 UX-Ghost ZeroBaran")
st.markdown(f"### لوحة التحكم — آخر {window} ساعة")
st.caption("تحليل حراري وسلوكي تلقائي 100% مجاني • الحقوق محفوظة لـ Baran Avisat")
st.divider()

# ---------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------
cutoff = time_window_ms(window)
events_all = sb_get("uxg_events",
                    {"ts": f"gte.{cutoff}",
                     "select": "visitor_id,type,session_id,page_url"},
                    limit=20000)
df_events = pd.DataFrame(events_all)

col1, col2, col3, col4 = st.columns(4)
with col1:
    visitors = df_events["visitor_id"].nunique() if not df_events.empty else 0
    st.metric("الزوار الفريدون", f"{visitors:,}")
with col2:
    total_events = len(df_events)
    st.metric("إجمالي الأحداث", f"{total_events:,}")
with col3:
    rage = int((df_events["type"] == "rage_click").sum()) if not df_events.empty else 0
    st.metric("نقرات الغضب", f"{rage:,}")
with col4:
    if not df_events.empty:
        top_page = df_events["page_url"].value_counts().head(1)
        top_page_label = top_page.index[0] if not top_page.empty else "—"
    else:
        top_page_label = "—"
    st.metric("أكثر صفحة نشاطاً", top_page_label)

st.divider()

# ---------------------------------------------------------------------
# Page selector
# ---------------------------------------------------------------------
pages = sorted(df_events["page_url"].dropna().unique()) if not df_events.empty else []
if page_filter:
    pages = [p for p in pages if page_filter.lower() in p.lower()]
selected_page = st.selectbox("اختر الصفحة لعرض الخريطة الحرارية",
                             options=pages or ["—"])
st.divider()

# ---------------------------------------------------------------------
# Heatmap
# ---------------------------------------------------------------------
left, right = st.columns([2, 1])

with left:
    st.markdown("## 🌡️ الخريطة الحرارية للنقرات")
    if selected_page != "—" and not df_events.empty:
        page_rows = df_events[df_events["page_url"] == selected_page]
        clicks = page_rows[page_rows["type"] == "click"].to_dict("records")
        if clicks:
            grid = defaultdict(int)
            for c in clicks:
                pass  # x,y already aggregated by JS as percentages
            # Re-pull full events with x,y,w,h
            enc = urllib.parse.quote(selected_page, safe="")
            full = sb_get("uxg_events",
                          {"page_url": f"eq.{enc}",
                           "ts": f"gte.{cutoff}",
                           "select": "x,y,w,h,type"},
                          limit=10000)
            gx, gy, gv = [], [], []
            for r in full:
                if r.get("x") is None or not r.get("w"): continue
                gx.append(min(99, max(0, int(r["x"] * 100 / max(1, r["w"])))))
                gy.append(min(99, max(0, int(r["y"] * 100 / max(1, r["h"] or 1)))))
                gv.append(2 if r["type"] == "rage_click" else 1)
            if gx:
                fig = go.Figure(go.Histogram2d(
                    x=gx, y=100 - pd.Series(gy), z=gv, histfunc="sum",
                    colorscale="YlOrRd", nbinsx=40, nbinsy=25,
                    colorbar=dict(title="كثافة النقر")
                ))
                fig.update_layout(
                    xaxis_title="X % (عرض الصفحة)",
                    yaxis_title="Y % (ارتفاع الصفحة)",
                    height=440, margin=dict(l=10,r=10,t=10,b=10),
                    yaxis=dict(range=[0,100])
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("لا توجد إحداثيات نقرات كافية لرسم الخريطة الحرارية.")
        else:
            st.info("لا توجد نقرات على هذه الصفحة خلال النطاق الزمني المحدد.")
    else:
        st.info("اختر صفحة لعرض الخريطة الحرارية.")

with right:
    st.markdown("## 🔥 أكثر العناصر غضباً (Rage Clicks)")
    rage_rows = df_events[df_events["type"] == "rage_click"]
    if not rage_rows.empty:
        rage_top = (rage_rows.groupby(["page_url","selector"])
                            .size()
                            .reset_index(name="count")
                            .sort_values("count", ascending=False)
                            .head(10))
        rage_top["page_url"] = rage_top["page_url"].str.slice(0, 40)
        rage_top["selector"]  = rage_top["selector"].fillna("body").str.slice(0, 50)
        st.dataframe(rage_top, use_container_width=True, hide_index=True)
    else:
        st.success("لا توجد نقرات غضب في هذه الفترة. تصميم ممتاز! ✅")

st.divider()

# ---------------------------------------------------------------------
# Funnel
# ---------------------------------------------------------------------
st.markdown("## 🕳️ قمع التحويل (Funnel)")
drops = sb_get("uxg_funnel_drops",
               {"select": "funnel_step,visitor_id,page_url",
                "order": "funnel_step.asc"})
if drops:
    df_drops = pd.DataFrame(drops)
    funnel = (df_drops.groupby("funnel_step")
                      .agg(visitors=("visitor_id","nunique"))
                      .reset_index())
    if not funnel.empty:
        fig = go.Figure(go.Funnel(
            y=funnel["funnel_step"],
            x=funnel["visitors"],
            textinfo="value+percent initial+percent previous"
        ))
        fig.update_layout(height=380, margin=dict(l=10,r=10,t=10,b=10))
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("لا توجد بيانات قمع بعد — عرّف خطوات القمع في لوحة التتبع.")

st.divider()

# ---------------------------------------------------------------------
# AI Reports
# ---------------------------------------------------------------------
st.markdown("## 🤖 تقارير الذكاء الاصطناعي")
reports = sb_get("uxg_ai_reports",
                 {"select": "page_url,severity,summary,analysis,recommendations,generated_at,model",
                  "order": "generated_at.desc"}, limit=20)
if reports:
    sev_color = {"critical":"sev-critical", "warning":"sev-warning", "info":"sev-info"}
    for r in reports[:6]:
        cls = sev_color.get(r.get("severity","info"), "sev-info")
        st.markdown(f"#### <span class='{cls}'>● {r.get('severity','info').upper()}</span> "
                    f"• `{r.get('page_url','—')[:60]}`", unsafe_allow_html=True)
        st.caption(f"النموذج: {r.get('model','—')} • "
                   f"وقت التوليد: {r.get('generated_at','—')[:19]}")
        st.write(r.get("summary",""))
        if r.get("analysis"):
            with st.expander("تفاصيل التحليل"):
                st.json(r["analysis"])
        if r.get("recommendations"):
            with st.expander("التوصيات التصميمية"):
                for i, rec in enumerate(r["recommendations"], 1):
                    pr = rec.get("priority","medium")
                    emoji = {"high":"🔴","medium":"🟡","low":"🟢"}.get(pr,"⚪")
                    st.markdown(f"{emoji} **{i}. {rec.get('action','')}**")
                    st.caption(f"الأثر المتوقع: {rec.get('expected_impact','—')}")
        st.divider()
else:
    st.info("لا توجد تقارير ذكاء اصطناعي بعد. شغّل سكريبت التحليل اليومي من GitHub Actions.")

# ---------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------
st.markdown("---")
st.caption("UX-Ghost ZeroBaran v1.0.0 — © 2026 Baran Avisat. "
           "جميع الحقوق محفوظة.")
