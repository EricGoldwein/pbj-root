/**
 * /owners hub — Connecticut CMS ownership profile search (PAC or organization name).
 */
(function () {
  'use strict';

  var input = document.getElementById('ownersHubSearchInput');
  var list = document.getElementById('ownersHubSearchResults');
  if (!input || !list) return;

  var debounceTimer = null;
  var activeIndex = -1;
  var lastSuggestions = [];

  function clearResults() {
    list.innerHTML = '';
    list.hidden = true;
    activeIndex = -1;
    lastSuggestions = [];
  }

  function renderSuggestions(items) {
    lastSuggestions = items || [];
    list.innerHTML = '';
    if (!lastSuggestions.length) {
      list.hidden = true;
      return;
    }
    lastSuggestions.forEach(function (item, idx) {
      var li = document.createElement('li');
      var btn = document.createElement('a');
      btn.href = item.profile_url || '/owners/' + item.associate_id;
      btn.className = 'owners-hub-result';
      btn.setAttribute('role', 'option');
      btn.id = 'ownersHubOpt' + idx;
      var name = document.createElement('span');
      name.className = 'owners-hub-result-name';
      name.textContent = item.name || item.associate_id;
      var pac = document.createElement('span');
      pac.className = 'owners-hub-result-pac';
      pac.textContent = item.associate_id || '';
      btn.appendChild(name);
      btn.appendChild(pac);
      btn.addEventListener('mousedown', function (e) {
        e.preventDefault();
      });
      li.appendChild(btn);
      list.appendChild(li);
    });
    list.hidden = false;
  }

  function fetchSuggestions(q) {
    var url = '/owners/api/cms-search?q=' + encodeURIComponent(q);
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

  input.addEventListener('keydown', function (e) {
    if (!lastSuggestions.length) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      activeIndex = Math.min(activeIndex + 1, lastSuggestions.length - 1);
      var el = document.getElementById('ownersHubOpt' + activeIndex);
      if (el) el.focus();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      activeIndex = Math.max(activeIndex - 1, 0);
      var elUp = document.getElementById('ownersHubOpt' + activeIndex);
      if (elUp) elUp.focus();
    } else if (e.key === 'Escape') {
      clearResults();
    }
  });

  document.addEventListener('click', function (e) {
    if (!list.contains(e.target) && e.target !== input) {
      clearResults();
    }
  });
})();
