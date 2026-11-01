# 🔒 PRIVACY — UX-Ghost ZeroBaran

**Author**: Baran Avisat · Baranavisat@gmail.com

UX-Ghost ZeroBaran is **privacy-first by design**. This document is your
compliance reference for GDPR, CCPA, and similar regulations.

## 1. What data we collect

| Field            | Stored where        | PII? | Purpose |
|------------------|---------------------|------|---------|
| `visitor_id`     | `uxg_visitors`      | No   | Anonymous random ID (e.g. `v_a1b2c3`) generated locally in the browser. |
| `session_id`     | `uxg_sessions`     | No   | Anonymous per-session ID. |
| `page_url`       | `uxg_events`         | No (URL only) | The page the event happened on. |
| `type`           | `uxg_events`         | No   | Event type: click / scroll / rage_click / form_drop / exit / tab_hidden. |
| `x, y`           | `uxg_events`         | No   | Viewport coordinates of the click (relative to viewport, not screen). |
| `selector`       | `uxg_events`         | No   | CSS-like selector of the element (e.g. `button#cta`). |
| `depth`          | `uxg_events`         | No   | Scroll depth % (25, 50, 75, 95). |
| `field`          | `uxg_events`         | No   | Form field NAME/ID — never the field VALUE. |
| `user_agent`     | `uxg_visitors`      | Indirect | Stored only for device-type classification (mobile/tablet/desktop). Consider hashing. |
| `dwell_ms`       | `uxg_events`         | No   | Time spent on page (ms). |

**We never collect**: IP addresses (handled by Supabase edge network, not stored in our schema),
form values, e-mails, names, cookies, fingerprints, or any personal data.

## 2. GDPR mapping

| GDPR Article | How UX-Ghost complies |
|--------------|------------------------|
| Art. 6 (Lawful basis) | Legitimate interest (website optimization). No consent banner required for purely anonymous analytics under Recital 26. |
| Art. 7 (Consent)       | Optional: you may add a consent gate before loading the tracker. |
| Art. 12 (Transparency) | Add a privacy notice to your site mentioning "UX-Ghost ZeroBaran anonymous behaviour analytics". |
| Art. 15 (Access)        | Provide visitor with their `visitor_id` (visible in DevTools localStorage `uxg_vid`). |
| Art. 17 (Erasure)       | `delete from uxg_visitors where visitor_id = 'v_xxx';` cascades to all related rows. |
| Art. 20 (Portability)   | Export any visitor's data: `select * from uxg_events where visitor_id = 'v_xxx';` |
| Art. 25 (Data protection by design) | RLS restricts anon key to INSERT-only. No third-party SDKs. |
| Art. 28 (Processor)     | Supabase is the only processor; sign their DPA. |

## 3. Data retention recommendation

```sql
-- Auto-delete events older than 90 days (run as a scheduled SQL job):
delete from uxg_events
 where ingested_at < now() - interval '90 days';
```

Or via Supabase pg_cron:
```sql
select cron.schedule(
  'uxg_retention_purge', '0 3 * * *',
  $$delete from uxg_events where ingested_at < now() - interval '90 days'$$
);
```

## 4. No third-party data sharing

- The tracker script talks **only** to your Supabase project.
- The AI analysis runs on Google Gemini / Groq servers — they receive only
  **aggregated, anonymized** JSON (no visitor_id, no IP, no PII).
- No marketing, advertising, or analytics SDK is bundled.

## 5. Self-audit checklist

- [ ] Tracker script is hosted on your own domain.
- [ ] `anon` key has INSERT-only access (RLS verified).
- [ ] `service_role` key never leaves your server / GitHub Secrets.
- [ ] Public website does NOT leak `service_role`.
- [ ] `.env` is in `.gitignore`.
- [ ] Privacy page on your website mentions UX-Ghost ZeroBaran.
- [ ] Retention job scheduled.

## 6. Contact

For privacy inquiries:
- 📧 Baranavisat@gmail.com
- 📱 +90 531 326 3722 (WhatsApp)
