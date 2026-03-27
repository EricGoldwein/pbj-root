/**
 * Single source of truth for PBJ320 site: contact number, footer, nav, and contact CTA fallback.
 * Contact CTAs use semantic <a href="mailto:"> with a copy-email fallback when no mail handler exists.
 * Include this script on static HTML pages and use #site-footer / #site-nav placeholders.
 * React app uses SiteNavbar.tsx and SiteFooter.tsx instead.
 */
(function () {
  'use strict';
  var CONTACT = {
    phoneDisplay: '(929) 804-4996',
    smsHref: 'sms:+19298084996',
    email: 'eric@320insight.com'
  };

  var FOOTER_BOILERPLATE = '<p class="footer-boilerplate" style="margin:0 0 1rem 0;font-size:0.8rem;line-height:1.5;text-align:center;color:rgba(255,255,255,0.8);max-width:720px;margin-left:auto;margin-right:auto"><strong>320 Consulting</strong> maintains the PBJ Dashboard, a free public resource tracking federal staffing data across ~15,000 U.S. nursing homes. As seen in Columbia Public Health, Positive Aging, Aging in America News, and WTVR CBS.</p>';

  var FOOTER_TAGLINE = [
    '<p class="footer-tagline" style="margin:0 0 1rem 0;font-size:0.8rem;text-align:center;letter-spacing:0.03em"><a href="https://www.320insight.com/" target="_blank" rel="noopener noreferrer" style="color:inherit;text-decoration:none;font-weight:700">320 Consulting</a>: Turning Spreadsheets into Stories.</p>',
    '<div style="display:flex;justify-content:center;align-items:center;gap:20px;margin-top:0.5rem">',
    '<a href="mailto:' + CONTACT.email + '" class="pbj-contact-cta" style="display:inline-block;transition:opacity 0.3s ease" title="Email: ' + CONTACT.email + '" aria-label="Email ' + CONTACT.email + '"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" style="opacity:0.7" aria-hidden="true"><path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z" fill="#60a5fa"/></svg></a>',
    '<a href="' + CONTACT.smsHref + '" style="display:inline-block;transition:opacity 0.3s ease" title="SMS: ' + CONTACT.phoneDisplay + '" aria-label="Text ' + CONTACT.phoneDisplay + '"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" style="opacity:0.7" aria-hidden="true"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z" fill="#60a5fa"/></svg></a>',
    '<a href="https://www.linkedin.com/in/eric-goldwein/" target="_blank" rel="noopener noreferrer" style="display:inline-block;transition:opacity 0.3s ease" title="LinkedIn" aria-label="LinkedIn"><img src="/LI-In-Bug.png" alt="" style="width:24px;height:24px;object-fit:contain;opacity:0.7"/></a>',
    '<a href="https://320insight.substack.com/" target="_blank" rel="noopener noreferrer" style="display:inline-block;transition:opacity 0.3s ease" title="The 320 Newsletter" aria-label="The 320 Newsletter"><img src="/substack.png" alt="" style="width:24px;height:24px;object-fit:contain;opacity:0.7"/></a>',
    '</div>'
  ].join('');

  function injectFooter(el) {
    if (!el) return;
    var path = typeof location !== 'undefined' && location.pathname ? location.pathname.replace(/\/$/, '') : '';
    var isIndex = path === '' || path === '/';
    el.innerHTML = isIndex ? FOOTER_BOILERPLATE + FOOTER_TAGLINE : FOOTER_TAGLINE;
  }

  /** Copy email to clipboard and show a short confirmation. Accessible and works when mailto fails. */
  function copyEmailAndNotify(email, triggerEl) {
    var text = email || CONTACT.email;
    if (typeof navigator !== 'undefined' && navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function() { showCopyToast(triggerEl); }).catch(function() { fallbackCopy(text, triggerEl); });
    } else {
      fallbackCopy(text, triggerEl);
    }
  }

  function fallbackCopy(text, triggerEl) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'absolute';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand('copy');
      showCopyToast(triggerEl);
    } catch (err) { /* ignore */ }
    document.body.removeChild(ta);
  }

  function showCopyToast(nearEl) {
    var existing = document.getElementById('pbj-copy-toast');
    if (existing) existing.remove();
    var toast = document.createElement('div');
    toast.id = 'pbj-copy-toast';
    toast.setAttribute('role', 'status');
    toast.setAttribute('aria-live', 'polite');
    toast.textContent = 'Email copied.';
    toast.style.cssText = 'position:fixed;bottom:1.25rem;left:50%;transform:translateX(-50%);background:rgba(15,23,42,0.95);color:#93c5fd;padding:0.5rem 1rem;border-radius:8px;font-size:0.875rem;z-index:10000;box-shadow:0 4px 12px rgba(0,0,0,0.3);border:1px solid rgba(96,165,250,0.3);';
    document.body.appendChild(toast);
    setTimeout(function() { toast.remove(); }, 2500);
    if (nearEl && nearEl.focus) nearEl.focus();
  }

  /** Inject lightweight contact modal (email + copy button). Do not rely solely on mailto. */
  function ensureContactModal() {
    if (document.getElementById('pbj-contact-modal')) return;
    var backdrop = document.createElement('div');
    backdrop.id = 'pbj-contact-modal-backdrop';
    backdrop.setAttribute('aria-hidden', 'true');
    backdrop.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:9998;display:none;';
    var modal = document.createElement('div');
    modal.id = 'pbj-contact-modal';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-labelledby', 'pbj-contact-modal-title');
    modal.setAttribute('aria-modal', 'true');
    modal.style.cssText = 'position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);background:#1e293b;color:#e2e8f0;padding:1.5rem;border-radius:12px;border:1px solid rgba(96,165,250,0.3);z-index:9999;min-width:280px;max-width:90vw;box-shadow:0 8px 32px rgba(0,0,0,0.4);';
    modal.innerHTML = '<h2 id="pbj-contact-modal-title" style="margin:0 0 1rem 0;font-size:1.1rem;">Contact</h2>' +
      '<p style="margin:0 0 0.75rem 0;font-size:0.9rem;">' + CONTACT.email + '</p>' +
      '<div style="display:flex;gap:0.75rem;flex-wrap:wrap;">' +
      '<button type="button" id="pbj-contact-modal-copy" class="pbj-copy-email" data-email="' + CONTACT.email + '" style="padding:0.4rem 0.75rem;background:rgba(96,165,250,0.2);color:#93c5fd;border:1px solid rgba(96,165,250,0.4);border-radius:6px;cursor:pointer;font-size:0.875rem;">Copy email</button>' +
      '<a href="mailto:' + CONTACT.email + '" class="pbj-contact-cta" style="padding:0.4rem 0.75rem;background:rgba(96,165,250,0.2);color:#93c5fd;border:1px solid rgba(96,165,250,0.4);border-radius:6px;text-decoration:none;font-size:0.875rem;">Open mail app</a>' +
      '<button type="button" id="pbj-contact-modal-close" style="padding:0.4rem 0.75rem;background:transparent;color:rgba(226,232,240,0.8);border:1px solid rgba(148,163,184,0.3);border-radius:6px;cursor:pointer;font-size:0.875rem;">Close</button>' +
      '</div>';
    backdrop.appendChild(modal);
    document.body.appendChild(backdrop);
    document.getElementById('pbj-contact-modal-close').addEventListener('click', closeContactModal);
    document.getElementById('pbj-contact-modal-copy').addEventListener('click', function() { copyEmailAndNotify(CONTACT.email, this); });
    backdrop.addEventListener('click', function(e) { if (e.target === backdrop) closeContactModal(); });
    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape' && document.getElementById('pbj-contact-modal-backdrop').style.display === 'block') closeContactModal();
    });
  }

  var _contactModalPreviousFocus = null;

  function openContactModal() {
    ensureContactModal();
    _contactModalPreviousFocus = document.activeElement;
    var backdrop = document.getElementById('pbj-contact-modal-backdrop');
    var modal = document.getElementById('pbj-contact-modal');
    backdrop.style.display = 'block';
    backdrop.setAttribute('aria-hidden', 'false');
    var focusable = modal.querySelector('button, [href]');
    if (focusable) focusable.focus();
  }

  function closeContactModal() {
    var backdrop = document.getElementById('pbj-contact-modal-backdrop');
    if (!backdrop) return;
    backdrop.style.display = 'none';
    backdrop.setAttribute('aria-hidden', 'true');
    if (_contactModalPreviousFocus && typeof _contactModalPreviousFocus.focus === 'function') {
      _contactModalPreviousFocus.focus();
    }
    _contactModalPreviousFocus = null;
  }

  /** Bind copy-email buttons and contact modal triggers. */
  function bindContactFallbacks() {
    ensureContactModal();
    var copyButtons = document.querySelectorAll('.pbj-copy-email, [data-pbj-copy-email]');
    for (var i = 0; i < copyButtons.length; i++) {
      (function(btn) {
        if (btn._pbjCopyBound) return;
        btn._pbjCopyBound = true;
        var email = btn.getAttribute('data-email') || btn.getAttribute('data-pbj-copy-email') || CONTACT.email;
        if (!btn.getAttribute('aria-label')) btn.setAttribute('aria-label', 'Copy email address');
        btn.addEventListener('click', function(e) { e.preventDefault(); copyEmailAndNotify(email, btn); });
      })(copyButtons[i]);
    }
    var triggers = document.querySelectorAll('.pbj-contact-modal-trigger, [data-pbj-contact-modal]');
    for (var j = 0; j < triggers.length; j++) {
      (function(trig) {
        if (trig._pbjModalBound) return;
        trig._pbjModalBound = true;
        trig.addEventListener('click', function(e) { e.preventDefault(); openContactModal(); });
      })(triggers[j]);
    }
  }

  function injectContactCtaStyles() {
    if (document.getElementById('pbj-contact-cta-styles')) return;
    var style = document.createElement('style');
    style.id = 'pbj-contact-cta-styles';
    style.textContent = '.pbj-copy-email{background:none;border:none;padding:0;font:inherit;cursor:pointer;text-decoration:underline;-webkit-appearance:none;appearance:none;}.pbj-copy-email:hover{opacity:0.9;}.pbj-copy-email:focus-visible{outline:2px solid #60a5fa;outline-offset:2px;}#pbj-contact-modal button:focus-visible,#pbj-contact-modal a:focus-visible{outline:2px solid #60a5fa;outline-offset:2px;}';
    document.head.appendChild(style);
  }

  /**
   * Enforce a consistent site shell across static pages:
   * - stable scrollbar gutter (prevents width jump between pages)
   * - unified navbar container width and spacing
   */
  function injectSiteShellStyles() {
    if (document.getElementById('pbj-site-shell-styles')) return;
    var style = document.createElement('style');
    style.id = 'pbj-site-shell-styles';
    style.textContent = [
      'html{overflow-y:scroll;scrollbar-gutter:stable;}',
      '.navbar .nav-container{max-width:1200px !important;margin:0 auto !important;padding:0 20px !important;height:60px !important;}',
      '.navbar .nav-brand,.navbar .nav-link{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif !important;}',
      '.navbar .nav-menu{gap:30px !important;align-items:center !important;}',
      '.navbar .nav-link{padding:8px 0 !important;font-size:16px !important;line-height:1.25 !important;font-weight:500 !important;}',
      '@media (max-width:768px){',
      '  .navbar .nav-menu{height:calc(100vh - 60px) !important;top:60px !important;left:-100% !important;padding:0 !important;gap:0 !important;justify-content:flex-start !important;align-items:stretch !important;border-top:1px solid rgba(255,255,255,0.1) !important;}',
      '  .navbar .nav-menu.active{left:0 !important;}',
      '  .navbar .nav-link{padding:18px 24px !important;border-bottom:1px solid rgba(255,255,255,0.1) !important;text-align:left !important;font-size:1rem !important;color:rgba(255,255,255,0.9) !important;background:transparent !important;transition:all 0.2s ease !important;}',
      '  .navbar .nav-link:hover,.navbar .nav-link.active{background:rgba(96,165,250,0.1) !important;color:#60a5fa !important;border-left:3px solid #60a5fa !important;}',
      '}'
    ].join('');
    document.head.appendChild(style);
  }

  function run() {
    var footer = document.getElementById('site-footer');
    if (footer) injectFooter(footer);
    injectSiteShellStyles();
    injectContactCtaStyles();
    bindContactFallbacks();
  }

  if (typeof window !== 'undefined') {
    window.PBJ320_CONTACT = CONTACT;
    window.PBJ320_openContactModal = openContactModal;
    window.PBJ320_copyEmail = copyEmailAndNotify;
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', run);
    } else {
      run();
    }
  }
})();
