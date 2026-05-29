"""Shared CHOW table rows, change summaries, and before/after detail panels."""
from __future__ import annotations

import html
import re
from typing import Any

from ownership.display_format import format_org_display
from ownership.chow_lookup import format_chow_date, format_chow_date_dashed

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


def _default_facility_link(rec: dict[str, Any]) -> str:
    ccn = str(rec.get("ccn") or "").strip().zfill(6)[-6:]
    fd = str(rec.get("facility_display_name") or "").strip()
    buyer_org = str(rec.get("buyer_org_name") or "").strip()
    buyer_dba = str(rec.get("buyer_dba_name") or "").strip()
    if fd and fd not in (buyer_org, buyer_dba):
        fac = format_org_display(fd)
    elif ccn.isdigit():
        fac = f"CCN {ccn}"
    else:
        fac = "—"
    if ccn.isdigit():
        return f'<a href="/provider/{html.escape(ccn)}">{html.escape(fac)}</a>'
    return html.escape(fac)


def _chow_details_button(panel_id: str) -> str:
    pid = html.escape(panel_id, quote=True)
    return (
        f'<button type="button" class="chow-view-details chow-view-details--btn" '
        f'data-chow-detail-store="{pid}" aria-expanded="false">Details</button>'
    )


def _party_initials(name: str) -> str:
    tokens = [t for t in re.split(r"\W+", str(name or "").strip()) if t]
    if not tokens:
        return "?"
    if len(tokens) == 1:
        return tokens[0][:2].upper()
    return (tokens[0][:1] + tokens[-1][:1]).upper()


def _chow_party_card(
    *,
    role: str,
    display_html: str,
    raw_name: str,
) -> str:
    initials = html.escape(_party_initials(raw_name))
    role_esc = html.escape(role)
    return (
        f'<div class="owners-chow-party">'
        f'<span class="owners-chow-party-mark" aria-hidden="true">{initials}</span>'
        f'<div class="owners-chow-party-text">'
        f'<span class="owners-chow-party-role">{role_esc}</span>'
        f'<span class="owners-chow-party-name">{display_html}</span>'
        f"</div></div>"
    )


def render_chow_transfer_modal_body(
    rec: dict[str, Any],
    *,
    org_link_fn,
    facility_link_fn=None,
) -> str:
    """Seller → buyer summary for state ownership index modals."""
    fac_fn = facility_link_fn or _default_facility_link
    eff = html.escape(format_chow_date(str(rec.get("effective_date") or "")) or "—")
    facility = fac_fn(rec)
    buyer_raw = str(rec.get("buyer_org_name") or rec.get("buyer_dba_name") or "").strip()
    seller_raw = str(rec.get("seller_org_name") or "").strip()
    buyer = org_link_fn(rec, "buyer")
    seller = org_link_fn(rec, "seller")
    summary = chow_change_summary(rec)
    summary_html = (
        f'<p class="owners-chow-modal-summary">{html.escape(summary)}</p>'
        if summary
        else ""
    )
    seller_card = _chow_party_card(role="Seller", display_html=seller, raw_name=seller_raw)
    buyer_card = _chow_party_card(role="Buyer", display_html=buyer, raw_name=buyer_raw)
    compare = render_chow_detail_panel(rec, panel_id="")
    return (
        f'<div class="owners-chow-modal-transfer">'
        f'<p class="owners-chow-modal-date"><span class="owners-chow-modal-date-k">Effective</span> {eff}</p>'
        f'<div class="owners-chow-modal-facility">{facility}</div>'
        f"{summary_html}"
        f'<div class="owners-chow-transfer-flow" role="group" aria-label="Ownership transfer">'
        f"{seller_card}"
        f'<span class="owners-chow-transfer-arrow" aria-hidden="true">→</span>'
        f"{buyer_card}"
        f"</div>"
        f'<details class="owners-chow-modal-compare">'
        f"<summary>Field-by-field comparison</summary>"
        f"{compare}"
        f"</details>"
        f"</div>"
    )


