/**
 * Desktop inline entity/state switcher on /entity and /state pages.
 * Rows: title on line 1; meta on line 2 (entity NH count, or state HPRD + NH count).
 */
(function () {
  'use strict';

  var INDEX_KEY = 'pbj-page-switcher-index-v4';
  var DESKTOP_MIN = 769;
  var SMALL_WORDS = /^(of|at|and|the|for|in|or|on|to|a|an)$/i;

  function escapeHtml(s) {
    var div = document.createElement('div');
    div.textContent = s == null ? '' : String(s);
    return div.innerHTML;
  }

  function titleCase(str) {
    if (!str) return '';
    var words = String(str).match(/\S+/g) || [];
    return words
      .map(function (word, i) {
        if (i === 0) return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
        if (SMALL_WORDS.test(word)) return word.toLowerCase();
        if (/^[A-Z]+-[A-Z]/.test(word)) return word;
        return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
      })
      .join(' ');
  }

  function minQueryLen(mode, q) {
    var s = String(q || '').trim();
    if (!s) return mode === 'state' ? 1 : 2;
    if (/^\d+$/.test(s)) return 1;
    return mode === 'state' ? 1 : 2;
  }

  function formatHprd(val) {
    if (val == null || isNaN(val)) return null;
    return (Math.round(Number(val) * 100) / 100).toFixed(2);
  }

  function formatCount(n) {
    if (n == null || isNaN(n)) return null;
    return Number(n).toLocaleString();
  }

  function buildStateFacilityCounts(facilities) {
    var counts = {};
    for (var i = 0; i < (facilities || []).length; i++) {
      var abbr = String((facilities[i] && facilities[i].s) || '').trim().toUpperCase();
      if (!abbr) continue;
      counts[abbr] = (counts[abbr] || 0) + 1;
    }
    return counts;
  }

  function buildStateHprdMap(stateHprd) {
    var map = {};
    var src = stateHprd || {};
    for (var abbr in src) {
      if (!Object.prototype.hasOwnProperty.call(src, abbr)) continue;
      var key = String(abbr || '').trim().toUpperCase();
      if (!key) continue;
      var arr = src[abbr];
      if (!arr || !arr.length) continue;
      var hprd = Number(arr[arr.length - 1]);
      if (!isNaN(hprd)) map[key] = hprd;
    }
    return map;
  }

  function loadIndex() {
    return Promise.all([
      fetch('/search_index.json', { credentials: 'same-origin' }).then(function (r) {
        if (!r.ok) throw new Error('index');
        return r.json();
      }),
      fetch('/state_historical_data.json', { credentials: 'same-origin' })
        .then(function (r) {
          return r.ok ? r.json() : {};
        })
        .catch(function () {
          return {};
        }),
    ])
      .then(function (parts) {
        var data = parts[0] || {};
        var stateHprd = parts[1] || {};
        var slim = {
          e: data.e || [],
          s: data.s || [],
          stateCounts: buildStateFacilityCounts(data.f || []),
          stateHprd: buildStateHprdMap(stateHprd),
        };
        try {
          sessionStorage.setItem(INDEX_KEY, JSON.stringify(slim));
        } catch (err) {
          /* quota */
        }
        return slim;
      })
      .catch(function () {
        try {
          var cached = sessionStorage.getItem(INDEX_KEY);
          if (cached) return JSON.parse(cached);
        } catch (e3) {
          /* ignore */
        }
        return { e: [], s: [], stateCounts: {}, stateHprd: {} };
      });
  }

  function entityScore(row, q) {
    if (!row || !q) return 0;
    var ql = String(q).toLowerCase().trim();
    if (!ql) return 0;
    var name = String(row.n || '').toLowerCase();
    var idStr = row.id != null ? String(row.id) : '';
    var linkStr = row.linkId != null ? String(row.linkId) : '';
    if (idStr === ql || linkStr === ql) return 1000;
    if (
      (idStr && idStr.indexOf(ql) === 0) ||
      (linkStr && linkStr.indexOf(ql) === 0)
    ) {
      return 900;
    }
    if (name.indexOf(ql) === 0) return 800;
    var wordRe = new RegExp(
      '(^|[\\s\\-])' + ql.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'),
      'i'
    );
    if (wordRe.test(row.n || '')) return 700;
    if (name.indexOf(ql) !== -1) return 100;
    if (
      (idStr && idStr.indexOf(ql) !== -1) ||
      (linkStr && linkStr.indexOf(ql) !== -1)
    ) {
      return 500;
    }
    return 0;
  }

  function stateScore(row, q) {
    if (!row || !q) return 0;
    var name = String(row.n || '').toLowerCase();
    var abbr = String(row.abbr || '').toLowerCase();
    var ql = String(q).toLowerCase().trim();
    if (!ql) return 0;
    if (abbr === ql) return 1000;
    if (abbr.indexOf(ql) === 0) return 900;
    if (name.indexOf(ql) === 0) return 800;
    var wordRe = new RegExp(
      '(^|[\\s\\-])' + ql.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'),
      'i'
    );
    if (wordRe.test(row.n || '')) return 700;
    if (abbr.indexOf(ql) !== -1) return 500;
    if (name.indexOf(ql) !== -1) return 100;
    return 0;
  }

  function buildEntityResults(index, q, limit) {
    var hits = [];
    var seen = {};
    var ql = String(q || '').trim();
    for (var i = 0; i < (index.e || []).length; i++) {
      var row = index.e[i];
      if (!row || row.id == null) continue;
      var score = entityScore(row, ql);
      if (!score) continue;
      var id = row.linkId != null ? row.linkId : row.id;
      if (seen[id]) continue;
      seen[id] = true;
      hits.push({ row: row, id: id, score: score });
    }
    hits.sort(function (a, b) {
      if (b.score !== a.score) return b.score - a.score;
      return String(a.row.n || '').localeCompare(String(b.row.n || ''));
    });
    var out = [];
    for (var j = 0; j < hits.length && j < limit; j++) {
      var h = hits[j];
      var fc = h.row.fc != null ? Number(h.row.fc) : null;
      var title = titleCase(h.row.n || 'Chain');
      var meta = '';
      if (fc != null && !isNaN(fc) && fc > 0) {
        meta =
          formatCount(fc) +
          ' nursing home' +
          (fc === 1 ? '' : 's');
      }
      out.push({
        url: '/entity/' + encodeURIComponent(String(h.id)),
        title: title,
        meta: meta,
      });
    }
    return out;
  }

  function buildStateResults(index, q, limit) {
    var hits = [];
    var ql = String(q || '').trim();
    var stateCounts = index.stateCounts || {};
    var stateHprd = index.stateHprd || index.stateMetrics || {};
    for (var i = 0; i < (index.s || []).length; i++) {
      var row = index.s[i];
      if (!row || !row.abbr) continue;
      var score = stateScore(row, ql);
      if (!score) continue;
      hits.push({ row: row, score: score });
    }
    hits.sort(function (a, b) {
      if (b.score !== a.score) return b.score - a.score;
      return String(a.row.n || a.row.abbr || '').localeCompare(
        String(b.row.n || b.row.abbr || '')
      );
    });
    var out = [];
    for (var k = 0; k < hits.length && k < limit; k++) {
      var st = hits[k].row;
      var abbr = String(st.abbr || '').trim().toUpperCase();
      var slug = (st.n || '').toLowerCase().replace(/\s+/g, '-');
      var url = slug
        ? '/state/' + encodeURIComponent(slug)
        : '/state/' + encodeURIComponent(st.abbr);
      var hprdVal = stateHprd[abbr];
      if (hprdVal && typeof hprdVal === 'object') hprdVal = hprdVal.hprd;
      var parts = [];
      var hprdStr = formatHprd(hprdVal);
      if (hprdStr) parts.push(hprdStr + ' HPRD');
      var nhStr = formatCount(stateCounts[abbr]);
      if (nhStr) parts.push(nhStr + ' nursing homes');
      out.push({
        url: url,
        title: st.n || st.abbr,
        meta: parts.join(' \u00b7 '),
      });
    }
    return out;
  }

  function renderResults(listEl, items, emptyMsg) {
    if (!items.length) {
      listEl.innerHTML =
        '<li><span class="pbj-page-header-switcher-empty">' +
        escapeHtml(emptyMsg || 'No matches') +
        '</span></li>';
      listEl.setAttribute('data-open', 'true');
      return;
    }
    var html = '';
    for (var i = 0; i < items.length; i++) {
      var it = items[i];
      html +=
        '<li><a href="' +
        escapeHtml(it.url) +
        '" role="option" class="pbj-page-header-switcher-option">' +
        '<span class="pbj-page-header-switcher-option-title">' +
        escapeHtml(it.title) +
        '</span>' +
        (it.meta
          ? '<span class="pbj-page-header-switcher-option-meta">' +
            escapeHtml(it.meta) +
            '</span>'
          : '') +
        '</a></li>';
    }
    listEl.innerHTML = html;
    listEl.setAttribute('data-open', 'true');
  }

  function runSearch(mode, input, listEl, index) {
    var q = String(input.value || '').trim();
    if (q.length < minQueryLen(mode, q)) {
      listEl.innerHTML = '';
      listEl.setAttribute('data-open', 'false');
      input.setAttribute('aria-expanded', 'false');
      return;
    }
    var items =
      mode === 'entity'
        ? buildEntityResults(index, q, 10)
        : buildStateResults(index, q, 12);
    var emptyMsg =
      mode === 'entity' ? 'No chains match.' : 'No states match.';
    renderResults(listEl, items, emptyMsg);
    input.setAttribute('aria-expanded', items.length ? 'true' : 'false');
  }

  function initSwitcher(root, index) {
    var mode = root.getAttribute('data-mode');
    var input = root.querySelector('.pbj-page-header-switcher-input');
    var listEl = root.querySelector('.pbj-page-header-switcher-results');
    if (!input || !listEl || !mode) return;

    function closeList() {
      listEl.innerHTML = '';
      listEl.setAttribute('data-open', 'false');
      input.setAttribute('aria-expanded', 'false');
    }

    function search() {
      runSearch(mode, input, listEl, index);
    }

    input.addEventListener('input', search);
    input.addEventListener('focus', search);

    input.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        closeList();
        input.blur();
      } else if (e.key === 'Enter') {
        var first = listEl.querySelector('a[href]');
        if (first) {
          e.preventDefault();
          window.location.href = first.getAttribute('href');
        }
      } else if (e.key === 'ArrowDown') {
        var firstLink = listEl.querySelector('a[href]');
        if (firstLink) {
          e.preventDefault();
          firstLink.focus();
        }
      }
    });

    document.addEventListener('click', function (e) {
      if (!root.contains(e.target)) closeList();
    });
  }

  function init() {
    if (window.matchMedia('(max-width: ' + (DESKTOP_MIN - 1) + 'px)').matches) {
      return;
    }
    var roots = document.querySelectorAll('.pbj-page-header-switcher[data-mode]');
    if (!roots.length) return;
    loadIndex().then(function (index) {
      for (var i = 0; i < roots.length; i++) {
        initSwitcher(roots[i], index);
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
