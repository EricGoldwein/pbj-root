# Agent PowerShell + Python safety (Windows)

Short checklist to avoid the SyntaxErrors that burn agent turns in this env.

## Prefer script files over `python -c`

PowerShell mangles nested quotes inside `python -c "..."`. That often becomes a Python `SyntaxError` even when the logic is fine.

**Do this instead:**

1. Write `_scratch/probe_name.py` (or a small file under `scripts/`).
2. Run: `python -u path\to\probe_name.py`
3. Prefer the editor **Write** / **StrReplace** tools, or `Set-Content`, over complex one-liners.

## Never use bash-only shell syntax on PowerShell

| Avoid | Use |
|-------|-----|
| `cmd1 && cmd2` | `cmd1; if ($LASTEXITCODE -eq 0) { cmd2 }` or separate Shell calls |
| bash heredocs / `$(cat <<'EOF')` | temp file + `git commit -F path`, or `git commit -m "title" -m "body"` |
| `export VAR=value` | `$env:VAR = "value"` |

## Quick patterns

```powershell
# OK: run a file
python -u _scratch\cms_title_probe.py

# OK: chain with PowerShell
Set-Location C:\Users\egold\PycharmProjects\PBJapp
python -u scripts\cms_source_registry.py refresh

# Risky: nested quotes in -c (often breaks)
# python -c "print('nested \"quotes\"')"
```

See also: `.cursor/rules/pbj320-agent-rules.mdc` §1 PowerShell-first.