def render_chow_table_rows(
    rows: list[dict[str, Any]],
    *,
    org_link_fn,
    facility_link_fn=None,
    compact: bool = False,
    table_id: str = "",
    max_rows: int = 0,
    initial_visible: int = 0,
    mobile_change_stack: bool = False,
    mobile_provider_stack: bool = False,
) -> str:
    """HTML tbody rows: Activity, Effective, Details, Facility, Buyer, Seller (modal)."""
    fac_fn = facility_link_fn or _default_facility_link
    limit = max_rows if max_rows > 0 else len(rows)
    trs: list[str] = []
    stores: list[str] = []
    for i, rec in enumerate(rows[:limit]):
        rid = html.escape(str(rec.get("chow_id") or f"row-{i}"), quote=True)
        eff = html.escape(format_chow_date_dashed(str(rec.get("effective_date") or "")))
        facility = fac_fn(rec)
        buyer = org_link_fn(rec, "buyer")
        seller = org_link_fn(rec, "seller")
        summary = chow_change_summary(rec)
        summary_esc = html.escape(summary) if summary else "—"
        panel_id = f"chow-detail-{rid}"
        panel = render_chow_detail_panel(rec, panel_id=panel_id)
        details_btn = _chow_details_button(panel_id)
        row_hidden = initial_visible > 0 and i >= initial_visible
        hidden_attr = " hidden" if row_hidden else ""
        row_extra = " chow-tx-row--paginated-hidden" if row_hidden else ""
        activity_cell = f'<td class="chow-tx-activity chow-tx-desktop-col">{summary_esc}</td>'
        date_cell = f'<td class="num chow-tx-date chow-tx-desktop-col">{eff}</td>'
        details_cell = f'<td class="chow-tx-details chow-tx-desktop-col">{details_btn}</td>'
        facility_cell = f'<td class="chow-tx-facility chow-tx-desktop-col">{facility}</td>'
        buyer_cell = f'<td class="chow-tx-org chow-tx-desktop-col">{buyer}</td>'
        seller_cell = f'<td class="chow-tx-org chow-tx-desktop-col">{seller}</td>'

        if mobile_provider_stack:
            trs.append(
                f'<tr class="chow-tx-row chow-tx-row--provider-mobile{row_extra}" data-chow-id="{rid}"{hidden_attr}>'
                f'<td class="chow-tx-provider-stack">'
                f'<div class="chow-tx-provider-row">'
                f'<div class="chow-tx-provider-details">{details_btn}</div>'
                f'<div class="chow-tx-provider-main">'
                f'<div class="chow-tx-provider-meta">'
                f'<span class="chow-tx-provider-change">{summary_esc}</span>'
                f'<span class="chow-tx-provider-sep" aria-hidden="true"> · </span>'
                f'<span class="chow-tx-provider-date">{eff}</span>'
                f"</div>"
                f'<div class="chow-tx-provider-parties">{buyer} → {seller}</div>'
                f"</div></div></td>"
                f"{activity_cell}{date_cell}{details_cell}{facility_cell}{buyer_cell}{seller_cell}</tr>"
            )
        elif mobile_change_stack:
            trs.append(
                f'<tr class="chow-tx-row chow-tx-row--stacked{row_extra}" data-chow-id="{rid}"{hidden_attr}>'
                f'<td class="chow-tx-change-stack">'
                f'<div class="chow-tx-stack-line chow-tx-stack-line--activity">'
                f'<span class="chow-tx-stack-k">Activity</span>'
                f'<span class="chow-tx-stack-v">{summary_esc}</span></div>'
                f'<div class="chow-tx-stack-line chow-tx-stack-line--date">'
                f'<span class="chow-tx-stack-v chow-tx-stack-v--date">{eff}</span></div>'
                f'<div class="chow-tx-stack-line chow-tx-stack-line--action">'
                f'<span class="chow-tx-stack-v">{details_btn}</span></div>'
                f'<div class="chow-tx-stack-extra">'
                f'<div class="chow-tx-stack-facility">{facility}</div>'
                f'<div class="chow-tx-stack-parties">{buyer} → {seller}</div>'
                f"</div></td>"
                f"{activity_cell}{date_cell}{details_cell}{facility_cell}{buyer_cell}{seller_cell}</tr>"
            )
        else:
            trs.append(
                f'<tr class="chow-tx-row{row_extra}" data-chow-id="{rid}"{hidden_attr}>'
                f'<td class="chow-tx-activity">{summary_esc}</td>'
                f'<td class="num chow-tx-date">{eff}</td>'
                f'<td class="chow-tx-details">{details_btn}</td>'
                f'<td class="chow-tx-facility">{facility}</td>'
                f'<td class="chow-tx-org">{buyer}</td>'
                f'<td class="chow-tx-org">{seller}</td>'
                f"</tr>"
            )
        stores.append(f'<div id="{panel_id}" class="chow-detail-store" hidden>{panel}</div>')
    return "".join(trs), "".join(stores)


