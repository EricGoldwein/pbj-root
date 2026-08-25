# Contact form spam protection (PBJ320)

Hardening for `POST /contact` (standalone `/contact`, homepage/provider popups, `/press`, `/report`).

This document covers Cloudflare Turnstile setup, environment variables, local/test behavior, aggregate rejection reasons, thresholds, rollback, and CSP.

## Create the Turnstile widget

1. Open [Cloudflare Turnstile](https://dash.cloudflare.com/?to=/:account/turnstile).
2. Create a widget:
   - **Widget mode:** Managed
   - **Appearance:** configure the widget for **interaction-only** (also set in markup as `data-appearance="interaction-only"`)
   - **Action:** `pbj_request` (must match server `TURNSTILE_ACTION`)
3. Allow hostnames:
   - `pbj320.com`
   - `www.pbj320.com`
   - Render preview / service host if used (e.g. `pbj.onrender.com` and any `*.onrender.com` preview hosts you rely on)
4. Copy the **site key** (public) and **secret key** (server-only).

## Required environment variables

| Variable | Where | Purpose |
|----------|--------|---------|
| `TURNSTILE_SITE_KEY` | Public (Render env / HTML injection) | Widget site key |
| `TURNSTILE_SECRET_KEY` | Server only | Siteverify secret |
| `TURNSTILE_EXPECTED_HOSTNAMES` | Optional | Comma-separated hostnames accepted from Siteverify (default: `pbj320.com,www.pbj320.com,pbj.onrender.com`) |
| `CONTACT_PROTECTION_DB_PATH` | Optional | SQLite path for rate limits, used tokens, quarantine, reason counters. Defaults to `contact_protection.db` beside `SUBSCRIBERS_DB_PATH`, else `instance/contact_protection.db` |
| `CONTACT_RATE_HASH_PEPPER` | Optional | Pepper for hashing IP/email rate-limit keys |
| `CONTACT_RATE_IP_15M` | Optional | Max attempts per IP / 15 min (default `3`) |
| `CONTACT_RATE_IP_24H` | Optional | Max attempts per IP / 24 h (default `10`) |
| `CONTACT_RATE_EMAIL_24H` | Optional | Max attempts per email / 24 h (default `3`) |
| `CONTACT_SPAM_SCORE_THRESHOLD` | Optional | High-confidence suppress threshold (default `5`) |
| `PBJ_CONTACT_SKIP_TURNSTILE` | Local/dev only | `1` skips Turnstile. **Ignored when `RENDER` / production env is set.** |

`render.yaml` declares the Turnstile / contact protection keys with `sync: false` so values are set in the Render Dashboard (not committed).

### Manual Render Dashboard steps (no automated production mutation)

1. Create the Turnstile widget (above).
2. In the **pbj** Render service → **Environment**:
   - Set `TURNSTILE_SITE_KEY` and `TURNSTILE_SECRET_KEY`.
   - Optionally set `TURNSTILE_EXPECTED_HOSTNAMES` to include preview hosts.
   - Prefer `CONTACT_PROTECTION_DB_PATH` on the **same persistent disk** as `SUBSCRIBERS_DB_PATH` (example: `/var/data/contact_protection.db`).
   - Optionally set `CONTACT_RATE_HASH_PEPPER` to a long random string.
3. Redeploy or restart so workers pick up env vars.
4. Smoke-test `/contact` as a human and confirm email arrives; confirm a blank Turnstile token does not send email.

## Local development and tests

- **Automated tests** use Cloudflare’s official always-pass test keys and a **mocked** Siteverify HTTP client. No live Cloudflare credentials are required.
- Local manual testing without Turnstile: set `PBJ_CONTACT_SKIP_TURNSTILE=1` (non-production only).
- With real keys locally: set `TURNSTILE_SITE_KEY` / `TURNSTILE_SECRET_KEY` and include `localhost` in Turnstile hostname allowlist + `TURNSTILE_EXPECTED_HOSTNAMES`.

Run tests:

```powershell
python -m pytest tests/test_contact_form_protection.py -q
```

## Request flow

### Before

Browser `POST /contact` → CSRF check → light field checks → SMTP email (plain text). Endpoint callable with a stolen CSRF token; Media checkbox only changed the subject line.

### After

1. CSRF  
2. Body size + content-type  
3. Normalize/validate fields (Media is metadata only; never a trust bypass)  
4. Honeypot → soft success, no email  
5. Turnstile Siteverify (hostname + action + one-time token); Cloudflare outage → fail closed with retry message  
6. Durable SQLite rate limits (hashed IP/email)  
7. Conservative spam score → quarantine + soft success when high confidence  
8. SMTP multipart plain + HTML (user HTML escaped)

## Aggregate rejection reasons

Logger name: `pbj.contact_protection`. Counters live in SQLite table `contact_reason_counts`.

Reason codes: `turnstile_failed`, `honeypot_filled`, `rate_limited`, `high_confidence_spam`, `validation_failed`, `accepted`.

Inspect:

```powershell
python -c "from contact_protection import aggregate_reason_counts, init_store; init_store(); print(aggregate_reason_counts())"
```

Do not expect full messages, raw Turnstile tokens, or secrets in logs.

## Adjust thresholds

- Rate limits: `CONTACT_RATE_IP_15M`, `CONTACT_RATE_IP_24H`, `CONTACT_RATE_EMAIL_24H`
- Spam suppress score: `CONTACT_SPAM_SCORE_THRESHOLD` (patterns in `contact_protection/spam.py`)

## Rollback

1. Remove or blank `TURNSTILE_SECRET_KEY` / `TURNSTILE_SITE_KEY` **only after** reverting code that fail-closes without them in production — or redeploy the previous git revision.
2. Preferred rollback: redeploy the prior release commit (forms + `contact_protection` package + `app.py` contact route).
3. Optional: leave DB files in place; they are unused if the old code path is restored.

## CSP

PBJ320 currently ships **without** a Content-Security-Policy on public pages. If you add CSP later, allow:

- `script-src` → `https://challenges.cloudflare.com`
- `frame-src` / `child-src` → `https://challenges.cloudflare.com`
- `connect-src` → `https://challenges.cloudflare.com`

## Durable store note

Rate limits and quarantine use SQLite. On Render they are durable only when the DB path is on a **persistent disk** (`CONTACT_PROTECTION_DB_PATH` or beside `SUBSCRIBERS_DB_PATH`). Without a disk, counters reset on deploy; Turnstile + honeypot + spam scoring still apply.

## Media / press checkbox

`press=yes` is informational only (email subject / Media: Yes). It must never skip Turnstile, rate limits, validation, or spam scoring.
