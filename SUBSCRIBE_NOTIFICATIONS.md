# PBJ320 Email Subscribe: Notifications and Subscriber List

## Where do I set the env vars? (Here vs Render)

- **If the live site runs on Render:** Set the variables **on Render** (Environment tab for your web service). That’s what production uses. You do **not** set them in a file on your computer for production.
- **If you only run the app locally** (e.g. `python app.py` or Flask on your machine): Set them **here** in a `.env` file in the project root (copy from `.env.example` and fill in). The app loads `.env` when you run it locally.
- **If you have both:** Use **Render** for the live site (so signups on pbj320.com send notifications). Use **.env** only for local testing.

**Summary:** Production (Render) → set env in **Render dashboard**. Local only → set env in **`.env` in this repo**.

---

## How to configure notifications

Notifications are sent **only when** `SUBSCRIBE_NOTIFY_SMTP_HOST` (and auth, if needed) is set.  
**Who gets the email:** `SUBSCRIBE_NOTIFY_TO` (default: `egoldwein@gmail.com,eric@320insight.com`).

### Set here (local): `.env` file in project root

1. Copy the example: `cp .env.example .env` (or create `.env` and paste from `.env.example`).
2. Edit `.env` and set:
   - **SUBSCRIBE_NOTIFY_SMTP_HOST** = `smtp.gmail.com`
   - **SUBSCRIBE_NOTIFY_SMTP_USER** = your Gmail address
   - **SUBSCRIBE_NOTIFY_SMTP_PASSWORD** = Gmail [App Password](https://support.google.com/accounts/answer/185833) (not your normal password)
   - Optionally **SUBSCRIBE_NOTIFY_TO** = `egoldwein@gmail.com,eric@320insight.com` (this is already the default if unset)
3. Run the app locally; it will load `.env` if `python-dotenv` is installed.

### Set on Render (production)

1. Open [Render Dashboard](https://dashboard.render.com) → your **Web Service** for PBJ320.
2. Go to **Environment**.
3. Add these **Environment Variables** (key = name, value = your value):

| Key | Value (example) |
|-----|------------------|
| `SUBSCRIBE_NOTIFY_SMTP_HOST` | `smtp.gmail.com` |
| `SUBSCRIBE_NOTIFY_SMTP_PORT` | `587` |
| `SUBSCRIBE_NOTIFY_SMTP_USER` | Your Gmail address |
| `SUBSCRIBE_NOTIFY_SMTP_PASSWORD` | Your Gmail App Password (16 chars) |
| `SUBSCRIBE_NOTIFY_TO` | `egoldwein@gmail.com,eric@320insight.com` (optional; this is the default) |

4. Save. Redeploy the service if needed so the new env is picked up.

After that, both addresses in `SUBSCRIBE_NOTIFY_TO` will get a “PBJ320: New subscriber” email when someone signs up on the live site.

### Gmail notes

- Turn on **2-Step Verification** for the Google account.
- Create an **App Password**: Google Account → Security → 2-Step Verification → App passwords → generate one for “Mail” or “Other (PBJ320)”.
- Use that 16-character password in `SUBSCRIBE_NOTIFY_SMTP_PASSWORD`; do not use your normal Gmail password.

---

## Will I get notification emails?

**Yes, but only if SMTP is configured.** The app sends a short “New subscriber” email to you (and any other addresses you set) **only when** these environment variables are set:

- **`SUBSCRIBE_NOTIFY_SMTP_HOST`** (required) – e.g. `smtp.gmail.com`
- **`SUBSCRIBE_NOTIFY_SMTP_PORT`** (optional, default `587`)
- **`SUBSCRIBE_NOTIFY_SMTP_USER`** and **`SUBSCRIBE_NOTIFY_SMTP_PASSWORD`** (if your provider requires auth)
- **`SUBSCRIBE_NOTIFY_FROM`** (optional) – “From” address; defaults to the SMTP user or `noreply@pbj320.com`

**Who receives the notification:**  
The addresses in **`SUBSCRIBE_NOTIFY_TO`** (comma-separated). Default: `egoldwein@gmail.com,eric@320insight.com`. So with the default and SMTP set, both of those addresses get a short email each time someone subscribes.

**If you don’t set `SUBSCRIBE_NOTIFY_SMTP_HOST`:**  
Subscribers are still saved to the database, but **no notification email is sent**. You can still see signups by querying the subscriber list (below).

---

## Where is the subscriber list?

There is **no in-app UI** for the list. Subscribers are stored in a SQLite database:

**File:** `instance/subscribers.db`  
(relative to the app root; the `instance` folder is created automatically when the first subscriber is added)

**Table:** `subscribers`  
Columns: `id`, `email`, `source`, `created_at`.

---

## How do I see the email list?

From the project root (where `instance/` lives), use SQLite from the command line:

```bash
# List all subscribers (email, source, created_at)
sqlite3 instance/subscribers.db "SELECT email, source, created_at FROM subscribers ORDER BY created_at DESC;"

# Count
sqlite3 instance/subscribers.db "SELECT COUNT(*) FROM subscribers;"
```

On Windows (PowerShell), same idea:

```powershell
sqlite3 instance/subscribers.db "SELECT email, source, created_at FROM subscribers ORDER BY created_at DESC;"
```

You can also open `instance/subscribers.db` in any SQLite viewer (e.g. DB Browser for SQLite, or the SQLite extension in VS Code) and run the same queries.

**In-app JSON list (no SQLite needed):** Set env **`ADMIN_VIEW_KEY`** to a secret string (e.g. a long random password). Then visit:

**`https://yoursite.com/admin/subscribers?key=YOUR_SECRET`**

You get JSON with `email`, `source`, `created_at` for each subscriber. If the key is missing or wrong, the route returns 403.

**Contact form:** Submissions are only sent by email (to `SUBSCRIBE_NOTIFY_TO`). There is no in-app list of contact messages; check your email.

---

## Summary

| Question | Answer |
|----------|--------|
| Will I get emails to egoldwein@gmail.com and eric@320insight.com? | Yes, **if** `SUBSCRIBE_NOTIFY_SMTP_HOST` (and auth if needed) is set. `SUBSCRIBE_NOTIFY_TO` defaults to those two addresses. |
| Do I need another setting for notifications? | You need the SMTP env vars above. No other app setting is required. |
| Where do I see the subscriber list? | In the database only: `instance/subscribers.db` → table `subscribers`. Use `sqlite3` or a SQLite GUI; there is no in-app “view list” page. |
