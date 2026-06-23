/**
 * PBJ320 facility switcher — desktop anchored popover, mobile expanded header mode.
 * Data source: /search_index.json (facility rows in .f).
 */
(function () {
  'use strict';

  var INDEX_CACHE_KEY = 'pbj-public-search-index-v1';
  var PLACEHOLDER = 'Find a nursing home';
  var DESKTOP_MIN = 769;
  var RESULT_LIMIT = 8;
  var MAX_BOOST_STATE_IN_RESULTS = 3;
  var OWNERSHIP_SLUGS = { ny: 'NY', ct: 'CT', fl: 'FL', nj: 'NJ', id: 'ID' };
  var USA_SLUGS = { usa: 1, us: 1, national: 1, 'united-states': 1 };

  var SLUG_TO_STATE = {
    usa: { abbr: 'USA', name: 'United States' },
    alabama: { abbr: 'AL', name: 'Alabama' },
    alaska: { abbr: 'AK', name: 'Alaska' },
    arizona: { abbr: 'AZ', name: 'Arizona' },
    arkansas: { abbr: 'AR', name: 'Arkansas' },
    california: { abbr: 'CA', name: 'California' },
    colorado: { abbr: 'CO', name: 'Colorado' },
    connecticut: { abbr: 'CT', name: 'Connecticut' },
    delaware: { abbr: 'DE', name: 'Delaware' },
    florida: { abbr: 'FL', name: 'Florida' },
    georgia: { abbr: 'GA', name: 'Georgia' },
    hawaii: { abbr: 'HI', name: 'Hawaii' },
    idaho: { abbr: 'ID', name: 'Idaho' },
    illinois: { abbr: 'IL', name: 'Illinois' },
    indiana: { abbr: 'IN', name: 'Indiana' },
    iowa: { abbr: 'IA', name: 'Iowa' },
    kansas: { abbr: 'KS', name: 'Kansas' },
    kentucky: { abbr: 'KY', name: 'Kentucky' },
    louisiana: { abbr: 'LA', name: 'Louisiana' },
    maine: { abbr: 'ME', name: 'Maine' },
    maryland: { abbr: 'MD', name: 'Maryland' },
    massachusetts: { abbr: 'MA', name: 'Massachusetts' },
    michigan: { abbr: 'MI', name: 'Michigan' },
    minnesota: { abbr: 'MN', name: 'Minnesota' },
    mississippi: { abbr: 'MS', name: 'Mississippi' },
    missouri: { abbr: 'MO', name: 'Missouri' },
    montana: { abbr: 'MT', name: 'Montana' },
    nebraska: { abbr: 'NE', name: 'Nebraska' },
    nevada: { abbr: 'NV', name: 'Nevada' },
    'new-hampshire': { abbr: 'NH', name: 'New Hampshire' },
    'new-jersey': { abbr: 'NJ', name: 'New Jersey' },
    'new-mexico': { abbr: 'NM', name: 'New Mexico' },
    'new-york': { abbr: 'NY', name: 'New York' },
    'north-carolina': { abbr: 'NC', name: 'North Carolina' },
    'north-dakota': { abbr: 'ND', name: 'North Dakota' },
    ohio: { abbr: 'OH', name: 'Ohio' },
    oklahoma: { abbr: 'OK', name: 'Oklahoma' },
    oregon: { abbr: 'OR', name: 'Oregon' },
    pennsylvania: { abbr: 'PA', name: 'Pennsylvania' },
    'rhode-island': { abbr: 'RI', name: 'Rhode Island' },
    'south-carolina': { abbr: 'SC', name: 'South Carolina' },
    'south-dakota': { abbr: 'SD', name: 'South Dakota' },
    tennessee: { abbr: 'TN', name: 'Tennessee' },
    texas: { abbr: 'TX', name: 'Texas' },
    utah: { abbr: 'UT', name: 'Utah' },
    vermont: { abbr: 'VT', name: 'Vermont' },
    virginia: { abbr: 'VA', name: 'Virginia' },
    washington: { abbr: 'WA', name: 'Washington' },
    'west-virginia': { abbr: 'WV', name: 'West Virginia' },
    wisconsin: { abbr: 'WI', name: 'Wisconsin' },
    wyoming: { abbr: 'WY', name: 'Wyoming' },
    'district-of-columbia': { abbr: 'DC', name: 'District Of Columbia' },
    'puerto-rico': { abbr: 'PR', name: 'Puerto Rico' }
  };

  var SMALL_WORDS = /^(of|at|and|the|for|in|or|on|to|a|an)$/i;
  var openTrigger = null;
  var trapHandler = null;
  var resizeHandler = null;
  var activeResultIndex = -1;
  var savedScrollY = 0;
  var scrollLocked = false;

  var state = {
    payload: null,
    searchIndex: { f: [] },
    indexReady: false,
    indexLoading: false,
    indexError: false
  };

  function isMobileViewport() {
    return window.matchMedia('(max-width: ' + (DESKTOP_MIN - 1) + 'px)').matches;
  }

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

  function titleCaseCity(str) {
    if (!str) return '';
    return String(str)
      .split(/\s+/)
      .map(function (w) {
        if (/^(mc|mac|o'|st\.?|mt\.?)$/i.test(w)) {
          return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase();
        }
        return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase();
      })
      .join(' ');
  }

  function matchQuery(str, q) {
    if (!q) return false;
    return String(str || '')
      .toLowerCase()
      .indexOf(String(q).toLowerCase()) !== -1;
  }

  function isMeaningfulQuery(q) {
    var trimmed = (q || '').trim();
    if (!trimmed) return false;
    if (trimmed.length >= 2) return true;
    return /^\d{3,6}$/.test(trimmed);
  }

  function resolveContextFromPathname(pathname) {
    var path = (pathname || '/').split('?')[0].split('#')[0].replace(/\/$/, '') || '/';
    var ctx = {
      kind: 'fallback',
      stateAbbr: null,
      stateName: null,
      stateSlug: null,
      ccn: null,
      entityId: null,
      ownershipStateSlug: null
    };
    if (path === '/') {
      ctx.kind = 'homepage';
      return ctx;
    }
    var prov = path.match(/^\/provider\/(\d{6})$/);
    if (prov) {
      ctx.kind = 'provider';
      ctx.ccn = prov[1];
      return ctx;
    }
    var st = path.match(/^\/state\/([^/]+)$/);
    if (st) {
      ctx.kind = 'state';
      var slug = st[1].toLowerCase();
      ctx.stateSlug = slug;
      if (USA_SLUGS[slug]) {
        ctx.stateAbbr = 'USA';
        ctx.stateName = 'United States';
      } else if (SLUG_TO_STATE[slug]) {
        ctx.stateAbbr = SLUG_TO_STATE[slug].abbr;
        ctx.stateName = SLUG_TO_STATE[slug].name;
      }
      return ctx;
    }
    var ent = path.match(/^\/entity\/(\d+)$/);
    if (ent) {
      ctx.kind = 'entity';
      ctx.entityId = parseInt(ent[1], 10);
      return ctx;
    }
    if (path === '/owners' || path.indexOf('/owners/') === 0) {
      ctx.kind = 'ownership';
      var seg = path === '/owners' ? '' : path.slice('/owners/'.length);
      if (seg && /^\d{10}$/.test(seg)) {
        return ctx;
      }
      if (seg && OWNERSHIP_SLUGS[seg.toLowerCase()]) {
        var oslug = seg.toLowerCase();
        ctx.ownershipStateSlug = oslug;
        var code = OWNERSHIP_SLUGS[oslug];
        ctx.stateAbbr = code;
        if (SLUG_TO_STATE[oslug]) {
          ctx.stateName = SLUG_TO_STATE[oslug].name;
        } else {
          for (var sk in SLUG_TO_STATE) {
            if (SLUG_TO_STATE[sk].abbr === code) {
              ctx.stateName = SLUG_TO_STATE[sk].name;
              break;
            }
          }
        }
      }
      return ctx;
    }
    return ctx;
  }

  function defaultSearchConfig(ctx) {
    var boost = null;
    if (ctx.stateAbbr && ctx.stateAbbr !== 'USA') {
      boost = ctx.stateAbbr;
    }
    return {
      placeholder: PLACEHOLDER,
      boostStateAbbr: boost
    };
  }

  function resolveRoutePayload() {
    var el = document.getElementById('pbj-route-context');
    if (el && el.textContent) {
      try {
        return JSON.parse(el.textContent);
      } catch (e) {
        /* fall through */
      }
    }
    var ctx = resolveContextFromPathname(window.location.pathname || '/');
    return { context: ctx, search: defaultSearchConfig(ctx) };
  }

  function injectStyles() {
    if (document.getElementById('pbj-public-search-styles')) return;
    var gutter = 'clamp(12px,4vw,20px)';
    var style = document.createElement('style');
    style.id = 'pbj-public-search-styles';
    style.textContent = [
      '.pbj-public-search-overlay{position:fixed;inset:0;z-index:10031;display:none;box-sizing:border-box;}',
      '.pbj-public-search-overlay[data-open="true"]{display:block;}',
      '.pbj-public-search-panel{box-sizing:border-box;display:flex;flex-direction:column;background:#0a0f1a;overflow:hidden;}',
      '.pbj-public-search-mobile-top{display:none;align-items:center;justify-content:space-between;gap:0.5rem;height:60px;min-height:60px;padding:0 ' + gutter + ';padding-top:env(safe-area-inset-top,0);border-bottom:1px solid rgba(71,85,105,0.45);flex-shrink:0;}',
      '.pbj-public-search-mobile-brand{display:flex;align-items:center;min-width:0;color:#eef2f7;font-size:1.2rem;font-weight:700;text-decoration:none;}',
      '.pbj-public-search-mobile-brand img{width:32px;height:32px;margin-right:8px;flex-shrink:0;}',
      '.pbj-public-search-input-row{display:flex;align-items:center;gap:0.5rem;padding:0.75rem;flex-shrink:0;}',
      '.pbj-public-search-input-wrap{position:relative;flex:1;min-width:0;display:flex;align-items:center;}',
      '.pbj-public-search-input-icon{position:absolute;left:0.7rem;color:rgba(148,163,184,0.9);pointer-events:none;display:flex;}',
      '.pbj-public-search-input{width:100%;padding:0.65rem 0.75rem 0.65rem 2.35rem;font-size:16px;line-height:1.35;border-radius:10px;border:1px solid rgba(100,116,139,0.55);background:rgba(15,23,42,0.92);color:#f8fafc;box-sizing:border-box;}',
      '.pbj-public-search-input::placeholder{color:rgba(148,163,184,0.75);}',
      '.pbj-public-search-input:focus{outline:none;border-color:#818cf8;box-shadow:0 0 0 3px rgba(99,102,241,0.25);}',
      '.pbj-public-search-close{flex-shrink:0;width:44px;height:44px;padding:0;border:none;border-radius:8px;background:transparent;color:rgba(226,232,240,0.9);font-size:1.65rem;line-height:1;cursor:pointer;}',
      '.pbj-public-search-close:hover{background:rgba(51,65,85,0.55);}',
      '.pbj-public-search-close:focus-visible{outline:2px solid #818cf8;outline-offset:2px;}',
      '.pbj-public-search-body{flex:1;min-height:0;overflow-y:auto;-webkit-overflow-scrolling:touch;padding:0 0.25rem 0.75rem;}',
      '.pbj-public-search-results{list-style:none;margin:0;padding:0;}',
      '.pbj-public-search-result{margin:0;padding:0;}',
      '.pbj-public-search-result-btn{display:block;width:100%;text-align:left;padding:0.65rem 0.75rem;border:none;border-radius:10px;background:transparent;color:#e2e8f0;cursor:pointer;font:inherit;box-sizing:border-box;}',
      '.pbj-public-search-result-btn:hover,.pbj-public-search-result-btn:focus-visible{background:rgba(30,41,59,0.75);outline:2px solid rgba(129,140,248,0.55);outline-offset:-2px;}',
      '.pbj-public-search-result-btn[aria-selected="true"]{background:rgba(51,65,85,0.85);outline:2px solid #818cf8;outline-offset:-2px;}',
      '.pbj-public-search-result-title{font-weight:600;font-size:0.95rem;line-height:1.3;color:#f1f5f9;}',
      '.pbj-public-search-result-meta{font-size:0.8rem;line-height:1.35;color:rgba(148,163,184,0.95);margin-top:0.15rem;}',
      '.pbj-public-search-empty{padding:1.25rem 0.75rem;text-align:left;}',
      '.pbj-public-search-empty-title{margin:0;font-size:0.95rem;font-weight:600;color:#e2e8f0;}',
      '.pbj-public-search-empty-hint{margin:0.35rem 0 0;font-size:0.85rem;line-height:1.4;color:rgba(148,163,184,0.95);}',
      '.pbj-public-search-error{padding:1.25rem 0.75rem;font-size:0.88rem;color:rgba(148,163,184,0.95);}',
      'body.pbj-mobile-search-open{overflow:hidden;}',
      'body.pbj-mobile-search-open .navbar{visibility:hidden;pointer-events:none;}',
      '@media (min-width:' + DESKTOP_MIN + 'px){',
      '.pbj-public-search-overlay{background:transparent;}',
      '.pbj-public-search-panel{position:fixed;background:#0f172a;width:min(480px,calc(100vw - 24px));min-width:min(420px,calc(100vw - 24px));max-width:520px;border:1px solid rgba(148,163,184,0.28);border-radius:12px;box-shadow:0 12px 40px rgba(0,0,0,0.38);max-height:min(calc(100vh - 24px),520px);}',
      '.pbj-public-search-input-row{border-bottom:1px solid rgba(71,85,105,0.45);}',
      '.pbj-public-search-close--mobile{display:none;}',
      '.pbj-public-search-body{max-height:22rem;}',
      '}',
      '@media (max-width:' + (DESKTOP_MIN - 1) + 'px){',
      '.pbj-public-search-overlay{background:#0a0f1a;}',
      '.pbj-public-search-overlay[data-open="true"]{display:flex;flex-direction:column;}',
      '.pbj-public-search-panel{width:100%;max-width:100vw;height:100%;max-height:100dvh;border:0;border-radius:0;box-shadow:none;}',
      '.pbj-public-search-mobile-top{display:flex;}',
      '.pbj-public-search-input-row{padding:0.75rem ' + gutter + ';border-bottom:1px solid rgba(71,85,105,0.45);}',
      '.pbj-public-search-close--desktop{display:none;}',
      '.pbj-public-search-body{padding-left:' + gutter + ';padding-right:' + gutter + ';padding-bottom:max(0.75rem,env(safe-area-inset-bottom,0));}',
      '}'
    ].join('');
    document.head.appendChild(style);
  }

  function searchIconSvg() {
    return (
      '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>'
    );
  }

  function syncMobileBrand() {
    var src = document.querySelector('.navbar .nav-brand a');
    var dst = document.getElementById('pbj-public-search-mobile-brand');
    if (!src || !dst) return;
    dst.innerHTML = src.innerHTML;
    dst.setAttribute('href', src.getAttribute('href') || '/');
  }

  function ensureOverlay() {
    injectStyles();
    var overlay = document.getElementById('pbj-public-search-overlay');
    if (overlay) return overlay;
    overlay = document.createElement('div');
    overlay.id = 'pbj-public-search-overlay';
    overlay.className = 'pbj-public-search-overlay';
    overlay.setAttribute('aria-hidden', 'true');
    overlay.innerHTML =
      '<div class="pbj-public-search-panel" id="pbj-public-search-panel" role="dialog" aria-modal="true" aria-label="' +
      escapeHtml(PLACEHOLDER) +
      '">' +
      '<div class="pbj-public-search-mobile-top">' +
      '<a class="pbj-public-search-mobile-brand" id="pbj-public-search-mobile-brand" href="/"></a>' +
      '<button type="button" class="pbj-public-search-close pbj-public-search-close--mobile" aria-label="Close search">&times;</button>' +
      '</div>' +
      '<div class="pbj-public-search-input-row">' +
      '<div class="pbj-public-search-input-wrap">' +
      '<span class="pbj-public-search-input-icon">' +
      searchIconSvg() +
      '</span>' +
      '<input type="text" id="pbj-public-search-input" class="pbj-public-search-input" autocomplete="off" inputmode="search" enterkeyhint="search" role="combobox" aria-autocomplete="list" aria-controls="pbj-public-search-results" aria-expanded="false" />' +
      '</div>' +
      '<button type="button" class="pbj-public-search-close pbj-public-search-close--desktop" aria-label="Close search">&times;</button>' +
      '</div>' +
      '<div class="pbj-public-search-body">' +
      '<ul class="pbj-public-search-results" id="pbj-public-search-results" role="listbox" aria-label="Search results"></ul>' +
      '</div>' +
      '</div>';
    document.body.appendChild(overlay);

    var panel = document.getElementById('pbj-public-search-panel');
    var closeBtns = overlay.querySelectorAll('.pbj-public-search-close');
    for (var i = 0; i < closeBtns.length; i++) {
      closeBtns[i].addEventListener('click', closePublicSearch);
    }
    var input = document.getElementById('pbj-public-search-input');
    if (input) {
      input.addEventListener('input', function () {
        renderSearchResults(input.value);
      });
      input.addEventListener('keydown', onInputKeydown);
    }
    overlay.addEventListener('click', function (e) {
      if (!isMobileViewport() && panel && !panel.contains(e.target)) {
        closePublicSearch();
      }
    });
    var results = document.getElementById('pbj-public-search-results');
    if (results) {
      results.addEventListener('click', function (e) {
        var btn = e.target.closest('.pbj-public-search-result-btn');
        if (btn && btn.getAttribute('data-url')) {
          e.preventDefault();
          navigateTo(btn.getAttribute('data-url'));
        }
      });
    }
    return overlay;
  }

  function positionDesktopPopover(trigger) {
    var panel = document.getElementById('pbj-public-search-panel');
    if (!panel || !trigger || isMobileViewport()) return;
    var rect = trigger.getBoundingClientRect();
    var viewportPad = 12;
    var panelWidth = Math.min(520, Math.max(420, Math.min(480, window.innerWidth - viewportPad * 2)));
    var left = rect.right - panelWidth;
    if (left < viewportPad) left = viewportPad;
    if (left + panelWidth > window.innerWidth - viewportPad) {
      left = window.innerWidth - panelWidth - viewportPad;
    }
    var top = rect.bottom + 8;
    var maxHeight = Math.min(window.innerHeight - viewportPad * 2, 520);
    if (top + maxHeight > window.innerHeight - viewportPad) {
      top = Math.max(viewportPad, rect.top - maxHeight - 8);
    }
    panel.style.width = panelWidth + 'px';
    panel.style.left = left + 'px';
    panel.style.top = top + 'px';
    panel.style.right = 'auto';
    panel.style.bottom = 'auto';
    panel.style.maxHeight = maxHeight + 'px';
  }

  function clearDesktopPopoverPosition() {
    var panel = document.getElementById('pbj-public-search-panel');
    if (!panel) return;
    panel.style.left = '';
    panel.style.top = '';
    panel.style.width = '';
    panel.style.right = '';
    panel.style.bottom = '';
    panel.style.maxHeight = '';
  }

  function lockBackgroundScroll() {
    if (!isMobileViewport() || scrollLocked) return;
    savedScrollY = window.scrollY || window.pageYOffset || 0;
    document.body.classList.add('pbj-mobile-search-open');
    document.body.style.position = 'fixed';
    document.body.style.top = '-' + savedScrollY + 'px';
    document.body.style.left = '0';
    document.body.style.right = '0';
    document.body.style.width = '100%';
    scrollLocked = true;
  }

  function unlockBackgroundScroll() {
    if (!scrollLocked) return;
    document.body.classList.remove('pbj-mobile-search-open');
    document.body.style.position = '';
    document.body.style.top = '';
    document.body.style.left = '';
    document.body.style.right = '';
    document.body.style.width = '';
    window.scrollTo(0, savedScrollY);
    scrollLocked = false;
  }

  function focusablesInPanel() {
    var panel = document.getElementById('pbj-public-search-panel');
    if (!panel) return [];
    return panel.querySelectorAll(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
  }

  function onTrapKey(e) {
    if (e.key === 'Escape') {
      e.preventDefault();
      closePublicSearch();
      return;
    }
    if (e.key !== 'Tab') return;
    var list = focusablesInPanel();
    if (!list.length) return;
    var first = list[0];
    var last = list[list.length - 1];
    if (e.shiftKey) {
      if (document.activeElement === first) {
        e.preventDefault();
        last.focus();
      }
    } else if (document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  function loadSearchIndex() {
    if (state.indexReady || state.indexLoading) {
      return state.indexLoading
        ? state.indexLoadPromise
        : Promise.resolve(state.searchIndex);
    }
    state.indexLoading = true;
    state.indexLoadPromise = new Promise(function (resolve) {
      try {
        var cached = sessionStorage.getItem(INDEX_CACHE_KEY);
        if (cached) {
          var data = JSON.parse(cached);
          state.searchIndex = { f: data.f || [] };
          state.indexReady = true;
          state.indexLoading = false;
          resolve(state.searchIndex);
          return;
        }
      } catch (e) {
        /* ignore */
      }
      fetch('/search_index.json', { credentials: 'same-origin' })
        .then(function (r) {
          if (!r.ok) throw new Error('index fetch failed');
          return r.json();
        })
        .then(function (data) {
          state.searchIndex = { f: data.f || [] };
          state.indexReady = true;
          state.indexError = false;
          try {
            sessionStorage.setItem(
              INDEX_CACHE_KEY,
              JSON.stringify({ f: state.searchIndex.f })
            );
          } catch (err) {
            /* quota */
          }
          resolve(state.searchIndex);
        })
        .catch(function () {
          state.indexError = true;
          state.indexReady = true;
          resolve(state.searchIndex);
        })
        .finally(function () {
          state.indexLoading = false;
        });
    });
    return state.indexLoadPromise;
  }

  function facilityBaseScore(row, q) {
    var score = 0;
    if (matchQuery(row.c, q)) score += 140;
    if (matchQuery(row.n, q)) score += 100;
    if (matchQuery(row.y, q)) score += 35;
    if (matchQuery(row.s, q)) score += 20;
    return score;
  }

  function buildFacilityResults(q, cfg, limit) {
    var boost = cfg.boostStateAbbr || null;
    var hits = [];
    for (var i = 0; i < state.searchIndex.f.length; i++) {
      var row = state.searchIndex.f[i];
      if (!row || !row.c) continue;
      var base = facilityBaseScore(row, q);
      if (!base) continue;
      hits.push({ row: row, base: base });
    }
    hits.sort(function (a, b) {
      if (b.base !== a.base) return b.base - a.base;
      return String(a.row.n || '').localeCompare(String(b.row.n || ''));
    });

    var maxInState = boost ? Math.min(MAX_BOOST_STATE_IN_RESULTS, Math.max(1, limit - 1)) : 0;
    var inStateHits = [];
    var otherHits = [];
    for (var i = 0; i < hits.length; i++) {
      if (boost && (hits[i].row.s || '') === boost) {
        inStateHits.push(hits[i]);
      } else {
        otherHits.push(hits[i]);
      }
    }

    var selected = [];
    var used = {};
    for (var j = 0; j < inStateHits.length && selected.length < maxInState; j++) {
      var key = String(inStateHits[j].row.c || '');
      if (used[key]) continue;
      used[key] = true;
      selected.push(inStateHits[j]);
    }
    for (var k = 0; k < otherHits.length && selected.length < limit; k++) {
      var key2 = String(otherHits[k].row.c || '');
      if (used[key2]) continue;
      used[key2] = true;
      selected.push(otherHits[k]);
    }
    if (selected.length < limit) {
      for (var m = 0; m < inStateHits.length && selected.length < limit; m++) {
        var key3 = String(inStateHits[m].row.c || '');
        if (used[key3]) continue;
        used[key3] = true;
        selected.push(inStateHits[m]);
      }
    }

    selected.sort(function (a, b) {
      if (b.base !== a.base) return b.base - a.base;
      var boostA = boost && (a.row.s || '') === boost ? 1 : 0;
      var boostB = boost && (b.row.s || '') === boost ? 1 : 0;
      if (boostB !== boostA) return boostB - boostA;
      return String(a.row.n || '').localeCompare(String(b.row.n || ''));
    });

    var rows = [];
    for (var n = 0; n < selected.length && n < limit; n++) {
      rows.push(selected[n].row);
    }
    return buildFacilityResultItems(rows);
  }

  function buildFacilityResultItems(rows) {
    var items = [];
    for (var j = 0; j < rows.length; j++) {
      var r = rows[j];
      var cityState = (r.y ? titleCaseCity(r.y) + ', ' : '') + (r.s || '');
      var meta = cityState ? cityState + ' · CCN ' + r.c : 'CCN ' + r.c;
      items.push({
        title: titleCase(r.n || ''),
        meta: meta,
        url: '/provider/' + encodeURIComponent(r.c)
      });
    }
    return items;
  }

  function renderNoResults() {
    return (
      '<li class="pbj-public-search-empty" role="presentation">' +
      '<p class="pbj-public-search-empty-title">No nursing homes found</p>' +
      '<p class="pbj-public-search-empty-hint">Try the facility name or CMS ID.</p>' +
      '</li>'
    );
  }

  function renderIndexError() {
    return (
      '<li class="pbj-public-search-error" role="presentation">Search is temporarily unavailable.</li>'
    );
  }

  function renderResultButton(item, index) {
    return (
      '<li class="pbj-public-search-result" role="presentation">' +
      '<button type="button" class="pbj-public-search-result-btn" role="option" data-url="' +
      escapeHtml(item.url) +
      '" data-index="' +
      index +
      '" aria-selected="' +
      (index === activeResultIndex ? 'true' : 'false') +
      '">' +
      '<div class="pbj-public-search-result-title">' +
      escapeHtml(item.title) +
      '</div>' +
      (item.meta
        ? '<div class="pbj-public-search-result-meta">' + escapeHtml(item.meta) + '</div>'
        : '') +
      '</button></li>'
    );
  }

  function renderSearchResults(query) {
    var input = document.getElementById('pbj-public-search-input');
    var resultsEl = document.getElementById('pbj-public-search-results');
    if (!resultsEl || !state.payload) return;

    var q = (query || '').trim();
    var cfg = state.payload.search;
    activeResultIndex = -1;

    if (!isMeaningfulQuery(q)) {
      resultsEl.innerHTML = '';
      if (input) input.setAttribute('aria-expanded', 'false');
      return;
    }

    if (!state.indexReady) {
      resultsEl.innerHTML = '';
      if (input) input.setAttribute('aria-expanded', 'false');
      return;
    }

    if (state.indexError) {
      resultsEl.innerHTML = renderIndexError();
      if (input) input.setAttribute('aria-expanded', 'false');
      return;
    }

    var items = buildFacilityResults(q, cfg, RESULT_LIMIT);

    if (!items.length) {
      resultsEl.innerHTML = renderNoResults();
      if (input) input.setAttribute('aria-expanded', 'false');
      return;
    }

    var html = '';
    for (var i = 0; i < items.length; i++) {
      html += renderResultButton(items[i], i);
    }
    resultsEl.innerHTML = html;
    if (input) input.setAttribute('aria-expanded', 'true');
  }

  function resultButtons() {
    var resultsEl = document.getElementById('pbj-public-search-results');
    if (!resultsEl) return [];
    return Array.prototype.slice.call(
      resultsEl.querySelectorAll('.pbj-public-search-result-btn')
    );
  }

  function setActiveResult(index) {
    var buttons = resultButtons();
    if (!buttons.length) return;
    if (index < 0) index = buttons.length - 1;
    if (index >= buttons.length) index = 0;
    activeResultIndex = index;
    buttons.forEach(function (btn, i) {
      btn.setAttribute('aria-selected', i === index ? 'true' : 'false');
    });
    buttons[index].focus();
  }

  function onInputKeydown(e) {
    var buttons = resultButtons();
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (!buttons.length) return;
      setActiveResult(activeResultIndex < 0 ? 0 : activeResultIndex + 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (!buttons.length) return;
      setActiveResult(activeResultIndex < 0 ? buttons.length - 1 : activeResultIndex - 1);
    } else if (e.key === 'Enter') {
      if (activeResultIndex >= 0 && buttons[activeResultIndex]) {
        e.preventDefault();
        navigateTo(buttons[activeResultIndex].getAttribute('data-url'));
      } else if (buttons.length) {
        e.preventDefault();
        navigateTo(buttons[0].getAttribute('data-url'));
      }
    }
  }

  function navigateTo(url) {
    if (!url) return;
    closePublicSearch();
    window.location.href = url;
  }

  function applySearchConfig() {
    var input = document.getElementById('pbj-public-search-input');
    if (!input) return;
    input.placeholder = PLACEHOLDER;
    input.setAttribute('aria-label', PLACEHOLDER);
  }

  function openPublicSearch(trigger) {
    state.payload = resolveRoutePayload();
    openTrigger = trigger || document.querySelector('.nav-search-btn--mobile, .nav-search-btn--desktop');
    ensureOverlay();
    applySearchConfig();
    syncMobileBrand();

    var overlay = document.getElementById('pbj-public-search-overlay');
    var input = document.getElementById('pbj-public-search-input');
    if (!overlay || !input) return;

    if (typeof window.PBJ320_closeMobileNav === 'function') {
      window.PBJ320_closeMobileNav();
    }

    if (isMobileViewport()) {
      lockBackgroundScroll();
      clearDesktopPopoverPosition();
    } else {
      unlockBackgroundScroll();
      positionDesktopPopover(openTrigger);
    }

    overlay.setAttribute('data-open', 'true');
    overlay.setAttribute('aria-hidden', 'false');
    if (openTrigger) openTrigger.setAttribute('aria-expanded', 'true');

    loadSearchIndex().then(function () {
      renderSearchResults(input.value);
    });

    window.setTimeout(function () {
      input.focus();
    }, 0);

    trapHandler = onTrapKey;
    document.addEventListener('keydown', trapHandler);
    resizeHandler = function () {
      if (overlay.getAttribute('data-open') === 'true' && !isMobileViewport()) {
        positionDesktopPopover(openTrigger);
      }
    };
    window.addEventListener('resize', resizeHandler);
  }

  function closePublicSearch() {
    var overlay = document.getElementById('pbj-public-search-overlay');
    var input = document.getElementById('pbj-public-search-input');
    if (!overlay) return;
    overlay.setAttribute('data-open', 'false');
    overlay.setAttribute('aria-hidden', 'true');
    unlockBackgroundScroll();
    clearDesktopPopoverPosition();
    if (input) input.value = '';
    var resultsEl = document.getElementById('pbj-public-search-results');
    if (resultsEl) resultsEl.innerHTML = '';
    if (openTrigger) {
      openTrigger.setAttribute('aria-expanded', 'false');
      openTrigger.focus();
    }
    openTrigger = null;
    activeResultIndex = -1;
    if (trapHandler) {
      document.removeEventListener('keydown', trapHandler);
      trapHandler = null;
    }
    if (resizeHandler) {
      window.removeEventListener('resize', resizeHandler);
      resizeHandler = null;
    }
  }

  function initPublicSearch() {
    state.payload = resolveRoutePayload();
    ensureOverlay();
    applySearchConfig();
  }

  if (typeof window !== 'undefined') {
    window.PBJ320_initPublicSearch = initPublicSearch;
    window.PBJ320_openPublicSearch = openPublicSearch;
    window.PBJ320_closePublicSearch = closePublicSearch;
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', initPublicSearch);
    } else {
      initPublicSearch();
    }
  }
})();
