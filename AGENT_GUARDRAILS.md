# AGENT_GUARDRAILS.md — pbj-root release intent (operational)

**Core rule:** Existing local changes are **not** authorization to commit, push, merge, or deploy them.

A Cursor session may edit files locally when asked, but must **not** include unrelated WIP in a commit/PR/deploy simply because those files are modified.

---

## Three explicit states

| State | Meaning |
|-------|---------|
| **Production baseline** | `origin/master` — what is live / what a hotfix diff targets |
| **Release candidate** | Files **explicitly staged** for the current task's commit/PR |
| **Local WIP** | Valid unfinished work — may stay modified/untracked; must **not** ship accidentally |

A dirty tree is normal. The dangerous condition is **ambiguity about what is intended to ship**.

---

## Before debugging, release, deployment, or shared-infrastructure edits

```powershell
python tools/preflight.py
```

Read: branch, `origin/master`, staged vs unstaged vs untracked, stashes, diff summaries.

---

## Before commit, PR, cherry-pick, push, or deployment

1. Edit `tools/release_scope.txt` (copy from `tools/release_scope.example.txt` if missing).
2. Stage **only** intended paths: `git add -- path1 path2` — never `git add -A` for a hotfix.
3. Inspect staged diff: `git diff --cached`
4. Run:

```powershell
python tools/check_release_diff.py
python tools/release_check.py
```

Or the wrapper (includes smoke tests):

```powershell
python tools/release_check.py
```

5. Commit/push/deploy **only when the user explicitly asks**.

---

## Never infer release intent

- Do not assume local modifications belong in the next ship.
- Compare against `origin/master` to see what actually changes.
- Identify **route → renderer/template → CSS/JS → API/data** before patching.
- Find the **first broken link** before broad changes.
- Narrow task = narrow release diff.
- Never resolve merge/cherry-pick conflicts by blindly accepting a whole file when unrelated WIP exists.
- Whole-file copy from another dirty branch/worktree is **unsafe** unless the entire file diff is reviewed.

---

## Protected high-blast-radius areas (PBJ)

`tools/check_release_diff.py` fails loudly when nav/site-shell tasks touch:

- `app.py::_owners_cms_index_html` and related owners handlers
- `/owners/api/*` route wiring
- `ownership/*` rendering/routing modules
- deploy/data-source gates (`render.yaml`, `scripts/ensure_deploy_csvs.py`, owners DB build scripts)

---

## Smoke invariants (run before release)

```powershell
python -m pytest -q tests/test_owners_hub_index_markers.py tests/test_release_smoke_invariants.py
```

Minimum contracts:

- `/owners/` → 200, `data-owners-hub="national"`, no `owners-hub-state-cards`
- `/provider/335513` → 200, shared navbar/site-shell JS present
- `/about` → 200
- `/owners/api/cms-search` → 200

---

## Stop rule

When acceptance criteria pass for the **declared task**, stop. Park follow-ups separately.

Do not bundle unrelated polish, ownership WIP, or copy experiments into a hotfix ship.

---

## Related docs

- `AGENTS.md` — env preamble and ship bar
- `.cursor/rules/pbj320-clean-hotfix.mdc` — selective `git add` on dirty trees
- `tools/release_scope.example.txt` — scope file template