def render_chow_paginate_footer(
    *,
    total: int,
    initial_visible: int,
    page_size: int = 10,
) -> str:
    """Inline show-more control (replaces dead /chow monitor links)."""
    if total <= initial_visible:
        return ""
    shown = min(initial_visible, total)
    return (
        f'<p class="chow-state-actions chow-state-paginate" data-page-size="{int(page_size)}" '
        f'data-total="{int(total)}" data-shown="{shown}">'
        f'<span class="chow-paginate-status">Showing {shown:,} of {total:,}</span>'
        f'<span class="chow-paginate-sep" aria-hidden="true"> · </span>'
        f'<button type="button" class="chow-paginate-more">Show next {int(page_size)}</button>'
        f"</p>"
    )


def render_chow_events_table(
    rows: list[dict[str, Any]],
    *,
    org_link_fn,
    facility_link_fn=None,
    max_rows: int = 0,
    initial_visible: int = 0,
    table_class: str = "chow-table chow-tx-table",
    mobile_change_stack: bool = False,
    mobile_provider_stack: bool = False,
) -> str:
    body, stores = render_chow_table_rows(
        rows,
        org_link_fn=org_link_fn,
        facility_link_fn=facility_link_fn,
        max_rows=max_rows,
        initial_visible=initial_visible,
        mobile_change_stack=mobile_change_stack,
        mobile_provider_stack=mobile_provider_stack,
    )
    if not body:
        return ""
    stack_class = ""
    if mobile_provider_stack:
        stack_class = " chow-tx-table--provider-mobile"
    elif mobile_change_stack:
        stack_class = " chow-tx-table--change-stack"
    if mobile_provider_stack:
        thead = (
            '<th class="chow-tx-provider-stack-head">Ownership change</th>'
            '<th class="chow-tx-desktop-col">Activity</th>'
            '<th class="num chow-tx-desktop-col">Effective</th>'
            '<th class="chow-tx-desktop-col">Details</th>'
            '<th class="chow-tx-desktop-col">Facility</th>'
            '<th class="chow-tx-desktop-col">Buyer</th>'
            '<th class="chow-tx-desktop-col">Seller</th>'
        )
    elif mobile_change_stack:
        thead = (
            '<th class="chow-tx-change-stack-head">Activity</th>'
            '<th class="chow-tx-desktop-col">Activity</th>'
            '<th class="num chow-tx-desktop-col">Effective</th>'
            '<th class="chow-tx-desktop-col">Details</th>'
            '<th class="chow-tx-desktop-col">Facility</th>'
            '<th class="chow-tx-desktop-col">Buyer</th>'
            '<th class="chow-tx-desktop-col">Seller</th>'
        )
    else:
        thead = (
            '<th>Activity</th><th class="num">Effective</th><th>Details</th>'
            '<th>Facility</th><th>Buyer</th><th>Seller</th>'
        )
    return (
        f'<div class="chow-tx-table-wrap">'
        f'<div class="chow-table-scroll chow-tx-scroll chow-table-scroll--touch mobile-table-scroll">'
        f'<table class="{table_class} chow-tx-table--mobile{stack_class}"><thead><tr>'
        f"{thead}"
        "</tr></thead><tbody>"
        + body
        + "</tbody></table></div>"
        f'<div class="chow-detail-stores" hidden aria-hidden="true">{stores}</div>'
        "</div>"
    )


