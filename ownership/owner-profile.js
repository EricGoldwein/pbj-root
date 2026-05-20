/**
 * Owner profile: info modals, facilities table sort/filter.
 */
(function () {
  'use strict';

  var root = document.querySelector('.owner-profile-root');
  if (!root) return;

  var infoDlg = document.getElementById('ownerInfoModal');
  var infoBody = document.getElementById('ownerInfoModalBody');
  var infoTitle = document.getElementById('ownerInfoModalTitle');

  function readInfoPayload(btn) {
    var title = btn.getAttribute('data-info-title');
    var body = btn.getAttribute('data-info-body');
    if (title || body) {
      return { title: title || 'Details', body: body || '' };
    }
    var raw = btn.getAttribute('data-owner-info-json');
    if (raw) {
      try {
        return JSON.parse(raw);
      } catch (e) {
        /* fall through */
      }
    }
    return {
      title: btn.getAttribute('data-info-title') || 'Details',
      body: btn.getAttribute('data-info-body') || '',
    };
  }

  function appendDlRow(dl, label, value) {
    if (!value || !String(value).trim()) return;
    var dt = document.createElement('dt');
    dt.textContent = label;
    var dd = document.createElement('dd');
    dd.textContent = String(value).trim();
    dl.appendChild(dt);
    dl.appendChild(dd);
  }

  function fillInfoBody(btn, data) {
    if (!infoBody) return;
    infoBody.textContent = '';
    infoBody.className = 'owner-info-modal-body';
    var fmt = btn.getAttribute('data-info-format') || '';

    if (fmt === 'ownership') {
      infoBody.classList.add('owner-info-modal-body--ownership');
      var kind = btn.getAttribute('data-role-kind') || '';
      var roleText = btn.getAttribute('data-role-text') || '';
      var since = btn.getAttribute('data-role-since') || '';
      if (kind) {
        var lead = document.createElement('p');
        lead.className = 'owner-info-lead';
        lead.textContent = kind;
        infoBody.appendChild(lead);
      }
      var dl = document.createElement('dl');
      dl.className = 'owner-info-dl';
      appendDlRow(dl, 'CMS role', roleText);
      appendDlRow(dl, 'Since', since);
      if (dl.children.length) infoBody.appendChild(dl);
      var note = document.createElement('p');
      note.className = 'owner-info-note';
      note.textContent = 'CMS-reported ownership role for this facility.';
      infoBody.appendChild(note);
      return;
    }

    var body = data.body || '';
    if (fmt === 'flag') {
      infoBody.classList.add('owner-info-modal-body--flag');
    }
    if (body.indexOf('\n\n') >= 0) {
      body.split(/\n\n+/).forEach(function (chunk) {
        if (!chunk.trim()) return;
        var p = document.createElement('p');
        p.textContent = chunk.trim();
        infoBody.appendChild(p);
      });
    } else if (body) {
      var p = document.createElement('p');
      p.textContent = body;
      infoBody.appendChild(p);
    }
  }

  function openInfo(btn) {
    if (!infoDlg || !infoBody) return;
    var data = readInfoPayload(btn);
    if (infoTitle) infoTitle.textContent = data.title || 'Details';
    if (infoDlg.classList) {
      infoDlg.classList.remove('owner-info-modal--ownership', 'owner-info-modal--flag');
      var fmt = btn.getAttribute('data-info-format') || '';
      if (fmt === 'ownership') infoDlg.classList.add('owner-info-modal--ownership');
      if (fmt === 'flag') infoDlg.classList.add('owner-info-modal--flag');
    }
    fillInfoBody(btn, data);
    if (typeof infoDlg.showModal === 'function') {
      infoDlg.showModal();
    } else {
      infoDlg.setAttribute('open', 'open');
    }
  }

  if (infoDlg && infoBody) {
    root.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-owner-info]');
      if (!btn || !root.contains(btn)) return;
      e.preventDefault();
      e.stopPropagation();
      openInfo(btn);
    });
    document.querySelectorAll('[data-owner-info-close]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        infoDlg.close();
      });
    });
    infoDlg.addEventListener('click', function (e) {
      if (e.target === infoDlg) infoDlg.close();
    });
  }

  var dlg = document.getElementById('ownerStatesModal');
  if (dlg) {
    document.querySelectorAll('[data-owner-states-open]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (typeof dlg.showModal === 'function') {
          dlg.showModal();
        } else {
          dlg.setAttribute('open', 'open');
        }
      });
    });
    document.querySelectorAll('[data-owner-states-close]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        dlg.close();
      });
    });
    dlg.addEventListener('click', function (e) {
      if (e.target === dlg) dlg.close();
    });
  }

  var table = document.getElementById('ownerFacilitiesTable');
  if (!table) return;

  var tbody = table.querySelector('tbody');
  if (!tbody) return;

  var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
  var filterInput = document.getElementById('ownerFacilitiesFilter');
  var filterCount = document.getElementById('ownerFacilitiesFilterCount');
  var sortKey = 'legal';
  var sortDir = 'asc';
  var colIndex = {
    legal: 0,
    state: 1,
    county: 2,
    role: 3,
    hprd: 4,
    stars: 5,
    census: 6,
  };

  function visibleRows() {
    return rows.filter(function (tr) {
      return tr.style.display !== 'none';
    });
  }

  function updateCounts() {
    var vis = visibleRows().length;
    var q = filterInput ? String(filterInput.value || '').trim() : '';
    if (filterCount) {
      if (q) {
        filterCount.hidden = false;
        filterCount.textContent = vis + ' shown';
      } else {
        filterCount.hidden = true;
        filterCount.textContent = '';
      }
    }
  }

  function sortValue(tr, key) {
    var idx = colIndex[key];
    if (idx === undefined) return '';
    var cell = tr.children[idx];
    if (!cell) return '';
    var raw = cell.getAttribute('data-sort') || cell.textContent || '';
    if (key === 'hprd' || key === 'stars' || key === 'role' || key === 'census') {
      var n = parseFloat(String(raw).replace(/[^0-9.-]/g, ''));
      return isNaN(n) ? -Infinity : n;
    }
    return String(raw).toLowerCase();
  }

  function applySort() {
    var dir = sortDir === 'asc' ? 1 : -1;
    rows.sort(function (a, b) {
      var av = sortValue(a, sortKey);
      var bv = sortValue(b, sortKey);
      if (av < bv) return -1 * dir;
      if (av > bv) return 1 * dir;
      return 0;
    });
    rows.forEach(function (tr) {
      tbody.appendChild(tr);
    });
  }

  function applyFilter() {
    var q = filterInput ? String(filterInput.value || '').trim().toLowerCase() : '';
    rows.forEach(function (tr) {
      if (!q) {
        tr.style.display = '';
        return;
      }
      var blob = tr.getAttribute('data-search') || tr.textContent || '';
      tr.style.display = blob.toLowerCase().indexOf(q) >= 0 ? '' : 'none';
    });
    updateCounts();
  }

  function updateSortHeaders() {
    table.querySelectorAll('th.sortable').forEach(function (th) {
      th.classList.remove('sort-asc', 'sort-desc');
      if (th.getAttribute('data-sort') === sortKey) {
        th.classList.add(sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
      }
    });
  }

  table.querySelectorAll('th.sortable').forEach(function (th) {
    th.addEventListener('click', function () {
      var key = th.getAttribute('data-sort');
      if (!key) return;
      if (sortKey === key) {
        sortDir = sortDir === 'asc' ? 'desc' : 'asc';
      } else {
        sortKey = key;
        sortDir =
          key === 'hprd' || key === 'stars' || key === 'census' || key === 'role'
            ? 'desc'
            : 'asc';
      }
      applySort();
      updateSortHeaders();
    });
  });

  if (filterInput) {
    filterInput.addEventListener('input', applyFilter);
  }

  applySort();
  updateSortHeaders();
  updateCounts();
})();
