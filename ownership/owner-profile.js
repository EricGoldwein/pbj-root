/**
 * Owner profile: info modals, facilities table sort/filter.
 */
(function () {
  'use strict';

  function initDistTabs() {
    document.querySelectorAll('[data-owner-dist-tabs]').forEach(function (wrap) {
      var tabs = wrap.querySelectorAll('[role="tab"]');
      var panels = wrap.querySelectorAll('[role="tabpanel"]');
      if (!tabs.length || tabs.length !== panels.length) return;

      function activate(index) {
        var heading = wrap.querySelector('[data-owner-dist-title]');
        tabs.forEach(function (tab, i) {
          var on = i === index;
          tab.classList.toggle('is-active', on);
          tab.setAttribute('aria-selected', on ? 'true' : 'false');
          tab.tabIndex = on ? 0 : -1;
          panels[i].hidden = !on;
          panels[i].classList.toggle('is-active', on);
          if (on && heading && tab.getAttribute('data-dist-title')) {
            heading.textContent = tab.getAttribute('data-dist-title');
          }
        });
      }

      tabs.forEach(function (tab, index) {
        tab.addEventListener('click', function () {
          activate(index);
        });
        tab.addEventListener('keydown', function (e) {
          if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
          e.preventDefault();
          var next = e.key === 'ArrowRight' ? index + 1 : index - 1;
          if (next < 0) next = tabs.length - 1;
          if (next >= tabs.length) next = 0;
          tabs[next].focus();
          activate(next);
        });
      });
    });
  }

  initDistTabs();

  var infoDlg = document.getElementById('ownerInfoModal');
  var infoBody = document.getElementById('ownerInfoModalBody');
  var infoTitle = document.getElementById('ownerInfoModalTitle');

  function infoButtonScope(btn) {
    return btn.closest(
      '.owner-profile-root, .entity-portfolio-root, .entity-high-risk-metrics, #pbj-takeaway, .entity-facilities-section'
    );
  }

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

    if (fmt === 'html') {
      var bodyHtml = data.body || btn.getAttribute('data-info-body') || '';
      if (bodyHtml) infoBody.innerHTML = bodyHtml;
      return;
    }

    if (fmt === 'address') {
      infoBody.classList.add('owner-info-modal-body--address');
      var street = (btn.getAttribute('data-address-street') || '').trim();
      var cityLine = (btn.getAttribute('data-address-cityline') || '').trim();
      var full = (btn.getAttribute('data-address-full') || '').trim();
      var lines = full ? full.split('\n') : [];
      if (!lines.length) {
        if (street) lines.push(street);
        if (cityLine) lines.push(cityLine);
      }
      if (lines.length) {
        var addr = document.createElement('address');
        addr.className = 'owner-info-address';
        lines.forEach(function (line) {
          if (!line.trim()) return;
          var p = document.createElement('p');
          p.textContent = line.trim();
          addr.appendChild(p);
        });
        infoBody.appendChild(addr);
      }
      var note = document.createElement('p');
      note.className = 'owner-info-note';
      note.textContent = 'Source: CMS Provider Info';
      infoBody.appendChild(note);
      return;
    }

    if (fmt === 'ownership') {
      infoBody.classList.add('owner-info-modal-body--ownership');
      var category = (btn.getAttribute('data-role-category') || '').trim();
      var pctReported = (btn.getAttribute('data-pct-reported') || '').trim();
      var roleText = (btn.getAttribute('data-role-text') || '').trim();
      var kind = (btn.getAttribute('data-role-kind') || '').trim();
      var since = (btn.getAttribute('data-role-since') || '').trim();
      var leadText = kind || category;
      if (leadText) {
        var lead = document.createElement('p');
        lead.className = 'owner-info-lead';
        lead.textContent = leadText;
        infoBody.appendChild(lead);
      }
      var dl = document.createElement('dl');
      dl.className = 'owner-info-dl';
      appendDlRow(dl, 'Reported stake', pctReported);
      appendDlRow(dl, 'CMS role', roleText);
      appendDlRow(dl, 'Since', since);
      if (dl.children.length) infoBody.appendChild(dl);
      var note = document.createElement('p');
      note.className = 'owner-info-note';
      note.textContent = 'CMS-reported ownership role for this facility.';
      infoBody.appendChild(note);
      return;
    }

    if (fmt === 'sff') {
      infoBody.classList.add('owner-info-modal-body--sff');
      var bodySff = data.body || btn.getAttribute('data-info-body') || '';
      if (bodySff.indexOf('\n\n') >= 0) {
        bodySff.split(/\n\n+/).forEach(function (chunk) {
          if (!chunk.trim()) return;
          var para = document.createElement('p');
          para.textContent = chunk.trim();
          infoBody.appendChild(para);
        });
      } else if (bodySff) {
        var lone = document.createElement('p');
        lone.textContent = bodySff;
        infoBody.appendChild(lone);
      }
      var linkUrl = (btn.getAttribute('data-info-link-url') || '').trim();
      var linkLabel = (btn.getAttribute('data-info-link-label') || '').trim();
      if (linkUrl && linkLabel) {
        var cta = document.createElement('p');
        cta.className = 'owner-info-cta';
        var a = document.createElement('a');
        a.href = linkUrl;
        a.textContent = linkLabel;
        a.className = 'owner-info-cta-link';
        a.setAttribute('rel', 'noopener');
        cta.appendChild(a);
        infoBody.appendChild(cta);
      }
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
      infoDlg.classList.remove(
        'owner-info-modal--ownership',
        'owner-info-modal--flag',
        'owner-info-modal--address',
        'owner-info-modal--sff'
      );
      var fmt = btn.getAttribute('data-info-format') || '';
      if (fmt === 'ownership') infoDlg.classList.add('owner-info-modal--ownership');
      if (fmt === 'flag') infoDlg.classList.add('owner-info-modal--flag');
      if (fmt === 'address') infoDlg.classList.add('owner-info-modal--address');
      if (fmt === 'sff') infoDlg.classList.add('owner-info-modal--sff');
    }
    fillInfoBody(btn, data);
    if (typeof infoDlg.showModal === 'function') {
      infoDlg.showModal();
    } else {
      infoDlg.setAttribute('open', 'open');
    }
  }

  if (infoDlg && infoBody) {
    document.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-owner-info]');
      if (!btn || !infoButtonScope(btn)) return;
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

  var dlg = document.getElementById('ownerStatesPopover');
  if (dlg) {
    function closeStatesPopover() {
      if (typeof dlg.close === 'function') dlg.close();
    }

    function openStatesPopover() {
      if (typeof dlg.showModal === 'function') dlg.showModal();
      else dlg.setAttribute('open', '');
    }

    function isStatesOpen() {
      return !!(dlg.open || dlg.hasAttribute('open'));
    }

    document.querySelectorAll('[data-owner-states-open]').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        if (isStatesOpen()) closeStatesPopover();
        else openStatesPopover();
      });
    });
    document.querySelectorAll('[data-owner-states-close]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        closeStatesPopover();
      });
    });
    dlg.addEventListener('click', function (e) {
      if (e.target === dlg) closeStatesPopover();
    });
  }

  function initRelatedAssociates() {
    var block = document.querySelector('.owner-associates-block[data-associates-url]');
    if (!block || block.getAttribute('data-associates-loaded') === '1') return;
    var details = block.querySelector('details.owner-associates-collapsible');
    var panel = block.querySelector('[data-associates-panel]');
    var countEl = block.querySelector('.owner-associates-count');
    if (!details || !panel) return;
    var loading = false;

    function setCount(n) {
      if (!countEl) return;
      countEl.textContent = n ? ' · ' + n : '';
    }

    function fetchAssociates() {
      if (loading || block.getAttribute('data-associates-loaded') === '1') return;
      var url = block.getAttribute('data-associates-url');
      if (!url) return;
      loading = true;
      var tip = panel.querySelector('.owner-associates-loading');
      if (tip) tip.hidden = false;
      fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
        .then(function (res) {
          return res.json().then(function (data) {
            return { ok: res.ok, data: data };
          });
        })
        .then(function (out) {
          var data = out.data || {};
          var html = data.html || '';
          var count = parseInt(data.count || 0, 10) || 0;
          if (!out.ok || !html || count < 1) {
            block.hidden = true;
            return;
          }
          panel.innerHTML = html;
          setCount(count);
          block.setAttribute('data-associates-loaded', '1');
        })
        .catch(function () {
          panel.innerHTML =
            '<p class="pbj-meta-line">Could not load related associates. Try again.</p>';
        })
        .finally(function () {
          loading = false;
        });
    }

    details.addEventListener('toggle', function () {
      if (details.open) fetchAssociates();
    });
  }

  initRelatedAssociates();

  var root = document.querySelector('.owner-profile-root');
  if (!root) return;

  var table = document.getElementById('ownerFacilitiesTable');
  if (!table) return;

  var tbody = table.querySelector('tbody');
  if (!tbody) return;

  var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
  var mobileList =
    document.getElementById('ownerFacilitiesMobileList') ||
    root.querySelector('.owner-mobile-card-list--facilities');
  var mobileCards = mobileList
    ? Array.prototype.slice.call(mobileList.querySelectorAll('.owner-m-card--facility'))
    : [];
  var facilitiesSection = root.querySelector('.owner-facilities-section');
  var tableViewBtn = document.getElementById('ownerFacilitiesTableViewBtn');
  var filterInput = document.getElementById('ownerFacilitiesFilter');
  var filterInputMobile = document.getElementById('ownerFacilitiesFilterMobile');
  var stateFilter = document.getElementById('ownerFacilitiesStateFilter');
  var filterCount = document.getElementById('ownerFacilitiesFilterCount');
  var filterCountMobile = document.getElementById('ownerFacilitiesFilterCountMobile');
  var showMoreBtn = document.getElementById('ownerFacilitiesShowMore');
  var shownLabel = document.getElementById('ownerFacilitiesShownLabel');
  var totalFacilities = showMoreBtn
    ? parseInt(showMoreBtn.getAttribute('data-total') || String(rows.length), 10)
    : rows.length;
  var batchSize = showMoreBtn
    ? parseInt(showMoreBtn.getAttribute('data-batch') || '50', 10)
    : 50;
  var facilitiesUrl = showMoreBtn
    ? showMoreBtn.getAttribute('data-facilities-url') || ''
    : '';
  var nextOffset = showMoreBtn
    ? parseInt(showMoreBtn.getAttribute('data-shown') || String(rows.length), 10)
    : rows.length;
  var facilitiesLoading = false;
  var facilitiesDone = !facilitiesUrl || nextOffset >= totalFacilities;
  var sortKey = 'legal';
  var sortDir = 'asc';
  var colIndex = {
    legal: 0,
    county: 1,
    role: 2,
    hprd: 3,
    stars: 4,
    census: 5,
  };

  function refreshRowCaches() {
    rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
    mobileCards = mobileList
      ? Array.prototype.slice.call(mobileList.querySelectorAll('.owner-m-card--facility'))
      : [];
  }

  function updateShownChrome() {
    var shown = rows.length;
    if (shownLabel) {
      shownLabel.textContent = facilitiesDone
        ? shown + ' facilities'
        : 'Showing ' + shown + ' of ' + totalFacilities;
    }
    if (showMoreBtn) {
      showMoreBtn.setAttribute('data-shown', String(shown));
      showMoreBtn.hidden = !!facilitiesDone;
      showMoreBtn.disabled = !!facilitiesLoading;
      showMoreBtn.textContent = facilitiesLoading ? 'Loading…' : 'Show more';
    }
  }

  function appendHtmlBatch(data) {
    if (data.rows_html) {
      var wrap = document.createElement('tbody');
      wrap.innerHTML = data.rows_html;
      while (wrap.firstChild) tbody.appendChild(wrap.firstChild);
    }
    if (data.cards_html && mobileList) {
      var ul = document.createElement('ul');
      ul.innerHTML = data.cards_html;
      while (ul.firstChild) mobileList.appendChild(ul.firstChild);
    }
    nextOffset = parseInt(data.next_offset || nextOffset, 10) || nextOffset;
    facilitiesDone = !!data.done || nextOffset >= totalFacilities;
    refreshRowCaches();
    updateShownChrome();
  }

  function fetchFacilitiesBatch(allRemaining) {
    if (!facilitiesUrl || facilitiesDone || facilitiesLoading) {
      return Promise.resolve(false);
    }
    facilitiesLoading = true;
    updateShownChrome();
    var limit = allRemaining
      ? Math.max(batchSize, totalFacilities - nextOffset)
      : batchSize;
    var url =
      facilitiesUrl +
      (facilitiesUrl.indexOf('?') >= 0 ? '&' : '?') +
      'offset=' +
      encodeURIComponent(String(nextOffset)) +
      '&limit=' +
      encodeURIComponent(String(limit));
    return fetch(url, { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(function (res) {
        return res.json().then(function (data) {
          if (!res.ok) throw new Error('facilities batch failed');
          return data;
        });
      })
      .then(function (data) {
        appendHtmlBatch(data || {});
        return true;
      })
      .catch(function () {
        if (showMoreBtn) showMoreBtn.textContent = 'Retry';
        return false;
      })
      .finally(function () {
        facilitiesLoading = false;
        updateShownChrome();
      });
  }

  function ensureAllFacilitiesLoaded() {
    if (facilitiesDone || !facilitiesUrl) return Promise.resolve();
    return fetchFacilitiesBatch(true).then(function (ok) {
      if (!ok || facilitiesDone) return;
      return ensureAllFacilitiesLoaded();
    });
  }

  function visibleRows() {
    if (mobileCards.length && window.matchMedia('(max-width: 699px)').matches) {
      return mobileCards.filter(function (li) {
        return li.style.display !== 'none';
      });
    }
    return rows.filter(function (tr) {
      return tr.style.display !== 'none';
    });
  }

  function activeFilterQuery() {
    var qDesktop = filterInput ? String(filterInput.value || '').trim() : '';
    var qMobile = filterInputMobile ? String(filterInputMobile.value || '').trim() : '';
    return qDesktop || qMobile;
  }

  function syncFilterInputs(fromInput) {
    var q = fromInput ? String(fromInput.value || '') : '';
    if (filterInput && fromInput !== filterInput) filterInput.value = q;
    if (filterInputMobile && fromInput !== filterInputMobile) filterInputMobile.value = q;
  }

  function updateCounts() {
    var vis = visibleRows().length;
    var q = activeFilterQuery();
    var st = activeStateFilter();
    var countText = q || st ? vis + ' shown' : '';
    [filterCount, filterCountMobile].forEach(function (el) {
      if (!el) return;
      if (q || st) {
        el.hidden = false;
        el.textContent = countText;
      } else {
        el.hidden = true;
        el.textContent = '';
      }
    });
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
    syncMobileOrder();
  }

  function syncMobileOrder() {
    if (!mobileList || !mobileCards.length) return;
    rows.forEach(function (tr) {
      var key = tr.getAttribute('data-search') || '';
      for (var i = 0; i < mobileCards.length; i++) {
        if ((mobileCards[i].getAttribute('data-search') || '') === key) {
          mobileList.appendChild(mobileCards[i]);
          break;
        }
      }
    });
  }

  function activeStateFilter() {
    return stateFilter ? String(stateFilter.value || '').trim().toUpperCase() : '';
  }

  function rowMatchesFilters(tr, q, st) {
    var blob = tr.getAttribute('data-search') || tr.textContent || '';
    var matchQ = !q || blob.toLowerCase().indexOf(q) >= 0;
    var matchSt = !st || (tr.getAttribute('data-state') || '').toUpperCase() === st;
    return matchQ && matchSt;
  }

  function applyFilter() {
    var q = activeFilterQuery().toLowerCase();
    var st = activeStateFilter();
    function paint() {
      rows.forEach(function (tr) {
        tr.style.display = rowMatchesFilters(tr, q, st) ? '' : 'none';
      });
      mobileCards.forEach(function (li) {
        li.style.display = rowMatchesFilters(li, q, st) ? '' : 'none';
      });
      updateCounts();
    }
    if (q || st) {
      ensureAllFacilitiesLoaded().then(paint);
      return;
    }
    paint();
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
      ensureAllFacilitiesLoaded().then(function () {
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
  });

  if (filterInput) {
    filterInput.addEventListener('input', function () {
      syncFilterInputs(filterInput);
      applyFilter();
    });
  }
  if (filterInputMobile) {
    filterInputMobile.addEventListener('input', function () {
      syncFilterInputs(filterInputMobile);
      applyFilter();
    });
  }
  if (stateFilter) {
    stateFilter.addEventListener('change', applyFilter);
  }
  if (showMoreBtn) {
    showMoreBtn.addEventListener('click', function () {
      fetchFacilitiesBatch(false).then(function () {
        applyFilter();
      });
    });
  }

  if (tableViewBtn && facilitiesSection) {
    tableViewBtn.addEventListener('click', function () {
      var on = facilitiesSection.classList.toggle('owner-facilities-section--table-view');
      tableViewBtn.setAttribute('aria-pressed', on ? 'true' : 'false');
      tableViewBtn.textContent = on ? 'Card view' : 'Table view';
      tableViewBtn.setAttribute(
        'aria-label',
        on ? 'Switch to card view' : 'Switch to table view'
      );
    });
  }

  applySort();
  updateSortHeaders();
  applyFilter();
})();