def _chow_effective_attrs(rec: dict[str, Any]) -> tuple[str, str]:
    """data-effective-date + visible date markup (ISO preserved for future logic)."""
    raw = str(rec.get("effective_date") or "").strip()
    if not raw:
        return "", '<span class="provider-chow-card__date">—</span>'
    iso = raw[:10] if len(raw) >= 10 else raw
    iso_esc = html.escape(iso, quote=True)
    label = html.escape(format_chow_date(iso) or format_chow_date_dashed(iso) or iso)
    return (
        f' data-effective-date="{iso_esc}"',
        f'<time class="provider-chow-card__date" datetime="{iso_esc}">{label}</time>',
    )


def render_provider_chow_cards(
    rows: list[dict[str, Any]],
    *,
    org_link_fn,
    max_rows: int = 40,
) -> str:
    """Card list for provider ownership (replaces wide table + Details column)."""
    limit = max_rows if max_rows > 0 else len(rows)
    if not rows[:limit]:
        return ""
    items: list[str] = []
    stores: list[str] = []
    for i, rec in enumerate(rows[:limit]):
        rid = html.escape(str(rec.get("chow_id") or f"row-{i}"), quote=True)
        eff_attr, eff_html = _chow_effective_attrs(rec)
        summary = chow_change_summary(rec)
        summary_html = (
            f'<span class="provider-chow-card__activity">{html.escape(summary)}</span>'
            if summary
            else ""
        )
        buyer = org_link_fn(rec, "buyer")
        seller = org_link_fn(rec, "seller")
        panel_id = f"chow-detail-{rid}"
        panel = render_chow_transfer_modal_body(rec, org_link_fn=org_link_fn)
        details_btn = _chow_details_button(panel_id).replace(
            ">Details</button>",
            '><span class="provider-chow-card__btn-line">Transfer</span>'
            '<span class="provider-chow-card__btn-line">details</span></button>',
        )
        items.append(
            f'<li class="provider-chow-card"{eff_attr} data-chow-id="{rid}">'
            f'<div class="provider-chow-card__head">{eff_html}{summary_html}</div>'
            f'<div class="provider-chow-card__flow" role="group" aria-label="Ownership transfer">'
            f'<div class="provider-chow-card__party provider-chow-card__party--seller">'
            f'<span class="provider-chow-card__party-k">Seller</span>'
            f'<span class="provider-chow-card__party-v">{seller}</span></div>'
            f'<span class="provider-chow-card__arrow" aria-hidden="true">→</span>'
            f'<div class="provider-chow-card__party provider-chow-card__party--buyer">'
            f'<span class="provider-chow-card__party-k">Buyer</span>'
            f'<span class="provider-chow-card__party-v">{buyer}</span></div>'
            f"</div>"
            f'<div class="provider-chow-card__action">{details_btn}</div>'
            f"</li>"
        )
        stores.append(f'<div id="{panel_id}" class="chow-detail-store" hidden>{panel}</div>')
    return (
        '<ul class="provider-chow-cards" role="list">'
        + "".join(items)
        + "</ul>"
        f'<div class="chow-detail-stores" hidden aria-hidden="true">{"".join(stores)}</div>'
    )


