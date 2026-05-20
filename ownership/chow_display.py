"""Shared CHOW table rows, change summaries, and before/after detail panels."""
from __future__ import annotations

import html
import re
from typing import Any

from ownership.display_format import format_org_display
from ownership.chow_lookup import format_chow_date

_CHOW_DETAIL_NOTE = (
    "CMS records this as a Change of Ownership. This comparison shows changes in "
    "CMS enrollment/entity fields. It does not, by itself, explain the business "
    "reason for the change."
)

_COMPARE_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("Organization name", "buyer_org_name", "seller_org_name"),
    ("DBA name", "buyer_dba_name", "seller_dba_name"),
    ("Enrollment ID", "buyer_enrollment_id", "seller_enrollment_id"),
    ("NPI", "buyer_npi", "seller_npi"),
    ("Associate ID", "buyer_associate_id", "seller_associate_id"),
    ("CCN", "ccn", "ccn"),
    ("Provider type", "chow_type", "chow_type"),
    ("Effective date", "effective_date", "effective_date"),
    ("CHOW type text", "chow_type", "chow_type"),
)


def _norm_cmp(val: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(val or "").strip().upper())


def _name_tokens(name: str) -> set[str]:
    return {t for t in re.split(r"[^A-Z0-9]+", _norm_cmp(name)) if len(t) > 2}


def _name_overlap_ratio(a: str, b: str) -> float:
    ta, tb = _name_tokens(a), _name_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


def _names_materially_different(buyer_org: str, seller_org: str) -> bool:
    a, b = str(buyer_org or "").strip(), str(seller_org or "").strip()
    if not a or not b:
        return False
    na, nb = _norm_cmp(a), _norm_cmp(b)
    if na == nb:
        return False
    if na in nb or nb in na:
        return False
    return _name_overlap_ratio(a, b) < 0.35


def chow_change_summary(rec: dict[str, Any]) -> str:
    """Compact Details label: Identifiers changed vs Entity changed."""
    buyer_org = str(rec.get("buyer_org_name") or rec.get("buyer_dba_name") or "").strip()
    seller_org = str(rec.get("seller_org_name") or "").strip()

    def changed(b_key: str, s_key: str) -> bool:
        b, s = _norm_cmp(rec.get(b_key)), _norm_cmp(rec.get(s_key))
        return bool(b or s) and b != s

    id_changes = any(
        changed(k, sk)
        for _label, k, sk in _COMPARE_FIELDS
        if k not in ("effective_date", "chow_type", "ccn")
    )
    if not id_changes:
        return ""

    if (
        _names_materially_different(buyer_org, seller_org)
        and _name_overlap_ratio(buyer_org, seller_org) < 0.15
    ):
        return "Entity changed"
    return "Identifiers changed"


def _field_display(key: str, val: Any, *, side: str, rec: dict[str, Any]) -> str:
    if key == "effective_date":
        return format_chow_date(str(val or "")) or "—"
    if key in ("buyer_org_name", "seller_org_name", "buyer_dba_name", "seller_dba_name"):
        return format_org_display(str(val or "")) or "—"
    if key == "ccn" and val:
        ccn = str(val).strip().zfill(6)[-6:]
        return ccn
    return str(val or "").strip() or "—"


def _field_status(b_val: Any, s_val: Any, key: str) -> str:
    if key == "ccn":
        return "same" if _norm_cmp(b_val) == _norm_cmp(s_val) and _norm_cmp(b_val) else "changed"
    if _norm_cmp(b_val) == _norm_cmp(s_val):
        return "same"
    if not _norm_cmp(b_val) and not _norm_cmp(s_val):
        return "same"
    return "changed"


