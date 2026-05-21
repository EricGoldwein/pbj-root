/**
 * PBJ320 Staffing Review Framework — client-side config + prompt compose.
 * Reads window.__PBJ_REVIEW_FRAMEWORK__ (injected by Flask on /pbj-ai-support).
 * Default: analyst mode; geography inferred when not set.
 */
(function (global) {
  'use strict';

  var DEFAULT_AUDIENCE = 'ombudsman';
  var AUDIENCE_ALIASES = {
    family: 'family_resident',
    resident: 'family_resident',
    ombuds: 'ombudsman',
    lawyer: 'attorney',
    legal: 'attorney',
    legislative: 'legislator',
    policy: 'legislator',
    admin: 'operator',
    facility_operator: 'operator',
  };
  var GEO_ALIASES = {
    ownership: 'ownership_group',
    chain: 'ownership_group',
    entity: 'ownership_group',
  };

  function bundle() {
    return global.__PBJ_REVIEW_FRAMEWORK__ || {};
  }

  function normalizeAudience(audience) {
    var key = String(audience || '')
      .trim()
      .toLowerCase()
      .replace(/\s+/g, '_')
      .replace(/-/g, '_');
    key = AUDIENCE_ALIASES[key] || key;
    var audiences = bundle().audiences || [];
    return audiences.indexOf(key) >= 0 ? key : DEFAULT_AUDIENCE;
  }

  function normalizeGeographyLevel(level) {
    if (!level) return null;
    var key = String(level)
      .trim()
      .toLowerCase()
      .replace(/\s+/g, '_')
      .replace(/-/g, '_');
    key = GEO_ALIASES[key] || key;
    var levels = bundle().contextLevels || {};
    return Object.prototype.hasOwnProperty.call(levels, key) ? key : null;
  }

  function normalizeConfig(config) {
    var src = config || global.__PBJ_REVIEW_DEFAULT_CONFIG__ || {};
    return {
      audience: normalizeAudience(src.audience),
      geography_level: normalizeGeographyLevel(src.geography_level || src.geography),
      context_note: String(src.context_note || src.context || '').trim(),
      infer_geography_from_material: src.infer_geography_from_material !== false,
    };
  }

  function getMode(audience) {
    var modes = bundle().modes || {};
    return modes[normalizeAudience(audience)] || modes[DEFAULT_AUDIENCE] || {};
  }

  function formatContextBlock(config) {
    var cfg = normalizeConfig(config);
    var mode = getMode(cfg.audience);
    var lines = [
      'Review mode: ' + (mode.label || cfg.audience) + ' (audience: ' + cfg.audience + ').',
    ];
    if (mode.emphasis && mode.emphasis.length) {
      lines.push('Output emphasis: ' + mode.emphasis.join(', ') + '.');
    }
    var levels = bundle().contextLevels || {};
    if (cfg.geography_level && levels[cfg.geography_level]) {
      lines.push('Geographic / jurisdiction scope: ' + levels[cfg.geography_level] + '.');
    } else if (cfg.infer_geography_from_material) {
      lines.push(
        'Geographic scope: not specified — infer state, region, facility, or national scope from the material when possible.'
      );
    }
    if (cfg.context_note) {
      lines.push('Additional context from user: ' + cfg.context_note);
    }
    return lines.join('\n');
  }

  function formatTierSections(tierKey, mode, audience) {
    var aud = audience || DEFAULT_AUDIENCE;
    var legacy = (mode && mode.sections) || [];
    if (legacy.length > 0) {
      return formatAdvancedSections(mode, aud);
    }
    var tiers = bundle().outputTierSections || {};
    var sectionList = (tiers[tierKey] || []).slice();
    var extra = (mode && mode.extraSections) || [];
    if (mode && mode.prependExtraSections) {
      sectionList = extra.concat(sectionList);
    } else {
      extra.forEach(function (pair) {
        sectionList.push(pair);
      });
    }
    var parts = ['Format your response using the ' + tierKey + ' output tier:', ''];
    var instructions = (mode && mode.sectionInstructions) || {};
    sectionList.forEach(function (pair) {
      var title = pair[0];
      var instruction = pair[1];
      parts.push('## ' + title);
      if (instructions[title]) parts.push(instructions[title]);
      else if (instruction) parts.push(instruction);
      parts.push('');
    });
    parts.push(
      'For "What the data cannot prove," list only limits relevant to this query — no boilerplate.'
    );
    return parts.join('\n').replace(/\n+$/, '');
  }

  function formatAdvancedSections(mode, audience) {
    var tier =
      (mode && mode.outputTier) ||
      (bundle().outputTierByAudience || {})[normalizeAudience(audience)] ||
      'detailed';
    if ((mode.sections || []).length) {
      var parts = ['Format your response with these sections:', ''];
      var instructions = mode.sectionInstructions || {};
      mode.sections.forEach(function (title) {
        parts.push('## ' + title);
        if (instructions[title]) parts.push(instructions[title]);
        parts.push('');
      });
      return parts.join('\n').replace(/\n+$/, '');
    }
    return formatTierSections(tier, mode, audience);
  }

  function layeredBundle() {
    return bundle().layered || {};
  }

  function sourceLevelKey(pageType, pageKind) {
    var ptype = String(pageType || 'facility').toLowerCase();
    var kind = String(pageKind || 'free').toLowerCase();
    if (kind.indexOf('premium') >= 0) return 'premium';
    if (ptype === 'state') return 'free_state';
    if (ptype === 'facility' || ptype === 'provider') return 'free_facility';
    return 'free';
  }

  function sourceTypeLabel(pageType, pageKind) {
    var labels = layeredBundle().sourceTypeLabels || {};
    var key = sourceLevelKey(pageType, pageKind);
    return labels[key] || labels.free || 'PBJ320 PAGE (quarterly context)';
  }

  function audienceModeDisplay(lens, audience) {
    var display = layeredBundle().audienceModeDisplay || {};
    var lensKey = lens != null ? normalizeLens(lens) : null;
    if (lensKey && display[lensKey]) return display[lensKey];
    var aud = normalizeAudience(audience || DEFAULT_AUDIENCE);
    var lc = bundle().lensConfig || {};
    var map = lc.lensToAudience || {};
    var lid;
    for (lid in map) {
      if (map[lid] === aud && display[lid]) return display[lid];
    }
    return display.general || 'GENERAL ANALYST';
  }

  function composeSourceLimitsBlock(pageType) {
    var lc = bundle().lensConfig || {};
    var shared = lc.guardrailsShared || [];
    var ptype = String(pageType || 'facility').toLowerCase();
    var lines = [];
    if (ptype === 'facility' || ptype === 'provider') {
      lines.push(
        '- Free provider pages are **quarterly** summaries from CMS PBJ — not the full daily PBJ file.'
      );
      lines.push(
        '- CMS collects daily facility-day PBJ; PBJ320 Premium can show daily detail. Do **not** say CMS ' +
          'lacks daily data — say what this **packet** includes.'
      );
      lines.push(
        '- Average daily census is included in the page context and embedded quarterly CSV when CMS ' +
          'reported it — use it for HPRD/denominator interpretation; do not claim census is unavailable ' +
          'when it appears in the material.'
      );
      lines.push(
        '- Do not infer daily/shift staffing, roster rows, incident-date windows, or resident-level care ' +
          'from this quarterly packet unless explicitly shown.'
      );
    } else if (ptype === 'state') {
      lines.push(
        '- If this is a state page, use state-level quarterly context only; do not infer individual facility conditions unless facility-level data is provided.'
      );
    } else {
      lines.push(
        '- Use only metrics and time depth shown on the page or export; do not infer premium-only fields.'
      );
    }
    shared.forEach(function (rule) {
      lines.push('- ' + rule);
    });
    return lines.join('\n');
  }

  function layeredOutputFormat(length) {
    var layer = layeredBundle();
    var lengthKey = normalizeLength(length);
    if (lengthKey === 'quick') {
      return (
        layer.outputQuick ||
        '1. What the data shows\n2. What it may suggest\n3. What it cannot prove\n4. Questions to ask next\n5. Bottom line (1–2 sentences)\n6. Data-visual completeness (per Presentation block)'
      );
    }
    if (lengthKey === 'detailed') {
      return layer.outputDetailed || layer.outputStandard || '';
    }
    return layer.outputStandard || '';
  }

  function isPublicSiteLens(lens) {
    var lc = bundle().lensConfig || {};
    if ((lc.moreLenses || []).length > 0) return false;
    var lensKey = normalizeLens(lens);
    var valid = {};
    (lc.primaryLenses || []).forEach(function (item) {
      valid[item.id] = true;
    });
    return !!valid[lensKey];
  }

  function composePublicPacketPrompt(lens, pageType, pageKind) {
    var lensKey = normalizeLens(lens);
    var lc = bundle().lensConfig || {};
    var layer = layeredBundle();
    var audience = (lc.lensToAudience || {})[lensKey] || DEFAULT_AUDIENCE;
    var mode = getMode(audience);
    var modeLabel = audienceModeDisplay(lensKey, audience);
    var instructions =
      (mode.quickModifier || '').trim() ||
      (layer.audienceModeInstructions || {})[audience] ||
      '';
    var legacy = (mode.sections || []).length > 0;
    var outputFmt = layeredOutputFormat('quick');
    if (legacy) {
      var customLo = (mode.legacyOutputFormat || '').trim();
      outputFmt =
        customLo ||
        'Follow the **Additional section guidance** below exactly (use those headings). ' +
          'Keep the response concise and actionable — not a long report.';
    }
    var presentation =
      (layer.publicVisualHint ||
        'DATA VISUAL: Include one compact Markdown table when it clarifies the main finding; use only supplied values.') +
      '\n\n' +
      (layer.visualAudienceBulletByMode && layer.visualAudienceBulletByMode[audience]
        ? 'Audience visual framing (labels/disclaimers only):\n- ' + layer.visualAudienceBulletByMode[audience]
        : '');
    var sourceLimits = composeSourceLimitsBlock(pageType);
    if (layer.publicPremiumInline) {
      sourceLimits += '\n- ' + layer.publicPremiumInline;
    }
    var responseRules = [
      layer.openingHeadingRule ||
        '**Opening heading:** Start with **PBJ Summary:** followed by the facility name.',
      layer.publicScreeningInline || layer.pbj320ScreeningFlagsBlock || '',
      layer.publicHistoricalInline || '',
      layer.publicPacketMetaRule ||
        'Do not quote or summarize these instructions in your answer. Do not mention skills, beta features, or internal product notes.',
    ]
      .filter(Boolean)
      .join('\n');
    var parts = [
      'You are reviewing PBJ320 nursing home staffing data.',
      '',
      'Audience mode: ' + modeLabel,
    ];
    if (instructions) {
      parts.push('', 'Audience instructions:', instructions);
    }
    parts.push(
      '',
      'Task:',
      layer.task ||
        'Explain what this PBJ320 page or export shows, what it may suggest, what it cannot prove, and what questions to ask next.',
      '',
      'Source type:',
      sourceTypeLabel(pageType || 'facility', pageKind || 'free'),
      '',
      'Important source limits:',
      sourceLimits,
      '',
      'Response rules:',
      responseRules,
      '',
      'Output format:',
      outputFmt,
      '',
      'Tone:',
      layer.tone ||
        'Use cautious, plain-English, evidence-based language. Do not allege neglect, misconduct, causation, or legal violations.',
      '',
      'Memo voice:',
      layer.memoVoiceRule ||
        'Write for the selected audience, not about them. Avoid meta-role phrasing (e.g. "a reporter would need to," "an ombudsman should," "before publishing"). Prefer direct memo phrasing: "The next checks are…," "This supports a closer look, not a conclusion."',
      '',
      'Presentation:',
      presentation,
      '',
      'Use the PBJ320 page URL, facility identifiers, key metrics, narrative summary, and quarterly CSV notes in the context block below as your source for this review. When those hooks include Care Compare, entity, state, report, or SFF URLs, keep them in your answer when useful.'
    );
    var body = parts.join('\n');
    if (legacy) {
      body += '\n\nAdditional section guidance:\n' + formatAdvancedSections(mode, audience);
    }
    return body;
  }

  function composeLayeredReviewPrompt(lens, pageType, length, pageKind) {
    var lensKey = normalizeLens(lens);
    var lc = bundle().lensConfig || {};
    var layer = layeredBundle();
    var audience = (lc.lensToAudience || {})[lensKey] || DEFAULT_AUDIENCE;
    var mode = getMode(audience);
    var modeLabel = audienceModeDisplay(lensKey, audience);
    var instructions =
      (mode.quickModifier || '').trim() ||
      (layer.audienceModeInstructions || {})[audience] ||
      '';
    var lenKey = normalizeLength(length || 'quick');
    var legacy = (mode.sections || []).length > 0;
    var outputFmt = layeredOutputFormat(lenKey);
    if (legacy) {
      var customLo = (mode.legacyOutputFormat || '').trim();
      outputFmt =
        customLo ||
        'Follow the **Additional section guidance** below exactly (use those headings). ' +
        'Keep the response concise and actionable — not a long report. ' +
        'Do not write in Attorney Mode (legal theories, discovery lists, proof language) or Journalist Mode ' +
        '(story angles, publication framing).';
    }
    var basePresentation =
      layer.visualOutputHint ||
      'DATA VISUAL (required): One audience-appropriate exhibit only when it clarifies the strongest supplied finding; use only pasted values; chart-ready Markdown or explicit why none if no figure.';
    var audBullets = layer.visualAudienceBulletByMode || {};
    var audBullet = audBullets[audience] || audBullets.analyst;
    var presentation = basePresentation;
    if (audBullet) {
      presentation +=
        '\n\nAudience visual framing (labels/disclaimers only — defer to DATA VISUAL rule above for whether to chart and which pattern matters):\n- ' +
        audBullet;
    }
    if (legacy) {
      var customPr = (mode.legacyPresentation || '').trim();
      if (customPr) {
        presentation += '\n\nPresentation mode note: ' + customPr;
      }
    }
    var parts = [
      'You are reviewing PBJ320 nursing home staffing data.',
      '',
      'Audience mode: ' + modeLabel,
    ];
    if (instructions) {
      parts.push('', 'Audience instructions:', instructions);
    }
    parts.push(
      '',
      'Task:',
      layer.task ||
        'Explain what this PBJ320 page or export shows, what it may suggest, what it cannot prove, and what questions to ask next.',
      '',
      'Source type:',
      sourceTypeLabel(pageType || 'facility', pageKind || 'free'),
      '',
      'Important source limits:',
      composeSourceLimitsBlock(pageType),
      ''
    );
    if (layer.pbj320ScreeningFlagsBlock || layer.cmsRiskScreeningBlock) {
      parts.push(
        '',
        'PBJ320 screening flags (when present in context):',
        layer.pbj320ScreeningFlagsBlock || layer.cmsRiskScreeningBlock
      );
    }
    if (layer.historicalContextBlock) {
      parts.push(
        '',
        'Pandemic-era longitudinal context (2020–2023 overlap):',
        layer.historicalContextBlock
      );
    }
    if (layer.audienceTimingEmphasis) {
      parts.push('', 'Staffing trend timing by audience:', layer.audienceTimingEmphasis);
    }
    parts.push(
      '',
      'Output format:',
      outputFmt,
      '',
      'Tone:',
      layer.tone ||
        'Use cautious, plain-English, evidence-based language. Do not allege neglect, misconduct, causation, or legal violations.',
      '',
      'Memo voice:',
      layer.memoVoiceRule ||
        'Write for the selected audience, not about them. Avoid meta-role phrasing (e.g. "a reporter would need to," "an ombudsman should," "before publishing"). Prefer direct memo phrasing: "The next checks are…," "This supports a closer look, not a conclusion."',
      '',
      'Presentation:',
      presentation,
      '',
      'Use the PBJ320 page URL, facility identifiers, key metrics, narrative summary, and quarterly CSV notes in the context block below as your source for this review. When those hooks include Care Compare, entity, state, report, or SFF URLs, keep them in your answer when useful.'
    );
    var body = parts.join('\n');
    if (legacy && lenKey === 'quick') {
      body += '\n\nAdditional section guidance:\n' + formatAdvancedSections(mode, audience);
    }
    return body;
  }

  function composeReviewPromptQuick(config, pageType) {
    var cfg = normalizeConfig(config);
    var lc = bundle().lensConfig || {};
    var lensKey = 'ombudsman';
    var map = lc.lensToAudience || {};
    var lid;
    for (lid in map) {
      if (map[lid] === cfg.audience) {
        lensKey = lid;
        break;
      }
    }
    if (isPublicSiteLens(lensKey)) {
      return composePublicPacketPrompt(lensKey, pageType || 'facility', 'free');
    }
    return composeLayeredReviewPrompt(lensKey, pageType || 'facility', 'quick');
  }

  function lensDisplayLabel(lens) {
    var lensKey = normalizeLens(lens);
    var lc = bundle().lensConfig || {};
    var items = (lc.primaryLenses || []).concat(lc.moreLenses || []);
    for (var i = 0; i < items.length; i++) {
      if (items[i].id === lensKey) return items[i].label;
    }
    return 'General';
  }

  function composeReviewPromptForLens(lens, pageType) {
    var lensKey = normalizeLens(lens);
    if (isPublicSiteLens(lensKey)) {
      return composePublicPacketPrompt(lensKey, pageType || 'facility', 'free');
    }
    return composeLayeredReviewPrompt(lens, pageType || 'facility', 'quick');
  }

  function composeReviewPromptAdvanced(config, materialPlaceholder, pageType, lens) {
    var cfg = normalizeConfig(config);
    var mode = getMode(cfg.audience);
    var core = bundle().core || {};
    var lc = bundle().lensConfig || {};
    var lensKey = lens != null ? normalizeLens(lens) : 'ombudsman';
    if (lens == null) {
      var map = lc.lensToAudience || {};
      var lid;
      for (lid in map) {
        if (map[lid] === cfg.audience) {
          lensKey = lid;
          break;
        }
      }
    }
    var placeholder =
      materialPlaceholder || core.handoffPlaceholder || '[PASTE PBJ320 PAGE TEXT, SCREENSHOT, CSV, OR EXPORT HERE]';
    var checks = (core.checks || []).map(function (c) {
      return '- ' + c;
    });
    var header = composeLayeredReviewPrompt(lensKey, pageType || 'facility', 'detailed');
    return (
      header +
      '\n\nAdditional section guidance:\n' +
      formatAdvancedSections(mode, cfg.audience) +
      '\n\nShared interpretation checks:\n' +
      checks.join('\n') +
      '\n\nAnalyze the PBJ320 material below:\n\n' +
      placeholder
    );
  }

  function composeReviewPrompt(config, useAdvanced) {
    if (useAdvanced) return composeReviewPromptAdvanced(config);
    return composeReviewPromptQuick(config);
  }

  function inferGeographyFromPageType(pageType) {
    var mapping = {
      facility: 'facility',
      provider: 'facility',
      state: 'state',
      entity: 'ownership_group',
      chain: 'ownership_group',
      ownership: 'ownership_group',
      region: 'region',
      cms_region: 'region',
      county: 'county',
      city: 'city',
      national: 'national',
    };
    return mapping[String(pageType || '').toLowerCase()] || null;
  }

  function reviewConfigForPage(pageType, overrides) {
    var base = normalizeConfig(overrides);
    if (!base.geography_level) {
      base.geography_level = inferGeographyFromPageType(pageType);
    }
    return base;
  }

  function getActiveConfig() {
    if (global.__PBJ_REVIEW_ACTIVE_CONFIG__) {
      return normalizeConfig(global.__PBJ_REVIEW_ACTIVE_CONFIG__);
    }
    return normalizeConfig(global.__PBJ_REVIEW_DEFAULT_CONFIG__);
  }

  function setActiveConfig(config) {
    global.__PBJ_REVIEW_ACTIVE_CONFIG__ = normalizeConfig(config);
    return global.__PBJ_REVIEW_ACTIVE_CONFIG__;
  }

  function normalizeLens(lens) {
    var lc = bundle().lensConfig || {};
    var key = String(lens || '')
      .trim()
      .toLowerCase()
      .replace(/\s+/g, '_')
      .replace(/-/g, '_');
    var aliases = {
      analyst: 'ombudsman',
      general: 'ombudsman',
      advocate: 'ombudsman',
      attorney: 'ombudsman',
      researcher: 'ombudsman',
      policymaker: 'ombudsman',
      legislator: 'ombudsman',
      operator: 'ombudsman',
      family_resident: 'family',
      ombuds: 'ombudsman',
      reporter: 'journalist',
    };
    key = aliases[key] || key;
    var valid = {};
    (lc.primaryLenses || []).concat(lc.moreLenses || []).forEach(function (item) {
      valid[item.id] = true;
    });
    return valid[key] ? key : lc.defaultLens || 'ombudsman';
  }

  function normalizeLength(length) {
    var lc = bundle().lensConfig || {};
    var key = String(length || '')
      .trim()
      .toLowerCase()
      .replace(/\s+/g, '_')
      .replace(/-/g, '_');
    var aliases = {
      quick_takeaway: 'quick',
      standard_review: 'standard',
      detailed_review: 'detailed',
    };
    key = aliases[key] || key;
    var valid = { quick: true, standard: true, detailed: true };
    return valid[key] ? key : lc.defaultLength || 'quick';
  }

  function composeReviewGuardrails(pageType) {
    return 'Important source limits:\n' + composeSourceLimitsBlock(pageType);
  }

  function composeStandardReviewPrompt(config, pageType, materialPlaceholder, lens) {
    var cfg = normalizeConfig(config);
    var mode = getMode(cfg.audience);
    var core = bundle().core || {};
    var lc = bundle().lensConfig || {};
    var lensKey = lens != null ? normalizeLens(lens) : 'ombudsman';
    if (lens == null) {
      var map = lc.lensToAudience || {};
      var lid;
      for (lid in map) {
        if (map[lid] === cfg.audience) {
          lensKey = lid;
          break;
        }
      }
    }
    var placeholder =
      materialPlaceholder || core.handoffPlaceholder || '[PASTE PBJ320 PAGE TEXT, SCREENSHOT, CSV, OR EXPORT HERE]';
    var checks = (core.checks || []).map(function (c) {
      return '- ' + c;
    });
    var header = composeLayeredReviewPrompt(lensKey, pageType || 'facility', 'standard');
    return (
      header +
      '\n\nAdditional section guidance:\n' +
      formatTierSections('standard', mode, cfg.audience) +
      '\n\nShared interpretation checks:\n' +
      checks.join('\n') +
      '\n\nAnalyze the PBJ320 material below:\n\n' +
      placeholder
    );
  }

  function fillProviderTemplate(tpl, stateLabel, stateExamples) {
    var st = String(stateLabel || '').trim();
    if (!st) {
      st = 'not stated — infer state from the pasted facility context';
    }
    var ex = stateExamples || '';
    return String(tpl || '')
      .split('{{state}}')
      .join(st)
      .split('{state}')
      .join(st)
      .split('{{state_examples}}')
      .join(ex)
      .split('{{ny_examples}}')
      .join(ex)
      .split('{ny_examples}')
      .join(ex);
  }

  function resolveStateExamplesBlock(stateLabel, stateCode, lensKey) {
    var fw = global.__PBJ_REVIEW_FRAMEWORK__ || {};
    var sup = fw.providerDashboardSupplements || {};
    var byCode = sup.stateExamplesByCode || {};
    var sc = String(stateCode || '')
      .trim()
      .toUpperCase();
    var stUp = String(stateLabel || '')
      .trim()
      .toUpperCase();
    if (!sc && stUp.indexOf('CONNECTICUT') >= 0) sc = 'CT';
    if (!sc && stUp.indexOf('NEW YORK') >= 0) sc = 'NY';
    var lens = lensKey || 'ombudsman';
    if (sc && byCode[sc]) {
      var pack = byCode[sc];
      if (pack[lens]) return pack[lens];
      if (pack.ombudsman) return pack.ombudsman;
    }
    return '';
  }

  function interpolateProviderSupplements(stateLabel, stateCode, lensKey) {
    var fw = global.__PBJ_REVIEW_FRAMEWORK__ || {};
    var sup = fw.providerDashboardSupplements || {};
    var st = String(stateLabel || '').trim();
    var stateEx = resolveStateExamplesBlock(st, stateCode, lensKey);
    var csv = sup.csvSourceDepthNote || '';
    var intro = fillProviderTemplate(sup.stateIntroTemplate || '', st, stateEx);
    var byLens = sup.stateSectionsByLens || {};
    var body = fillProviderTemplate(byLens[lensKey] || byLens.ombudsman || byLens.general || '', st, stateEx);
    var parts = [];
    if (csv) parts.push(csv);
    if (intro) parts.push(intro);
    if (body) parts.push(body);
    return parts.join('\n\n').trim();
  }

  function appendProviderDashboardSupplements(
    promptBody,
    lens,
    length,
    pageType,
    stateLabel,
    stateCode
  ) {
    var ptype = String(pageType || '').toLowerCase();
    if (ptype !== 'facility' && ptype !== 'provider') return promptBody;
    var lensKey = normalizeLens(lens);
    var extra = interpolateProviderSupplements(stateLabel, stateCode, lensKey);
    if (!extra) return promptBody;
    return String(promptBody || '').replace(/\s+$/, '') + '\n\n' + extra;
  }

  function composeDashboardPrompt(lens, length, pageType, materialPlaceholder, stateLabel, stateCode) {
    var lc = bundle().lensConfig || {};
    var lensKey = normalizeLens(lens);
    var lengthKey = normalizeLength(length);
    var audience = (lc.lensToAudience || {})[lensKey] || DEFAULT_AUDIENCE;
    var cfg = reviewConfigForPage(pageType || 'facility', { audience: audience });
    var placeholder =
      materialPlaceholder ||
      (bundle().core || {}).handoffPlaceholder ||
      '[PASTE PBJ320 PAGE TEXT, SCREENSHOT, CSV, OR EXPORT HERE]';

    var base;
    if (lengthKey === 'quick') {
      base = isPublicSiteLens(lensKey)
        ? composePublicPacketPrompt(lensKey, pageType, 'free')
        : composeLayeredReviewPrompt(lensKey, pageType, 'quick');
    } else if (lengthKey === 'standard') {
      base = composeStandardReviewPrompt(cfg, pageType, placeholder, lensKey);
    } else {
      base = composeReviewPromptAdvanced(cfg, placeholder, pageType, lensKey);
    }
    return appendProviderDashboardSupplements(
      base,
      lensKey,
      lengthKey,
      pageType,
      stateLabel || '',
      stateCode || ''
    );
  }

  var api = {
    DEFAULT_AUDIENCE: DEFAULT_AUDIENCE,
    bundle: bundle,
    normalizeAudience: normalizeAudience,
    normalizeGeographyLevel: normalizeGeographyLevel,
    normalizeConfig: normalizeConfig,
    getMode: getMode,
    formatContextBlock: formatContextBlock,
    composeReviewPromptQuick: composeReviewPromptQuick,
    composeLayeredReviewPrompt: composeLayeredReviewPrompt,
    composePublicPacketPrompt: composePublicPacketPrompt,
    isPublicSiteLens: isPublicSiteLens,
    composeReviewPromptForLens: composeReviewPromptForLens,
    lensDisplayLabel: lensDisplayLabel,
    composeReviewPromptAdvanced: composeReviewPromptAdvanced,
    composeReviewPrompt: composeReviewPrompt,
    inferGeographyFromPageType: inferGeographyFromPageType,
    reviewConfigForPage: reviewConfigForPage,
    getActiveConfig: getActiveConfig,
    setActiveConfig: setActiveConfig,
    normalizeLens: normalizeLens,
    normalizeLength: normalizeLength,
    audienceModeDisplay: audienceModeDisplay,
    composeReviewGuardrails: composeReviewGuardrails,
    composeStandardReviewPrompt: composeStandardReviewPrompt,
    composeDashboardPrompt: composeDashboardPrompt,
  };

  global.PBJReviewFramework = api;
})(typeof window !== 'undefined' ? window : this);
