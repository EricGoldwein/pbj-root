/**
 * PBJ320 contact form: Turnstile token refresh + duplicate-submit guard.
 * Expects Cloudflare Turnstile api.js and widgets with data-action="pbj_request".
 */
(function () {
  'use strict';

  function forms() {
    return document.querySelectorAll(
      'form#contact-form, form#pbj-contact-popup-form, form#contact-popup-form, form#contact-popup-form-static, form.press-contact-form'
    );
  }

  function disableSubmit(form, disabled) {
    var btn = form.querySelector('button[type="submit"], input[type="submit"]');
    if (!btn) return;
    btn.disabled = !!disabled;
    if (disabled) btn.setAttribute('aria-busy', 'true');
    else btn.removeAttribute('aria-busy');
  }

  function resetTurnstile(form) {
    if (!window.turnstile || typeof window.turnstile.reset !== 'function') return;
    var widget = form.querySelector('.cf-turnstile');
    if (!widget) return;
    try {
      window.turnstile.reset(widget);
    } catch (e) {
      try {
        window.turnstile.reset();
      } catch (e2) {}
    }
  }

  function bindForm(form) {
    if (!form || form.getAttribute('data-pbj-protect') === '1') return;
    form.setAttribute('data-pbj-protect', '1');
    form.addEventListener('submit', function (e) {
      if (form.getAttribute('data-pbj-submitting') === '1') {
        e.preventDefault();
        return;
      }
      form.setAttribute('data-pbj-submitting', '1');
      disableSubmit(form, true);
      // Allow classic POST navigation; if page stays (error redirect back), re-enable on pageshow.
    });
  }

  function init() {
    forms().forEach(bindForm);
    window.addEventListener('pageshow', function () {
      forms().forEach(function (form) {
        form.removeAttribute('data-pbj-submitting');
        disableSubmit(form, false);
        resetTurnstile(form);
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
