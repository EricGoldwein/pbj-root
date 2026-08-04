/* PBJ320 Insights — sortable rankings + map slider/lightbox */
(function () {
  'use strict';

  function initRoot(root) {
    if (!root || root.getAttribute('data-irt-ready') === '1') return;
    root.setAttribute('data-irt-ready', '1');

    var filter = root.querySelector('.insight-rankings__search input');
    var tabs = Array.prototype.slice.call(root.querySelectorAll('.insight-rankings__tab'));
    var panels = Array.prototype.slice.call(
      root.querySelectorAll('.insight-rankings__panel')
    );
    var activePanel = null;
    var sortCol = 3;
    var sortDir = -1;

    function currentTable() {
      return activePanel && activePanel.querySelector('.insight-rankings__table');
    }

    function currentTbody() {
      var table = currentTable();
      return table && table.tBodies && table.tBodies[0] ? table.tBodies[0] : null;
    }

    function rows() {
      var tbody = currentTbody();
      return tbody ? Array.prototype.slice.call(tbody.querySelectorAll('tr')) : [];
    }

    function applyFilter() {
      var q = ((filter && filter.value) || '').trim().toLowerCase();
      rows().forEach(function (tr) {
        var stateCell = tr.cells[1];
        var state = (stateCell && stateCell.getAttribute('data-sort')) || '';
        var abbr = (stateCell && stateCell.getAttribute('data-abbr')) || '';
        var hit = !q || state.indexOf(q) !== -1 || abbr.indexOf(q) !== -1;
        tr.hidden = !hit;
      });
    }

    function sortBy(col, dir) {
      var tbody = currentTbody();
      if (!tbody) return;
      sortCol = col;
      sortDir = dir;
      var list = rows();
      list.sort(function (a, b) {
        var av = (a.cells[col] && a.cells[col].getAttribute('data-sort')) || '';
        var bv = (b.cells[col] && b.cells[col].getAttribute('data-sort')) || '';
        var an = parseFloat(av);
        var bn = parseFloat(bv);
        var cmp;
        if (!isNaN(an) && !isNaN(bn) && av !== '' && bv !== '' && col !== 1) {
          cmp = an - bn;
        } else {
          cmp = String(av).localeCompare(String(bv));
        }
        return cmp * sortDir;
      });
      list.forEach(function (tr) {
        tbody.appendChild(tr);
      });
      if (!activePanel) return;
      activePanel.querySelectorAll('.irt-sort').forEach(function (btn) {
        var active = Number(btn.getAttribute('data-col')) === col;
        btn.setAttribute('aria-pressed', active ? 'true' : 'false');
        btn.classList.toggle('is-asc', active && sortDir === 1);
        btn.classList.toggle('is-desc', active && sortDir === -1);
      });
    }

    function bindSortButtons(panel) {
      panel.querySelectorAll('.irt-sort').forEach(function (btn) {
        if (btn.getAttribute('data-irt-bound') === '1') return;
        btn.setAttribute('data-irt-bound', '1');
        btn.addEventListener('click', function () {
          var col = Number(btn.getAttribute('data-col'));
          var next =
            col === sortCol ? -sortDir : btn.getAttribute('data-default') === 'desc' ? -1 : 1;
          sortBy(col, next);
        });
      });
    }

    function activateMetric(metricId) {
      panels.forEach(function (panel) {
        var on = panel.getAttribute('data-panel') === metricId;
        panel.hidden = !on;
        panel.setAttribute('aria-hidden', on ? 'false' : 'true');
        if (on) activePanel = panel;
      });
      tabs.forEach(function (tab) {
        var on = tab.getAttribute('data-metric') === metricId;
        tab.classList.toggle('is-active', on);
        tab.setAttribute('aria-selected', on ? 'true' : 'false');
        tab.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
      if (activePanel) {
        bindSortButtons(activePanel);
        sortCol = 3;
        sortDir = -1;
        sortBy(3, -1);
        applyFilter();
      }
    }

    tabs.forEach(function (tab) {
      tab.addEventListener('click', function () {
        activateMetric(tab.getAttribute('data-metric'));
      });
    });

    if (filter) {
      filter.addEventListener('input', applyFilter);
    }

    var initial =
      (tabs[0] && tabs[0].getAttribute('data-metric')) ||
      (panels[0] && panels[0].getAttribute('data-panel')) ||
      'total';
    activateMetric(initial);
  }

  function ensureLightbox() {
    var box = document.getElementById('insight-map-lightbox');
    if (box) return box;
    box = document.createElement('div');
    box.id = 'insight-map-lightbox';
    box.className = 'insight-map-lightbox';
    box.setAttribute('data-open', 'false');
    box.setAttribute('aria-hidden', 'true');
    box.innerHTML =
      '<div class="insight-map-lightbox__panel" role="dialog" aria-modal="true" aria-labelledby="insight-map-lightbox-title">' +
      '<button type="button" class="insight-map-lightbox__close" aria-label="Close map">×</button>' +
      '<p class="insight-map-lightbox__title" id="insight-map-lightbox-title"></p>' +
      '<img class="insight-map-lightbox__img" alt="" />' +
      '</div>';
    document.body.appendChild(box);
    function close() {
      box.setAttribute('data-open', 'false');
      box.setAttribute('aria-hidden', 'true');
      document.body.style.overflow = '';
    }
    box.addEventListener('click', function (ev) {
      if (ev.target === box) close();
    });
    box.querySelector('.insight-map-lightbox__close').addEventListener('click', close);
    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape' && box.getAttribute('data-open') === 'true') close();
    });
    box._close = close;
    return box;
  }

  function openLightbox(src, title) {
    var box = ensureLightbox();
    var img = box.querySelector('.insight-map-lightbox__img');
    var titleEl = box.querySelector('.insight-map-lightbox__title');
    titleEl.textContent = title || '';
    img.alt = title || 'State map';
    img.src = src;
    box.setAttribute('data-open', 'true');
    box.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
  }

  function initMapSlider(root) {
    if (!root || root.getAttribute('data-map-ready') === '1') return;
    root.setAttribute('data-map-ready', '1');
    var track = root.querySelector('.insight-map-slider__track');
    var slides = Array.prototype.slice.call(root.querySelectorAll('.insight-map-slider__slide'));
    var dotsHost = root.querySelector('.insight-map-slider__dots');
    if (!track || slides.length < 1) return;
    var index = 0;
    var timer = null;
    var reduced =
      window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    function syncDots() {
      if (!dotsHost) return;
      Array.prototype.forEach.call(dotsHost.children, function (dot, i) {
        var on = i === index;
        dot.classList.toggle('is-active', on);
        dot.setAttribute('aria-selected', on ? 'true' : 'false');
        dot.setAttribute('tabindex', on ? '0' : '-1');
      });
    }

    function go(i) {
      index = (i + slides.length) % slides.length;
      track.style.transform = 'translateX(' + -index * 100 + '%)';
      syncDots();
    }

    if (dotsHost) {
      dotsHost.innerHTML = '';
      slides.forEach(function (_slide, i) {
        var dot = document.createElement('button');
        dot.type = 'button';
        dot.className = 'insight-map-slider__dot';
        dot.setAttribute('role', 'tab');
        dot.setAttribute('aria-label', 'Show map ' + (i + 1));
        dot.addEventListener('click', function () {
          go(i);
          restartAuto();
        });
        dotsHost.appendChild(dot);
      });
    }

    function stopAuto() {
      if (timer) {
        window.clearInterval(timer);
        timer = null;
      }
    }

    function startAuto() {
      if (reduced || slides.length < 2) return;
      stopAuto();
      timer = window.setInterval(function () {
        go(index + 1);
      }, 5000);
    }

    function restartAuto() {
      stopAuto();
      startAuto();
    }

    root.querySelectorAll('.insight-map-slider__open').forEach(function (btn) {
      btn.addEventListener('click', function () {
        openLightbox(
          btn.getAttribute('data-map-src') || '',
          btn.getAttribute('data-map-title') || ''
        );
      });
    });

    root.addEventListener('mouseenter', stopAuto);
    root.addEventListener('mouseleave', startAuto);
    root.addEventListener('focusin', stopAuto);
    root.addEventListener('focusout', function (ev) {
      if (!root.contains(ev.relatedTarget)) startAuto();
    });

    go(0);
    startAuto();
  }

  function boot() {
    document.querySelectorAll('.insight-rankings').forEach(initRoot);
    document.querySelectorAll('[data-insight-map-slider], .insight-map-slider').forEach(initMapSlider);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
