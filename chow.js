/**
 * CHOW monitor — client-side filter/table for /chow
 * Data: /chow_index.json (built by scripts/build_chow_index.py)
 *
 * TODO: Wire pre/post PBJ staffing comparison in detail drawer when backend is ready.
 */
(function () {
  'use strict';
  var allRecords = [];
  var summary = {};
  var meta = {};
  var filtered = [];
  var expandedId = null;
  var activeClusterFilter = null;
  var sortKey = 'effective_date';
  var sortDir = 'desc';
  var displayLimit = 50;
  var buyerNameCounts = {};
  var sellerNameCounts = {};
  var RECENT_DAYS = 365;
  var PAGE_SIZE = 50;
  var PATTERN_LABELS = {
    repeat_buyer: 'Repeat buyer',
    repeat_seller: 'Repeat seller',
    acquisition_operator: 'Acquisition Operator',
    opco: 'Opco pattern',
    complete_care: 'Complete Care',
    havencare: 'Havencare',
    harborside_seller: 'Harborside seller',
  };
  function $(id) {
    return document.getElementById(id);
  }
  function esc(s) {
    if (s == null || s === '') return '';
    var d = document.createElement('span');
    d.textContent = String(s);
    return d.innerHTML;
  }
  function formatDate(iso) {
    if (!iso) return '—';
    var p = iso.split('-');
    if (p.length !== 3) return iso;
    return p[1] + '/' + p[2] + '/' + p[0];
  }
  function formatCount(n) {
    if (n == null || n === '') return '—';
    var x = Number(n);
    if (isNaN(x)) return String(n);
    return x.toLocaleString('en-US');
  }
  function daysAgo(iso) {
    if (!iso) return Infinity;
    var d = new Date(iso + 'T12:00:00');
    if (isNaN(d.getTime())) return Infinity;
    return (Date.now() - d.getTime()) / 86400000;
  }
  var ORG_UPPER = {
    llc: 'LLC',
    llp: 'LLP',
    lp: 'LP',
    inc: 'Inc.',
    corp: 'Corp.',
    ltd: 'Ltd.',
    pllc: 'PLLC',
    pc: 'PC',
    pa: 'PA',
    dba: 'DBA',
    snf: 'SNF',
    nh: 'NH',
  };
  var SMALL_WORDS = {
    at: true,
    of: true,
    in: true,
    on: true,
    to: true,
    by: true,
    for: true,
    the: true,
    and: true,
    or: true,
    a: true,
    an: true,
  };
  function titleWord(w, isFirst) {
    if (!w) return w;
    var lower = w.toLowerCase();
    if (ORG_UPPER[lower]) return ORG_UPPER[lower];
    if (/^\d+$/.test(w)) return w;
    if (!isFirst && SMALL_WORDS[lower]) return lower;
    return lower.charAt(0).toUpperCase() + lower.slice(1);
  }
  /** Display-friendly org name (legal strings often arrive ALL CAPS). */
  function formatOrgName(name) {
    if (!name || typeof name !== 'string') return name || '';
    var trimmed = name.trim();
    if (!trimmed) return '';
    if (trimmed === trimmed.toUpperCase() && /[A-Z]/.test(trimmed) && trimmed.length > 4) {
      var words = trimmed.split(/\s+/);
      return words
        .map(function (w, idx) {
          if (/^[&,.\-()]+$/.test(w)) return w;
          var parts = w.split(/([\/\-])/);
          return parts
            .map(function (part) {
              if (/^[\/\-]$/.test(part)) return part;
              return titleWord(part, idx === 0);
            })
            .join('');
        })
        .join(' ');
    }
    return trimmed;
  }
  function buildNameCounts() {
    buyerNameCounts = {};
    sellerNameCounts = {};
    allRecords.forEach(function (r) {
      if (r.buyer_normalized) {
        buyerNameCounts[r.buyer_normalized] = (buyerNameCounts[r.buyer_normalized] || 0) + 1;
      }
      if (r.seller_normalized) {
        sellerNameCounts[r.seller_normalized] = (sellerNameCounts[r.seller_normalized] || 0) + 1;
      }
    });
  }
  function normalizeCcn(val) {
    if (!val) return '';
    return String(val).replace(/\D/g, '').slice(-6).padStart(6, '0');
  }
  function ccnFromUrl() {
    var p = new URLSearchParams(window.location.search);
    return normalizeCcn(p.get('ccn'));
  }
  function hasUrlParams() {
    var p = new URLSearchParams(window.location.search);
    return !!(
      p.get('ccn') ||
      p.get('state') ||
      p.get('q') ||
      p.get('search') ||
      p.get('buyer') ||
      p.get('seller')
    );
  }
  function applyDefaultFilters() {
    if (hasUrlParams()) return;
    var recent = $('chowRecentOnly');
    if (recent) recent.checked = true;
    displayLimit = PAGE_SIZE;
  }
  function readFilters() {
    return {
      ccnExact: ccnFromUrl(),
      q: ($('chowSearch') && $('chowSearch').value.trim().toLowerCase()) || '',
      state: ($('chowState') && $('chowState').value) || '',
      year: ($('chowYear') && $('chowYear').value) || '',
      chowType: ($('chowType') && $('chowType').value) || '',
      buyerContains: ($('chowBuyerContains') && $('chowBuyerContains').value.trim().toLowerCase()) || '',
      sellerContains: ($('chowSellerContains') && $('chowSellerContains').value.trim().toLowerCase()) || '',
      recentOnly: $('chowRecentOnly') && $('chowRecentOnly').checked,
      showAllYears: $('chowShowAllYears') && $('chowShowAllYears').checked,
      repeatBuyer: $('chowRepeatBuyer') && $('chowRepeatBuyer').checked,
      repeatSeller: $('chowRepeatSeller') && $('chowRepeatSeller').checked,
      acquisitionOperator: $('chowAcquisitionOperator') && $('chowAcquisitionOperator').checked,
      cluster: activeClusterFilter,
    };
  }
  function recordHaystack(r) {
    return [
      r.facility_display_name,
      r.ccn,
      r.buyer_org_name,
      r.seller_org_name,
      r.buyer_dba_name,
      r.seller_dba_name,
      r.buyer_enrollment_id,
      r.seller_enrollment_id,
      r.buyer_npi,
      r.seller_npi,
      r.buyer_associate_id,
      r.seller_associate_id,
      r.state,
      r.chow_type,
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();
  }
  function matchesCluster(r, cluster) {
    if (!cluster) return true;
    var key = cluster.filter_key;
    var val = cluster.filter_value;
    if (key === 'repeat_buyer' && val) return r.buyer_normalized === val;
    if (key === 'repeat_seller' && val) return r.seller_normalized === val;
    if (key && r.pattern_tags && r.pattern_tags.indexOf(key) >= 0) return true;
    return false;
  }
  function applyFilters() {
    var f = readFilters();
    filtered = allRecords.filter(function (r) {
      if (f.ccnExact) {
        if (normalizeCcn(r.ccn) !== f.ccnExact) return false;
      }
      if (f.state && r.state !== f.state) return false;
      if (f.year && String(r.effective_year) !== f.year) return false;
      if (f.chowType && (r.chow_type || '') !== f.chowType) return false;
      if (f.buyerContains) {
        var b = ((r.buyer_org_name || '') + ' ' + (r.buyer_dba_name || '')).toLowerCase();
        if (b.indexOf(f.buyerContains) < 0) return false;
      }
      if (f.sellerContains) {
        var s = ((r.seller_org_name || '') + ' ' + (r.seller_dba_name || '')).toLowerCase();
        if (s.indexOf(f.sellerContains) < 0) return false;
      }
      if (f.recentOnly && !f.showAllYears && daysAgo(r.effective_date) > RECENT_DAYS) return false;
      if (f.repeatBuyer && (!r.pattern_tags || r.pattern_tags.indexOf('repeat_buyer') < 0)) return false;
      if (f.repeatSeller && (!r.pattern_tags || r.pattern_tags.indexOf('repeat_seller') < 0)) return false;
      if (f.acquisitionOperator && (!r.pattern_tags || r.pattern_tags.indexOf('acquisition_operator') < 0)) return false;
      if (f.cluster && !matchesCluster(r, f.cluster)) return false;
      if (f.q && recordHaystack(r).indexOf(f.q) < 0) return false;
      return true;
    });
    sortFiltered();
    renderTable();
    updateResultMeta();
    renderTopParties();
  }
  function updateResultMeta() {
    var metaEl = $('chowResultMeta');
    if (!metaEl) return;
    var shown = Math.min(filtered.length, displayLimit);
    var parts = [
      shown.toLocaleString() + ' of ' + filtered.length.toLocaleString() + ' matching',
      '(' + allRecords.length.toLocaleString() + ' total in index)',
    ];
    if ($('chowRecentOnly') && $('chowRecentOnly').checked && !($('chowShowAllYears') && $('chowShowAllYears').checked)) {
      parts.push('· last 12 months');
    }
    if (activeClusterFilter && activeClusterFilter.label) {
      parts.push('· cluster: ' + activeClusterFilter.label);
    }
    metaEl.textContent = parts.join(' ');
  }
  function sortValue(r, key) {
    var v = r[key];
    if (v == null) return '';
    if (key === 'effective_date') return v;
    return String(v).toLowerCase();
  }
  function sortFiltered() {
    if (!sortKey) return;
    var dir = sortDir === 'asc' ? 1 : -1;
    filtered.sort(function (a, b) {
      var av = sortValue(a, sortKey);
      var bv = sortValue(b, sortKey);
      if (av < bv) return -1 * dir;
      if (av > bv) return 1 * dir;
      return 0;
    });
  }
  function updateSortHeaders() {
    var table = $('chowTable');
    if (!table) return;
    table.querySelectorAll('th.sortable').forEach(function (th) {
      th.classList.remove('sort-asc', 'sort-desc');
      if (th.getAttribute('data-sort') === sortKey) {
        th.classList.add(sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
      }
    });
  }
  function bindSortHeaders() {
    var table = $('chowTable');
    if (!table) return;
    table.querySelectorAll('th.sortable').forEach(function (th) {
      th.addEventListener('click', function (e) {
        e.stopPropagation();
        var key = th.getAttribute('data-sort');
        if (!key) return;
        if (sortKey === key) {
          sortDir = sortDir === 'asc' ? 'desc' : 'asc';
        } else {
          sortKey = key;
          sortDir = key === 'effective_date' ? 'desc' : 'asc';
        }
        sortFiltered();
        updateSortHeaders();
        renderTable();
      });
    });
    updateSortHeaders();
  }
  function renderCards() {
    var grid = $('chowCards');
    if (!grid || !summary) return;
    var cards = [
      { label: 'Total CHOW records', value: summary.total_records },
      { label: 'Date range', value: (summary.date_min && summary.date_max) ? formatDate(summary.date_min) + ' – ' + formatDate(summary.date_max) : '—' },
      { label: 'States represented', value: summary.states_count },
      { label: 'Most recent CHOW', value: formatDate(summary.most_recent_chow_date) },
      { label: 'Unique buyer entities', value: summary.unique_buyers },
      { label: 'Unique seller entities', value: summary.unique_sellers },
      { label: 'Unique CCNs', value: summary.unique_ccns },
      {
        label: 'Largest year (count)',
        value: summary.largest_year
          ? summary.largest_year + ' (' + (summary.largest_year_count || 0).toLocaleString() + ')'
          : '—',
      },
    ];
    if (meta.is_ct_only) {
      cards.push({ label: '2024 CT CHOWs', value: summary.ct_2024_count });
      cards.push({ label: '2025 CT CHOWs', value: summary.ct_2025_count });
      if (summary.acquisition_operator_count) {
        cards.push({
          label: 'Acquisition Operator LLC (buyer pattern)',
          value: summary.acquisition_operator_count,
        });
      }
    }
    grid.innerHTML = cards
      .map(function (c) {
        return (
          '<div class="chow-card"><div class="label">' +
          esc(c.label) +
          '</div><div class="value">' +
          esc(
            typeof c.value === 'number'
              ? formatCount(c.value)
              : String(c.value != null ? c.value : '—')
          ) +
          '</div></div>'
        );
      })
      .join('');
  }

  function computeTopPartiesFromRecords(records, limit) {
    function agg(side) {
      var counts = {};
      var meta = {};
      var ccns = {};
      var normKey = side + '_normalized';
      var nameKey = side + '_org_name';
      var assocKey = side + '_associate_id';
      var urlKey = side + '_owner_url';
      records.forEach(function (r) {
        var norm = r[normKey];
        if (!norm) return;
        counts[norm] = (counts[norm] || 0) + 1;
        if (r.ccn) {
          if (!ccns[norm]) ccns[norm] = {};
          ccns[norm][r.ccn] = true;
        }
        if (!meta[norm]) {
          meta[norm] = {
            name: r[nameKey] || norm,
            count: 0,
            owner_url: r[urlKey] || '',
            associate_id: r[assocKey] || '',
            normalized: norm,
          };
        }
      });
      return Object.keys(counts)
        .sort(function (a, b) {
          return counts[b] - counts[a];
        })
        .slice(0, limit)
        .map(function (norm) {
          var m = meta[norm];
          return {
            name: m.name,
            count: counts[norm],
            facility_count: ccns[norm] ? Object.keys(ccns[norm]).length : 0,
            owner_url: m.owner_url,
            associate_id: m.associate_id,
            normalized: norm,
          };
        });
    }
    return { buyers: agg('buyer'), sellers: agg('seller') };
  }

  function partyFilterUrl(p, side, state) {
    var q = '/chow?' + side + '=' + encodeURIComponent(p.name || '');
    if (state) q += '&state=' + encodeURIComponent(state);
    return q;
  }

  function enrichPartiesWithFacilities(parties, side, records) {
    if (!parties || !parties.length) return parties;
    var normKey = side + '_normalized';
    var ccnByNorm = {};
    records.forEach(function (r) {
      var norm = r[normKey];
      if (!norm) return;
      var ccn = r.ccn;
      if (!ccn) return;
      if (!ccnByNorm[norm]) ccnByNorm[norm] = {};
      ccnByNorm[norm][ccn] = true;
    });
    return parties.map(function (p) {
      var norm = p.normalized;
      var fc = norm && ccnByNorm[norm] ? Object.keys(ccnByNorm[norm]).length : 0;
      return Object.assign({}, p, { facility_count: fc || p.facility_count || 0 });
    });
  }

  function recordsForParty(p, side, state) {
    var normKey = side + '_normalized';
    var norm = p.normalized;
    if (!norm) return [];
    return allRecords
      .filter(function (r) {
        if (r[normKey] !== norm) return false;
        if (state && r.state !== state) return false;
        return true;
      })
      .sort(function (a, b) {
        return (b.effective_date || '').localeCompare(a.effective_date || '');
      });
  }

  function facilityLinkFromRecord(r) {
    var ccn = String(r.ccn || '').replace(/\D/g, '').slice(-6).padStart(6, '0');
    var fac = formatOrgName(r.facility_display_name || r.buyer_dba_name || ccn || '—');
    if (ccn && /^\d{6}$/.test(ccn)) {
      return '<a href="/provider/' + esc(ccn) + '">' + esc(fac) + '</a>';
    }
    return esc(fac);
  }

  function renderPartyEventsCell(p, side, state) {
    var events = recordsForParty(p, side, state);
    var n = events.length;
    if (!n) return '—';
    var href = partyFilterUrl(p, side, state);
    var items = events.slice(0, 8).map(function (r) {
      var eff = formatDate(r.effective_date);
      var fac = facilityLinkFromRecord(r);
      var other;
      var otherLbl;
      if (side === 'buyer') {
        other = esc(formatOrgName(r.seller_org_name || '—'));
        otherLbl = 'seller';
      } else {
        other = esc(formatOrgName(r.buyer_org_name || r.buyer_dba_name || '—'));
        otherLbl = 'buyer';
      }
      return (
        '<li><span class="chow-party-ev-date">' +
        esc(eff) +
        '</span> ' +
        fac +
        ' <span class="chow-party-ev-muted">(' +
        otherLbl +
        ': ' +
        other +
        ')</span></li>'
      );
    });
    if (n > 8) {
      items.push(
        '<li class="chow-party-ev-more"><a href="' +
          esc(href) +
          '">All ' +
          formatCount(n) +
          ' events on CHOW monitor</a></li>'
      );
    }
    return (
      '<details class="chow-party-events"><summary class="chow-party-events-summary">' +
      '<a href="' +
      esc(href) +
      '" onclick="event.stopPropagation()">' +
      formatCount(n) +
      ' event' +
      (n === 1 ? '' : 's') +
      '</a></summary><ul class="chow-party-events-list">' +
      items.join('') +
      '</ul></details>'
    );
  }

  function renderPartyFacilitiesCell(p, side, state) {
    var events = recordsForParty(p, side, state);
    var byCcn = {};
    events.forEach(function (r) {
      var ccn = String(r.ccn || '').replace(/\D/g, '').slice(-6).padStart(6, '0');
      if (!ccn || !/^\d{6}$/.test(ccn)) return;
      if (!byCcn[ccn]) {
        byCcn[ccn] = formatOrgName(r.facility_display_name || r.buyer_dba_name || ccn);
      }
    });
    var keys = Object.keys(byCcn);
    var n = keys.length;
    if (!n) return '—';
    if (n === 1) {
      var c0 = keys[0];
      return '<a href="/provider/' + esc(c0) + '">' + esc(byCcn[c0]) + '</a>';
    }
    var items = keys
      .sort(function (a, b) {
        return byCcn[a].localeCompare(byCcn[b]);
      })
      .slice(0, 8)
      .map(function (ccn) {
        return '<li><a href="/provider/' + esc(ccn) + '">' + esc(byCcn[ccn]) + '</a></li>';
      });
    if (n > 8) {
      items.push('<li class="chow-party-ev-more">+ ' + formatCount(n - 8) + ' more facilities</li>');
    }
    return (
      '<details class="chow-party-events"><summary class="chow-party-events-summary">' +
      formatCount(n) +
      ' facilities</summary><ul class="chow-party-events-list">' +
      items.join('') +
      '</ul></details>'
    );
  }

  function ownerPageLink(p) {
    if (!p.owner_url) return '—';
    var pac = String(p.associate_id || '').trim();
    var label = pac.length === 10 ? 'Owner page · ' + pac : 'Owner page';
    return (
      '<a href="' +
      esc(p.owner_url) +
      '" title="PBJ320 owner/enrollment profile (CMS 10-digit PAC)">' +
      esc(label) +
      '</a>'
    );
  }

  function renderTopPartiesTable(parties, side, state) {
    if (!parties || !parties.length) {
      return '<tr><td colspan="5" class="chow-empty">No data for this view.</td></tr>';
    }
    return parties
      .map(function (p) {
        var name = formatOrgName(p.name || '—');
        var href = partyFilterUrl(p, side, state);
        var role = side === 'buyer' ? 'Buyer' : 'Seller';
        return (
          '<tr><td class="chow-org-name"><a href="' +
          esc(href) +
          '">' +
          esc(name) +
          '</a></td><td>' +
          esc(role) +
          '</td><td class="chow-party-events-col">' +
          renderPartyEventsCell(p, side, state) +
          '</td><td class="chow-party-facilities-col">' +
          renderPartyFacilitiesCell(p, side, state) +
          '</td><td class="links">' +
          ownerPageLink(p) +
          '</td></tr>'
        );
      })
      .join('');
  }

  function renderTopParties() {
    var stateEl = $('chowState');
    var state = stateEl && stateEl.value ? stateEl.value : '';
    var scopeEl = $('chowTopScopeLabel');
    var tbody = $('chowTopPartiesBody');
    var noteEl = $('chowTopPartiesNote');
    var limit = state ? 8 : 10;
    var source = state ? allRecords.filter(function (r) { return r.state === state; }) : allRecords;
    var block;
    if (state && summary.top_by_state && summary.top_by_state[state]) {
      block = summary.top_by_state[state];
    } else if (!state && summary.top_buyers && summary.top_sellers) {
      block = { buyers: summary.top_buyers, sellers: summary.top_sellers };
    } else {
      block = computeTopPartiesFromRecords(source, limit);
    }
    var buyers = enrichPartiesWithFacilities((block.buyers || []).slice(0, limit), 'buyer', source);
    var sellers = enrichPartiesWithFacilities((block.sellers || []).slice(0, limit), 'seller', source);
    var maxCount = 0;
    buyers.concat(sellers).forEach(function (p) {
      maxCount = Math.max(maxCount, p.count || 0);
    });
    var flatCounts = maxCount <= 1;
    var thead = $('chowTopPartiesHead');
    if (thead) {
      thead.innerHTML =
        '<tr><th>Organization</th><th>Role</th><th>CHOW events</th><th>Facilities</th><th>Owner PAC</th></tr>';
    }
    var dateNote = '';
    if (summary.date_min && summary.date_max) {
      dateNote =
        ' Effective dates: ' +
        formatDate(summary.date_min) +
        ' – ' +
        formatDate(summary.date_max) +
        '.';
    }
    if (noteEl) {
      noteEl.textContent = flatCounts
        ? 'No organization appears more than once in this view—expand CHOW events for dates and facilities.' +
          dateNote
        : 'Expand CHOW events for transaction detail; Owner PAC links to PBJ320 (not CMS.gov).' +
          dateNote +
          ' Screening only.';
    }
    if (tbody) {
      tbody.innerHTML =
        renderTopPartiesTable(buyers, 'buyer', state, flatCounts) +
        renderTopPartiesTable(sellers, 'seller', state, flatCounts);
    }
    if (scopeEl) {
      scopeEl.textContent = state ? '(' + state + ')' : '(national)';
    }
  }

  function populateFilterDropdowns() {
    var states = {};
    var years = {};
    var types = {};
    allRecords.forEach(function (r) {
      if (r.state) states[r.state] = true;
      if (r.effective_year) years[r.effective_year] = true;
      if (r.chow_type) types[r.chow_type] = true;
    });
    function fillSelect(el, items, labelAll) {
      if (!el) return;
      var opts = '<option value="">' + esc(labelAll) + '</option>';
      items.sort().forEach(function (v) {
        opts += '<option value="' + esc(String(v)) + '">' + esc(String(v)) + '</option>';
      });
      el.innerHTML = opts;
    }
    fillSelect($('chowState'), Object.keys(states), 'All states');
    fillSelect(
      $('chowYear'),
      Object.keys(years).map(Number).sort(function (a, b) { return b - a; }),
      'All years'
    );
    fillSelect($('chowType'), Object.keys(types), 'All CHOW types');
  }
  function linkHtml(href, text) {
    if (!href || !text) return '';
    return '<a href="' + esc(href) + '">' + esc(text) + '</a>';
  }
  function renderLinks(r) {
    var parts = [];
    if (r.provider_url) parts.push(linkHtml(r.provider_url, 'Provider'));
    if (r.buyer_owner_url) parts.push(linkHtml(r.buyer_owner_url, 'Buyer'));
    if (r.seller_owner_url) parts.push(linkHtml(r.seller_owner_url, 'Seller'));
    return parts.length ? parts.join(' ') : '—';
  }
  function patternBadgesHtml(r) {
    var tags = r.pattern_tags || [];
    if (!tags.length) return '—';
    return (
      '<div class="chow-partner-badges">' +
      tags
        .map(function (t) {
          var cls = 'chow-badge-pattern';
          if (t === 'repeat_buyer') cls = 'chow-badge-repeat-buyer';
          if (t === 'repeat_seller') cls = 'chow-badge-repeat-seller';
          return '<span class="chow-badge ' + cls + '" title="Name pattern in CHOW data—not confirmed partnership">' + esc(PATTERN_LABELS[t] || t) + '</span>';
        })
        .join('') +
      '</div>'
    );
  }
  function partnerNotesHtml(r) {
    var notes = [];
    if (r.buyer_normalized && buyerNameCounts[r.buyer_normalized] > 1) {
      notes.push(
        'Buyer name appears in <strong>' +
          buyerNameCounts[r.buyer_normalized] +
          '</strong> CHOW records (same normalized name—not confirmed common ownership).'
      );
    }
    if (r.seller_normalized && sellerNameCounts[r.seller_normalized] > 1) {
      notes.push(
        'Seller name appears in <strong>' +
          sellerNameCounts[r.seller_normalized] +
          '</strong> CHOW records (same normalized name—not confirmed common ownership).'
      );
    }
    if (!notes.length) return '';
    var buttons = '';
    if (r.buyer_org_name) {
      buttons +=
        '<button type="button" class="chow-btn chow-btn-secondary chow-filter-buyer" data-name="' +
        esc(r.buyer_org_name) +
        '">Filter by this buyer</button>';
    }
    if (r.seller_org_name) {
      buttons +=
        '<button type="button" class="chow-btn chow-btn-secondary chow-filter-seller" data-name="' +
        esc(r.seller_org_name) +
        '">Filter by this seller</button>';
    }
    return (
      '<div class="chow-detail-partner"><strong>Name-pattern screening</strong><p>' +
      notes.join(' ') +
      '</p>' +
      buttons +
      '<p style="margin:0.5rem 0 0;font-size:0.8rem;color:#94a3b8;">PBJ320 does not infer buy–sell partnerships or control groups from CHOW alone. Confirm with CMS all-owner records.</p></div>'
    );
  }
  function renderDetailRow(r) {
    var fields = [
      ['Facility / DBA', formatOrgName(r.facility_display_name || r.buyer_dba_name)],
      ['CCN', r.ccn],
      ['State', r.state],
      ['Effective date', formatDate(r.effective_date)],
      ['Buyer legal organization', formatOrgName(r.buyer_org_name)],
      ['Buyer DBA', formatOrgName(r.buyer_dba_name)],
      ['Buyer enrollment ID', r.buyer_enrollment_id],
      ['Buyer NPI', r.buyer_npi],
      ['Buyer PAC / associate ID', r.buyer_associate_id],
      ['Seller legal organization', formatOrgName(r.seller_org_name)],
      ['Seller DBA', formatOrgName(r.seller_dba_name)],
      ['Seller enrollment ID', r.seller_enrollment_id],
      ['Seller NPI', r.seller_npi],
      ['Seller PAC / associate ID', r.seller_associate_id],
      ['CHOW type', r.chow_type],
    ];
    var grid = fields
      .map(function (pair) {
        var v = pair[1];
        if (v == null || v === '') v = '—';
        return '<dt>' + esc(pair[0]) + '</dt><dd>' + esc(v) + '</dd>';
      })
      .join('');
    return (
      partnerNotesHtml(r) +
      '<dl class="chow-detail-grid">' +
      grid +
      '</dl>' +
      '<p class="chow-detail-links"><strong>Profiles:</strong> ' +
      renderLinks(r) +
      '</p>' +
      (r.pattern_tags && r.pattern_tags.length
        ? '<p><strong>Pattern tags:</strong> ' + esc(r.pattern_tags.join(', ')) + '</p>'
        : '') +
      '<p class="chow-detail-placeholder">Historical PBJ staffing comparison coming later. ' +
      '<!-- TODO: pre/post CHOW HPRD, RN, aide, weekend staffing -->' +
      '</p>'
    );
  }
  function renderTable() {
    var tbody = $('chowTableBody');
    var loadWrap = $('chowLoadMoreWrap');
    if (!tbody) return;
    if (!filtered.length) {
      tbody.innerHTML =
        '<tr><td colspan="9" class="chow-empty">No records match the current filters.</td></tr>';
      if (loadWrap) loadWrap.style.display = 'none';
      return;
    }
    var slice = filtered.slice(0, displayLimit);
    var html = '';
    slice.forEach(function (r) {
      var id = r.chow_id;
      var expanded = expandedId === id;
      html +=
        '<tr class="chow-row' +
        (expanded ? ' expanded' : '') +
        '" data-chow-id="' +
        esc(id) +
        '">' +
        '<td class="chow-col-expand" aria-hidden="true"></td>' +
        '<td>' +
        esc(formatDate(r.effective_date)) +
        '</td>' +
        '<td>' +
        esc(r.state || '—') +
        '</td>' +
        '<td>' +
        (r.provider_url ? linkHtml(r.provider_url, r.ccn) : esc(r.ccn || '—')) +
        '</td>' +
        '<td class="chow-org-name">' +
        esc(formatOrgName(r.facility_display_name || r.buyer_dba_name || '—')) +
        '</td>' +
        '<td class="chow-org-name">' +
        esc(formatOrgName(r.buyer_org_name || '—')) +
        '</td>' +
        '<td class="chow-org-name">' +
        esc(formatOrgName(r.seller_org_name || '—')) +
        '</td>' +
        '<td>' +
        patternBadgesHtml(r) +
        '</td>' +
        '<td class="links">' +
        renderLinks(r) +
        '</td>' +
        '</tr>';
      if (expanded) {
        html +=
          '<tr class="chow-detail-row"><td colspan="9">' +
          renderDetailRow(r) +
          '</td></tr>';
      }
    });
    tbody.innerHTML = html;
    if (loadWrap) {
      loadWrap.style.display = filtered.length > displayLimit ? 'block' : 'none';
    }
    tbody.querySelectorAll('.chow-row').forEach(function (row) {
      row.addEventListener('click', function () {
        var cid = row.getAttribute('data-chow-id');
        expandedId = expandedId === cid ? null : cid;
        renderTable();
      });
    });
    tbody.querySelectorAll('.chow-filter-buyer').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var el = $('chowBuyerContains');
        if (el) el.value = btn.getAttribute('data-name') || '';
        activeClusterFilter = null;
        displayLimit = PAGE_SIZE;
        applyFilters();
      });
    });
    tbody.querySelectorAll('.chow-filter-seller').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var el = $('chowSellerContains');
        if (el) el.value = btn.getAttribute('data-name') || '';
        activeClusterFilter = null;
        displayLimit = PAGE_SIZE;
        applyFilters();
      });
    });
  }
  function renderClusters() {
    var tbody = $('chowClustersBody');
    if (!tbody || !summary.clusters) return;
    tbody.innerHTML = summary.clusters
      .map(function (c, idx) {
        var ex = (c.examples || []).map(formatOrgName).join('; ') || '—';
        return (
          '<tr>' +
          '<td>' +
          esc(c.label) +
          '</td>' +
          '<td>' +
          formatCount(c.count) +
          '</td>' +
          '<td>' +
          esc(ex) +
          '</td>' +
          '<td><button type="button" data-cluster-idx="' +
          idx +
          '">Filter table</button></td>' +
          '</tr>'
        );
      })
      .join('');
    tbody.querySelectorAll('button[data-cluster-idx]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var idx = parseInt(btn.getAttribute('data-cluster-idx'), 10);
        activeClusterFilter = summary.clusters[idx];
        clearFilterInputsExceptCluster();
        displayLimit = Math.max(PAGE_SIZE, (summary.clusters[idx].count || 0) + 10);
        applyFilters();
        var table = $('chowTableScroll');
        if (table && table.scrollIntoView) table.scrollIntoView({ behavior: 'smooth' });
      });
    });
  }
  function clearFilterInputsExceptCluster() {
    ['chowSearch', 'chowBuyerContains', 'chowSellerContains'].forEach(function (id) {
      var el = $(id);
      if (el) el.value = '';
    });
    ['chowState', 'chowYear', 'chowType'].forEach(function (id) {
      var el = $(id);
      if (el) el.value = '';
    });
    ['chowRepeatBuyer', 'chowRepeatSeller', 'chowAcquisitionOperator'].forEach(function (id) {
      var el = $(id);
      if (el) el.checked = false;
    });
  }
  function bindFilterEvents() {
    var ids = [
      'chowSearch',
      'chowState',
      'chowYear',
      'chowType',
      'chowBuyerContains',
      'chowSellerContains',
      'chowRecentOnly',
      'chowShowAllYears',
      'chowRepeatBuyer',
      'chowRepeatSeller',
      'chowAcquisitionOperator',
    ];
    ids.forEach(function (id) {
      var el = $(id);
      if (!el) return;
      var ev = el.tagName === 'INPUT' && (el.type === 'text' || el.type === 'search') ? 'input' : 'change';
      el.addEventListener(ev, function () {
        activeClusterFilter = null;
        displayLimit = PAGE_SIZE;
        var showAll = $('chowShowAllYears');
        var recent = $('chowRecentOnly');
        if (id === 'chowShowAllYears' && showAll && showAll.checked && recent) {
          recent.checked = false;
        }
        if (id === 'chowRecentOnly' && recent && recent.checked && showAll) {
          showAll.checked = false;
        }
        applyFilters();
      });
    });
    var clearBtn = $('chowClearFilters');
    if (clearBtn) {
      clearBtn.addEventListener('click', function () {
        activeClusterFilter = null;
        clearFilterInputsExceptCluster();
        var recent = $('chowRecentOnly');
        if (recent) recent.checked = true;
        var showAll = $('chowShowAllYears');
        if (showAll) showAll.checked = false;
        displayLimit = PAGE_SIZE;
        applyFilters();
      });
    }
    var loadMore = $('chowLoadMore');
    if (loadMore) {
      loadMore.addEventListener('click', function () {
        displayLimit += PAGE_SIZE;
        renderTable();
        updateResultMeta();
      });
    }
  }
  function applyUrlParams() {
    var params = new URLSearchParams(window.location.search);
    var ccn = params.get('ccn');
    var state = params.get('state');
    var q = params.get('q') || params.get('search');
    if (ccn && $('chowSearch')) $('chowSearch').value = ccn;
    if (q && $('chowSearch') && !ccn) $('chowSearch').value = q;
    if (state && $('chowState')) $('chowState').value = state.toUpperCase().slice(0, 2);
    var buyer = params.get('buyer');
    if (buyer && $('chowBuyerContains')) $('chowBuyerContains').value = buyer;
    var seller = params.get('seller');
    if (seller && $('chowSellerContains')) $('chowSellerContains').value = seller;
    if (hasUrlParams()) {
      var recent = $('chowRecentOnly');
      if (recent) recent.checked = false;
    }
  }
  function initScopeNote() {
    var el = $('chowScopeNote');
    if (el && meta.scope_note) {
      el.textContent = meta.scope_note;
      el.style.display = 'block';
    }
  }
  function load() {
    var loading = $('chowLoading');
    fetch('/chow_index.json')
      .then(function (r) {
        if (!r.ok) throw new Error('Failed to load CHOW data');
        return r.json();
      })
      .then(function (data) {
        meta = data.meta || {};
        summary = data.summary || {};
        allRecords = data.records || [];
        buildNameCounts();
        if (loading) loading.style.display = 'none';
        initScopeNote();
        renderCards();
        renderTopParties();
        populateFilterDropdowns();
        applyDefaultFilters();
        applyUrlParams();
        renderClusters();
        bindFilterEvents();
        bindSortHeaders();
        applyFilters();
      })
      .catch(function (err) {
        if (loading) {
          loading.textContent = 'Could not load CHOW data. ' + (err.message || '');
        }
      });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', load);
  } else {
    load();
  }
})();