CHOW_TABLE_INIT_SCRIPT = """
<script>(function(){
  var modal = document.getElementById('chowDetailModal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'chowDetailModal';
    modal.className = 'chow-detail-modal';
    modal.setAttribute('aria-hidden', 'true');
    modal.innerHTML =
      '<div class="chow-detail-modal__backdrop" data-chow-modal-close></div>' +
      '<div class="chow-detail-modal__dialog" role="dialog" aria-modal="true" aria-labelledby="chowDetailModalTitle">' +
      '<div class="chow-detail-modal__head"><h3 id="chowDetailModalTitle">Ownership change details</h3>' +
      '<button type="button" class="chow-detail-modal__close" data-chow-modal-close aria-label="Close">&times;</button></div>' +
      '<div class="chow-detail-modal__body" id="chowDetailModalBody"></div></div>';
    document.body.appendChild(modal);
    function closeModal(){
      var active = document.activeElement;
      if (active && modal.contains(active)) active.blur();
      modal.setAttribute('aria-hidden','true');
      document.body.classList.remove('chow-modal-open');
    }
    modal.querySelectorAll('[data-chow-modal-close]').forEach(function(el){
      el.addEventListener('click', closeModal);
    });
    document.addEventListener('keydown', function(e){
      if (e.key === 'Escape' && modal.getAttribute('aria-hidden') === 'false') closeModal();
    });
  }
  function openDetail(storeId) {
    var store = document.getElementById(storeId);
    var body = document.getElementById('chowDetailModalBody');
    if (!store || !body) return;
    body.innerHTML = store.innerHTML;
    modal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('chow-modal-open');
  }
  function bind(root){
    if(!root) return;
    root.querySelectorAll('.chow-view-details').forEach(function(btn){
      if(btn._chowBound) return;
      btn._chowBound = true;
      btn.addEventListener('click', function(e){
        e.preventDefault();
        e.stopPropagation();
        var sid = btn.getAttribute('data-chow-detail-store');
        if (sid) openDetail(sid);
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
  function bindPaginate(root){
    if(!root) return;
    root.querySelectorAll('.chow-state-paginate').forEach(function(bar){
      if(bar._chowPaginateBound) return;
      bar._chowPaginateBound = true;
      var wrap = bar.closest('.chow-state-block, .pbj-details-content, .owners-state-panel');
      if(!wrap) wrap = bar.parentElement;
      var btn = bar.querySelector('.chow-paginate-more');
      var status = bar.querySelector('.chow-paginate-status');
      var sep = bar.querySelector('.chow-paginate-sep');
      if(!btn || !wrap) return;
      var pageSize = parseInt(bar.getAttribute('data-page-size'), 10) || 10;
      var total = parseInt(bar.getAttribute('data-total'), 10) || 0;
      function hiddenRows(){
        return wrap.querySelectorAll('.chow-tx-row--paginated-hidden[hidden], .owners-chow-item--more[hidden]');
      }
      function visibleCount(){
        return wrap.querySelectorAll('.chow-tx-row:not([hidden]), .owners-state-chow-item:not([hidden])').length;
      }
      function update(){
        var shown = visibleCount();
        var left = hiddenRows().length;
        if(status) status.textContent = 'Showing ' + shown.toLocaleString() + ' of ' + total.toLocaleString();
        if(left <= 0){
          btn.hidden = true;
          if(sep) sep.hidden = true;
        } else {
          btn.hidden = false;
          if(sep) sep.hidden = false;
          var next = Math.min(pageSize, left);
          btn.textContent = 'Show next ' + next.toLocaleString();
        }
      }
      btn.addEventListener('click', function(){
        var rows = hiddenRows();
        for(var i = 0; i < pageSize && i < rows.length; i++){
          rows[i].removeAttribute('hidden');
        }
        update();
      });
      update();
    });
  }
  document.querySelectorAll('.provider-chow-block, .provider-chow-cards, .pbj-ownership-chow-content, .chow-state-block, .owners-state-panel').forEach(function(el){
    bind(el);
    bindPaginate(el);
  });
  bind(document);
  bindPaginate(document);
})();</script>
"""
