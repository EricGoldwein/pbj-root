/**
 * Insights article search: opens sitewide public-search overlay with live
 * results (same index as homepage / nav). Focus or type → overlay autofill.
 */
(function () {
  'use strict';

  function seedOverlay(query) {
    var q = query || '';
    var oi = document.getElementById('pbj-public-search-input');
    var overlay = document.getElementById('pbj-public-search-overlay');
    if (!oi || !overlay || overlay.getAttribute('data-open') !== 'true') return false;
    if (oi.value !== q) oi.value = q;
    // Prefer InputEvent so listeners that check event.type still fire.
    try {
      oi.dispatchEvent(new InputEvent('input', { bubbles: true, data: q, inputType: 'insertText' }));
    } catch (e) {
      oi.dispatchEvent(new Event('input', { bubbles: true }));
    }
    try {
      oi.focus();
      if (typeof oi.setSelectionRange === 'function') {
        var len = oi.value.length;
        oi.setSelectionRange(len, len);
      }
    } catch (e2) { /* ignore */ }
    return true;
  }

  function openWithQuery(trigger, query) {
    var q = (query || '').trim();
    var open = window.PBJ320_openPublicSearch;
    if (typeof open !== 'function') {
      // Retry briefly — universal bundle may still be parsing
      var tries = 0;
      var t = window.setInterval(function () {
        tries += 1;
        if (typeof window.PBJ320_openPublicSearch === 'function') {
          window.clearInterval(t);
          openWithQuery(trigger, query);
        } else if (tries > 20) {
          window.clearInterval(t);
          window.location.href = '/#home-search';
        }
      }, 50);
      return;
    }
    open(trigger);
    // openPublicSearch clears the overlay input; re-seed after paint
    window.setTimeout(function () {
      seedOverlay(q);
    }, 0);
    window.setTimeout(function () {
      seedOverlay(q);
    }, 50);
  }

  function bindInsightSearch() {
    var input = document.getElementById('insight-search-input');
    if (!input || input.getAttribute('data-pbj-bound') === '1') return;
    input.setAttribute('data-pbj-bound', '1');

    var opened = false;

    function markExpanded(on) {
      input.setAttribute('aria-expanded', on ? 'true' : 'false');
    }

    function ensureOpen() {
      opened = true;
      markExpanded(true);
      openWithQuery(input, input.value);
    }

    input.addEventListener('focus', function () {
      ensureOpen();
    });

    input.addEventListener('pointerdown', function () {
      // Open before focus settles so first keystrokes land in the overlay
      ensureOpen();
    });

    input.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') return;
      if (ev.key === 'Tab') return;
      // Let printable keys / Enter open+seed; overlay takes focus for live results
      if (ev.key === 'Enter') {
        ev.preventDefault();
      }
      ensureOpen();
      if (ev.key.length === 1 && !ev.ctrlKey && !ev.metaKey && !ev.altKey) {
        // Character will be typed into article field; sync on next input event
        window.setTimeout(function () {
          seedOverlay(input.value);
        }, 0);
      }
    });

    input.addEventListener('input', function () {
      var overlay = document.getElementById('pbj-public-search-overlay');
      if (!overlay || overlay.getAttribute('data-open') !== 'true') {
        ensureOpen();
        return;
      }
      seedOverlay(input.value);
    });

    var obsTimer = window.setInterval(function () {
      var overlay = document.getElementById('pbj-public-search-overlay');
      if (!overlay) return;
      if (overlay.getAttribute('data-open') !== 'true') {
        opened = false;
        markExpanded(false);
      }
    }, 400);
    window.addEventListener('pagehide', function () {
      window.clearInterval(obsTimer);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindInsightSearch);
  } else {
    bindInsightSearch();
  }
})();
