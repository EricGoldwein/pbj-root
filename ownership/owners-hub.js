/**

 * /owners hub and state index pages — CMS ownership profile search (PAC or organization name).

 */

(function () {

  'use strict';



  var root = document.querySelector('.owners-state-index, .owners-hub-index');

  var input = document.getElementById('ownersHubSearchInput');

  var list = document.getElementById('ownersHubSearchResults');

  var stateSlug = '';

  var stateCode = '';

  var stateName = '';



  if (root && root.getAttribute) {

    stateSlug = (root.getAttribute('data-state-slug') || '').trim().toLowerCase();

    stateCode = (root.getAttribute('data-state-code') || '').trim().toUpperCase();

    stateName = (root.getAttribute('data-state-name') || '').trim();

  }



  function clearResults() {

    if (!list) return;

    list.innerHTML = '';

    list.hidden = true;

    if (input) input.setAttribute('aria-expanded', 'false');

  }



  function renderSuggestions(items) {

    if (!list) return;

    list.innerHTML = '';

    if (!items || !items.length) {

      list.hidden = true;

      if (input) input.setAttribute('aria-expanded', 'false');

      return;

    }

    items.forEach(function (item, idx) {

      var li = document.createElement('li');

      var btn = document.createElement('a');

      var cnt = parseInt(item.facility_count, 10);

      btn.href = item.profile_url || '/owners/' + item.associate_id;

      btn.className = 'owners-hub-result';

      btn.setAttribute('role', 'option');

      btn.id = 'ownersHubOpt' + idx;

      var name = document.createElement('span');

      name.className = 'owners-hub-result-name';

      name.textContent = item.name || item.associate_id;

      var meta = document.createElement('span');

      meta.className = 'owners-hub-result-pac';

      var totalCnt = parseInt(item.facility_count_total, 10);

      if (isNaN(totalCnt) || totalCnt < cnt) totalCnt = cnt;

      if (stateCode && cnt > 0) {

        var facWord = cnt === 1 ? ' facility' : ' facilities';

        meta.textContent = cnt + ' ' + stateCode + facWord + (totalCnt > cnt ? ' (' + totalCnt + ' total)' : '');

      } else if (item.associate_id && cnt > 0) {

        meta.textContent = 'PAC ' + item.associate_id + ' · ' + cnt + ' linked';

      } else if (item.associate_id) {

        meta.textContent = 'PAC ' + item.associate_id;

      } else if (cnt > 0) {

        meta.textContent = cnt + ' linked facilities';

      }

      btn.appendChild(name);

      if (meta.textContent) btn.appendChild(meta);

      btn.addEventListener('mousedown', function (e) {

        e.preventDefault();

      });

      li.appendChild(btn);

      list.appendChild(li);

    });

    list.hidden = false;

    if (input) input.setAttribute('aria-expanded', 'true');

  }



  function fetchSuggestions(q) {

    var url = '/owners/api/cms-search?q=' + encodeURIComponent(q);

    if (stateSlug) {

      url += '&state=' + encodeURIComponent(stateSlug);

    }

    fetch(url, { credentials: 'same-origin' })

      .then(function (r) {

        return r.json();

      })

      .then(function (data) {

        renderSuggestions((data && data.suggestions) || []);

      })

      .catch(function () {

        clearResults();

      });

  }



  if (input) {

    var debounceTimer = null;



    function scheduleFetch() {

      var q = (input.value || '').trim();

      if (q.length < 2 && !/^\d{9,11}$/.test(q.replace(/\D/g, ''))) {

        clearResults();

        return;

      }

      window.clearTimeout(debounceTimer);

      debounceTimer = window.setTimeout(function () {

        fetchSuggestions(q);

      }, 220);

    }



    input.addEventListener('input', scheduleFetch);

    input.addEventListener('focus', scheduleFetch);



    function bindTryChipFallback(el) {
      el.addEventListener('click', function (e) {
        var href = (el.getAttribute('href') || '').trim();
        if (href && href.indexOf('/owners/') === 0 && href.length > 8) {
          return;
        }
        e.preventDefault();
        var q = (el.getAttribute('data-try-query') || el.textContent || '').trim();
        if (!q || !input) return;
        input.value = q;
        input.focus();
        fetchSuggestions(q);
      });
    }

    function renderTryChip(chip) {
      var name = (chip.display_name || chip.name || '').trim();
      var href = (chip.href || '').trim();
      var pac = (chip.associate_id || '').trim();
      if (!href && pac.length === 10) {
        href = '/owners/' + pac;
      }
      if (href && href.indexOf('/owners/') === 0 && href.length > 8) {
        var link = document.createElement('a');
        link.className = 'owners-state-try-chip';
        link.href = href;
        link.textContent = name || pac;
        link.setAttribute('aria-label', 'View ' + (name || pac) + ' ownership profile');
        return link;
      }
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'owners-state-try-chip';
      btn.setAttribute('data-try-query', name || pac);
      btn.textContent = name || pac;
      bindTryChipFallback(btn);
      return btn;
    }

    function tryChipWantCount(tryWrap) {
      var wantDesktop = parseInt(tryWrap.getAttribute('data-try-count'), 10) || 3;
      var wantMobile = parseInt(tryWrap.getAttribute('data-try-count-mobile'), 10) || 2;
      return window.matchMedia('(max-width: 520px)').matches
        ? Math.min(wantMobile, wantDesktop)
        : wantDesktop;
    }

    function syncTryChipVisibility(chipHost, want) {
      var chips = chipHost.querySelectorAll('.owners-state-try-chip');
      chips.forEach(function (chip, idx) {
        if (idx < want) {
          chip.hidden = false;
          chip.removeAttribute('hidden');
        } else {
          chip.hidden = true;
        }
      });
    }

    function tryChipKey(chip) {
      return String((chip && chip.associate_id) || (chip && chip.display_name) || '');
    }

    function pickTryChips(pool, want, topTier) {
      if (!pool || !pool.length) return [];
      var tierN = Math.max(1, parseInt(topTier, 10) || 5);
      want = Math.min(Math.max(1, want), pool.length);
      if (want === 1) {
        return [pool[Math.floor(Math.random() * pool.length)]];
      }
      var tier = pool.slice(0, Math.min(tierN, pool.length));
      var picked = [];
      var used = {};
      if (want >= 2 && tier.length) {
        var anchor = tier[Math.floor(Math.random() * tier.length)];
        picked.push(anchor);
        used[tryChipKey(anchor)] = true;
      }
      var rest = pool.filter(function (chip) {
        return !used[tryChipKey(chip)];
      });
      while (picked.length < want && rest.length) {
        var ri = Math.floor(Math.random() * rest.length);
        var choice = rest.splice(ri, 1)[0];
        picked.push(choice);
        used[tryChipKey(choice)] = true;
      }
      for (var i = picked.length - 1; i > 0; i--) {
        var j = Math.floor(Math.random() * (i + 1));
        var tmp = picked[i];
        picked[i] = picked[j];
        picked[j] = tmp;
      }
      return picked;
    }

    function initTryChips() {
      var tryWrap = root && root.querySelector('.owners-state-try');
      var chipHost = tryWrap && tryWrap.querySelector('[data-try-chips]');
      if (!tryWrap || !chipHost) return;
      var want = tryChipWantCount(tryWrap);
      var existing = chipHost.querySelectorAll('.owners-state-try-chip');
      if (existing.length) {
        syncTryChipVisibility(chipHost, want);
        return;
      }
      var raw = tryWrap.getAttribute('data-try-pool') || '[]';
      var pool;
      try {
        pool = JSON.parse(raw);
      } catch (e) {
        return;
      }
      if (!pool || !pool.length) return;
      if (pool[0] && typeof pool[0] === 'string') {
        pool = pool.map(function (label) {
          return { display_name: label, query: label };
        });
      }
      var topTier = tryWrap.getAttribute('data-try-top-tier') || '5';
      var chosen = pickTryChips(pool, want, topTier);
      chipHost.innerHTML = '';
      chosen.forEach(function (chip) {
        chipHost.appendChild(renderTryChip(chip));
      });
    }

    function bindTryChipLayout() {
      if (!root || !root.querySelector('.owners-state-try')) return;
      var mq = window.matchMedia('(max-width: 520px)');
      function onChange() {
        initTryChips();
      }
      if (mq.addEventListener) {
        mq.addEventListener('change', onChange);
      } else if (mq.addListener) {
        mq.addListener(onChange);
      }
    }

    function initSourcesModal() {
      if (!root) return;
      var dlg = document.getElementById('ownersStateSourcesModal');
      if (!dlg || typeof dlg.showModal !== 'function') return;
      root.querySelectorAll('[data-owners-sources-open]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          dlg.showModal();
        });
      });
      dlg.querySelectorAll('[data-owners-sources-close]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          dlg.close();
        });
      });
      dlg.addEventListener('click', function (e) {
        var card = dlg.querySelector('.owners-state-sources-modal-card');
        if (card && !card.contains(e.target)) dlg.close();
      });
      dlg.addEventListener('cancel', function () {
        dlg.close();
      });
    }

    function initAboutAccordion() {
      root.querySelectorAll('.owners-state-method').forEach(function (det) {
        var trig = det.querySelector('.owners-state-method-trigger');
        if (!trig) return;
        function syncExpanded() {
          trig.setAttribute('aria-expanded', det.open ? 'true' : 'false');
        }
        syncExpanded();
        det.addEventListener('toggle', syncExpanded);
      });
    }

    function initStatePanelTabs() {
      var tablist = root && root.querySelector('.owners-state-panel-tabs');
      if (!tablist) return;
      var tabs = tablist.querySelectorAll('[data-owners-state-tab]');
      var panels = root.querySelectorAll('[data-owners-state-panel]');
      if (!tabs.length || !panels.length) return;

      function isMobileTabs() {
        return window.matchMedia('(max-width: 520px)').matches;
      }

      function syncDesktopPanels() {
        panels.forEach(function (panel) {
          if (isMobileTabs()) return;
          panel.hidden = false;
          panel.classList.add('is-active');
        });
      }

      function activateTab(name) {
        tabs.forEach(function (tab) {
          var on = tab.getAttribute('data-owners-state-tab') === name;
          tab.classList.toggle('is-active', on);
          tab.setAttribute('aria-selected', on ? 'true' : 'false');
          tab.tabIndex = on ? 0 : -1;
        });
        panels.forEach(function (panel) {
          var on = panel.getAttribute('data-owners-state-panel') === name;
          panel.classList.toggle('is-active', on);
          if (isMobileTabs()) {
            panel.hidden = !on;
          } else {
            panel.hidden = false;
          }
        });
      }

      tabs.forEach(function (tab) {
        tab.addEventListener('click', function () {
          if (!isMobileTabs()) return;
          activateTab(tab.getAttribute('data-owners-state-tab') || 'portfolios');
        });
        tab.addEventListener('keydown', function (e) {
          if (!isMobileTabs()) return;
          var idx = Array.prototype.indexOf.call(tabs, tab);
          var next = -1;
          if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
            next = (idx + 1) % tabs.length;
          } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
            next = (idx - 1 + tabs.length) % tabs.length;
          } else if (e.key === 'Home') {
            next = 0;
          } else if (e.key === 'End') {
            next = tabs.length - 1;
          }
          if (next >= 0) {
            e.preventDefault();
            tabs[next].focus();
            activateTab(tabs[next].getAttribute('data-owners-state-tab') || 'portfolios');
          }
        });
      });

      function onLayoutChange() {
        if (isMobileTabs()) {
          var active =
            tablist.querySelector('.owners-state-panel-tab.is-active') ||
            tabs[0];
          activateTab(
            (active && active.getAttribute('data-owners-state-tab')) || 'portfolios'
          );
        } else {
          syncDesktopPanels();
        }
      }

      onLayoutChange();
      window.addEventListener('resize', onLayoutChange);
    }

    if (root) {
      initTryChips();
      bindTryChipLayout();
      initSourcesModal();
      initAboutAccordion();
      initStatePanelTabs();
    }



    input.addEventListener('keydown', function (e) {

      if (e.key === 'Escape') {

        clearResults();

        input.value = '';

      }

    });



    document.addEventListener('click', function (e) {

      if (list && !list.contains(e.target) && e.target !== input) {

        clearResults();

      }

    });

  }

})();

