# CMS watcher durable state

Mutable `watcher_state.json` is **not** used.

Release deduplication is stored as **GitHub issues** on this repository:

- Label: `cms-release-watcher`
- Marker in issue body: `<!-- cms-release-watcher:{source_id}:{fingerprint} -->`
- Open **and** closed issues count equally for dedup

`last_checked_at` appears only in Action/CLI runtime JSON output and is never committed.
