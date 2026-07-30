/**
 * PBJ320 audience system — compact signup row + one-line confirmation.
 */
(function (global) {
  'use strict';

  var STORAGE_KEY = 'pbj_audience_v2';
  var SUBSTACK_URL = 'https://320insight.substack.com/';
  var FACILITY_POPUP_PROMPT_TYPE = 'facility_follow_popup';
  var SESSION_PROMPT_SHOWN_KEY = 'pbj_audience_facility_popup_shown';
  var SESSION_MODAL_OPENED_KEY = 'pbj_audience_email_modal_opened';
  var SESSION_INLINE_INTERACTION_PREFIX = 'pbj_audience_facility_inline_interacted:';
  // Verified from: audience/service.py _EMAIL_RE
  var EMAIL_RE = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;

  var SUB_TYPES = {
    PBJ320_INSIGHTS: 'pbj320_insights',
    FACILITY: 'facility',
    STATE: 'state',
    NATIONAL: 'national',
    APP: 'app_early_access',
    RESEARCH: 'research_tools',
    ATTORNEY: 'attorney_resources',
    ADVOCACY: 'advocacy'
  };

  var state = loadState();
  var config = { engagementPromptsEnabled: false, feedbackPromptsEnabled: false };
  var csrfToken = '';
  var promptsShownThisSession = false;
  var inlineCtaMounted = false;
  var lastFocusedBeforeModal = null;
  var pageStartedAt = Date.now();
  var inlineFacilityVisible = false;
  var inlineFacilityObserver = null;
  var popupSuppressionLogged = {};
  var popupEligibleLogged = false;
  var popupRetryBound = false;

  function loadState() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (raw) return normalizeState(JSON.parse(raw));
    } catch (e) {}
    return normalizeState({
      visitorKey: randomId(),
      sessionCount: 0,
      pageviewCount: 0,
      facilityPageViews: 0,
      facilityCcnsViewed: [],
      followedFacilityCcns: [],
      subscribedTypes: [],
      recentStateAbbr: '',
      recentStateName: '',
      email: '',
      dismissedPrompts: {},
      searchStateFilters: []
    });
  }

  function normalizeState(value) {
    var next = value && typeof value === 'object' ? value : {};
    next.visitorKey = next.visitorKey || randomId();
    next.sessionCount = Number(next.sessionCount || 0);
    next.pageviewCount = Number(next.pageviewCount || 0);
    next.subscribedTypes = Array.isArray(next.subscribedTypes) ? next.subscribedTypes : [];
    next.facilityCcnsViewed = Array.isArray(next.facilityCcnsViewed) ? next.facilityCcnsViewed : [];
    if (!Array.isArray(next.followedFacilityCcns)) {
      next.legacyFacilityFollow = next.subscribedTypes.indexOf(SUB_TYPES.FACILITY) >= 0;
      next.followedFacilityCcns = [];
    }
    next.facilityPageViews = next.facilityCcnsViewed.length;
    next.searchStateFilters = Array.isArray(next.searchStateFilters) ? next.searchStateFilters : [];
    return next;
  }

  function saveState() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch (e) {}
  }

  function sessionGet(key) {
    try { return sessionStorage.getItem(key); } catch (e) { return null; }
  }

  function sessionSet(key, value) {
    try { sessionStorage.setItem(key, value); } catch (e) {}
  }

  function randomId() {
    var a = new Uint8Array(16);
    if (global.crypto && global.crypto.getRandomValues) {
      global.crypto.getRandomValues(a);
      return Array.from(a, function (b) { return b.toString(16).padStart(2, '0'); }).join('');
    }
    return String(Date.now()) + Math.random().toString(16).slice(2);
  }

  function parseRouteContext() {
    var el = document.getElementById('pbj-route-context');
    if (!el) return { kind: 'fallback' };
    try {
      var payload = JSON.parse(el.textContent || '{}');
      return payload.context || { kind: 'fallback' };
    } catch (e) { return { kind: 'fallback' }; }
  }

  function deviceCategory() {
    return global.matchMedia && global.matchMedia('(max-width: 639px)').matches ? 'mobile' : 'desktop';
  }

  function utmParams() {
    var p = new URLSearchParams(global.location.search);
    return { utmSource: p.get('utm_source') || '', utmMedium: p.get('utm_medium') || '', utmCampaign: p.get('utm_campaign') || '' };
  }

  function buildContext(extra) {
    var ctx = parseRouteContext();
    var utm = utmParams();
    var base = {
      sourceUrl: global.location.href.split('#')[0],
      pageType: ctx.kind || 'fallback',
      referrer: document.referrer || '',
      deviceCategory: deviceCategory(),
      utmSource: utm.utmSource,
      utmMedium: utm.utmMedium,
      utmCampaign: utm.utmCampaign,
      visitorStatus: state.sessionCount > 1 ? 'repeat' : 'first',
      pageviewCount: state.pageviewCount,
      facilityPageViews: state.facilityPageViews,
      visitorKey: state.visitorKey,
      searchStateFilters: state.searchStateFilters || []
    };
    if (ctx.ccn) { base.ccn = ctx.ccn; base.resourceId = ctx.ccn; }
    if (ctx.stateAbbr) base.stateAbbr = ctx.stateAbbr;
    if (ctx.stateName) base.stateName = ctx.stateName;
    if (ctx.stateSlug) base.stateSlug = ctx.stateSlug;
    if (ctx.entityId) base.entityId = ctx.entityId;
    if (state.recentStateAbbr && !base.stateAbbr) {
      base.recentStateAbbr = state.recentStateAbbr;
      base.recentStateName = state.recentStateName;
    }
    if (extra) Object.keys(extra).forEach(function (k) { base[k] = extra[k]; });
    return base;
  }

  function resolveCta(ctx, explicitVariant) {
    ctx = ctx || buildContext();
    var pageType = (ctx.pageType || ctx.kind || 'fallback').toLowerCase();
    var stateName = (ctx.stateName || ctx.recentStateName || '').trim();
    var stateAbbr = (ctx.stateAbbr || ctx.recentStateAbbr || '').trim().toUpperCase();
    var filters = ctx.searchStateFilters || [];
    var variant = explicitVariant;

    if (!variant) {
      if (pageType === 'provider' || pageType === 'facility') variant = 'facility_follow';
      else if (pageType === 'state' && stateAbbr && stateAbbr !== 'USA') variant = 'state_follow';
      else if (pageType === 'search' || ctx.fromSearch) {
        variant = filters.length === 1 ? 'search_state' : 'search_national';
        if (filters.length === 1) stateAbbr = filters[0];
      } else if (pageType === 'insights' || pageType === 'insights_article') variant = 'insights_article';
      else if (pageType === 'attorneys' || pageType === 'premium') variant = 'attorney_updates';
      else if (pageType === 'homepage') variant = 'homepage_insights';
      else variant = 'homepage_insights';
    }

    var spec = {
      variant: variant,
      primary: SUB_TYPES.PBJ320_INSIGHTS,
      submitLabel: 'Subscribe',
      preferenceDefaults: [SUB_TYPES.PBJ320_INSIGHTS],
      isMultiProductModal: false
    };

    if (variant === 'facility_follow') {
      spec.primary = SUB_TYPES.FACILITY;
      spec.preferenceDefaults = [SUB_TYPES.FACILITY];
    } else if (variant === 'state_follow' || variant === 'search_state' || variant === 'homepage_continue_state') {
      spec.primary = SUB_TYPES.STATE;
      spec.preferenceDefaults = [SUB_TYPES.STATE];
    } else if (variant === 'search_national' || variant === 'national_updates') {
      spec.primary = SUB_TYPES.NATIONAL;
      spec.preferenceDefaults = [SUB_TYPES.NATIONAL];
    } else if (variant === 'insights_article') {
      spec.primary = SUB_TYPES.PBJ320_INSIGHTS;
      spec.preferenceDefaults = [SUB_TYPES.PBJ320_INSIGHTS];
    } else if (variant === 'attorney_updates') {
      spec.primary = SUB_TYPES.ATTORNEY;
      spec.preferenceDefaults = [SUB_TYPES.ATTORNEY];
    } else if (variant === 'homepage_app') {
      spec.primary = SUB_TYPES.APP;
      spec.preferenceDefaults = [SUB_TYPES.APP];
    } else if (variant === 'email_updates_modal') {
      spec.isMultiProductModal = true;
      spec.preferenceDefaults = [SUB_TYPES.PBJ320_INSIGHTS];
    }

    spec.suppressed = spec.primary === SUB_TYPES.FACILITY
      ? isCurrentFacilityFollowed(ctx.ccn)
      : hasSubscription(spec.primary);
    return spec;
  }

  function inlineLabelForSpec(spec, ctx) {
    var stateName = (ctx.stateName || ctx.stateAbbr || '').trim();
    if (spec.variant === 'homepage_insights' || spec.variant === 'email_updates_modal' || spec.variant === 'homepage_app') {
      return '';
    }
    if (spec.variant === 'facility_follow') return 'Facility updates';
    if (spec.variant === 'state_follow' || spec.variant === 'search_state' || spec.variant === 'homepage_continue_state') {
      return stateName ? (stateName + ' updates') : 'State updates';
    }
    if (spec.variant === 'search_national' || spec.variant === 'national_updates') return 'National staffing updates';
    if (spec.variant === 'insights_article') return 'PBJ320 Insights';
    if (spec.variant === 'attorney_updates') return 'Attorney updates';
    return '';
  }

  function successMessageForSpec(spec, ctx) {
    var stateName = (ctx.stateName || ctx.stateAbbr || '').trim();
    if (spec.primary === SUB_TYPES.FACILITY) return 'You\u2019re subscribed to updates for this facility.';
    if (spec.primary === SUB_TYPES.STATE && stateName) {
      return 'You\u2019re subscribed to ' + stateName + ' staffing updates.';
    }
    if (spec.primary === SUB_TYPES.NATIONAL) return 'You\u2019re subscribed to national staffing updates.';
    if (spec.primary === SUB_TYPES.APP) return 'You\u2019re on the PBJ320 app early-access list.';
    if (spec.primary === SUB_TYPES.ATTORNEY) return 'You\u2019re subscribed to attorney updates.';
    return 'You\u2019re subscribed to PBJ320 Insights.';
  }

  /** Only facility pages may offer an optional adjacent state subscription. */
  function adjacentOffer(spec, ctx) {
    var stateName = (ctx.stateName || ctx.stateAbbr || '').trim();
    if (spec.variant === 'facility_follow' && stateName && !hasSubscription(SUB_TYPES.STATE)) {
      return { subscriptionType: SUB_TYPES.STATE, label: 'Also get ' + stateName + ' staffing updates' };
    }
    return null;
  }

  function trackEvent(name, params) {
    var p = params || {};
    p.visitor_status = state.sessionCount > 1 ? 'repeat' : 'first';
    p.device_category = deviceCategory();
    sendEngagementEvent(name, p);
  }

  function sendEngagementEvent(name, params) {
    var p = params || {};
    if (typeof global.gtag === 'function') global.gtag('event', name, p);
    var safe = {};
    Object.keys(p).forEach(function (k) {
      if (k.toLowerCase().indexOf('email') < 0 && k.toLowerCase().indexOf('token') < 0) safe[k] = p[k];
    });
    fetch('/api/audience/engagement', {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({
        visitorKey: state.visitorKey, eventName: name,
        pageType: safe.page_type || parseRouteContext().kind,
        resourceId: safe.resource_id, metadata: safe
      })
    }).catch(function () {});
  }

  function hasSubscription(type) {
    return state.subscribedTypes && state.subscribedTypes.indexOf(type) >= 0;
  }

  function isValidEmail(email) {
    return EMAIL_RE.test(String(email || '').trim());
  }

  function isCurrentFacilityFollowed(ccn) {
    var normalized = String(ccn || '').trim();
    if (normalized && state.followedFacilityCcns.indexOf(normalized) >= 0) return true;
    return state.legacyFacilityFollow === true;
  }

  function markCurrentFacilityFollowed(ccn) {
    var normalized = String(ccn || '').trim();
    if (normalized && state.followedFacilityCcns.indexOf(normalized) < 0) {
      state.followedFacilityCcns.push(normalized);
    }
  }

  function fetchCsrf() {
    var home = document.querySelector('input[name="csrf_token"]');
    if (home && home.value) { csrfToken = home.value; return Promise.resolve(csrfToken); }
    return fetch('/api/subscribe/csrf', { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(function (r) { return r.json(); })
      .then(function (d) { csrfToken = (d && d.csrf_token) || ''; return csrfToken; })
      .catch(function () { return ''; });
  }

  function fetchConfig() {
    return fetch('/api/audience/config', { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(function (r) { return r.json(); })
      .then(function (d) { config = d || config; return config; })
      .catch(function () { return config; });
  }

  function escapeHtml(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function analyticsForPrimary(primary) {
    if (primary === SUB_TYPES.FACILITY) return 'facility_followed';
    if (primary === SUB_TYPES.STATE) return 'state_followed';
    if (primary === SUB_TYPES.NATIONAL) return 'national_updates_subscribed';
    if (primary === SUB_TYPES.PBJ320_INSIGHTS) return 'pbj320_insights_subscribed';
    if (primary === SUB_TYPES.APP) return 'app_early_access_joined';
    return 'signup_completed';
  }

  function analyticsForType(type) {
    return analyticsForPrimary(type);
  }

  function mountSignup(target, options) {
    options = options || {};
    var ctx = buildContext(options.contextExtra || {});
    if (options.facilityName) ctx.facilityName = options.facilityName;
    var spec = resolveCta(ctx, options.variant);

    var root = document.createElement('section');
    var layout = options.layout || (options.compact && spec.variant === 'insights_article' ? 'insights-sticky' : 'default');
    root.className = 'pbj-audience pbj-audience--minimal' +
      (options.compact ? ' pbj-audience--compact' : '') +
      (layout === 'insights-sticky' ? ' pbj-audience--insights-sticky' : '') +
      (inlineLabelForSpec(spec, ctx) ? ' pbj-audience--labeled' : '');
    if (!options.isModal) {
      root.setAttribute('data-pbj-audience-inline', '1');
      inlineCtaMounted = true;
    }
    root.setAttribute('data-pbj-audience-variant', spec.variant);
    var sectionLabel = options.inlineLabel || inlineLabelForSpec(spec, ctx);
    if (sectionLabel) root.setAttribute('aria-label', sectionLabel);
    if (options.popup) root.classList.add('pbj-audience--facility-popup');

    if (spec.suppressed && !options.force) {
      root.classList.add('pbj-audience--already');
      root.innerHTML = layout === 'insights-sticky'
        ? '<div class="subscribe-cta-inner"></div>'
        : '<div class="hero-email-cta"></div>';
      var alreadyHost = root.querySelector('.hero-email-cta') || root.querySelector('.subscribe-cta-inner') || root;
      showAlreadySubscribedState(alreadyHost, spec, ctx, options);
      if (target) { target.innerHTML = ''; target.appendChild(root); }
      return root;
    }

    var formOptions = {};
    if (spec.variant === 'homepage_insights') {
      formOptions.labelledBy = 'pbj-home-subscribe-title';
    } else if (!options.popup && (spec.variant === 'email_updates_modal' || options.isModal)) {
      formOptions.labelledBy = 'pbj-subscribe-popup-title';
    }
    if (options.inlineLabel) formOptions.inlineLabel = options.inlineLabel;
    if (options.placeholder) formOptions.placeholder = options.placeholder;
    if (options.submitLabel) formOptions.submitLabel = options.submitLabel;

    var formHtml = buildSingleProductForm(spec, ctx, options.inputIdSuffix || spec.variant, formOptions);
    var inner;

    if (layout === 'insights-sticky') {
      inner = '<div class="subscribe-cta-inner">' + formHtml +
        '<p class="pbj-audience__msg pbj-audience__msg--err" hidden role="alert"></p></div>';
    } else {
      inner = '<div class="hero-email-cta">' + formHtml +
        '<p class="pbj-audience__msg pbj-audience__msg--err" hidden role="alert"></p></div>';
    }

    root.innerHTML = inner;

    if (!options.popup) {
      trackEvent('signup_cta_viewed', { page_type: ctx.pageType, cta_variant: spec.variant, resource_id: ctx.ccn || ctx.stateAbbr });
    }

    var form = root.querySelector('form');
    var errEl = root.querySelector('.pbj-audience__msg--err');
    if (form) {
      wireEmailValidation(form, errEl);
      form.addEventListener('submit', function (ev) {
        ev.preventDefault();
        handleSubmit(form, errEl, root, spec, ctx, options);
      });
    }

    if (target) { target.innerHTML = ''; target.appendChild(root); }
    if (spec.variant === 'facility_follow' && !options.isModal && !options.popup) {
      setupInlineFacilityTracking(root, ctx);
    }
    return root;
  }

  function buildSingleProductForm(spec, ctx, idSuffix, formOptions) {
    formOptions = formOptions || {};
    var inputId = 'pbj-aud-email-' + (idSuffix || 'default');
    var inlineLabel = formOptions.inlineLabel || inlineLabelForSpec(spec, ctx);
    var labelId = inlineLabel ? ('pbj-aud-label-' + (idSuffix || 'default')) : '';
    var labelHtml = inlineLabel
      ? '<span class="pbj-audience__inline-label" id="' + labelId + '">' + escapeHtml(inlineLabel) + '</span>'
      : '';
    var labelledBy = formOptions.labelledBy || labelId;
    var ariaLabelledBy = labelledBy ? (' aria-labelledby="' + escapeHtml(labelledBy) + '"') : '';
    var placeholder = formOptions.placeholder || 'Enter your email';
    var submitLabel = formOptions.submitLabel || spec.submitLabel || 'Subscribe';
    return '<form class="pbj-audience__form" novalidate>' +
      labelHtml +
      '<input class="pbj-audience__input" id="' + inputId + '" type="email" name="email" required autocomplete="email" placeholder="' + escapeHtml(placeholder) + '"' + ariaLabelledBy + '>' +
      '<button type="submit" class="pbj-audience__submit hero-subscribe-submit">' + escapeHtml(submitLabel) + '</button>' +
      '</form>';
  }

  function appendAdjacentOffer(host, offer, email, ctx, spec) {
    if (!offer || host.querySelector('.pbj-audience__adjacent')) return;
    var p = document.createElement('p');
    p.className = 'pbj-audience__secondary pbj-audience__secondary--quiet pbj-audience__adjacent';
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'pbj-audience__link';
    btn.textContent = offer.label;
    btn.addEventListener('click', function () {
      if (btn.disabled) return;
      btn.disabled = true;
      fetchCsrf().then(function (token) {
        return fetch('/api/audience/preferences', {
          method: 'POST', credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json', 'X-CSRF-Token': token },
          body: JSON.stringify({ email: email, preferences: [offer.subscriptionType], context: ctx })
        });
      }).then(function (r) { return r.json(); }).then(function (data) {
        if (!data.ok) { btn.disabled = false; return; }
        if (state.subscribedTypes.indexOf(offer.subscriptionType) < 0) {
          state.subscribedTypes.push(offer.subscriptionType);
        }
        saveState();
        btn.textContent = 'Added.';
        trackEvent('subscription_preference_added', {
          page_type: ctx.pageType, cta_variant: spec.variant, resource_id: ctx.ccn || ctx.stateAbbr
        });
        trackEvent(analyticsForType(offer.subscriptionType), {
          page_type: ctx.pageType, cta_variant: spec.variant, resource_id: ctx.ccn || ctx.stateAbbr
        });
      }).catch(function () { btn.disabled = false; });
    });
    p.appendChild(btn);
    host.appendChild(p);
  }

  function showSuccessState(host, spec, ctx, email, options) {
    var ok = document.createElement('p');
    ok.className = 'pbj-audience__msg pbj-audience__msg--ok';
    ok.setAttribute('role', 'status');
    ok.textContent = (options && options.successMessage) || successMessageForSpec(spec, ctx);
    host.appendChild(ok);

    var offer = options && options.suppressAdjacentOffer ? null : adjacentOffer(spec, ctx);
    if (offer) appendAdjacentOffer(host, offer, email, ctx, spec);
  }

  function showAlreadySubscribedState(host, spec, ctx, options) {
    var chip = document.createElement('p');
    chip.className = 'pbj-audience__chip';
    chip.setAttribute('role', 'status');
    chip.textContent = (options && options.successMessage) || successMessageForSpec(spec, ctx);
    host.appendChild(chip);
  }

  function syncEmailSubmitState(form, errEl) {
    var input = form.querySelector('input[name="email"]');
    var btn = form.querySelector('.pbj-audience__submit');
    if (!input || !btn || btn.classList.contains('is-busy')) return;
    var email = (input.value || '').trim();
    var empty = !email;
    var valid = isValidEmail(email);
    btn.disabled = !valid;
    btn.classList.toggle('is-ready', valid);
    input.classList.toggle('is-invalid', !empty && !valid);
    input.setAttribute('aria-invalid', (!empty && !valid) ? 'true' : 'false');
    if ((valid || empty) && errEl && errEl.getAttribute('data-reason') === 'invalid_email') {
      errEl.hidden = true;
      errEl.removeAttribute('data-reason');
    }
  }

  function wireEmailValidation(form, errEl) {
    var input = form.querySelector('input[name="email"]');
    var btn = form.querySelector('.pbj-audience__submit');
    if (!input || !btn) return;
    btn.disabled = true;
    input.addEventListener('input', function () { syncEmailSubmitState(form, errEl); });
    input.addEventListener('blur', function () { syncEmailSubmitState(form, errEl); });
    syncEmailSubmitState(form, errEl);
  }

  function handleSubmit(form, errEl, root, spec, ctx, options) {
    if (!options.popup) {
      trackEvent('signup_started', { page_type: ctx.pageType, cta_variant: spec.variant });
    }
    var input = form.querySelector('input[name="email"]');
    var email = (input && input.value || '').trim();
    if (!isValidEmail(email)) {
      errEl.hidden = false;
      errEl.setAttribute('data-reason', 'invalid_email');
      errEl.textContent = 'Please enter a valid email address.';
      if (input) {
        input.classList.add('is-invalid');
        input.setAttribute('aria-invalid', 'true');
        try { input.focus(); } catch (e) {}
      }
      if (options.popup) trackFacilityPopupEvent('popup_error', ctx, options.triggerReason, 'invalid_email');
      return;
    }

    var prefs = spec.preferenceDefaults && spec.preferenceDefaults.length
      ? spec.preferenceDefaults.slice()
      : [spec.primary];
    if (spec.isMultiProductModal) {
      prefs = [SUB_TYPES.PBJ320_INSIGHTS];
    }

    var btn = form.querySelector('.pbj-audience__submit');
    var submitLabel = options.submitLabel || spec.submitLabel || 'Subscribe';
    btn.disabled = true;
    btn.classList.add('is-busy');
    btn.textContent = options.popup ? 'Following\u2026' : 'Subscribing\u2026';
    errEl.hidden = true;
    errEl.removeAttribute('data-reason');

    fetchCsrf().then(function (token) {
      return fetch('/api/audience/signup', {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json', 'X-CSRF-Token': token },
        body: JSON.stringify({
          email: email, ctaVariant: spec.variant,
          context: ctx, preferences: prefs
        })
      });
    }).then(function (r) { return r.json(); }).then(function (data) {
      if (!data.ok) {
        errEl.hidden = false;
        errEl.textContent = data.status === 'csrf' ? 'Session expired. Refresh and try again.' : 'Something went wrong.';
        btn.classList.remove('is-busy');
        btn.textContent = submitLabel;
        syncEmailSubmitState(form, errEl);
        if (options.popup) trackFacilityPopupEvent('popup_error', ctx, options.triggerReason, data.status || 'signup_error');
        return;
      }
      state.email = email;
      prefs.forEach(function (p) { if (state.subscribedTypes.indexOf(p) < 0) state.subscribedTypes.push(p); });
      if (spec.primary === SUB_TYPES.FACILITY) markCurrentFacilityFollowed(ctx.ccn);
      if (ctx.stateAbbr) { state.recentStateAbbr = ctx.stateAbbr; state.recentStateName = ctx.stateName || ctx.stateAbbr; }
      saveState();
      form.remove();
      var host = root.querySelector('.hero-email-cta') || root.querySelector('.subscribe-cta-inner');
      if (!host) host = root;
      showSuccessState(host, spec, ctx, email, options);
      if (options.popup) {
        trackFacilityPopupEvent('popup_submitted', ctx, options.triggerReason);
      } else {
        trackEvent(analyticsForPrimary(spec.primary), { page_type: ctx.pageType, cta_variant: spec.variant, resource_id: ctx.ccn || ctx.stateAbbr });
        trackEvent('signup_completed', { page_type: ctx.pageType, cta_variant: spec.variant });
      }
      if (options.onSuccess) options.onSuccess();
    }).catch(function () {
      errEl.hidden = false;
      errEl.textContent = 'Something went wrong. Try again later.';
      btn.classList.remove('is-busy');
      btn.textContent = submitLabel;
      syncEmailSubmitState(form, errEl);
      if (options.popup) trackFacilityPopupEvent('popup_error', ctx, options.triggerReason, 'network_error');
    });
  }

  function autoMount() {
    document.querySelectorAll('[data-pbj-audience]').forEach(function (el) {
      mountSignup(el, {
        variant: el.getAttribute('data-pbj-audience-variant') || undefined,
        compact: el.hasAttribute('data-pbj-audience-compact'),
        facilityName: el.getAttribute('data-facility-name') || undefined
      });
    });
    var ctx = parseRouteContext();
    var providerMount = document.getElementById('pbj-audience-provider');
    if (providerMount && ctx.kind === 'provider') {
      mountSignup(providerMount, {
        variant: 'facility_follow',
        facilityName: providerMount.getAttribute('data-facility-name') || ''
      });
    }
    var stateMount = document.getElementById('pbj-audience-state');
    if (stateMount && ctx.kind === 'state' && ctx.stateAbbr !== 'USA') {
      mountSignup(stateMount, { variant: 'state_follow' });
    }
    var homeMount = document.getElementById('pbj-audience-home');
    if (homeMount) {
      mountSignup(homeMount, { variant: 'homepage_insights' });
    }
    var insightsMount = document.getElementById('pbj-audience-insights');
    if (insightsMount) {
      mountSignup(insightsMount, { variant: 'insights_article', compact: true, layout: 'insights-sticky' });
    }
    var searchMount = document.getElementById('pbj-audience-search');
    if (searchMount) {
      var sctx = buildContext({ fromSearch: true, pageType: 'search' });
      mountSignup(searchMount, { variant: resolveCta(sctx).variant, compact: true });
    }
  }

  function mountEmailUpdatesModal(container) {
    if (!container) return;
    container.innerHTML = '';
    mountSignup(container, { variant: 'email_updates_modal', isModal: true });
    var mounted = container.querySelector('.pbj-audience');
    if (mounted) mounted.classList.remove('pbj-audience--inline');
  }

  function mountModalContent(container) {
    mountEmailUpdatesModal(container);
  }

  function inlineInteractionKey(ccn) {
    return SESSION_INLINE_INTERACTION_PREFIX + String(ccn || 'unknown');
  }

  function hasInlineFacilityInteraction(ccn) {
    return sessionGet(inlineInteractionKey(ccn)) === '1';
  }

  function markInlineFacilityInteraction(ctx) {
    sessionSet(inlineInteractionKey(ctx.ccn), '1');
    logPopupSuppression(ctx, 'inline_cta_interacted');
  }

  function setupInlineFacilityTracking(root, ctx) {
    ['focusin', 'input', 'change', 'pointerdown', 'submit'].forEach(function (name) {
      root.addEventListener(name, function () { markInlineFacilityInteraction(ctx); }, { once: true });
    });
    if (!global.IntersectionObserver) return;
    if (inlineFacilityObserver) inlineFacilityObserver.disconnect();
    inlineFacilityObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        var wasVisible = inlineFacilityVisible;
        inlineFacilityVisible = entry.isIntersecting && entry.intersectionRatio > 0;
        if (wasVisible && !inlineFacilityVisible) attemptFacilityPopup();
      });
    }, { threshold: [0, 0.01] });
    inlineFacilityObserver.observe(root);
  }

  function markManualEmailUpdatesModalOpened() {
    sessionSet(SESSION_MODAL_OPENED_KEY, '1');
    var ctx = buildContext();
    if (ctx.pageType === 'provider' || ctx.pageType === 'facility') {
      logPopupSuppression(ctx, 'manual_modal_opened');
    }
  }

  function facilityPopupDecision(ctx, overrides) {
    var data = overrides || {};
    var pageType = String(data.pageType || ctx.pageType || '').toLowerCase();
    var ccn = String(data.ccn || ctx.ccn || '').trim();
    var elapsedMs = data.elapsedMs == null ? Date.now() - pageStartedAt : Number(data.elapsedMs);
    var minimumMs = Number(config.minFacilityPageSeconds == null ? 20 : config.minFacilityPageSeconds) * 1000;
    var distinctViews = Number(data.distinctFacilityViews == null ? state.facilityCcnsViewed.length : data.distinctFacilityViews);
    var sessionCount = Number(data.sessionCount == null ? state.sessionCount : data.sessionCount);
    var triggerReason = distinctViews >= Number(config.minFacilityPagesForHeavy || 3)
      ? 'distinct_facility_pages_3plus'
      : (sessionCount > 1 ? 'repeat_session' : '');

    if (pageType !== 'provider' && pageType !== 'facility') return { eligible: false, reason: 'not_facility_page' };
    if (Number(data.pageviewCount == null ? state.pageviewCount : data.pageviewCount) <= 1) return { eligible: false, reason: 'first_pageview' };
    if (elapsedMs < minimumMs) return { eligible: false, reason: 'before_minimum_time' };
    if (data.alreadyFollowing == null ? isCurrentFacilityFollowed(ccn) : data.alreadyFollowing) return { eligible: false, reason: 'already_following' };
    if (data.promptShown == null
      ? (promptsShownThisSession || sessionGet(SESSION_PROMPT_SHOWN_KEY) === '1')
      : data.promptShown) return { eligible: false, reason: 'prompt_already_shown' };
    if (data.manualModalOpened == null
      ? sessionGet(SESSION_MODAL_OPENED_KEY) === '1'
      : data.manualModalOpened) return { eligible: false, reason: 'manual_modal_opened' };
    if (data.inlineInteracted == null
      ? hasInlineFacilityInteraction(ccn)
      : data.inlineInteracted) return { eligible: false, reason: 'inline_cta_interacted' };
    if (data.inlineVisible == null ? inlineFacilityVisible : data.inlineVisible) return { eligible: false, reason: 'inline_cta_visible' };
    if (!triggerReason) return { eligible: false, reason: 'not_heavy_user' };
    return { eligible: true, reason: triggerReason, triggerReason: triggerReason };
  }

  function currentFacilityTriggerReason() {
    if (state.facilityCcnsViewed.length >= Number(config.minFacilityPagesForHeavy || 3)) {
      return 'distinct_facility_pages_3plus';
    }
    return state.sessionCount > 1 ? 'repeat_session' : 'not_heavy_user';
  }

  function popupMetadata(ctx, triggerReason) {
    return {
      page_type: ctx.pageType,
      resource_id: ctx.ccn,
      facility_ccn: ctx.ccn,
      facility_view_count: state.facilityCcnsViewed.length,
      session_count: state.sessionCount,
      trigger_reason: triggerReason || currentFacilityTriggerReason()
    };
  }

  function trackFacilityPopupEvent(eventName, ctx, triggerReason, detail) {
    var metadata = popupMetadata(ctx, triggerReason);
    if (eventName === 'popup_suppressed') metadata.suppression_reason = detail || 'unknown';
    if (eventName === 'popup_error') metadata.error_reason = detail || 'unknown';
    sendEngagementEvent(eventName, metadata);
  }

  function logPopupSuppression(ctx, reason) {
    if (!config.engagementPromptsEnabled || !reason || reason === 'before_minimum_time') return;
    var key = String(ctx.ccn || '') + ':' + reason;
    if (popupSuppressionLogged[key]) return;
    popupSuppressionLogged[key] = true;
    trackFacilityPopupEvent('popup_suppressed', ctx, '', reason);
  }

  function importantControlOverlaps(panel) {
    var panelRect = panel.getBoundingClientRect();
    var selectors = [
      '.navbar', 'canvas', '.chart-container', '[data-chart]',
      '[class*="filter"]', '[href*="/premium"]', '.premium-cta'
    ];
    var nodes = document.querySelectorAll(selectors.join(','));
    for (var i = 0; i < nodes.length; i += 1) {
      if (panel.contains(nodes[i])) continue;
      var rect = nodes[i].getBoundingClientRect();
      var visible = rect.width > 0 && rect.height > 0 && rect.bottom > 0 &&
        rect.right > 0 && rect.top < global.innerHeight && rect.left < global.innerWidth;
      var overlaps = visible && rect.left < panelRect.right && rect.right > panelRect.left &&
        rect.top < panelRect.bottom && rect.bottom > panelRect.top;
      if (overlaps) return true;
    }
    return false;
  }

  function attemptFacilityPopup() {
    if (!config.engagementPromptsEnabled) return;
    var ctx = buildContext();
    var decision = facilityPopupDecision(ctx);
    if (!decision.eligible) {
      logPopupSuppression(ctx, decision.reason);
      return;
    }
    fetch('/api/audience/prompt-suppressed?visitorKey=' + encodeURIComponent(state.visitorKey) +
      '&promptType=' + encodeURIComponent(FACILITY_POPUP_PROMPT_TYPE))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.suppressed) {
          logPopupSuppression(ctx, 'dismissed_30_days');
          return;
        }
        if (!popupEligibleLogged) {
          popupEligibleLogged = true;
          trackFacilityPopupEvent('popup_eligible', ctx, decision.triggerReason);
        }
        showFacilityPopup(ctx, decision.triggerReason);
      })
      .catch(function () {
        logPopupSuppression(ctx, 'suppression_check_error');
      });
  }

  function showFacilityPopup(ctx, triggerReason) {
    if (document.getElementById('pbj-audience-facility-popup')) return;
    var sheet = document.createElement('aside');
    sheet.className = 'pbj-audience-sheet pbj-audience-sheet--facility';
    sheet.id = 'pbj-audience-facility-popup';
    sheet.setAttribute('role', 'dialog');
    sheet.setAttribute('aria-label', 'Follow this facility');
    sheet.setAttribute('aria-hidden', 'true');
    sheet.innerHTML = '<div class="pbj-audience-sheet__panel">' +
      '<button type="button" class="pbj-audience-sheet__close" aria-label="Close">&times;</button>' +
      '<div id="pbj-facility-popup-mount"></div></div>';
    document.body.appendChild(sheet);

    var completed = false;
    var mount = sheet.querySelector('#pbj-facility-popup-mount');
    mountSignup(mount, {
      variant: 'facility_follow',
      force: true,
      isModal: true,
      popup: true,
      inputIdSuffix: 'facility_popup',
      inlineLabel: 'Follow this facility',
      placeholder: 'Email address',
      submitLabel: 'Follow',
      successMessage: 'You\u2019re following this facility.',
      suppressAdjacentOffer: true,
      triggerReason: triggerReason,
      contextExtra: ctx,
      onSuccess: function () { completed = true; }
    });

    var panel = sheet.querySelector('.pbj-audience-sheet__panel');
    sheet.classList.add('pbj-audience-sheet--measuring');
    if (importantControlOverlaps(panel)) {
      sheet.remove();
      logPopupSuppression(ctx, 'key_control_overlap');
      schedulePopupRetry();
      return;
    }
    sheet.classList.remove('pbj-audience-sheet--measuring');

    promptsShownThisSession = true;
    sessionSet(SESSION_PROMPT_SHOWN_KEY, '1');
    lastFocusedBeforeModal = document.activeElement;
    trackFacilityPopupEvent('popup_shown', ctx, triggerReason);

    function syncWithKeyboard() {
      if (!global.visualViewport || global.innerWidth >= 640) {
        sheet.style.bottom = '';
        return;
      }
      var keyboardInset = Math.max(
        0,
        global.innerHeight - global.visualViewport.height - global.visualViewport.offsetTop
      );
      sheet.style.bottom = keyboardInset + 'px';
    }

    function closeSheet() {
      if (!sheet.isConnected) return;
      sheet.setAttribute('aria-hidden', 'true');
      if (global.visualViewport) global.visualViewport.removeEventListener('resize', syncWithKeyboard);
      if (!completed) {
        trackFacilityPopupEvent('popup_dismissed', ctx, triggerReason);
        fetch('/api/audience/prompt-dismiss', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ visitorKey: state.visitorKey, promptType: FACILITY_POPUP_PROMPT_TYPE })
        }).catch(function () {});
      }
      global.setTimeout(function () {
        sheet.remove();
        if (lastFocusedBeforeModal && lastFocusedBeforeModal.focus) lastFocusedBeforeModal.focus();
      }, 220);
    }

    sheet.querySelector('.pbj-audience-sheet__close').addEventListener('click', closeSheet);
    if (global.visualViewport) {
      global.visualViewport.addEventListener('resize', syncWithKeyboard);
      syncWithKeyboard();
    }
    document.addEventListener('keydown', function escHandler(e) {
      if (e.key === 'Escape') {
        closeSheet();
        document.removeEventListener('keydown', escHandler);
      }
    });
    requestAnimationFrame(function () { sheet.setAttribute('aria-hidden', 'false'); });
  }

  function schedulePopupRetry() {
    if (popupRetryBound) return;
    popupRetryBound = true;
    var retry = function () {
      popupRetryBound = false;
      global.removeEventListener('scroll', retry);
      global.removeEventListener('resize', retry);
      global.setTimeout(attemptFacilityPopup, 200);
    };
    global.addEventListener('scroll', retry, { passive: true });
    global.addEventListener('resize', retry);
  }

  function recordPageview() {
    if (!sessionStorage.getItem('pbj_audience_session')) {
      sessionStorage.setItem('pbj_audience_session', '1');
      state.sessionCount = (state.sessionCount || 0) + 1;
    }
    state.pageviewCount = (state.pageviewCount || 0) + 1;
    var ctx = parseRouteContext();
    if (ctx.kind === 'provider' && ctx.ccn) {
      var ccn = String(ctx.ccn);
      if (state.facilityCcnsViewed.indexOf(ccn) < 0) state.facilityCcnsViewed.push(ccn);
      state.facilityPageViews = state.facilityCcnsViewed.length;
    }
    if (ctx.stateAbbr) { state.recentStateAbbr = ctx.stateAbbr; state.recentStateName = ctx.stateName || ctx.stateAbbr; }
    saveState();
  }

  function init() {
    recordPageview();
    fetchConfig().then(function () {
      autoMount();
      if (config.engagementPromptsEnabled) {
        var waitMs = Math.max(0, Number(config.minFacilityPageSeconds == null ? 20 : config.minFacilityPageSeconds) * 1000);
        setTimeout(attemptFacilityPopup, waitMs);
      }
    });
    fetchCsrf();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();

  global.PBJAudience = {
    mountSignup: mountSignup,
    mountModalContent: mountModalContent,
    mountEmailUpdatesModal: mountEmailUpdatesModal,
    resolveCta: resolveCta,
    buildContext: buildContext,
    trackEvent: trackEvent,
    fetchCsrf: fetchCsrf,
    isValidEmail: isValidEmail,
    facilityPopupDecision: facilityPopupDecision,
    attemptFacilityPopup: attemptFacilityPopup,
    markManualEmailUpdatesModalOpened: markManualEmailUpdatesModalOpened,
    getState: function () { return state; },
    SUBSTACK_URL: SUBSTACK_URL,
    successMessageForSpec: successMessageForSpec,
    adjacentOffer: adjacentOffer,
    inlineLabelForSpec: inlineLabelForSpec,
    submitFeedback: function (payload) {
      return fetch('/api/audience/feedback', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload || {})
      }).then(function (r) { return r.json(); }).then(function (res) {
        if (res && res.ok) trackEvent('feedback_submitted', { page_type: parseRouteContext().kind });
        return res;
      });
    }
  };
})(typeof window !== 'undefined' ? window : this);
