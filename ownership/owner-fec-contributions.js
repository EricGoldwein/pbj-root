/**
 * Inline FEC contributions on /owners/<pac> — same API as /owner political search.
 */
(function () {
  'use strict';

  var section = document.getElementById('ownerFecContributions');
  if (!section) return;

  var btn = document.getElementById('ownerFecLoadBtn');
  var panel = document.getElementById('ownerFecPanel');
  var ownerName = (section.getAttribute('data-owner-name') || '').trim();
  var ownerType = (section.getAttribute('data-owner-type') || 'ORGANIZATION').trim();
  var loaded = false;

  function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
  }

  function formatDonationDate(dateStr) {
    if (!dateStr || dateStr === 'nan' || dateStr === 'None') return 'N/A';
    var m = String(dateStr).match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m) return m[2] + '/' + m[3] + '/' + m[1];
    return String(dateStr);
  }

  function fecLinkHtml(d) {
    if (d.fec_link) {
      return ' <a href="' + escapeHtml(d.fec_link) + '" target="_blank" rel="noopener" class="owner-fec-source-btn" title="View FEC filing">View on FEC</a>';
    }
    if (d.donor_name) {
      var url = 'https://www.fec.gov/data/receipts/individual-contributions/?contributor_name=' +
        encodeURIComponent(d.donor_name).replace(/%20/g, '+');
      return ' <a href="' + url + '" target="_blank" rel="noopener" class="owner-fec-source-btn" title="Search contributor on FEC">Search on FEC</a>';
    }
    return '';
  }

  function formatContributionAmount(amount) {
    var n = Number(amount);
    if (isNaN(n)) return '$0';
    var mobile = window.innerWidth <= 768;
    if (mobile) return '$' + Math.round(n).toLocaleString();
    return '$' + n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function fecSearchUrl(name) {
    return 'https://www.fec.gov/data/receipts/individual-contributions/?contributor_name=' +
      encodeURIComponent(name || '').replace(/%20/g, '+');
  }

  function fecEmptyMessageHtml(name) {
    var label = escapeHtml(name || 'this name');
    var fecUrl = fecSearchUrl(name);
    return '<p class="owner-fec-empty">No FEC contributions found for <strong>' + label +
      '</strong>. <a href="' + escapeHtml(fecUrl) + '" target="_blank" rel="noopener">Search on FEC.gov</a></p>';
  }

  function toTitleCaseName(str) {
    if (!str) return '';
    return String(str).toLowerCase().replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }

  var hideDonorPopupTimer = null;

  function positionDonorPopup(el, wrap) {
    var pad = 8;
    if (window.innerWidth <= 768) {
      el.style.left = '50%';
      el.style.top = '50%';
      el.style.transform = 'translate(-50%, -50%)';
    } else {
      var r = wrap.getBoundingClientRect();
      var popupHeight = el.offsetHeight || 220;
      var spaceBelow = window.innerHeight - 20 - r.bottom;
      var spaceAbove = r.top - 20;
      var centerX = r.left + r.width / 2;
      el.style.left = centerX + 'px';
      if (spaceBelow >= popupHeight + pad || spaceBelow >= spaceAbove) {
        el.style.top = (r.bottom + pad) + 'px';
        el.style.transform = 'translate(-50%, 0)';
      } else {
        el.style.top = (r.top - pad) + 'px';
        el.style.transform = 'translate(-50%, -100%)';
      }
    }
  }

  function showDonorPopup(uid) {
    if (hideDonorPopupTimer) {
      clearTimeout(hideDonorPopupTimer);
      hideDonorPopupTimer = null;
    }
    document.querySelectorAll('.donor-popup.show').forEach(function (open) {
      if (open.id !== uid) {
        open.classList.remove('show');
        open.style.display = '';
      }
    });
    var el = document.getElementById(uid);
    if (!el) return;
    var wrap = el._donorPopupParent || el.closest('.donor-info-wrap');
    if (!wrap) return;
    if (!el._donorPopupParent) {
      el._donorPopupParent = wrap;
      document.body.appendChild(el);
    }
    positionDonorPopup(el, wrap);
    el.classList.add('show');
    el.style.display = 'block';
  }

  function hideDonorPopup(uid) {
    hideDonorPopupTimer = setTimeout(function () {
      var el = document.getElementById(uid);
      if (el) {
        el.classList.remove('show');
        el.style.display = '';
        if (el._donorPopupParent) {
          el._donorPopupParent.appendChild(el);
          el._donorPopupParent = null;
        }
      }
    }, 200);
  }

  function toggleDonorPopup(uid) {
    var el = document.getElementById(uid);
    if (!el) return;
    if (el.classList.contains('show')) hideDonorPopup(uid);
    else showDonorPopup(uid);
  }

  window.showDonorPopup = showDonorPopup;
  window.hideDonorPopup = hideDonorPopup;
  window.toggleDonorPopup = toggleDonorPopup;

  function formatFecContributor(d) {
    if (!d || !d.donor_name) return '';
    var name = escapeHtml(toTitleCaseName(d.donor_name));
    var cityDisplay = d.donor_city ? toTitleCaseName(d.donor_city) : '';
    var stateDisplay = d.donor_state ? String(d.donor_state).toUpperCase() : '';
    var loc = (cityDisplay && stateDisplay)
      ? ' (' + escapeHtml(cityDisplay) + ', ' + escapeHtml(stateDisplay) + ')'
      : '';
    var inlineText = name + loc;
    var hasPopup = !!(d.donor_city || d.donor_state || d.employer || d.occupation || d.committee || d.candidate);
    if (!hasPopup) return '<strong>FEC listing:</strong> ' + inlineText;
    var popupParts = [];
    if (name) popupParts.push('<strong>' + name + '</strong>');
    if (d.employer || d.occupation) {
      popupParts.push(
        '<div><strong>Employer/Occupation:</strong> ' +
        escapeHtml([d.employer, d.occupation].filter(Boolean).map(function (s) {
          return toTitleCaseName(s);
        }).join(' — ')) +
        '</div>'
      );
    }
    if (d.committee) popupParts.push('<div><strong>Committee:</strong> ' + escapeHtml(d.committee) + '</div>');
    if (d.candidate) {
      popupParts.push(
        '<div><strong>Candidate:</strong> ' + escapeHtml(d.candidate) +
        (d.office ? ' (' + escapeHtml(d.office) + ')' : '') + '</div>'
      );
    }
    if (d.date) popupParts.push('<div><strong>Date:</strong> ' + formatDonationDate(d.date) + '</div>');
    popupParts.push('<div style="margin-top:0.5rem;">' + fecLinkHtml(d) + '</div>');
    var uid = 'popup-' + Math.random().toString(36).slice(2);
    var touch = 'ontouchstart' in window;
    var hoverOn = touch ? '' : ' onmouseenter="showDonorPopup(\'' + uid + '\')" onmouseleave="hideDonorPopup(\'' + uid + '\')"';
    return (
      '<strong>FEC listing:</strong> ' +
      '<span class="donor-info-wrap" style="position:relative;display:inline-block;"' + hoverOn + '>' +
      '<span class="donor-info-trigger" role="button" tabindex="0" aria-label="Show contributor details" ' +
      'onclick="event.stopPropagation();toggleDonorPopup(\'' + uid + '\')" ' +
      'onkeydown="if(event.key===\'Enter\'||event.key===\' \'){event.preventDefault();toggleDonorPopup(\'' + uid + '\')}">' +
      inlineText + '</span>' +
      '<div id="' + uid + '" class="donor-popup">' + popupParts.join('') + '</div></span>'
    );
  }

  function fecRecipientLineHtml(d) {
    if (d.candidate) {
      return '<div><strong>To:</strong> ' + escapeHtml(d.candidate) +
        (d.office ? ' (' + escapeHtml(d.office) + ')' : '') +
        (d.party ? ' — ' + escapeHtml(d.party) : '') + '</div>';
    }
    if (d.committee) {
      return '<div><strong>Committee:</strong> ' + escapeHtml(d.committee) + '</div>';
    }
    return '';
  }

  function fecContributionMetaHtml(d) {
    var fecBlock = formatFecContributor(d);
    var meta = fecBlock ? fecBlock : '';
    if (!fecBlock && d.donor_name) {
      meta += '<div><strong>FEC contributor:</strong> ' + escapeHtml(d.donor_name) + '</div>';
    }
    var recipient = fecRecipientLineHtml(d);
    if (recipient) {
      meta += (meta ? '<br>' : '') + recipient;
    }
    if (d.date) {
      meta += (meta ? '<br>' : '') + 'Date: ' + formatDonationDate(d.date);
    }
    return meta;
  }

  function renderDonations(donations, total, count, ownerLabel, oType) {
    if (!donations || !donations.length) {
      panel.innerHTML = fecEmptyMessageHtml(ownerLabel || ownerName);
      return;
    }

    var totalAmount = total != null ? total : donations.reduce(function (s, d) { return s + (d.amount || 0); }, 0);
    var donationCount = count != null ? count : donations.length;
    var byCommittee = {};
    var byCandidate = {};
    var committeeIds = {};
    var byYear = {};

    donations.forEach(function (d) {
      if (d.committee) byCommittee[d.committee] = (byCommittee[d.committee] || 0) + d.amount;
      if (d.candidate) {
        var ck = d.candidate + ' (' + (d.office || 'Unknown') + ')';
        byCandidate[ck] = (byCandidate[ck] || 0) + d.amount;
      }
      if (d.committee && d.committee_id && !committeeIds[d.committee]) {
        committeeIds[d.committee] = d.committee_id;
      }
      if (d.date) {
        var ym = String(d.date).match(/^(\d{4})/);
        if (ym) byYear[parseInt(ym[1], 10)] = (byYear[parseInt(ym[1], 10)] || 0) + (d.amount || 0);
      }
    });

    var topCommittees = Object.keys(byCommittee).map(function (k) { return [k, byCommittee[k]]; })
      .sort(function (a, b) { return b[1] - a[1]; }).slice(0, 5);
    var topCandidates = Object.keys(byCandidate).map(function (k) { return [k, byCandidate[k]]; })
      .sort(function (a, b) { return b[1] - a[1]; }).slice(0, 5);

    var curYear = new Date().getFullYear();
    var yearBits = [curYear, curYear - 1, curYear - 2].filter(function (y) { return y >= 2020; }).map(function (year) {
      var amt = byYear[year] || 0;
      var amtStr = amt > 0 ? '$' + amt.toLocaleString(undefined, { maximumFractionDigits: 0 }) : 'N/A';
      return '<strong>' + year + '</strong>: ' + amtStr;
    }).join('; ');

    var csvRows = [['FEC Contributor', 'Date', 'Amount', 'Committee', 'Candidate', 'Office', 'Party', 'Employer', 'Occupation', 'Location', 'FEC Link']];
    donations.forEach(function (d) {
      csvRows.push([
        d.donor_name || '', d.date || '', d.amount || 0, d.committee || '', d.candidate || '',
        d.office || '', d.party || '', d.employer || '', d.occupation || '',
        (d.donor_city && d.donor_state) ? d.donor_city + ', ' + d.donor_state : '',
        d.fec_link || ''
      ]);
    });
    var csvContent = csvRows.map(function (row) {
      return row.map(function (cell) { return '"' + String(cell).replace(/"/g, '""') + '"'; }).join(',');
    }).join('\n');
    var csvUrl = URL.createObjectURL(new Blob([csvContent], { type: 'text/csv;charset=utf-8;' }));

    window.ownerFecPageData = { donations: donations, ownerName: ownerLabel, csvUrl: csvUrl };
    window.ownerFecPage = 1;

    var summaryHtml = topCommittees.length || topCandidates.length
      ? '<div class="owner-fec-tops">' +
        (topCommittees.length ? '<div class="owner-fec-top-box"><strong>Top committees</strong>' +
          topCommittees.map(function (pair) {
            var link = committeeIds[pair[0]]
              ? '<a href="https://www.fec.gov/data/receipts/?committee_id=' + encodeURIComponent(committeeIds[pair[0]]) + '" target="_blank" rel="noopener" class="owner-fec-link">' + escapeHtml(pair[0]) + '</a>'
              : escapeHtml(pair[0]);
            return '<div class="owner-fec-top-row">' + link + ': $' + pair[1].toLocaleString(undefined, { maximumFractionDigits: 0 }) + '</div>';
          }).join('') + '</div>' : '') +
        (topCandidates.length ? '<div class="owner-fec-top-box"><strong>Top candidates</strong>' +
          topCandidates.map(function (pair) {
            return '<div class="owner-fec-top-row">' + escapeHtml(pair[0]) + ': $' + pair[1].toLocaleString(undefined, { maximumFractionDigits: 0 }) + '</div>';
          }).join('') + '</div>' : '') +
        '</div>'
      : '';

    panel.innerHTML =
      '<div class="owner-fec-results">' +
      '<h3 class="owner-fec-results-title">Political contributions — ' + escapeHtml(ownerLabel) + '</h3>' +
      '<div class="owner-fec-total-bar">' +
      '<div><div class="owner-fec-total-amt">Total contributed: $' +
      totalAmount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + '</div>' +
      '<div class="owner-fec-total-meta">' + donationCount + ' contribution' + (donationCount === 1 ? '' : 's') +
      (yearBits ? ' · ' + yearBits : '') + '</div></div>' +
      '<a class="owner-fec-export" href="' + csvUrl + '" download="fec_' + ownerLabel.replace(/[^a-zA-Z0-9]/g, '_') + '.csv">Export CSV</a>' +
      '</div>' + summaryHtml +
      '<h4 class="owner-fec-list-heading">All contributions (' + donationCount + ')</h4>' +
      '<div id="ownerFecList" class="owner-fec-list"></div>' +
      '<div id="ownerFecPagination" class="owner-fec-pagination"></div>' +
      '<p class="owner-fec-source">Data from the <a href="https://www.fec.gov/data/receipts/" target="_blank" rel="noopener">Federal Election Commission</a></p>' +
      '</div>';

    renderPage(1);
  }

  function renderPage(page) {
    var data = window.ownerFecPageData;
    if (!data || !data.donations) return;
    var PER = 20;
    var totalPages = Math.max(1, Math.ceil(data.donations.length / PER));
    page = Math.max(1, Math.min(page, totalPages));
    window.ownerFecPage = page;
    var slice = data.donations.slice((page - 1) * PER, page * PER);
    var list = document.getElementById('ownerFecList');
    if (list) {
      list.innerHTML = slice.map(function (d) {
        var meta = fecContributionMetaHtml(d);
        return '<article class="owner-fec-card">' +
          '<div class="owner-fec-card-amt">' + formatContributionAmount(d.amount) +
          fecLinkHtml(d) +
          '</div>' +
          (meta ? '<div class="owner-fec-card-meta">' + meta + '</div>' : '') +
          '</article>';
      }).join('');
    }
    var pag = document.getElementById('ownerFecPagination');
    if (pag && data.donations.length > PER) {
      pag.innerHTML =
        '<span>Page ' + page + ' of ' + totalPages + '</span>' +
        (page > 1 ? '<button type="button" class="owner-fec-page-btn" data-page="' + (page - 1) + '">Prev</button>' : '') +
        (page < totalPages ? '<button type="button" class="owner-fec-page-btn" data-page="' + (page + 1) + '">Next</button>' : '');
      pag.querySelectorAll('.owner-fec-page-btn').forEach(function (b) {
        b.addEventListener('click', function () { renderPage(parseInt(b.getAttribute('data-page'), 10)); });
      });
    } else if (pag) {
      pag.innerHTML = '';
    }
  }

  async function loadFec() {
    if (!ownerName) {
      panel.innerHTML = '<p class="owner-fec-error">No owner name available for FEC search.</p>';
      return;
    }
    panel.hidden = false;
    panel.innerHTML = '<p class="owner-fec-loading">Searching FEC records for ' + escapeHtml(ownerName) + '… This may take a moment.</p>';
    btn.disabled = true;
    btn.setAttribute('aria-busy', 'true');

    try {
      var response = await fetch('/owner/api/query-fec', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ owner_name: ownerName, owner_type: ownerType })
      });
      if (!response.ok) {
        panel.innerHTML = fecEmptyMessageHtml(ownerName);
        return;
      }
      var data = await response.json();
      if (data.error) {
        panel.innerHTML = fecEmptyMessageHtml(ownerName);
        return;
      }
      renderDonations(data.donations, data.total, data.count, ownerName, ownerType);
      loaded = true;
      btn.textContent = 'Refresh FEC contributions';
    } catch (err) {
      panel.innerHTML = fecEmptyMessageHtml(ownerName);
    } finally {
      btn.disabled = false;
      btn.removeAttribute('aria-busy');
      btn.setAttribute('aria-expanded', 'true');
    }
  }

  if (btn && panel) {
    btn.addEventListener('click', function () {
      loadFec();
    });
  }
})();
