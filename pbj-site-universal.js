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

  var FOOTER_TRUST_BLURB =
    'PBJ320 is a nursing home data platform from 320 Consulting LLC, built from CMS Payroll-Based Journal' +
    '<br class="footer-boilerplate-br-desktop" aria-hidden="true"> ' +
    'and other public federal and state datasets.';

  var FOOTER_LINK_STYLE = 'color:rgba(148,163,184,0.95)';

  var FOOTER_BOILERPLATE =
    '<p class="footer-boilerplate" style="margin:0 0 0.65rem 0;font-size:0.75rem;line-height:1.5;text-align:center;color:rgba(148,163,184,0.82);max-width:52rem;margin-left:auto;margin-right:auto">' +
    FOOTER_TRUST_BLURB +
    '</p>';

  var FOOTER_ICON_IMG_STYLE = 'display:block;width:24px;height:24px;object-fit:contain';
  var FOOTER_LINKEDIN_IMG_STYLE = 'display:block;height:20px;width:auto;object-fit:contain';
  var FOOTER_ICON_LINK_STYLE = 'display:inline-flex;align-items:center;justify-content:center';

  var FOOTER_NAV_LINKS =
    '<p class="footer-trust-links footer-nav-links" style="margin:0 0 0.35rem 0;font-size:0.75rem;text-align:center;color:rgba(148,163,184,0.95)">' +
    '<a href="/about" style="' + FOOTER_LINK_STYLE + '">About</a> · ' +
    '<a href="/premium" style="' + FOOTER_LINK_STYLE + '">Premium</a> · ' +
    '<a href="/press" style="' + FOOTER_LINK_STYLE + '">Press</a> · ' +
    '<a href="/contact" style="' + FOOTER_LINK_STYLE + '">Contact</a> · ' +
    '<a href="/data-sources" style="' + FOOTER_LINK_STYLE + '">Sources</a>' +
    '</p>';

  var FOOTER_CORE = [
    '<div style="display:flex;justify-content:center;align-items:center;gap:20px;margin-top:0.5rem">',
    '<a href="mailto:' + CONTACT.email + '" class="pbj-contact-cta pbj-footer-icon-link" style="' + FOOTER_ICON_LINK_STYLE + '" title="Email: ' + CONTACT.email + '" aria-label="Email ' + CONTACT.email + '"><svg class="pbj-footer-svg" width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z" fill="#60a5fa"/></svg></a>',
    '<a href="' + CONTACT.smsHref + '" class="pbj-footer-icon-link" style="' + FOOTER_ICON_LINK_STYLE + '" title="SMS: ' + CONTACT.phoneDisplay + '" aria-label="Text ' + CONTACT.phoneDisplay + '"><svg class="pbj-footer-svg" width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z" fill="#60a5fa"/></svg></a>',
    '<a href="https://www.linkedin.com/in/eric-goldwein/" target="_blank" rel="noopener noreferrer" class="pbj-footer-icon-link" style="' + FOOTER_ICON_LINK_STYLE + '" title="LinkedIn" aria-label="LinkedIn"><img src="/static/img/linkedin-in-logo.png" alt="" width="24" height="20" decoding="async" class="pbj-footer-icon pbj-footer-icon--linkedin" style="' + FOOTER_LINKEDIN_IMG_STYLE + '" /></a>',
    '<a href="https://320insight.substack.com/" target="_blank" rel="noopener noreferrer" class="pbj-footer-icon-link" style="' + FOOTER_ICON_LINK_STYLE + '" title="The 320 Newsletter" aria-label="The 320 Newsletter"><img src="/substack.png" alt="" width="24" height="24" decoding="async" class="pbj-footer-icon" style="' + FOOTER_ICON_IMG_STYLE + '" /></a>',
    '</div>',
  ].join('');

  function footerSignoffHtml() {
    var y = new Date().getFullYear();
    var legalStyle = 'color:rgba(203,213,225,0.78);text-decoration:none;';
    return (
      '<p class="footer-signoff">\u00a9 ' + y + ', ' +
      '<a href="https://www.320insight.com/" target="_blank" rel="noopener noreferrer" class="footer-signoff-brand">320 Consulting</a> · ' +
      '<a href="/terms" class="footer-signoff-link" style="' + legalStyle + '">Terms</a> · ' +
      '<a href="/privacy" class="footer-signoff-link" style="' + legalStyle + '">Privacy</a></p>'
    );
  }

  /** Remove legacy per-page PBJ quarter line (pre-v27 footer). */
  function purgeLegacyFooterMarkup(root) {
    var scope = root || document;
    var selectors = ['#pbj-footer-sources-line', '.pbj-footer-sources-line'];
    for (var i = 0; i < selectors.length; i++) {
      var nodes = scope.querySelectorAll(selectors[i]);
      for (var j = 0; j < nodes.length; j++) nodes[j].remove();
    }
    var legacyDlg = document.getElementById('pbj-sources-general');
    if (legacyDlg) legacyDlg.remove();
  }

  function injectFooter(el) {
    if (!el) return;
    purgeLegacyFooterMarkup(el);
    var body = FOOTER_CORE + footerSignoffHtml();
    el.innerHTML = FOOTER_BOILERPLATE + FOOTER_NAV_LINKS + body;
    el.setAttribute('data-pbj-footer', 'universal');
  }

  function bindSourcesDialogs() {
    document.addEventListener('click', function (e) {
      var btn = e.target && e.target.closest ? e.target.closest('[data-pbj-sources-open]') : null;
      if (!btn) return;
      e.preventDefault();
      var id = btn.getAttribute('data-pbj-sources-open');
      if (!id) return;
      var dlg = document.getElementById(id);
      if (dlg && typeof dlg.showModal === 'function') dlg.showModal();
    });
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
    toast.style.cssText = 'position:fixed;bottom:1.25rem;left:50%;transform:translateX(-50%);background:rgba(15,23,42,0.95);color:#a5b4fc;padding:0.5rem 1rem;border-radius:8px;font-size:0.875rem;z-index:10000;box-shadow:0 4px 12px rgba(0,0,0,0.3);border:1px solid rgba(129,140,248,0.3);';
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
      '<button type="button" id="pbj-contact-modal-copy" class="pbj-copy-email" data-email="' + CONTACT.email + '" style="padding:0.4rem 0.75rem;background:rgba(129,140,248,0.2);color:#a5b4fc;border:1px solid rgba(129,140,248,0.4);border-radius:6px;cursor:pointer;font-size:0.875rem;">Copy email</button>' +
      '<a href="mailto:' + CONTACT.email + '" class="pbj-contact-cta" style="padding:0.4rem 0.75rem;background:rgba(129,140,248,0.2);color:#a5b4fc;border:1px solid rgba(129,140,248,0.4);border-radius:6px;text-decoration:none;font-size:0.875rem;">Open mail app</a>' +
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
    style.textContent = '.pbj-copy-email{background:none;border:none;padding:0;font:inherit;cursor:pointer;text-decoration:underline;-webkit-appearance:none;appearance:none;}.pbj-copy-email:hover{opacity:0.9;}.pbj-copy-email:focus-visible{outline:2px solid #818cf8;outline-offset:2px;}#pbj-contact-modal button:focus-visible,#pbj-contact-modal a:focus-visible{outline:2px solid #818cf8;outline-offset:2px;}';
    document.head.appendChild(style);
  }

  /** Footer signoff + trust link polish */
  function injectFooterStyles() {
    if (document.getElementById('pbj-footer-styles')) return;
    var style = document.createElement('style');
    style.id = 'pbj-footer-styles';
    style.textContent = [
      '.footer .pbj-footer-icon{display:block;object-fit:contain;}',
      '.footer .pbj-footer-icon:not(.pbj-footer-icon--linkedin){width:24px;height:24px;}',
      '.footer .pbj-footer-icon--linkedin{height:20px;width:auto;max-height:20px;}',
      '.footer .pbj-footer-svg{display:block;width:24px;height:24px;flex-shrink:0;}',
      '.footer a.pbj-footer-icon-link,.footer a.pbj-contact-cta.pbj-footer-icon-link{opacity:.7;transition:opacity .3s ease;}',
      '.footer a.pbj-footer-icon-link:hover,.footer a.pbj-footer-icon-link:focus-visible,.footer a.pbj-contact-cta.pbj-footer-icon-link:hover,.footer a.pbj-contact-cta.pbj-footer-icon-link:focus-visible{opacity:1;}',
      '.footer .footer-trust-links a{text-decoration:none;transition:color .15s ease;}',
      '.footer .footer-trust-links a:hover,.footer .footer-trust-links a:focus-visible{color:#cbd5e1 !important;text-decoration:underline;text-underline-offset:2px;}',
      '.footer .footer-trust-links a:focus-visible{outline:2px solid #818cf8;outline-offset:3px;border-radius:2px;}',
      '.footer .footer-signoff{margin:12px auto 0;padding:0 10px;max-width:36rem;width:100%;box-sizing:border-box;font-size:0.68rem;line-height:1.45;text-align:center;letter-spacing:0.04em;color:rgba(203,213,225,0.82);}',
      '.footer .footer-signoff .footer-signoff-brand{color:rgba(226,232,240,0.92);font-weight:600;text-decoration:none;}',
      '.footer .footer-signoff .footer-signoff-brand:hover,.footer .footer-signoff .footer-signoff-brand:focus-visible{color:#cbd5e1;text-decoration:underline;text-underline-offset:2px;}',
      '.footer .footer-signoff .footer-signoff-brand:focus-visible{outline:2px solid #818cf8;outline-offset:2px;border-radius:2px;}',
      '.footer .footer-signoff .footer-signoff-link{color:rgba(203,213,225,0.78);text-decoration:none;}',
      '.footer .footer-signoff .footer-signoff-link:hover,.footer .footer-signoff .footer-signoff-link:focus-visible{color:rgba(203,213,225,0.95) !important;text-decoration:underline;text-underline-offset:2px;}',
      '.footer .footer-signoff .footer-signoff-link:focus-visible{outline:2px solid #818cf8;outline-offset:2px;border-radius:2px;}',
      'abbr.pbj-na{cursor:help;text-decoration:underline;text-decoration-style:dotted;text-underline-offset:2px;border:none;}',
      '.pbj-sources-about-btn{font:inherit;font-size:inherit;font-weight:600;color:rgba(148,163,184,0.95);background:none;border:none;padding:0;cursor:pointer;text-decoration:underline;text-underline-offset:3px;}',
      '.pbj-sources-about-btn:hover{color:#cbd5e1;}',
      '.pbj-sources-dialog{border:none;padding:0;margin:auto;background:transparent;max-width:min(34rem,92vw);color:#e2e8f0;}',
      '.pbj-sources-dialog::backdrop{background:rgba(0,0,0,0.55);}',
      '.pbj-sources-dialog__panel{background:#1e293b;border:1px solid rgba(129,140,248,0.35);border-radius:12px;padding:1.1rem 1.25rem 1rem;box-shadow:0 12px 40px rgba(0,0,0,0.45);}',
      '.pbj-sources-dialog__title{margin:0 0 0.65rem;font-size:1rem;font-weight:700;color:#c7d2fe;}',
      '.pbj-sources-dialog__list{margin:0 0 0.75rem 1.1rem;padding:0;font-size:0.8rem;line-height:1.5;color:rgba(226,232,240,0.88);}',
      '.pbj-sources-dialog__list li{margin-bottom:0.45rem;}',
      '.pbj-sources-dialog__list a{color:#818cf8;}',
      '.pbj-sources-dialog__more{margin:0 0 0.85rem;font-size:0.78rem;color:rgba(148,163,184,0.85);}',
      '.pbj-sources-dialog__close{font:inherit;font-size:0.8rem;font-weight:600;padding:0.4rem 0.9rem;border-radius:6px;border:1px solid rgba(129,140,248,0.45);background:rgba(67,56,202,0.35);color:#e0e7ff;cursor:pointer;}',
      '.pbj-sources-about-btn:focus-visible,.pbj-sources-dialog__close:focus-visible{outline:2px solid #818cf8;outline-offset:2px;}'
    ].join('');
    document.head.appendChild(style);
  }

  /** Highlight nav link for current route (desktop + mobile). */
  function markActiveNavLink() {
    var path = (typeof location !== 'undefined' && location.pathname)
      ? location.pathname.replace(/\/$/, '') || '/'
      : '/';
    var links = document.querySelectorAll('.navbar .nav-link[href], .navbar .nav-links a[href]');
    for (var i = 0; i < links.length; i++) {
      var a = links[i];
      a.classList.remove('active');
      var href = a.getAttribute('href');
      if (!href || href.charAt(0) === '#') continue;
      var linkPath = href.replace(/\/$/, '') || '/';
      var match = path === linkPath;
      if (!match && linkPath === '/owner' && (path === '/owner' || path.indexOf('/owner/') === 0)) match = true;
      if (!match && linkPath === '/owners' && (path === '/owners' || path.indexOf('/owners/') === 0)) match = true;
      if (!match && linkPath === '/owners-test' && (path === '/owners-test' || path.indexOf('/owners-test/') === 0)) match = true;
      if (!match && linkPath === '/insights' && path.indexOf('/insights') === 0) match = true;
      if (!match && linkPath === '/insights/trends' && (path === '/insights/trends' || path.indexOf('/insights/trends/') === 0)) match = true;
      if (!match && linkPath === '/report' && path.indexOf('/report') === 0) match = true;
      if (!match && linkPath === '/phoebe' && path.indexOf('/phoebe') === 0) match = true;
      if (!match && linkPath === '/about' && path.indexOf('/about') === 0) match = true;
      if (!match && linkPath === '/premium' && path.indexOf('/premium') === 0) match = true;
      if (!match && linkPath === '/data-sources' && path.indexOf('/data-sources') === 0) match = true;
      if (match) a.classList.add('active');
    }
  }

  /** FEC political contributions tool — single nav item at /owner (not CMS /owners profiles). */
  function ownershipNavHref(a) {
    var h = (a.getAttribute('href') || '').replace(/\/$/, '') || '/';
    return h === '/owner' || h === '/owners';
  }

  /** Hide FEC /owner nav link (page stays live); ensure Premium is last. */
  function ensureSiteNavLinks() {
    var menu = document.querySelector('.navbar .nav-menu') || document.querySelector('.navbar .nav-links');
    if (!menu) return;
    var navAnchors = menu.querySelectorAll('a[href]');
    for (var i = 0; i < navAnchors.length; i++) {
      if (ownershipNavHref(navAnchors[i])) navAnchors[i].remove();
    }
    var premium = menu.querySelector('a[href="/premium"]');
    if (!premium) {
      premium = document.createElement('a');
      premium.href = '/premium';
      premium.className = menu.classList.contains('nav-links') ? '' : 'nav-link';
      premium.textContent = 'Premium';
      menu.appendChild(premium);
    } else {
      premium.classList.remove('nav-link--premium-mobile');
      if (!menu.classList.contains('nav-links')) {
        premium.className = 'nav-link' + (premium.classList.contains('active') ? ' active' : '');
      }
    }
    if (premium !== menu.lastElementChild) {
      menu.appendChild(premium);
    }
  }

  function preloadNavFavicon() {
    if (document.querySelector('link[data-pbj-nav-favicon-preload]')) return;
    var link = document.createElement('link');
    link.rel = 'preload';
    link.as = 'image';
    link.href = '/pbj_favicon.png';
    link.setAttribute('data-pbj-nav-favicon-preload', '');
    document.head.appendChild(link);
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
      '.navbar{background:rgba(10,15,26,0.92)!important;backdrop-filter:blur(12px)!important;-webkit-backdrop-filter:blur(12px)!important;box-shadow:inset 0 -1px 0 rgba(255,255,255,0.08)!important;border-bottom:1px solid rgba(148,163,184,0.28)!important;}',
      '.navbar .nav-container{max-width:1200px !important;margin:0 auto !important;padding:0 20px !important;height:60px !important;}',
      '.navbar .nav-brand,.navbar .nav-link{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif !important;}',
      '.navbar .nav-menu{gap:30px !important;align-items:center !important;}',
      '.navbar .nav-link{padding:8px 0 !important;font-size:16px !important;line-height:1.25 !important;font-weight:500 !important;color:rgba(255,255,255,0.88) !important;}',
      '.navbar .nav-link:hover{color:#93c5fd !important;}',
      '.navbar .nav-link.active{color:#60a5fa !important;font-weight:600 !important;}',
      '.navbar .nav-link.active:hover{color:#60a5fa !important;}',
      '.navbar .nav-links a{color:rgba(255,255,255,0.88) !important;font-weight:500 !important;text-decoration:none !important;}',
      '.navbar .nav-links a:hover{color:#93c5fd !important;}',
      '.navbar .nav-links a.active{color:#60a5fa !important;font-weight:600 !important;}',
      '.navbar .nav-links a.active:hover{color:#60a5fa !important;}',
      '.navbar .nav-brand a{display:flex !important;align-items:center !important;gap:0 !important;}',
      '.navbar .nav-brand img{width:32px !important;height:32px !important;min-width:32px !important;min-height:32px !important;margin-right:8px !important;object-fit:contain !important;flex-shrink:0 !important;display:block !important;vertical-align:middle !important;}',
      '.navbar .nav-brand span span:last-child{color:#818cf8 !important;}',
      '@media (max-width:768px){',
      '  .navbar .nav-menu{height:calc(100vh - 60px) !important;top:60px !important;left:-100% !important;padding:0 !important;gap:0 !important;justify-content:flex-start !important;align-items:stretch !important;border-top:1px solid rgba(71,85,105,0.45) !important;background:rgba(10,15,26,0.98) !important;backdrop-filter:blur(12px) !important;-webkit-backdrop-filter:blur(12px) !important;}',
      '  .navbar .nav-menu.active{left:0 !important;}',
      '  .navbar .nav-link{padding:18px 24px !important;border-bottom:1px solid rgba(30,41,59,0.55) !important;text-align:left !important;font-size:1rem !important;color:rgba(255,255,255,0.88) !important;background:transparent !important;transition:color 0.2s ease !important;}',
      '  .navbar .nav-link:hover{background:transparent !important;color:#93c5fd !important;}',
      '  .navbar .nav-link.active{color:#60a5fa !important;font-weight:600 !important;background:transparent !important;border-left:none !important;}',
      '  .navbar .nav-link.active:hover{color:#60a5fa !important;}',
      '}'
    ].join('');
    document.head.appendChild(style);
  }

  function run() {
    preloadNavFavicon();
    purgeLegacyFooterMarkup(document);
    var footer = document.getElementById('site-footer');
    injectFooterStyles();
    if (footer) injectFooter(footer);
    injectSiteShellStyles();
    ensureSiteNavLinks();
    markActiveNavLink();
    injectContactCtaStyles();
    bindContactFallbacks();
    bindSourcesDialogs();
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
