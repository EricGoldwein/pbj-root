/**
 * PBJ320 AI Support — icon launch + popover copy.
 */
(function (global) {
  'use strict';

  var MSG_PROMPT = 'PBJ320 prompt copied.';
  var MSG_CONTEXT = 'PBJ320 context copied.';
  var MSG_PACKET = 'PBJ320 AI packet copied.';
  var MSG_INSTALL = 'Install steps copied.';
  var MSG_CSV = 'CSV download started.';
  var AI_URLS = {
    claude: 'https://claude.ai/new',
    chatgpt: 'https://chatgpt.com/',
  };
  var PREFILL_MAX = {
    chatgpt: 8000,
    claude: 12000,
  };
  /** Reject ?q= when encodeURIComponent(text) exceeds this (browser / gateway limits). */
  var PREFILL_ENCODE_SOFT = {
    chatgpt: 1900,
    claude: 11000,
  };
  var LAUNCH_MSG = {
    chatgpt: 'ChatGPT opened — paste the prompt from your clipboard (Ctrl+V / Cmd+V).',
    claude: 'Opened Claude — review prompt ready to send.',
  };
  var LAUNCH_MSG_FULL = {
    claude:
      'Opened Claude — review prefilled. Facility snapshot (.txt with embedded quarterly data) downloaded for upload.',
  };
  var LAUNCH_MSG_CLIPBOARD = {
    claude:
      'Opened Claude — full prompt copied to clipboard before opening the tab. Paste with Ctrl+V / Cmd+V (link prefill is skipped when the prompt is long).',
  };
  var ONESHOT_OPTIONAL =
    '\n\n(Optional: a single facility snapshot text file downloads with your review — page context, longitudinal summaries, and embedded quarterly CSV data. Spreadsheet CSVs are optional via the CSV button.)';
  var ONESHOT_OPTIONAL_CHATGPT =
    '\n\n(Optional: attach the downloaded PBJ320 snapshot .txt in ChatGPT for full page context and embedded quarterly data.)';

  function isMobileHandoff() {
    try {
      if (global.matchMedia) {
        if (global.matchMedia('(max-width: 768px)').matches) return true;
        if (global.matchMedia('(pointer: coarse)').matches && global.matchMedia('(max-width: 1024px)').matches) {
          return true;
        }
      }
    } catch (eMobile) {
      /* ignore */
    }
    return false;
  }

  /** Compact visual ask for URL openers (fits ?q= limits). */
  function urlVisualAskLine() {
    return (
      'Include one small exhibit for the strongest supported finding—a simple table, trend, or role-mix ' +
      'chart using only the metrics below (or chart-ready Markdown, or one sentence on why none).'
    );
  }

  /** External-facing review ask for ?q= URL prefill (never clipboard/upload meta). */
  function externalUrlReviewIntro(helperEl, opts) {
    opts = opts || {};
    var audience = stubAudienceLabel(helperEl);
    var withVisual = opts.withVisual !== false;
    var parts = [
      'Review this nursing home\'s CMS PBJ quarterly staffing (' +
        audience +
        ' lens). Separate shows / suggests / cannot prove; cite HPRD from the metrics below.',
    ];
    if (withVisual) parts.push(urlVisualAskLine());
    parts.push(
      'Quarterly PBJ is screening data—not proof of harm or violations. Verify against Care Compare and official PBJ before relying on this.'
    );
    return parts.join(' ');
  }

  function launchToastForChatgpt(opts) {
    opts = opts || {};
    var mobile = !!opts.mobile;
    var tier = opts.tier || 'full';
    var snap = !!opts.snapshot;
    var pasted = !!opts.clipboard;
    if (tier === 'full') {
      if (mobile) {
        return (
          'ChatGPT opened — starter prompt in the box. Full review on your clipboard; paste in a follow-up. ' +
          (snap ? ' Snapshot .txt saved if your browser allows downloads.' : '')
        );
      }
      return (
        'ChatGPT opened — starter prompt in the box. Full review copied to clipboard; paste after you send. ' +
        (snap ? ' Attach the downloaded PBJ320 snapshot .txt for full context.' : '')
      );
    }
    if (mobile) {
      return (
        'ChatGPT opened — short prompt in the box. Full review on your clipboard — paste it in your next message. ' +
        (snap ? ' (.txt upload on phone is optional; pasting is easier.)' : '')
      );
    }
    return (
      'ChatGPT opened — short prompt in the box. Full review on your clipboard — paste after you send.' +
      (snap ? ' Attach the downloaded PBJ320 snapshot .txt if you want file upload too.' : '') +
      (pasted ? '' : ' (Allow clipboard access if paste is empty.)')
    );
  }

  function buildPrefillUrl(provider, text) {
    if (!text) return null;
    var p = String(provider || '').toLowerCase();
    var max = PREFILL_MAX[p] || 8000;
    if (p === 'chatgpt') {
      var cg = (global.__PBJ_REVIEW_FRAMEWORK__ || {}).chatgpt || {};
      max = Number(cg.urlPrefillMax) || 1900;
    }
    if (text.length > max) return null;
    var q = encodeURIComponent(text);
    var soft = PREFILL_ENCODE_SOFT[p] != null ? PREFILL_ENCODE_SOFT[p] : 11000;
    if (q.length > soft) return null;
    /* Claude/ChatGPT can accept long query strings in modern browsers; keep a high guardrail only. */
    if (q.length > 48000) return null;
    if (p === 'claude') return 'https://claude.ai/new?q=' + q;
    if (p === 'chatgpt') return 'https://chatgpt.com/?q=' + q;
    return null;
  }

  function copyForLaunch(text) {
    if (!text) return Promise.resolve(false);
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).then(function () { return true; }).catch(function () {
        return syncCopy(text);
      });
    }
    return Promise.resolve(syncCopy(text));
  }

  function showToast(msg) {
    var existing = document.querySelector('.pbj-ai-toast');
    if (existing) existing.remove();
    var toast = document.createElement('div');
    toast.className = 'pbj-ai-toast';
    toast.setAttribute('role', 'status');
    toast.setAttribute('aria-live', 'polite');
    toast.textContent = msg;
    document.body.appendChild(toast);
    requestAnimationFrame(function () {
      toast.classList.add('pbj-ai-toast--visible');
    });
    setTimeout(function () {
      toast.classList.remove('pbj-ai-toast--visible');
      setTimeout(function () { toast.remove(); }, 220);
    }, 3200);
  }

  function syncCopy(text) {
    if (!text) return false;
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.cssText = 'position:fixed;top:0;left:0;width:2px;height:2px;padding:0;border:none;opacity:0;';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    var ok = false;
    try {
      ok = document.execCommand('copy');
    } catch (e) {
      ok = false;
    }
    document.body.removeChild(ta);
    return ok;
  }

  function markCopied(btn) {
    if (!btn) return;
    var textEl =
      btn.querySelector('.ai-copy-btn__text') || btn.querySelector('.pbj-ai-provider-chip__text');
    if (!textEl) return;
    if (!btn.dataset.pbjCopyDefault) btn.dataset.pbjCopyDefault = textEl.textContent;
    btn.classList.add('is-copied');
    textEl.textContent = 'Copied!';
    setTimeout(function () {
      btn.classList.remove('is-copied');
      textEl.textContent = btn.dataset.pbjCopyDefault;
    }, 2200);
  }

  function copyText(text, msg, btn) {
    if (!text) {
      showToast('Nothing to copy — refresh and try again.');
      return;
    }
    function done() {
      showToast(msg || 'Copied — paste with Ctrl+V');
      markCopied(btn);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done).catch(function () {
        if (syncCopy(text)) done();
      });
      return;
    }
    if (syncCopy(text)) done();
  }

  function readFromId(id) {
    if (!id) return '';
    var el = document.getElementById(id);
    if (!el) return '';
    return (el.value || el.textContent || '').trim();
  }

  function downloadBlob(text, filename, mime, quiet) {
    if (!text) {
      if (!quiet) showToast('Nothing to download — refresh and try again.');
      return false;
    }
    var name = filename || 'pbj320_export.dat';
    try {
      var blob = new Blob([text], { type: mime || 'application/octet-stream' });
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url;
      a.download = name;
      a.style.display = 'none';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(function () {
        URL.revokeObjectURL(url);
      }, 500);
      return true;
    } catch (err) {
      if (!quiet) showToast('Download failed — try again.');
      return false;
    }
  }

  function downloadCsv(text, filename, quiet) {
    var ok = downloadBlob(text, filename || 'pbj320_export.csv', 'text/csv;charset=utf-8', true);
    if (ok && !quiet) showToast(MSG_CSV);
    return ok;
  }

  function downloadTextFile(text, filename, quiet) {
    return downloadBlob(text, filename || 'pbj320_page_context.txt', 'text/plain;charset=utf-8', quiet);
  }

  function readExtendedContext(helperEl) {
    if (!helperEl) return '';
    var eid = helperEl.getAttribute('data-extended-context-id');
    if (eid) {
      var t = readFromId(eid);
      if (t && t.trim()) return t;
    }
    return readHelperContext(helperEl) || '';
  }

  function facilitySnapshotFilename(helperEl) {
    var slug = (helperEl.getAttribute('data-facility-name') || 'facility')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '')
      .slice(0, 36);
    if (!slug) slug = 'facility';
    var ccn = helperEl.getAttribute('data-ai-ccn') || '';
    if (!ccn) {
      var ctx0 = readHelperContext(helperEl) || '';
      var m = ctx0.match(/CCN:\s*(\d{5,6})/i);
      if (m) ccn = m[1];
    }
    return 'pbj320_' + slug + (ccn ? '_' + ccn : '') + '_facility_snapshot.txt';
  }

  function buildSnapshotDownloadPreamble(helperEl) {
    if (!helperEl || !helperEl.getAttribute) return '';
    var lens = (helperEl.dataset.pbjLens || '').trim();
    var len = (helperEl.dataset.pbjLength || '').trim();
    if (!lens && !len) return '';
    if (!lens) lens = 'general';
    if (!len) len = 'quick';
    return (
      '--- Client note: UI selection at download time ---\n' +
      'review_lens=' +
      lens +
      '\nreview_length=' +
      len +
      '\n' +
      '(Snapshot body is generated with the page; align your pasted PBJ320 review prompt with this lens/length, ' +
      'or change the dropdown and re-download.)\n\n'
    );
  }

  /** One combined snapshot for Claude/GPT (embedded quarterly CSV sections). */
  function downloadFacilitySnapshotFile(helperEl, text) {
    var out = { ok: false, filename: '' };
    if (!helperEl || !(text || '').trim()) return out;
    out.filename = facilitySnapshotFilename(helperEl);
    var preamble = buildSnapshotDownloadPreamble(helperEl);
    var body = (preamble || '') + text;
    out.ok = !!downloadBlob(
      body,
      out.filename,
      'text/plain;charset=utf-8',
      true
    );
    return out;
  }

  /** Optional spreadsheet exports (CSV chip / footer links). */
  function downloadProviderSpreadsheetCsvs(helperEl) {
    var n = 0;
    if (!helperEl) return n;
    var delay = 0;
    var snapId = helperEl.getAttribute('data-snapshot-csv-id');
    var trendId = helperEl.getAttribute('data-trends-csv-id');
    var snapFn =
      helperEl.getAttribute('data-snapshot-csv-filename') ||
      'pbj320_facility_snapshot_detail.csv';
    var trendFn =
      helperEl.getAttribute('data-trends-csv-filename') || 'pbj320_quarterly_trends.csv';
    if (snapId && readFromId(snapId)) {
      n += 1;
      (function (id, fn, d) {
        setTimeout(function () {
          downloadCsv(readFromId(id), fn, true);
        }, d);
      })(snapId, snapFn, delay);
      delay += 400;
    }
    if (trendId && readFromId(trendId)) {
      n += 1;
      (function (id, fn, d) {
        setTimeout(function () {
          downloadCsv(readFromId(id), fn, true);
        }, d);
      })(trendId, trendFn, delay);
      delay += 400;
    }
    return n;
  }

  function downloadProviderCsvs(helperEl) {
    return downloadProviderSpreadsheetCsvs(helperEl);
  }

  function frameworkBundle() {
    if (global.PBJReviewFramework && global.PBJReviewFramework.bundle) {
      return global.PBJReviewFramework.bundle() || {};
    }
    return global.__PBJ_REVIEW_FRAMEWORK__ || {};
  }

  function lensConfig() {
    return frameworkBundle().lensConfig || {};
  }

  function normalizeLensKey(lens) {
    var fw = global.PBJReviewFramework;
    if (fw && fw.normalizeLens) return fw.normalizeLens(lens);
    var lc = lensConfig();
    var key = String(lens || '')
      .trim()
      .toLowerCase()
      .replace(/\s+/g, '_')
      .replace(/-/g, '_');
    var aliases = {
      analyst: 'general',
      family_resident: 'family',
      legislator: 'policymaker',
      policy: 'policymaker',
      ombuds: 'ombudsman',
    };
    key = aliases[key] || key;
    var valid = {};
    (lc.primaryLenses || []).concat(lc.moreLenses || []).forEach(function (item) {
      valid[item.id] = true;
    });
    return valid[key] ? key : lc.defaultLens || 'ombudsman';
  }

  function normalizeLengthKey(length) {
    var fw = global.PBJReviewFramework;
    if (fw && fw.normalizeLength) return fw.normalizeLength(length);
    var lc = lensConfig();
    var key = String(length || '')
      .trim()
      .toLowerCase()
      .replace(/\s+/g, '_')
      .replace(/-/g, '_');
    var aliases = { quick_takeaway: 'quick', standard_review: 'standard', detailed_review: 'detailed' };
    key = aliases[key] || key;
    if (key === 'quick' || key === 'standard' || key === 'detailed') return key;
    return lc.defaultLength || 'quick';
  }

  function composeGuardrailsFallback(pageType) {
    var fw = global.PBJReviewFramework;
    if (fw && fw.composeReviewGuardrails) return fw.composeReviewGuardrails(pageType);
    var lc = lensConfig();
    var shared = lc.guardrailsShared || [];
    var ptype = String(pageType || 'facility').toLowerCase();
    var lines = ['Always follow these rules:'];
    if (ptype === 'facility' || ptype === 'provider') {
      lines.push(
        '- If this is a free PBJ320 provider page, treat it as quarterly staffing context and visible facility-level metrics only.'
      );
    }
    if (ptype === 'state') {
      lines.push(
        '- If this is a state page, do not infer facility-level conclusions from state-level aggregates alone.'
      );
    }
    shared.forEach(function (rule) {
      lines.push('- ' + rule);
    });
    return lines.join('\n');
  }

  function composeDashboardPrompt(lens, length, pageType, materialPlaceholder, stateLabel, stateCode) {
    var fw = global.PBJReviewFramework;
    if (fw && fw.composeDashboardPrompt) {
      return fw.composeDashboardPrompt(
        lens,
        length,
        pageType,
        materialPlaceholder,
        stateLabel || '',
        stateCode || ''
      );
    }
    var lensKey = normalizeLensKey(lens);
    var lengthKey = normalizeLengthKey(length);
    var lc = lensConfig();
    var placeholder =
      materialPlaceholder ||
      (frameworkBundle().core || {}).handoffPlaceholder ||
      '[PASTE PBJ320 PAGE TEXT, SCREENSHOT, CSV, OR EXPORT HERE]';
    var takeaway =
      (lc.quickTakeaways || {})[lensKey] || (lc.quickTakeaways || {}).general || '';
    if (lengthKey === 'quick') {
      return takeaway + '\n\n' + composeGuardrailsFallback(pageType);
    }
    return takeaway + '\n\n' + composeGuardrailsFallback(pageType) + '\n\n' + placeholder;
  }

  function packetHasPageContext(text) {
    if (!text) return false;
    return (
      text.indexOf('PBJ320 page context') >= 0 ||
      text.indexOf('PBJ320 URL:') >= 0 ||
      text.indexOf('Facility:') >= 0
    );
  }

  function readHelperContext(helperEl) {
    if (!helperEl) return '';
    var id = helperEl.getAttribute('data-context-id');
    var text = readFromId(id);
    if (!text) {
      var ta = helperEl.querySelector('.pbj-ai-context-data');
      if (ta) text = (ta.value || ta.textContent || '').trim();
    }
    if (!text) {
      var hid = helperEl.getAttribute('data-handoff-id');
      var handoff = readFromId(hid);
      var idx = handoff.indexOf('PBJ320 page context');
      if (idx >= 0) {
        text = handoff.slice(idx).trim();
      } else if (handoff.indexOf('--- Facility under review ---') >= 0) {
        text = handoff.slice(handoff.indexOf('--- Facility under review ---')).trim();
      }
    }
    return text;
  }

  function compactFacilityMaterial(ctx, helperEl, maxSummary) {
    var text = (ctx || '').trim();
    if (!text) return providerContextStub(helperEl);
    var lines = ['--- This facility (PBJ320 quarterly page) ---'];
    var seen = {};
    text.split('\n').forEach(function (raw) {
      var line = raw.trim();
        if (
        line.indexOf('Facility:') === 0 ||
        line.indexOf('CCN:') === 0 ||
        line.indexOf('State:') === 0 ||
        line.indexOf('Quarter / period:') === 0 ||
        line.indexOf('PBJ320 URL:') === 0 ||
        line.indexOf('CMS Care Compare') === 0 ||
        line.indexOf('Facility operating context') === 0 ||
        line.indexOf('Reported average daily census') === 0 ||
        line.indexOf('Ownership type (Care Compare') === 0 ||
        line.indexOf('CMS Special Focus') === 0 ||
        line.indexOf('CMS abuse icon') === 0 ||
        line.indexOf('Affiliated entity — portfolio snapshot') === 0
      ) {
        if (!seen[line]) {
          lines.push(line);
          seen[line] = true;
        }
      }
    });
    var name = helperEl && helperEl.getAttribute('data-facility-name');
    var url = helperEl && helperEl.getAttribute('data-page-url');
    if (name && !seen['Facility: ' + name] && lines.join('\n').indexOf('Facility:') < 0) {
      lines.push('Facility: ' + name);
    }
    if (url && lines.join('\n').indexOf('PBJ320 URL:') < 0) {
      lines.push('PBJ320 URL: ' + url);
    }
    var metrics = [];
    var inMetrics = false;
    text.split('\n').forEach(function (raw) {
      if (raw.indexOf('Key metrics shown on this page:') === 0) {
        inMetrics = true;
        return;
      }
      if (inMetrics) {
        if (
          raw.indexOf('Definitions') === 0 ||
          raw.indexOf('Main PBJ320 summary:') === 0 ||
          raw.indexOf('Interpretation checks:') === 0
        ) {
          inMetrics = false;
          return;
        }
        if (raw.trim().indexOf('- ') === 0 && metrics.length < 8) {
          metrics.push(raw.trim());
        }
      }
    });
    if (metrics.length) {
      lines.push('');
      lines.push('Key metrics on page:');
      metrics.forEach(function (m) {
        lines.push(m);
      });
    }
    var summaryParts = [];
    var inSummary = false;
    text.split('\n').forEach(function (raw) {
      if (raw.trim() === 'Main PBJ320 summary:') {
        inSummary = true;
        return;
      }
      if (inSummary) {
        if (
          raw.indexOf('Interpretation checks:') === 0 ||
          raw.indexOf('Important limitations:') === 0
        ) {
          inSummary = false;
          return;
        }
        if (raw.trim()) summaryParts.push(raw.trim());
      }
    });
    if (summaryParts.length) {
      var cap = maxSummary || 900;
      var summary = summaryParts.join(' ');
      if (summary.length > cap) summary = summary.slice(0, cap - 3).trim() + '...';
      lines.push('');
      lines.push('Summary on page:');
      lines.push(summary);
    }
    return lines.join('\n');
  }

  function stubAudienceLabel(helperEl) {
    var lens = (helperEl && helperEl.dataset && helperEl.dataset.pbjLens) || getStoredLens();
    var lensKey = normalizeLensKey(lens);
    var lc = lensConfig();
    var aud = (lc.lensToAudience || {})[lensKey] || 'analyst';
    var fw = global.PBJReviewFramework;
    if (fw && fw.audienceModeDisplay) {
      return fw.audienceModeDisplay(lensKey, aud);
    }
    var disp = (frameworkBundle().layered || {}).audienceModeDisplay || {};
    if (lensKey && disp[lensKey]) return disp[lensKey];
    var lid;
    for (lid in lc.lensToAudience || {}) {
      if (lc.lensToAudience[lid] === aud && disp[lid]) return disp[lid];
    }
    return disp.general || 'GENERAL ANALYST';
  }

  function buildChatgptStubCore(helperEl) {
    var tpl = String((frameworkBundle().chatgpt || {}).stubTemplate || '').trim();
    if (!tpl) return '';
    return tpl.split('{audience_label}').join(stubAudienceLabel(helperEl));
  }

  /** One line before the long framework prompt so URL ?q= / truncation still names the facility. */
  function oneLineFacilityAnchor(helperEl) {
    if (!helperEl || !helperEl.getAttribute) return '';
    var name = (helperEl.getAttribute('data-facility-name') || '').trim();
    var ccn = (helperEl.getAttribute('data-ai-ccn') || '').trim();
    var url = (helperEl.getAttribute('data-page-url') || '').trim();
    var bits = [];
    if (name) bits.push('Facility: ' + name);
    if (ccn) bits.push('CCN: ' + ccn);
    if (url) bits.push('PBJ320 URL: ' + url);
    if (!bits.length) return '';
    return bits.join(' | ');
  }

  function buildProviderOneShotPrefill(helperEl, provider) {
    syncHelperFromUi(helperEl);
    var lens = helperEl.dataset.pbjLens || getStoredLens();
    var pageType = helperEl.getAttribute('data-page-type') || 'facility';
    var ctx = readHelperContext(helperEl) || providerContextStub(helperEl);
    var head = oneLineFacilityAnchor(helperEl);
    var prefix = head ? head + '\n\n' : '';
    var providerNorm = String(provider || 'claude').toLowerCase();
    var cg = frameworkBundle().chatgpt || {};
    if (providerNorm === 'chatgpt') {
      var stub = buildChatgptStubCore(helperEl);
      if (!stub.trim()) stub = 'Review this PBJ320 nursing home staffing page.';
      var gptMax = (Number(cg.urlPrefillMax) || 1900) - 150;
      var footer = ONESHOT_OPTIONAL_CHATGPT;
      var caps = [520, 420, 300, 220, 140, 100];
      var i;
      for (i = 0; i < caps.length; i++) {
        var compactG = compactFacilityMaterial(ctx, helperEl, caps[i]);
        var packetG = prefix + stub + '\n\n' + compactG + footer;
        if (packetG.length <= gptMax) return packetG;
      }
      var fallbackG = prefix + stub + '\n\n' + compactFacilityMaterial(ctx, helperEl, 80) + footer;
      return fallbackG.length <= gptMax ? fallbackG : fallbackG.slice(0, gptMax);
    }
    var prompt = composeHelperPrompt(lens, effectiveLength(helperEl), pageType, helperEl);
    var max = (PREFILL_MAX[providerNorm] || 8000) - 120;
    var caps = [900, 650, 450, 280, 160];
    for (i = 0; i < caps.length; i++) {
      var compact = compactFacilityMaterial(ctx, helperEl, caps[i]);
      var packet = prefix + prompt + '\n\n' + compact + ONESHOT_OPTIONAL;
      if (packet.length <= max) return packet;
    }
    var fallback = prefix + prompt + '\n\n' + compactFacilityMaterial(ctx, helperEl, 120);
    return fallback.length <= max ? fallback + ONESHOT_OPTIONAL : fallback.slice(0, max);
  }

  /** Short ?q= body: facility anchor + review ask + key metrics (external-facing only). */
  function buildAbbreviatedProviderPrefill(helperEl, provider) {
    syncHelperFromUi(helperEl);
    var ctx = readHelperContext(helperEl) || providerContextStub(helperEl);
    var anchor = oneLineFacilityAnchor(helperEl);
    var p = String(provider || 'claude').toLowerCase();
    var task = externalUrlReviewIntro(helperEl);
    var compactCaps = p === 'chatgpt' ? [320, 240, 180, 120, 80, 50] : [100, 80, 60, 40];
    var i;
    for (i = 0; i < compactCaps.length; i++) {
      var compact = compactFacilityMaterial(ctx, helperEl, compactCaps[i]);
      var lines = [];
      if (anchor) lines.push(anchor);
      lines.push('');
      lines.push(task);
      if (compact) {
        lines.push('');
        lines.push(compact);
      }
      var body = lines.join('\n').trim();
      if (buildPrefillUrl(p, body)) return body;
    }
    return '';
  }

  /** Short ?q= body for Claude/ChatGPT: anchor + review ask (with visual) + key metrics. */
  function buildExternalUrlPrefill(helperEl, provider) {
    var p = String(provider || 'chatgpt').toLowerCase();
    syncHelperFromUi(helperEl);
    var ctx = readHelperContext(helperEl) || providerContextStub(helperEl);
    var anchor = oneLineFacilityAnchor(helperEl);
    var caps = [480, 380, 280, 200, 140, 90, 55];
    var i;
    for (i = 0; i < caps.length; i++) {
      var compact = compactFacilityMaterial(ctx, helperEl, caps[i]);
      var intro = externalUrlReviewIntro(helperEl, { withVisual: i < 4 });
      var parts = [];
      if (anchor) parts.push(anchor);
      parts.push('');
      parts.push(intro);
      if (compact) {
        parts.push('');
        parts.push(compact);
      }
      var body = parts.join('\n').trim();
      if (buildPrefillUrl(p, body)) return body;
    }
    var abbr = buildAbbreviatedProviderPrefill(helperEl, p);
    if (abbr) return abbr;
    var minimal = [
      anchor || 'PBJ320 nursing home staffing review',
      '',
      externalUrlReviewIntro(helperEl, { withVisual: true }),
    ].join('\n');
    return buildPrefillUrl(p, minimal) ? minimal : minimal.slice(0, 500);
  }

  /**
   * Pick text to place in ?q= — never empty UX: try one-shot, then abbreviated, then minimal stub.
   * @returns {{ text: string, tier: 'full'|'abbr'|'stub' }}
   */
  function pickUrlPrefillTextForProvider(helperEl, provider, primaryBody, opts) {
    opts = opts || {};
    var p = String(provider || 'claude').toLowerCase();
    if (p === 'chatgpt' || p === 'claude') {
      var extBody = buildExternalUrlPrefill(helperEl, p);
      if (primaryBody && buildPrefillUrl(p, primaryBody)) {
        return { text: primaryBody, tier: 'full' };
      }
      if (extBody && buildPrefillUrl(p, extBody)) {
        var hasMetrics =
          extBody.indexOf('Key metrics on page:') >= 0 ||
          extBody.indexOf('--- This facility') >= 0;
        return { text: extBody, tier: hasMetrics ? 'abbr' : 'stub' };
      }
    }
    if (primaryBody && buildPrefillUrl(p, primaryBody)) {
      return { text: primaryBody, tier: 'full' };
    }
    var abbr = buildAbbreviatedProviderPrefill(helperEl, p);
    if (abbr && buildPrefillUrl(p, abbr)) {
      return { text: abbr, tier: 'abbr' };
    }
    var stubAnchor = oneLineFacilityAnchor(helperEl) || 'PBJ320 nursing home staffing review';
    var stub = stubAnchor + '\n\n' + externalUrlReviewIntro(helperEl);
    return { text: stub, tier: 'stub' };
  }

  function refreshPrefillTextarea(helperEl, provider) {
    if (!helperEl) return;
    var pid = helperEl.getAttribute('data-prefill-id');
    if (!pid) return;
    var text = buildProviderOneShotPrefill(helperEl, provider || 'claude');
    var ta = document.getElementById(pid);
    if (ta && text) ta.value = text;
  }

  function providerContextStub(helperEl) {
    if (!helperEl) return '';
    var url = helperEl.getAttribute('data-page-url') || '';
    var name = helperEl.getAttribute('data-facility-name') || '';
    if (!url && !name) return '';
    var lines = ['PBJ320 page context', ''];
    if (name) lines.push('Facility: ' + name);
    if (url) lines.push('PBJ320 URL: ' + url);
    return lines.join('\n');
  }

  function getStoredLens() {
    var lc = lensConfig();
    var key = (lc.storageKeys || {}).lens || 'pbj320_ai_review_lens';
    try {
      var raw = localStorage.getItem(key);
      if (raw) return normalizeLensKey(raw);
    } catch (e) {
      /* ignore */
    }
    return lc.defaultLens || 'ombudsman';
  }

  function getStoredLength() {
    var lc = lensConfig();
    var key = (lc.storageKeys || {}).length || 'pbj320_ai_review_length';
    try {
      var raw = localStorage.getItem(key);
      if (raw) return normalizeLengthKey(raw);
    } catch (e) {
      /* ignore */
    }
    return lc.defaultLength || 'quick';
  }

  function briefStorageKey() {
    var h = frameworkBundle().helper || {};
    return h.briefStorageKey || 'pbj320_ai_brief_mode';
  }

  function isProviderBar(helperEl) {
    return !!(helperEl && helperEl.classList && helperEl.classList.contains('pbj-ai-provider-bar'));
  }

  function getStoredBrief() {
    try {
      return localStorage.getItem(briefStorageKey()) === '1';
    } catch (e) {
      return false;
    }
  }

  function saveBrief(on) {
    try {
      localStorage.setItem(briefStorageKey(), on ? '1' : '0');
    } catch (e) {
      /* ignore */
    }
  }

  function effectiveLength(helperEl) {
    if (isProviderBar(helperEl)) {
      return getStoredBrief() ? 'quick' : 'standard';
    }
    return helperEl.dataset.pbjLength || getStoredLength();
  }

  function appendOutputLengthNote(prompt, helperEl) {
    if (!prompt) return prompt;
    var h = frameworkBundle().helper || {};
    var len = effectiveLength(helperEl);
    var note = len === 'quick' ? h.briefOutputNote : h.standardOutputNote;
    if (!note || prompt.indexOf(note) >= 0) return prompt;
    return prompt + '\n\n' + note;
  }

  function applyBriefUi(helperEl, briefOn) {
    if (!helperEl) return;
    var on = !!briefOn;
    helperEl.dataset.pbjBrief = on ? '1' : '0';
    applyLengthUi(helperEl, on ? 'quick' : 'standard');
    helperEl.querySelectorAll('[data-pbj-brief-toggle]').forEach(function (btn) {
      var isBriefBtn = btn.getAttribute('data-brief-value') === '1';
      btn.classList.toggle('is-active', on === isBriefBtn);
      btn.setAttribute('aria-pressed', on === isBriefBtn ? 'true' : 'false');
    });
  }

  function getProviderBarLens() {
    var lens = normalizeLensKey(getStoredLens());
    var pub = ['ombudsman', 'family', 'journalist'];
    return pub.indexOf(lens) >= 0 ? lens : 'ombudsman';
  }

  function saveLensLength(lens, length) {
    var lc = lensConfig();
    try {
      if ((lc.storageKeys || {}).lens) localStorage.setItem(lc.storageKeys.lens, lens);
      if ((lc.storageKeys || {}).length) localStorage.setItem(lc.storageKeys.length, length);
    } catch (e) {
      /* ignore */
    }
  }

  function applyLensUi(helperEl, lens) {
    if (!helperEl) return;
    var lid = normalizeLensKey(lens);
    helperEl.dataset.pbjLens = lid;
    var sel = helperEl.querySelector('[data-pbj-lens-select]');
    if (sel) sel.value = lid;
  }

  function applyLengthUi(helperEl, length) {
    if (!helperEl) return;
    var len = normalizeLengthKey(length);
    helperEl.dataset.pbjLength = len;
    var sel = helperEl.querySelector('[data-pbj-length-select]');
    if (sel) sel.value = len;
  }

  function syncHelperFromUi(helperEl) {
    if (!helperEl) return;
    var lensSel = helperEl.querySelector('[data-pbj-lens-select]');
    if (lensSel) {
      applyLensUi(helperEl, lensSel.value);
      saveLensLength(lensSel.value, effectiveLength(helperEl));
    }
    if (!helperEl.dataset.pbjLength) {
      applyLengthUi(helperEl, isProviderBar(helperEl) ? effectiveLength(helperEl) : 'quick');
    }
  }

  function appendCsvBlocks(packet, helperEl) {
    if (!helperEl || helperEl.getAttribute('data-csv-enabled') !== '1') return packet;
    var snapId = helperEl.getAttribute('data-snapshot-csv-id');
    var trendId = helperEl.getAttribute('data-trends-csv-id');
    var snap = snapId ? readFromId(snapId) : '';
    var trend = trendId ? readFromId(trendId) : '';
    if (snap) packet += '\n\n--- PBJ320 quarterly CSV (snapshot) ---\n' + snap;
    if (trend) packet += '\n\n--- PBJ320 quarterly CSV (trends) ---\n' + trend;
    return packet;
  }

  function refreshHandoffTextarea(helperEl) {
    if (!helperEl) return;
    var hid = helperEl.getAttribute('data-handoff-id');
    if (!hid) return;
    var existing = readFromId(hid);
    var packet = '';
    try {
      packet = buildAiPacket(helperEl, true);
    } catch (err) {
      console.warn('PBJ320 refreshHandoff', err);
    }
    if (!packet || !packetHasPageContext(packet)) {
      if (existing && packetHasPageContext(existing)) return;
    }
    if (!packet) return;
    var ta = document.getElementById(hid);
    if (ta) ta.value = packet;
  }

  function composeHelperPrompt(lens, length, pageType, helperEl) {
    var fw = global.PBJReviewFramework;
    var lensKey = normalizeLensKey(lens);
    var lengthKey = length || (helperEl && isProviderBar(helperEl) ? 'standard' : 'quick');
    var st = '';
    var sc = '';
    if (helperEl && helperEl.getAttribute) {
      st = helperEl.getAttribute('data-ai-state-label') || '';
      sc = helperEl.getAttribute('data-ai-state-code') || '';
    }
    if (fw && fw.composeDashboardPrompt) {
      var core = frameworkBundle().core || {};
      return appendOutputLengthNote(
        fw.composeDashboardPrompt(
          lensKey,
          lengthKey,
          pageType,
          core.handoffPlaceholder || '',
          st,
          sc
        ),
        helperEl
      );
    }
    var lc = lensConfig();
    var audience = (lc.lensToAudience || {})[lensKey] || 'analyst';
    if (fw && fw.composeReviewPromptForLens && lensKey !== 'general' && lengthKey === 'quick') {
      return appendOutputLengthNote(fw.composeReviewPromptForLens(lensKey, pageType), helperEl);
    }
    if (fw && fw.composeReviewPromptQuick && fw.reviewConfigForPage) {
      var cfg = fw.reviewConfigForPage(pageType, { audience: audience });
      var prompt = fw.composeReviewPromptQuick(cfg);
      if (fw.composeReviewGuardrails) {
        var guardrails = fw.composeReviewGuardrails(pageType);
        if (guardrails && prompt.indexOf(guardrails) < 0) prompt += '\n\n' + guardrails;
      }
      return appendOutputLengthNote(prompt, helperEl);
    }
    var coreFallback = frameworkBundle().core || {};
    return appendOutputLengthNote(
      composeDashboardPrompt(
        lens,
        length,
        pageType,
        coreFallback.handoffPlaceholder || '',
        st,
        sc
      ),
      helperEl
    );
  }

  function buildAiPacket(helperEl, skipHandoffSync, opts) {
    opts = opts || {};
    if (!helperEl) return '';
    syncHelperFromUi(helperEl);
    var lens = helperEl.dataset.pbjLens || getStoredLens();
    var length = effectiveLength(helperEl);
    var pageType = helperEl.getAttribute('data-page-type') || 'facility';
    var ctx = readHelperContext(helperEl);
    if (!ctx) ctx = providerContextStub(helperEl);
    var core = frameworkBundle().core || {};
    var placeholder = core.handoffPlaceholder || '';
    var prompt = composeHelperPrompt(lens, length, pageType, helperEl);
    var packet;
    var ctxBlock = ctx ? '\n\n--- PBJ320 page context ---\n\n' + ctx : '';
    if (length === 'quick') {
      packet = prompt + ctxBlock;
    } else if (placeholder && prompt.indexOf(placeholder) >= 0) {
      packet = prompt.split(placeholder).join(ctx);
    } else {
      packet = prompt + ctxBlock;
    }
    if (helperEl.getAttribute('data-csv-enabled') === '1') {
      var h = frameworkBundle().helper || {};
      if (h.csvAttachmentNote) packet += '\n\n---\n' + h.csvAttachmentNote;
      if (h.csvHandoffNote) packet += '\n' + h.csvHandoffNote;
    }
    if (opts.skipInlineCsv) {
      /* CSV + full .txt download separately; prefill already has facility facts */
    } else {
      packet = appendCsvBlocks(packet, helperEl);
    }
    if (!packet.trim() && ctx) {
      packet = (prompt || 'Review this PBJ320 nursing home staffing page.') + '\n\n' + ctx;
    }
    if (!skipHandoffSync) refreshHandoffTextarea(helperEl);
    return packet;
  }

  function promptOnlyForHelper(helperEl) {
    if (!helperEl) return '';
    syncHelperFromUi(helperEl);
    var lens = helperEl.dataset.pbjLens || getStoredLens();
    var length = effectiveLength(helperEl);
    var pageType = helperEl.getAttribute('data-page-type') || 'facility';
    return composeHelperPrompt(lens, length, pageType, helperEl);
  }

  function openBetaModal(modal) {
    if (!modal) return;
    if (modal._pbjBetaHost && modal.parentNode !== document.body) {
      document.body.appendChild(modal);
    }
    modal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('pbj-ai-beta-modal-open');
    var card = modal.querySelector('.pbj-casemix-modal-card');
    if (card) card.focus();
  }

  function closeBetaModal(modal, markSeen) {
    if (!modal) return;
    modal.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('pbj-ai-beta-modal-open');
    if (modal._pbjBetaHost && modal.parentNode === document.body) {
      modal._pbjBetaHost.appendChild(modal);
    }
    if (markSeen) {
      var h = frameworkBundle().helper || {};
      var key = h.betaModalStorageKey || 'pbj320_ai_beta_modal_seen';
      try {
        localStorage.setItem(key, '1');
      } catch (e) {
        /* ignore */
      }
    }
  }

  function initBetaModals() {
    document.querySelectorAll('.pbj-ai-beta-modal').forEach(function (modal) {
      if (modal.dataset.pbjBetaModalBound) return;
      modal.dataset.pbjBetaModalBound = '1';
      var host = modal.closest('.pbj-ai-beta-modal-host');
      if (host) modal._pbjBetaHost = host;
      var closeBtn = modal.querySelector('.pbj-casemix-modal-close');
      var gotIt = modal.querySelector('[data-pbj-ai-beta-close]');
      function close(markSeen) {
        closeBetaModal(modal, markSeen);
      }
      if (closeBtn) closeBtn.addEventListener('click', function () { close(true); });
      if (gotIt) gotIt.addEventListener('click', function () { close(true); });
      modal.addEventListener('click', function (e) {
        if (e.target === modal) close(true);
      });
    });
  }

  function initPageHelpers() {
    if (!global.__PBJ_REVIEW_FRAMEWORK__ && !global.PBJReviewFramework) return;
    var lens = getStoredLens();
    var length = getStoredLength();
    var brief = getStoredBrief();
    document.querySelectorAll('.pbj-ai-page-helper').forEach(function (helperEl) {
      if (helperEl.classList.contains('pbj-ai-provider-bar')) {
        lens = getProviderBarLens();
        applyBriefUi(helperEl, brief);
        length = effectiveLength(helperEl);
      } else {
        applyLengthUi(helperEl, length);
      }
      applyLensUi(helperEl, lens);
      helperEl.querySelectorAll('[data-pbj-brief-toggle]').forEach(function (briefBtn) {
        if (briefBtn.dataset.pbjBriefBound) return;
        briefBtn.dataset.pbjBriefBound = '1';
        briefBtn.addEventListener('click', function () {
          var next = briefBtn.getAttribute('data-brief-value') === '1';
          applyBriefUi(helperEl, next);
          saveBrief(next);
          refreshHandoffTextarea(helperEl);
          refreshPrefillTextarea(helperEl, 'claude');
          refreshPrefillTextarea(helperEl, 'chatgpt');
        });
      });
      var lenSel = helperEl.querySelector('[data-pbj-length-select]');
      if (lenSel && !lenSel.dataset.pbjLengthBound) {
        lenSel.dataset.pbjLengthBound = '1';
        lenSel.addEventListener('change', function () {
          var len = lenSel.value;
          applyLengthUi(helperEl, len);
          saveLensLength(helperEl.dataset.pbjLens || getStoredLens(), len);
        });
      }
      var lensSel = helperEl.querySelector('[data-pbj-lens-select]');
      if (lensSel && !lensSel.dataset.pbjLensBound) {
        lensSel.dataset.pbjLensBound = '1';
        lensSel.addEventListener('change', function () {
          var lid = lensSel.value;
          applyLensUi(helperEl, lid);
          saveLensLength(lid, helperEl.dataset.pbjLength || getStoredLength());
          refreshHandoffTextarea(helperEl);
          refreshPrefillTextarea(helperEl, 'claude');
        });
      }
      refreshHandoffTextarea(helperEl);
      refreshPrefillTextarea(helperEl, 'claude');
    });
    initBetaModals();
  }

  function mapSourceToPageMeta(sourceId) {
    var map = {
      facility: { pageType: 'facility', pageKind: '' },
      state: { pageType: 'state', pageKind: '' },
      screenshot: { pageType: 'facility', pageKind: 'screenshot' },
      csv: { pageType: 'facility', pageKind: 'csv export' },
      premium: { pageType: 'facility', pageKind: 'premium dashboard' },
    };
    return map[sourceId] || map.facility;
  }

  function sourceLevelLine(pageType, pageKind) {
    var levels = frameworkBundle().sourceLevels || {};
    var kind = String(pageKind || '').toLowerCase();
    var ptype = String(pageType || '').toLowerCase();
    var key = 'free';
    if (kind.indexOf('premium') >= 0) key = 'premium';
    else if (ptype === 'state') key = 'free_state';
    else if (ptype === 'facility' || ptype === 'provider') key = 'free_facility';
    return levels[key] ? 'Source level: ' + levels[key] : '';
  }

  function buildSupportPagePrompt() {
    var fw = global.PBJReviewFramework;
    var roleEl = document.getElementById('ai-prompt-role');
    var sourceEl = document.getElementById('ai-prompt-source');
    var lens = 'general';
    var meta = mapSourceToPageMeta('facility');
    if (fw) {
      lens = roleEl ? fw.normalizeLens(roleEl.value) : 'ombudsman';
      meta = mapSourceToPageMeta(sourceEl ? sourceEl.value : 'facility');
    }
    var prompt = '';
    if (fw && fw.composeDashboardPrompt) {
      prompt = fw.composeDashboardPrompt(lens, 'quick', meta.pageType, '', '', '');
      var lc = frameworkBundle().lensConfig || {};
      var audience = (lc.lensToAudience || {})[lens] || 'analyst';
      if (fw.reviewConfigForPage && fw.setActiveConfig) {
        fw.setActiveConfig(fw.reviewConfigForPage(meta.pageType, { audience: audience }));
      }
    } else if (typeof window.__PBJ_AI_PROMPT_QUICK__ === 'string') {
      prompt = window.__PBJ_AI_PROMPT_QUICK__;
    }
    var sl = sourceLevelLine(meta.pageType, meta.pageKind);
    if (sl && prompt.indexOf('Source level:') < 0) prompt += '\n\n' + sl;
    return prompt;
  }

  function refreshPromptPreview() {
    var text = buildSupportPagePrompt();
    var ta = document.getElementById('pbj-ai-prompt-quick');
    var pre = document.getElementById('pbj-ai-prompt-quick-display');
    if (ta) ta.value = text;
    if (pre) pre.textContent = text;
    window.__PBJ_AI_PROMPT_QUICK_DYNAMIC__ = text;
    return text;
  }

  function initPromptBuilder() {
    var roleEl = document.getElementById('ai-prompt-role');
    if (!roleEl) return;
    var sourceEl = document.getElementById('ai-prompt-source');
    try {
      var stored = localStorage.getItem('pbj320_ai_review_lens');
      if (stored) roleEl.value = normalizeLensKey(stored);
    } catch (e) {
      /* ignore */
    }
    function onChange() {
      saveLensLength(roleEl.value, 'quick');
      refreshPromptPreview();
    }
    roleEl.addEventListener('change', onChange);
    if (sourceEl) sourceEl.addEventListener('change', onChange);
    refreshPromptPreview();
  }

  function promptForButton(btn) {
    var pid = (btn && btn.getAttribute('data-prompt-id')) || '';
    var useAdvanced = pid.indexOf('advanced') >= 0;
    if (!useAdvanced && document.getElementById('ai-prompt-role')) {
      var dynamic = window.__PBJ_AI_PROMPT_QUICK_DYNAMIC__;
      if (dynamic) return dynamic;
      return refreshPromptPreview();
    }
    var fw = global.PBJReviewFramework;
    var cfg = fw && fw.getActiveConfig ? fw.getActiveConfig() : null;
    if (fw && cfg) {
      if (useAdvanced) return fw.composeReviewPromptAdvanced(cfg);
      return fw.composeReviewPromptQuick(cfg);
    }
    if (useAdvanced) {
      if (typeof window.__PBJ_AI_PROMPT_ADVANCED__ === 'string') return window.__PBJ_AI_PROMPT_ADVANCED__;
      return readFromId('pbj-ai-prompt-advanced');
    }
    if (typeof window.__PBJ_AI_PROMPT_QUICK__ === 'string') return window.__PBJ_AI_PROMPT_QUICK__;
    return readFromId(pid) || readFromId('pbj-ai-prompt-quick');
  }

  function closeAllPopovers(except) {
    document.querySelectorAll('.pbj-ai-popover').forEach(function (menu) {
      if (except && menu === except) return;
      menu.setAttribute('hidden', '');
      var chip = menu.closest('.pbj-ai-chip');
      var toggle = chip && chip.querySelector('.pbj-ai-chip__menu');
      if (toggle) toggle.setAttribute('aria-expanded', 'false');
    });
    document.querySelectorAll('.pbj-ai-lens-more-wrap .pbj-ai-lens-chip[data-lens="more"]').forEach(function (btn) {
      if (except && btn.nextElementSibling === except) return;
      btn.setAttribute('aria-expanded', 'false');
    });
  }

  function togglePopover(menuBtn) {
    var chip = menuBtn.closest('.pbj-ai-chip');
    if (!chip) return;
    var menu = chip.querySelector('.pbj-ai-popover');
    if (!menu) return;
    var open = menu.hasAttribute('hidden');
    closeAllPopovers();
    if (open) {
      menu.removeAttribute('hidden');
      menuBtn.setAttribute('aria-expanded', 'true');
    } else {
      menu.setAttribute('hidden', '');
      menuBtn.setAttribute('aria-expanded', 'false');
    }
  }

  function copyThen(fn) {
    return function (text) {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        return navigator.clipboard.writeText(text).then(fn).catch(function () {
          if (syncCopy(text)) return fn();
          showToast('Copy failed — use ⋯ menu to copy manually.');
        });
      }
      if (syncCopy(text)) return fn();
      showToast('Copy failed — use ⋯ menu to copy manually.');
    };
  }

  function resolveFullPacket(btn) {
    var packetHelper = btn.closest('.pbj-ai-page-helper');
    var handoffId =
      btn.getAttribute('data-handoff-id') ||
      (packetHelper && packetHelper.getAttribute('data-handoff-id'));
    var handoff = readFromId(handoffId);

    if (handoffId && handoffId.indexOf('prompt') >= 0) {
      return promptForButton({ getAttribute: function () { return handoffId; } });
    }

    if (packetHelper) {
      try {
        var built = buildAiPacket(packetHelper, true);
        if (built && packetHasPageContext(built)) return built;
      } catch (err) {
        console.warn('PBJ320 buildAiPacket', err);
      }
      if (handoff && packetHasPageContext(handoff)) return handoff;
      var ctxOnly = readHelperContext(packetHelper) || providerContextStub(packetHelper);
      if (ctxOnly) {
        var lens = packetHelper.dataset.pbjLens || getStoredLens();
        var pageType = packetHelper.getAttribute('data-page-type') || 'facility';
        var prompt = composeHelperPrompt(lens, effectiveLength(packetHelper), pageType, packetHelper);
        return prompt + '\n\n--- PBJ320 page context ---\n\n' + ctxOnly;
      }
    }

    return handoff;
  }

  /** Review prompt only — Claude may use ?q= prefill when short enough; ChatGPT uses clipboard + new tab. */
  function buildProviderPrefillPromptOnly(helperEl) {
    syncHelperFromUi(helperEl);
    var lens = helperEl.dataset.pbjLens || getStoredLens();
    var length = effectiveLength(helperEl);
    var pageType = helperEl.getAttribute('data-page-type') || 'facility';
    return composeHelperPrompt(lens, length, pageType, helperEl);
  }

  function launchProviderQuick(btn, packetHelper, provider) {
    var providerNorm = String(provider || 'claude').toLowerCase();
    var isProvBar =
      packetHelper &&
      packetHelper.classList &&
      packetHelper.classList.contains('pbj-ai-provider-bar');
    var prefillText =
      providerNorm === 'chatgpt' && packetHelper
        ? buildProviderOneShotPrefill(packetHelper, 'chatgpt')
        : buildProviderPrefillPromptOnly(packetHelper);
    var ctx = readHelperContext(packetHelper);
    if (!prefillText && !ctx) {
      showToast('Nothing to copy — refresh and try again.');
      return;
    }
    closeAllPopovers();

    var snap = readExtendedContext(packetHelper);
    var mobileHandoff = isMobileHandoff();
    var snapDownloaded = false;
    if (snap && snap.trim()) {
      snapDownloaded = downloadFacilitySnapshotFile(packetHelper, snap).ok;
    }

    var fullClip = '';
    if (packetHelper) {
      try {
        fullClip = buildAiPacket(packetHelper, true, { skipInlineCsv: true });
      } catch (eQuick) {
        fullClip = '';
      }
    }
    if (!fullClip) {
      fullClip = prefillText || ctx || '';
    }

    var primaryForUrl = null;
    if (isProvBar && packetHelper) {
      primaryForUrl =
        providerNorm === 'chatgpt' || providerNorm === 'claude'
          ? null
          : buildProviderOneShotPrefill(packetHelper, providerNorm) || prefillText;
    } else {
      primaryForUrl = prefillText;
    }
    var urlPick = { text: primaryForUrl || 'Review this PBJ320 nursing home staffing page.', tier: 'full' };
    if (isProvBar && packetHelper) {
      urlPick = pickUrlPrefillTextForProvider(packetHelper, providerNorm, primaryForUrl, {
        mobile: mobileHandoff,
        hasSnapshot: snapDownloaded,
      });
    }

    var gptCopied = false;
    if (providerNorm === 'chatgpt' && fullClip) {
      gptCopied = syncCopy(fullClip);
    }
    if (providerNorm === 'claude' && fullClip) {
      syncCopy(fullClip);
    }

    var prefillUrl = buildPrefillUrl(
      providerNorm,
      urlPick.text || 'Review this PBJ320 nursing home staffing page.'
    );
    if (providerNorm === 'chatgpt' && !prefillUrl && fullClip) {
      syncCopy(fullClip);
      gptCopied = true;
    }
    var url = prefillUrl || AI_URLS[providerNorm] || AI_URLS.claude;
    var opened = window.open(url, '_blank', 'noopener,noreferrer');
    if (!opened) {
      showToast('Popup blocked — allow popups for this site, then try again.');
      return;
    }

    var msg;
    if (providerNorm === 'chatgpt') {
      msg = launchToastForChatgpt({
        mobile: mobileHandoff,
        tier: urlPick.tier,
        snapshot: snapDownloaded,
        clipboard: gptCopied,
      });
    } else if (!prefillUrl) {
      msg = LAUNCH_MSG_CLIPBOARD.claude;
    } else if (isProvBar && urlPick.tier !== 'full') {
      msg =
        'Opened Claude — short prompt prefilled from the link. Full review packet is on the clipboard (Ctrl+V / Cmd+V).';
    } else {
      msg = 'Claude opened — prompt via link; clipboard also has the same text (Ctrl+V if the box is empty).';
    }
    if (providerNorm === 'claude' && snapDownloaded) {
      msg += ' Facility snapshot (.txt) downloaded for upload.';
    }

    if (providerNorm === 'chatgpt' && !gptCopied && fullClip) {
      copyForLaunch(fullClip).then(function () {
        showToast(msg);
      });
    } else {
      showToast(msg);
    }
  }

  function launchProvider(btn) {
    var provider = btn.getAttribute('data-ai') || 'claude';
    var providerNorm = String(provider).toLowerCase();
    var packetHelper = btn.closest('.pbj-ai-page-helper');
    var handoffId =
      btn.getAttribute('data-handoff-id') ||
      (packetHelper && packetHelper.getAttribute('data-handoff-id'));
    var isProviderLaunch =
      packetHelper &&
      packetHelper.classList.contains('pbj-ai-provider-bar') &&
      !(handoffId && handoffId.indexOf('prompt') >= 0);

    var clipboardText = resolveFullPacket(btn);
    if (!clipboardText) {
      showToast('Nothing to copy — refresh and try again.');
      return;
    }
    closeAllPopovers();

    var mobileHandoff = isMobileHandoff();
    var snapDownloaded = false;
    var prefillText = clipboardText;
    if (isProviderLaunch && packetHelper) {
      prefillText = buildProviderOneShotPrefill(packetHelper, providerNorm) || clipboardText;
      var contextFileText = readExtendedContext(packetHelper) || clipboardText;
      snapDownloaded = downloadFacilitySnapshotFile(packetHelper, contextFileText).ok;
    }

    var urlPrimary =
      isProviderLaunch && (providerNorm === 'chatgpt' || providerNorm === 'claude') ? null : prefillText;
    var urlPick =
      isProviderLaunch && packetHelper
        ? pickUrlPrefillTextForProvider(packetHelper, providerNorm, urlPrimary, {
            mobile: mobileHandoff,
            hasSnapshot: snapDownloaded,
          })
        : { text: prefillText, tier: 'full' };
    var urlBody = urlPick.text || 'Review this PBJ320 nursing home staffing page.';
    var prefillUrl = buildPrefillUrl(providerNorm, urlBody);

    var gptCopied = false;
    if (providerNorm === 'chatgpt' && clipboardText) {
      gptCopied = syncCopy(clipboardText);
      if (!prefillUrl && clipboardText) {
        syncCopy(clipboardText);
        gptCopied = true;
      }
    }

    if (providerNorm === 'claude' && clipboardText) {
      syncCopy(clipboardText);
    }

    var url = prefillUrl || AI_URLS[providerNorm] || AI_URLS.claude;
    var msg;
    if (providerNorm === 'chatgpt') {
      msg = launchToastForChatgpt({
        mobile: mobileHandoff,
        tier: urlPick.tier,
        snapshot: snapDownloaded,
        clipboard: gptCopied,
      });
    } else if (!prefillUrl) {
      msg = LAUNCH_MSG_CLIPBOARD[providerNorm] || LAUNCH_MSG_CLIPBOARD.claude;
    } else if (isProviderLaunch && urlPick.tier !== 'full') {
      msg =
        'Opened Claude — compose box has a short prefill from the link. Full review packet is on the clipboard (Ctrl+V / Cmd+V).';
    } else if (isProviderLaunch) {
      msg = LAUNCH_MSG_FULL[providerNorm] || LAUNCH_MSG_FULL.claude;
    } else {
      msg = LAUNCH_MSG[providerNorm] || LAUNCH_MSG.claude;
    }
    if (providerNorm === 'claude' && prefillUrl && urlPick.tier === 'full' && isProviderLaunch) {
      msg += ' Clipboard has the same prompt if the link box is empty.';
    }
    if (providerNorm === 'claude' && snapDownloaded) {
      msg += ' Facility snapshot (.txt) downloaded for upload.';
    }

    var opened = window.open(url, '_blank', 'noopener,noreferrer');
    if (!opened) {
      showToast('Popup blocked — allow popups for this site, then try again.');
      return;
    }

    if (providerNorm === 'chatgpt') {
      if (!gptCopied && clipboardText) {
        copyForLaunch(clipboardText).then(function () {
          showToast(msg);
        });
      } else {
        showToast(msg);
      }
      return;
    }

    showToast(msg);
  }

  function bindHandlers() {
    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape') return;
      document.querySelectorAll('.pbj-ai-beta-modal[aria-hidden="false"]').forEach(function (modal) {
        closeBetaModal(modal, false);
      });
    });

    document.addEventListener('click', function (e) {
      var betaOpen = e.target && e.target.closest ? e.target.closest('[data-pbj-ai-beta-open]') : null;
      if (betaOpen) {
        e.preventDefault();
        var bar = betaOpen.closest('.pbj-ai-provider-bar') || betaOpen.closest('.pbj-ai-page-helper');
        var modal = bar
          ? bar.querySelector('.pbj-ai-beta-modal')
          : document.querySelector('.pbj-ai-beta-modal');
        openBetaModal(modal);
        return;
      }

      var betaClose = e.target && e.target.closest ? e.target.closest('[data-pbj-ai-beta-close]') : null;
      if (betaClose) {
        e.preventDefault();
        var modalClose = betaClose.closest('.pbj-ai-beta-modal');
        closeBetaModal(modalClose, true);
        return;
      }

      var launchBtn = e.target && e.target.closest ? e.target.closest('.pbj-ai-launch') : null;
      if (launchBtn && !launchBtn.classList.contains('pbj-ai-chip__menu')) {
        e.preventDefault();
        launchProvider(launchBtn);
        return;
      }

      var menuBtn = e.target && e.target.closest ? e.target.closest('.pbj-ai-chip__menu') : null;
      if (menuBtn) {
        e.preventDefault();
        e.stopPropagation();
        togglePopover(menuBtn);
        return;
      }

      var ctxBtn = e.target && e.target.closest ? e.target.closest('.pbj-ai-copy-context') : null;
      if (ctxBtn) {
        e.preventDefault();
        var ctxId = ctxBtn.getAttribute('data-context-id');
        var ctxHelper = ctxBtn.closest('.pbj-ai-page-helper');
        if (!ctxId && ctxHelper) ctxId = ctxHelper.getAttribute('data-context-id');
        copyText(readFromId(ctxId), MSG_CONTEXT, ctxBtn);
        closeAllPopovers();
        return;
      }

      var bundleBtn = e.target && e.target.closest ? e.target.closest('.pbj-footer-csv-bundle') : null;
      if (bundleBtn) {
        e.preventDefault();
        var uid = bundleBtn.getAttribute('data-csv-bundle-for') || '';
        var helper = uid
          ? document.querySelector('.pbj-ai-page-helper[data-helper-uid="' + uid.replace(/"/g, '') + '"]')
          : null;
        var n = downloadProviderCsvs(helper);
        showToast(
          n > 0
            ? 'Downloaded ' + n + ' CSV file' + (n > 1 ? 's' : '') + ' for upload.'
            : 'No CSV data on this page.'
        );
        return;
      }

      var csvsBtn = e.target && e.target.closest ? e.target.closest('.pbj-ai-provider-csvs') : null;
      if (csvsBtn) {
        e.preventDefault();
        var csvHelper = csvsBtn.closest('.pbj-ai-page-helper');
        var n = downloadProviderCsvs(csvHelper);
        showToast(
          n > 0
            ? 'Downloaded ' + n + ' CSV file' + (n > 1 ? 's' : '') + ' for upload.'
            : 'No CSV data on this page.'
        );
        return;
      }

      var packetBtn = e.target && e.target.closest ? e.target.closest('.pbj-ai-copy-packet') : null;
      if (packetBtn) {
        e.preventDefault();
        var helperPkt = packetBtn.closest('.pbj-ai-page-helper');
        copyText(buildAiPacket(helperPkt), MSG_PACKET, packetBtn);
        closeAllPopovers();
        return;
      }

      var handoffBtn = e.target && e.target.closest ? e.target.closest('.pbj-ai-copy-handoff') : null;
      if (handoffBtn) {
        e.preventDefault();
        copyText(readFromId(handoffBtn.getAttribute('data-handoff-id')), MSG_PACKET, handoffBtn);
        closeAllPopovers();
        return;
      }

      var promptOnlyBtn = e.target && e.target.closest ? e.target.closest('.pbj-ai-copy-prompt-only') : null;
      if (promptOnlyBtn) {
        e.preventDefault();
        var helperPrompt = promptOnlyBtn.closest('.pbj-ai-page-helper');
        copyText(promptOnlyForHelper(helperPrompt), MSG_PROMPT, promptOnlyBtn);
        closeAllPopovers();
        return;
      }

      var csvBtn = e.target && e.target.closest ? e.target.closest('.pbj-ai-download-csv') : null;
      if (csvBtn) {
        e.preventDefault();
        downloadCsv(
          readFromId(csvBtn.getAttribute('data-csv-id')),
          csvBtn.getAttribute('data-csv-filename') || 'pbj320_export.csv'
        );
        closeAllPopovers();
        return;
      }

      var promptBtn = e.target && e.target.closest ? e.target.closest('.pbj-ai-copy-prompt') : null;
      if (promptBtn) {
        e.preventDefault();
        copyText(promptForButton(promptBtn), MSG_PROMPT, promptBtn);
        closeAllPopovers();
        return;
      }

      var installBtn = e.target && e.target.closest ? e.target.closest('.pbj-ai-copy-install') : null;
      if (installBtn) {
        e.preventDefault();
        var iid = installBtn.getAttribute('data-install-id');
        copyText(readFromId(iid) || installBtn.getAttribute('data-install-text') || '', MSG_INSTALL, installBtn);
        return;
      }

      if (!e.target.closest('.pbj-ai-chip')) {
        closeAllPopovers();
      }
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeAllPopovers();
    });
  }

  function escapeHtml(s) {
    var d = document.createElement('div');
    d.textContent = s || '';
    return d.innerHTML;
  }

  function titleCaseFacility(str) {
    if (!str) return '';
    return String(str)
      .toLowerCase()
      .replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }

  function initFacilitySearch() {
    var input = document.getElementById('ai-facility-search');
    var resultsEl = document.getElementById('ai-facility-results');
    if (!input || !resultsEl) return;

    var facilities = [];
    var indexReady = false;
    var debounceTimer;

    function closeResults() {
      resultsEl.hidden = true;
      resultsEl.innerHTML = '';
      input.setAttribute('aria-expanded', 'false');
    }

    function openResults() {
      resultsEl.hidden = false;
      input.setAttribute('aria-expanded', 'true');
    }

    function showFacilityNextStep(row) {
      if (!row || !row.c) return;
      var label = titleCaseFacility(row.n || 'Facility');
      input.value = label;
      closeResults();
      var hint = document.getElementById('ai-facility-next-step');
      var link = document.getElementById('ai-facility-open-link');
      if (hint) hint.hidden = false;
      if (link) link.href = '/provider/' + encodeURIComponent(String(row.c));
    }

    function renderFacilityResults(query) {
      var q = (query || '').trim();
      if (q.length < 2) {
        closeResults();
        return;
      }
      if (!indexReady) {
        resultsEl.innerHTML = '<div class="ai-facility-results__loading">Loading facilities…</div>';
        openResults();
        return;
      }
      var ql = q.toLowerCase();
      var matches = [];
      for (var i = 0; i < facilities.length && matches.length < 8; i++) {
        var row = facilities[i];
        if (!row || !row.c) continue;
        var name = (row.n || '').toLowerCase();
        var ccn = String(row.c).toLowerCase();
        var city = (row.y || '').toLowerCase();
        if (name.indexOf(ql) === -1 && ccn.indexOf(ql) === -1 && city.indexOf(ql) === -1) continue;
        matches.push(row);
      }
      if (!matches.length) {
        resultsEl.innerHTML = '<div class="ai-facility-results__empty">No facilities match. Try a different name or ID.</div>';
        openResults();
        return;
      }
      resultsEl.innerHTML = matches.map(function (row) {
        var label = titleCaseFacility(row.n || 'Facility');
        var meta = (row.y ? titleCaseFacility(row.y) + ', ' : '') + (row.s || '') + ' · CCN ' + row.c;
        return (
          '<button type="button" class="ai-facility-result" role="option" data-ccn="' +
          escapeHtml(String(row.c)) +
          '"><span class="ai-facility-result__name">' +
          escapeHtml(label) +
          '</span><span class="ai-facility-result__meta">' +
          escapeHtml(meta) +
          '</span></button>'
        );
      }).join('');
      openResults();
    }

    resultsEl.addEventListener('click', function (e) {
      var btn = e.target && e.target.closest ? e.target.closest('.ai-facility-result') : null;
      if (!btn) return;
      var ccn = btn.getAttribute('data-ccn');
      for (var j = 0; j < facilities.length; j++) {
        if (String(facilities[j].c) === String(ccn)) {
          showFacilityNextStep(facilities[j]);
          return;
        }
      }
      var nameEl = btn.querySelector('.ai-facility-result__name');
      showFacilityNextStep({ c: ccn, n: nameEl ? nameEl.textContent : '' });
    });

    input.addEventListener('input', function () {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(function () {
        renderFacilityResults(input.value);
      }, 180);
    });

    input.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        closeResults();
        return;
      }
      if (e.key === 'Enter') {
        var first = resultsEl.querySelector('.ai-facility-result');
        if (first) {
          e.preventDefault();
          first.click();
        }
      }
    });

    document.addEventListener('click', function (e) {
      if (!e.target.closest('.ai-facility-search-wrap')) closeResults();
    });

    fetch('/search_index.json')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        facilities = data.f || [];
        indexReady = true;
        if ((input.value || '').trim().length >= 2) renderFacilityResults(input.value);
      })
      .catch(function () {
        indexReady = true;
      });

    global.__pbjFocusFacilitySearch = function () {
      var block = document.getElementById('ai-facility-finder');
      if (block) block.scrollIntoView({ behavior: 'smooth', block: 'start' });
      setTimeout(function () { input.focus(); }, 280);
    };
  }

  function initMobileBar() {
    function focusFacilitySearch() {
      if (global.__pbjFocusFacilitySearch) global.__pbjFocusFacilitySearch();
    }
    var focusBtn = document.getElementById('ai-mobile-focus-search');
    var focusBtnDesktop = document.getElementById('ai-focus-facility');
    var heroFind = document.getElementById('ai-hero-find-facility');
    if (focusBtn) focusBtn.addEventListener('click', focusFacilitySearch);
    if (focusBtnDesktop) focusBtnDesktop.addEventListener('click', focusFacilitySearch);
    if (heroFind) heroFind.addEventListener('click', focusFacilitySearch);
    if (window.location.hash === '#ai-facility-finder' && global.__pbjFocusFacilitySearch) {
      setTimeout(global.__pbjFocusFacilitySearch, 400);
    }
  }

  function initChecksTabs() {
    var root = document.querySelector('[data-ai-checks-tabs]');
    if (!root) return;
    var tabs = root.querySelectorAll('.ai-check-tab');
    var panels = root.querySelectorAll('.ai-check-panel');
    if (!tabs.length || !panels.length) return;

    function activate(index) {
      tabs.forEach(function (tab, i) {
        var on = i === index;
        tab.classList.toggle('is-active', on);
        tab.setAttribute('aria-selected', on ? 'true' : 'false');
      });
      panels.forEach(function (panel, i) {
        panel.classList.toggle('is-active', i === index);
        if (i === index) panel.removeAttribute('hidden');
        else panel.setAttribute('hidden', '');
      });
    }

    tabs.forEach(function (tab, i) {
      tab.addEventListener('click', function () {
        activate(i);
      });
    });
  }

  function initScrollReveal() {
    var els = document.querySelectorAll('.ai-reveal:not(.ai-reveal--hero)');
    if (!els.length) return;
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      els.forEach(function (el) { el.classList.add('is-visible'); });
      return;
    }
    if (!('IntersectionObserver' in window)) {
      els.forEach(function (el) { el.classList.add('is-visible'); });
      return;
    }
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (!entry.isIntersecting) return;
          entry.target.classList.add('is-visible');
          io.unobserve(entry.target);
        });
      },
      { rootMargin: '0px 0px -6% 0px', threshold: 0.06 }
    );
    els.forEach(function (el, i) {
      el.style.transitionDelay = (i % 5) * 0.05 + 's';
      io.observe(el);
    });
  }

  function init() {
    bindHandlers();
    initPageHelpers();
    initPromptBuilder();
    initFacilitySearch();
    initMobileBar();
    initChecksTabs();
    initScrollReveal();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(typeof window !== 'undefined' ? window : this);
