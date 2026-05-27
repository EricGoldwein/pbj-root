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

  function renderDonations(donations, total, count, ownerLabel, oType) {
    if (!donations || !donations.length) {
      panel.innerHTML = '<p class="owner-fec-empty">No contributions found in FEC records for this name.</p>';
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
        return '<article class="owner-fec-card">' +
          '<div class="owner-fec-card-amt">' + formatContributionAmount(d.amount) +
          fecLinkHtml(d) +
          '</div>' +
          '<div class="owner-fec-card-meta">' +
          (d.donor_name ? '<div><strong>FEC contributor:</strong> ' + escapeHtml(d.donor_name) + '</div>' : '') +
          (d.date ? '<div>Date: ' + formatDonationDate(d.date) + '</div>' : '') +
          (d.committee ? '<div><strong>Committee:</strong> ' + escapeHtml(d.committee) + '</div>' : '') +
          (d.candidate ? '<div><strong>Candidate:</strong> ' + escapeHtml(d.candidate) +
            (d.office ? ' (' + escapeHtml(d.office) + ')' : '') +
            (d.party ? ' — ' + escapeHtml(d.party) : '') + '</div>' : '') +
          '</div></article>';
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
        var msg = 'Request failed. Please try again.';
        if (response.status === 502) msg = 'FEC request timed out. Try again.';
        else if (response.status === 503) msg = 'Search temporarily unavailable.';
        panel.innerHTML = '<p class="owner-fec-error">' + escapeHtml(msg) + '</p>';
        return;
      }
      var data = await response.json();
      if (data.error) {
        panel.innerHTML = '<p class="owner-fec-error">' + escapeHtml(data.error) + '</p>';
        return;
      }
      renderDonations(data.donations, data.total, data.count, ownerName, ownerType);
      loaded = true;
      btn.textContent = 'Refresh FEC contributions';
    } catch (err) {
      panel.innerHTML = '<p class="owner-fec-error">Error: ' + escapeHtml(err.message || 'Network error') + '</p>';
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
