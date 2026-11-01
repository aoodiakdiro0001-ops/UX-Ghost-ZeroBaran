/* =====================================================================
 *  UX-Ghost ZeroBaran — Lightweight Behavior Tracker v1.0.0
 *  Author : Baran Avisat  <Baranavisat@gmail.com>
 *  Mobile : +90 531 326 3722
 *  License: MIT (attribution required — see LICENSE)
 *
 *  Size : < 2 KB gzipped
 *  Role : Silently capture clicks, scroll depth, rage clicks and form
 *         drops, then ship them to Supabase in batches.
 * ===================================================================== */
(function () {
  "use strict";
  if (window.__UXGHOST__) return;
  window.__UXGHOST__ = true;

  var CFG = {
    supabaseUrl: window.UXGHOST_URL || "",
    supabaseKey: window.UXGHOST_KEY || "",
    endpoint: "/rest/v1/events",
    batch: 10,
    flushMs: 8000,
    sessionMs: 30 * 60 * 1000,
    rageThreshold: 3,
    rageWindowMs: 2000,
    debug: !!window.UXGHOST_DEBUG
  };

  var q = [], lastFlush = Date.now(), sid = getSessionId();
  var clkLog = {}, clkTim = {}, scrollMax = 0, visHidden = false;

  function getSessionId() {
    try {
      var k = "uxg_sid", v = sessionStorage.getItem(k), t = Date.now();
      if (v) { var p = v.split("|"); if (t - (+p[1]) < CFG.sessionMs) return p[0]; }
      var n = "s_" + Math.random().toString(36).slice(2) + t.toString(36);
      sessionStorage.setItem(k, n + "|" + t);
      return n;
    } catch (e) { return "s_" + Date.now(); }
  }

  function uid() {
    try { var k = "uxg_vid", v = localStorage.getItem(k);
      if (v) return v; var n = "v_" + Math.random().toString(36).slice(2);
      localStorage.setItem(k, n); return n; }
    catch (e) { return "v_" + Math.random().toString(36).slice(2); }
  }

  function sel(el) {
    if (!el || el.nodeType !== 1) return "";
    if (el.id) return "#" + el.id;
    var t = el.tagName.toLowerCase();
    if (el.className && typeof el.className === "string")
      t += "." + el.className.trim().split(/\s+/).slice(0, 2).join(".");
    var p = el.parentNode, idx = 1;
    if (p) for (var i = 0; i < p.children.length; i++)
      if (p.children[i] === el) { idx = i + 1; break; }
    return t + ":nth-child(" + idx + ")";
  }

  function push(e) {
    e.session_id = sid; e.visitor_id = uid();
    e.page_url = location.href; e.ts = Date.now();
    q.push(e);
    if (q.length >= CFG.batch || Date.now() - lastFlush > CFG.flushMs) flush();
  }

  function flush() {
    if (!q.length || !CFG.supabaseUrl || !CFG.supabaseKey) return;
    var body = JSON.stringify(q.slice(0, 50)), left = q.slice(50);
    q = left; lastFlush = Date.now();
    if (navigator.sendBeacon) {
      var blob = new Blob([body], { type: "application/json" });
      navigator.sendBeacon(
        CFG.supabaseUrl + CFG.endpoint,
        new Request(CFG.supabaseUrl + CFG.endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json",
                     apikey: CFG.supabaseKey,
                     Authorization: "Bearer " + CFG.supabaseKey,
                     Prefer: "return=minimal" },
          body: blob
        })
      );
    } else {
      var x = new XMLHttpRequest();
      x.open("POST", CFG.supabaseUrl + CFG.endpoint, true);
      x.setRequestHeader("Content-Type", "application/json");
      x.setRequestHeader("apikey", CFG.supabaseKey);
      x.setRequestHeader("Authorization", "Bearer " + CFG.supabaseKey);
      x.setRequestHeader("Prefer", "return=minimal");
      x.send(body);
    }
    if (CFG.debug) console.log("[UX-Ghost] flushed", body.length);
  }

  /* click + rage detection */
  document.addEventListener("click", function (ev) {
    var el = ev.target, s = sel(el), k = s || "body";
    var now = Date.now();
    clkLog[k] = (clkLog[k] || 0) + 1;
    if (!clkTim[k]) clkTim[k] = now;
    if (now - clkTim[k] > CFG.rageWindowMs) { clkLog[k] = 1; clkTim[k] = now; }
    var x = ev.clientX, y = ev.clientY;
    push({ type: "click", x: x, y: y, selector: s,
           w: window.innerWidth, h: window.innerHeight });
    if (clkLog[k] >= CFG.rageThreshold) {
      push({ type: "rage_click", selector: s, x: x, y: y, count: clkLog[k] });
      clkLog[k] = 0;
    }
  }, { passive: true });

  /* scroll depth */
  var sT;
  window.addEventListener("scroll", function () {
    if (sT) return;
    sT = setTimeout(function () {
      var doc = document.documentElement;
      var depth = (window.scrollY + window.innerHeight) /
                  Math.max(1, (doc.scrollHeight || 1));
      if (depth > scrollMax) { scrollMax = depth;
        if (depth >= 0.25 && depth < 0.27 ||
            depth >= 0.5 && depth < 0.52 ||
            depth >= 0.75 && depth < 0.77 ||
            depth >= 0.95 && depth < 0.97)
          push({ type: "scroll", depth: Math.round(depth * 100) }); }
      sT = null;
    }, 400);
  }, { passive: true });

  /* form drop detection */
  document.addEventListener("blur", function (ev) {
    var el = ev.target;
    if (el && el.tagName === "INPUT" || el && el.tagName === "TEXTAREA" ||
        el && el.tagName === "SELECT") {
      if (!el.value || !el.value.length) {
        push({ type: "form_drop", selector: sel(el),
               field: el.name || el.id || el.type || "unknown" });
      }
    }
  }, { passive: true, capture: true });

  /* page exit */
  window.addEventListener("beforeunload", function () {
    push({ type: "exit", scroll_depth: Math.round(scrollMax * 100),
           dwell_ms: Date.now() - (sid ? parseInt(sid.split("_").pop(),36)||Date.now() : Date.now()) });
    flush();
  });

  /* visibility (tab hide = soft drop) */
  document.addEventListener("visibilitychange", function () {
    if (document.hidden && !visHidden) {
      visHidden = true;
      push({ type: "tab_hidden", scroll_depth: Math.round(scrollMax * 100) });
    }
  });

  setInterval(flush, CFG.flushMs);
  if (CFG.debug) console.log("[UX-Ghost] tracker armed", CFG);
})();
