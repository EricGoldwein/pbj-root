# Next site update — deferred push

**Do not push until Eric is intentionally updating the live site.**

## Pending (local only)

| Item | Detail |
|------|--------|
| Commits (local, not pushed) | `85a85cd` passport/archive · `f773a10` this deferral note |
| Why deferred | Docs/rules only (no route/behavior change), but a push to `master` may still trigger a Render redeploy |
| Safe to include next deploy | Yes — ship with the next real site update |

## When updating the site next

1. `git log origin/master..HEAD --oneline` — confirm `85a85cd` (and any newer ships) are in the batch.
2. Push only when ready to redeploy.
3. Optional smoke after deploy: `/health`, `/`, `/sff` (SFF still uses `pbj-wrapped/public/`).

## Not part of this deferral

- Sibling passport commits (PBJapp / 320website / Dog-of-the-day) do **not** affect pbj320.com; commit those locally anytime.
- Unrelated dirty tree in pbj-root (`app.py`, premium, `pbj-wrapped/dist` JSON, etc.) stays unstaged — do not bundle into a “docs only” push.