def render_chow_detail_panel(rec: dict[str, Any], *, panel_id: str = "") -> str:
    """Before/after comparison for one CHOW row."""
    pid = html.escape(panel_id, quote=True) if panel_id else ""
    id_attr = f' id="{pid}"' if pid else ""
    rows_html: list[str] = []
    for label, b_key, s_key in _COMPARE_FIELDS:
        if label == "CHOW type text":
            continue
        b_raw, s_raw = rec.get(b_key), rec.get(s_key)
        status = _field_status(b_raw, s_raw, b_key)
        pill = (
            '<span class="chow-field-pill chow-field-pill--same">Same</span>'
            if status == "same"
            else '<span class="chow-field-pill chow-field-pill--changed">Changed</span>'
        )
        b_disp = html.escape(_field_display(b_key, b_raw, side="buyer", rec=rec))
        s_disp = html.escape(_field_display(s_key, s_raw, side="seller", rec=rec))
        rows_html.append(
            f'<tr class="chow-compare-row chow-compare-row--{status}">'
            f"<th>{html.escape(label)}</th>"
            f'<td class="chow-compare-before">{b_disp}</td>'
            f'<td class="chow-compare-after">{s_disp} {pill}</td>'
            "</tr>"
        )
    chow_type = html.escape(str(rec.get("chow_type") or "—"))
    return (
        f'<div class="chow-detail-compare"{id_attr}>'
        '<table class="chow-compare-table">'
        "<thead><tr><th>Field</th>"
        '<th class="chow-compare-before">Before / Seller</th>'
        '<th class="chow-compare-after">After / Buyer</th>'
        "</tr></thead><tbody>"
        + "".join(rows_html)
        + f'<tr><th>CHOW type text</th><td colspan="2">{chow_type}</td></tr>'
        + "</tbody></table>"
        f'<p class="chow-detail-note">{html.escape(_CHOW_DETAIL_NOTE)}</p>'
        "</div>"
    )


def render_chow_table_rows(
    rows: list[dict[str, Any]],
    *,
    org_link_fn,
    compact: bool = False,
    table_id: str = "",
    max_rows: int = 0,
) -> str:
    """HTML tbody rows: Effective, Buyer, Seller, Details (+ optional expand panel)."""
    limit = max_rows if max_rows > 0 else len(rows)
    trs: list[str] = []
    for i, rec in enumerate(rows[:limit]):
        rid = html.escape(str(rec.get("chow_id") or f"row-{i}"), quote=True)
        eff = html.escape(format_chow_date(str(rec.get("effective_date") or "")))
        buyer = org_link_fn(rec, "buyer")
        seller = org_link_fn(rec, "seller")
        summary = chow_change_summary(rec)
        summary_esc = html.escape(summary) if summary else "—"
        panel_id = f"chow-detail-{rid}"
        panel = render_chow_detail_panel(rec, panel_id=panel_id)
        trs.append(
            f'<tr class="chow-tx-row" data-chow-id="{rid}">'
            f'<td class="num chow-tx-date">{eff}</td>'
            f'<td class="chow-tx-org">{buyer}</td>'
            f'<td class="chow-tx-org">{seller}</td>'
            f'<td class="chow-tx-details">'
            f'<span class="chow-tx-summary">{summary_esc}</span> '
            f'<button type="button" class="chow-view-details" '
            f'data-chow-detail="{panel_id}" aria-expanded="false">View details</button>'
            f"</td></tr>"
            f'<tr class="chow-tx-detail-row" id="{panel_id}-row" hidden>'
            f'<td colspan="4">{panel}</td></tr>'
        )
    return "".join(trs)


def render_chow_events_table(
    rows: list[dict[str, Any]],
    *,
    org_link_fn,
    max_rows: int = 0,
    table_class: str = "chow-table chow-tx-table",
) -> str:
    body = render_chow_table_rows(
        rows, org_link_fn=org_link_fn, max_rows=max_rows
    )
    if not body:
        return ""
    return (
        f'<div class="chow-table-scroll chow-tx-scroll">'
        f'<table class="{table_class}"><thead><tr>'
        "<th class=\"num\">Effective</th><th>Buyer</th><th>Seller</th><th>Details</th>"
        "</tr></thead><tbody>"
        + body
        + "</tbody></table></div>"
    )


CHOW_TABLE_INIT_SCRIPT = """
<script>(function(){
  function bind(root){
    if(!root) return;
    root.querySelectorAll('.chow-view-details').forEach(function(btn){
      if(btn._chowBound) return;
      btn._chowBound = true;
      btn.addEventListener('click', function(e){
        e.preventDefault();
        e.stopPropagation();
        var pid = btn.getAttribute('data-chow-detail');
        var row = pid ? document.getElementById(pid + '-row') : null;
        if(!row) return;
        var open = row.hidden;
        row.hidden = !open;
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
        btn.textContent = open ? 'Hide details' : 'View details';
      });
    });
    root.querySelectorAll('.chow-btn-chow-toggle').forEach(function(btn){
      if(btn._chowBound) return;
      btn._chowBound = true;
      btn.addEventListener('click', function(e){
        e.preventDefault();
        var tid = btn.getAttribute('aria-controls');
        var panel = tid ? document.getElementById(tid) : null;
        if(!panel) return;
        var open = panel.hidden;
        panel.hidden = !open;
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      });
    });
  }
  document.querySelectorAll('.provider-chow-block, .pbj-ownership-chow-content').forEach(bind);
  bind(document);
})();</script>
"""
