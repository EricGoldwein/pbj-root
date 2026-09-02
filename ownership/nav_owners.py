"""Site nav: Owners dropdown (CMS search, state index, FEC)."""
from __future__ import annotations

import html
import json

from ownership.state_owner_index import public_owner_index_hub_entries
from ownership.us_states import US_STATE_CODE_TO_NAME, US_STATE_CODES


_GLOBE_ICON_SVG = (
    '<svg class="owners-scope-select-globe" width="15" height="15" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="1.85" stroke-linecap="round" '
    'stroke-linejoin="round" aria-hidden="true">'
    '<circle cx="12" cy="12" r="9"/>'
    '<path d="M3 12h18"/>'
    '<path d="M12 3a14 14 0 0 1 0 18"/>'
    '<path d="M12 3a14 14 0 0 0 0 18"/>'
    "</svg>"
)


def owners_state_index_json() -> str:
    """JSON for nav / hub state pickers. Verified from: public_owner_index_hub_entries()."""
    rows = public_owner_index_hub_entries()
    return json.dumps(
        [{"code": r["state_code"], "name": r["name"], "path": r["path"]} for r in rows],
        separators=(",", ":"),
    )


def owners_scope_select_html(
    *,
    selected_code: str | None = None,
    select_id: str = "ownersHubScopeSelect",
    national_path: str = "/owners",
) -> str:
    """Accessible custom state-scope control (All states + full names).

    Navigates to /owners or /owners/<slug>. Used on national and state ownership pages.
    """
    raw = (selected_code or "").strip().upper()[:2]
    sel = raw if raw in US_STATE_CODES else ""
    selected_label = US_STATE_CODE_TO_NAME.get(sel, "All states") if sel else "All states"
    selected_path = f"/owners/{sel.lower()}" if sel else national_path
    sid = html.escape(select_id, quote=True)
    list_id = html.escape(f"{select_id}List", quote=True)
    label_id = html.escape(f"{select_id}Label", quote=True)

    options: list[str] = [
        '<li role="option" class="owners-scope-select-option'
        + (' is-selected" aria-selected="true"' if not sel else '" aria-selected="false"')
        + f' data-path="{html.escape(national_path, quote=True)}" data-code="" '
        f'tabindex="-1">All states</li>'
    ]
    options.append('<li class="owners-scope-select-divider" role="presentation" aria-hidden="true"></li>')
    for row in public_owner_index_hub_entries():
        code = str(row.get("state_code") or "").upper()[:2]
        name = str(row.get("name") or code)
        path = str(row.get("path") or f"/owners/{code.lower()}")
        is_sel = code == sel
        options.append(
            '<li role="option" class="owners-scope-select-option'
            + (' is-selected" aria-selected="true"' if is_sel else '" aria-selected="false"')
            + f' data-path="{html.escape(path, quote=True)}" '
            f'data-code="{html.escape(code, quote=True)}" tabindex="-1">'
            f"{html.escape(name)}</li>"
        )

    return (
        f'<div class="owners-scope-select" data-owners-scope-select '
        f'data-selected-code="{html.escape(sel, quote=True)}" '
        f'data-selected-path="{html.escape(selected_path, quote=True)}">'
        f'<label class="owners-scope-select-field-label" for="{sid}">Select state</label>'
        f'<button type="button" id="{sid}" class="owners-scope-select-trigger" '
        f'aria-haspopup="listbox" aria-expanded="false" aria-controls="{list_id}" '
        f'aria-labelledby="{label_id}">'
        f"{_GLOBE_ICON_SVG}"
        f'<span id="{label_id}" class="owners-scope-select-value">'
        f"{html.escape(selected_label)}</span>"
        f'<span class="owners-scope-select-chevron" aria-hidden="true"></span>'
        f"</button>"
        f'<ul id="{list_id}" class="owners-scope-select-menu" role="listbox" '
        f'aria-label="Select ownership scope" hidden>'
        f'{"".join(options)}'
        f"</ul>"
        f"</div>"
    )


def owners_hub_panel_state_filter_html(*, select_id: str, selected_code: str | None = None) -> str:
    """Back-compat alias — custom All-states scope selector (full state names)."""
    return owners_scope_select_html(select_id=select_id, selected_code=selected_code)


def owners_state_select_options_html(*, select_id: str, placeholder: str = "Choose a state…") -> str:
    sid = html.escape(select_id, quote=True)
    ph = html.escape(placeholder)
    opts = [f'<option value="">{ph}</option>']
    for row in public_owner_index_hub_entries():
        path = html.escape(row["path"], quote=True)
        name = html.escape(row["name"])
        opts.append(f'<option value="{path}">{name}</option>')
    return f'<select id="{sid}" class="owners-state-select">{"".join(opts)}</select>'


def owners_nav_link_html(*, active: bool = False) -> str:
    """Desktop/mobile nav: direct link to national /owners (no dropdown, no FEC)."""
    cls = "nav-link"
    if active:
        cls += " active"
    aria = ' aria-current="page"' if active else ""
    return f'<a href="/owners" class="{cls}"{aria}>Owners</a>'


def owners_nav_dropdown_html(*, active: bool = False) -> str:
    """Back-compat alias — Owners is a direct /owners link (dropdown removed)."""
    return owners_nav_link_html(active=active)


def owners_nav_state_json_script() -> str:
    """Embed state list for ownership page scope pickers (not used by site nav)."""
    payload = html.escape(owners_state_index_json(), quote=True)
    return f'<script type="application/json" id="pbj-owners-state-index">{payload}</script>'
