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
    '<p class="footer-trust-links footer-nav-links">' +
    '<a href="/about" style="' + FOOTER_LINK_STYLE + '">About</a> · ' +
    '<a href="/premium" style="' + FOOTER_LINK_STYLE + '">Premium</a> · ' +
    '<a href="/press" style="' + FOOTER_LINK_STYLE + '">Press</a> · ' +
    '<a href="/data-sources" style="' + FOOTER_LINK_STYLE + '">Sources</a> · ' +
    '<a href="#" data-pbj-corrections-open style="' + FOOTER_LINK_STYLE + '">Corrections</a> · ' +
    '<a href="#" data-pbj-subscribe-open style="' + FOOTER_LINK_STYLE + '">Subscribe</a>' +
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
      '<p class="footer-signoff"><span class="footer-signoff-line">\u00a9 ' + y + ', ' +
      '<a href="https://www.320insight.com/" target="_blank" rel="noopener noreferrer" class="footer-signoff-brand">320 Consulting</a> · ' +
      '<a href="/terms" class="footer-signoff-link" style="' + legalStyle + '">Terms</a> · ' +
      '<a href="/privacy" class="footer-signoff-link" style="' + legalStyle + '">Privacy</a> · ' +
      '<a href="/contact" class="footer-signoff-link" style="' + legalStyle + '">Contact</a></span></p>'
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
      '.footer .footer-nav-links{margin:0 0 0.35rem 0;font-size:clamp(0.64rem,2.6vw,0.75rem);line-height:1.35;text-align:center;color:rgba(148,163,184,0.95);display:flex;flex-wrap:wrap;justify-content:center;align-items:center;gap:0.12rem 0.28rem;max-width:100%;padding:0 8px;box-sizing:border-box;}',
      '.footer .footer-trust-links a{text-decoration:none;transition:color .15s ease;white-space:nowrap;}',
      '.footer .footer-trust-links a:hover,.footer .footer-trust-links a:focus-visible{color:#cbd5e1 !important;text-decoration:underline;text-underline-offset:2px;}',
      '.footer .footer-trust-links a:focus-visible{outline:2px solid #818cf8;outline-offset:3px;border-radius:2px;}',
      '.footer .footer-signoff{margin:12px auto 0;padding:0 8px;max-width:100%;width:100%;box-sizing:border-box;font-size:clamp(0.58rem,2.4vw,0.68rem);line-height:1.35;text-align:center;letter-spacing:0.02em;color:rgba(203,213,225,0.82);}',
      '.footer .footer-signoff-line{display:inline-block;max-width:100%;white-space:nowrap;}',
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

  var SITE_NAV_ITEMS = [
    ['/about', 'About'],
    ['/report', 'Report'],
    ['/insights', 'Insights'],
    ['/phoebe', 'PBJ Explained'],
    ['/premium', 'Premium']
  ];

  function navPathActive(path, href) {
    var linkPath = href.replace(/\/$/, '') || '/';
    if (path === linkPath) return true;
    if (linkPath === '/insights' && path.indexOf('/insights') === 0) return true;
    if (linkPath === '/report' && path.indexOf('/report') === 0) return true;
    if (linkPath === '/phoebe' && path.indexOf('/phoebe') === 0) return true;
    if (linkPath === '/about' && path.indexOf('/about') === 0) return true;
    if (linkPath === '/premium' && path.indexOf('/premium') === 0) return true;
    return false;
  }

  function navMenuMatchesPreset(menu) {
    var links = menu.querySelectorAll('a[href]');
    if (links.length !== SITE_NAV_ITEMS.length) return false;
    for (var i = 0; i < SITE_NAV_ITEMS.length; i++) {
      if (links[i].getAttribute('href') !== SITE_NAV_ITEMS[i][0]) return false;
      if ((links[i].textContent || '').trim() !== SITE_NAV_ITEMS[i][1]) return false;
    }
    return true;
  }

  /** Same top nav on every static page (no FEC / Contact shortcuts). */
  function normalizeSiteNavbar() {
    var menu = document.querySelector('.navbar .nav-menu') || document.querySelector('.navbar .nav-links');
    if (!menu) return;
    if (navMenuMatchesPreset(menu)) {
      markActiveNavLink();
      return;
    }
    var path = (typeof location !== 'undefined' && location.pathname)
      ? location.pathname.replace(/\/$/, '') || '/'
      : '/';
    var useNavLink = menu.classList.contains('nav-menu');
    var html = '';
    for (var i = 0; i < SITE_NAV_ITEMS.length; i++) {
      var href = SITE_NAV_ITEMS[i][0];
      var label = SITE_NAV_ITEMS[i][1];
      var active = navPathActive(path, href);
      if (useNavLink) {
        html += '<a href="' + href + '" class="nav-link' + (active ? ' active' : '') + '">' + label + '</a>';
      } else {
        html += '<a href="' + href + '"' + (active ? ' class="active" aria-current="page"' : '') + '">' + label + '</a>';
      }
    }
    menu.innerHTML = html;
  }

  function bindMobileNavToggle() {
    var toggle = document.getElementById('navToggle');
    var menu = document.getElementById('navMenu');
    if (!toggle || !menu || toggle.getAttribute('data-pbj-nav-bound')) return;
    toggle.setAttribute('data-pbj-nav-bound', '1');
    toggle.addEventListener('click', function () {
      var open = menu.classList.toggle('active');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
    var navLinks = menu.querySelectorAll('a[href]');
    for (var j = 0; j < navLinks.length; j++) {
      navLinks[j].addEventListener('click', function () {
        menu.classList.remove('active');
        toggle.setAttribute('aria-expanded', 'false');
      });
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
      '.navbar{background:rgba(10,15,26,0.92)!important;backdrop-filter:blur(12px)!important;-webkit-backdrop-filter:blur(12px)!important;border-bottom:1px solid rgba(148,163,184,0.28)!important;}',
      '.navbar .nav-container{max-width:1200px !important;margin:0 auto !important;padding:0 clamp(12px,4vw,20px) !important;height:60px !important;max-height:60px !important;display:flex !important;align-items:center !important;justify-content:space-between !important;box-sizing:border-box !important;min-width:0 !important;}',
      '.navbar .nav-brand,.navbar .nav-link{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif !important;}',
      '.navbar .nav-menu{gap:30px !important;align-items:center !important;}',
      '.navbar .nav-link{padding:8px 0 !important;font-size:16px !important;line-height:1.25 !important;font-weight:500 !important;color:rgba(255,255,255,0.88) !important;display:inline-block !important;min-height:0 !important;border:0 !important;background:transparent !important;}',
      '@media (min-width:769px){',
      '  .navbar .nav-menu{position:static !important;flex-direction:row !important;height:auto !important;min-height:0 !important;background:transparent !important;border:0 !important;padding:0 !important;margin:0 !important;}',
      '  .navbar .nav-link{padding:8px 0 !important;min-height:0 !important;border:0 !important;display:inline-block !important;}',
      '}',
      '.navbar .nav-link:hover{color:#93c5fd !important;}',
      '.navbar .nav-link.active{color:#60a5fa !important;font-weight:600 !important;}',
      '.navbar .nav-link.active:hover{color:#60a5fa !important;}',
      '.navbar .nav-links a{color:rgba(255,255,255,0.88) !important;font-weight:500 !important;text-decoration:none !important;}',
      '.navbar .nav-links a:hover{color:#93c5fd !important;}',
      '.navbar .nav-links a.active{color:#60a5fa !important;font-weight:600 !important;}',
      '.navbar .nav-links a.active:hover{color:#60a5fa !important;}',
      '.navbar .nav-brand,.navbar .brand{display:flex !important;align-items:center !important;color:#eef2f7 !important;font-size:1.2rem !important;font-weight:700 !important;line-height:1.2 !important;min-width:0 !important;}',
      '.navbar .nav-brand a,.navbar .brand{display:flex !important;align-items:center !important;gap:0 !important;color:inherit !important;text-decoration:none !important;}',
      '.navbar .nav-brand img,.navbar .brand img{width:32px !important;height:32px !important;min-width:32px !important;min-height:32px !important;margin-right:8px !important;object-fit:contain !important;flex-shrink:0 !important;display:block !important;vertical-align:middle !important;}',
      '.navbar .nav-brand span span:first-child,.navbar .brand .pbj-brand-pbj{color:#e2e8f0 !important;}',
      '.navbar .nav-brand span span:last-child,.navbar .brand .pbj-brand-320{color:#818cf8 !important;}',
      '@media (max-width:768px){',
      '  .navbar .nav-menu{height:calc(100vh - 60px) !important;top:60px !important;left:-100% !important;padding:0 !important;gap:0 !important;justify-content:flex-start !important;align-items:stretch !important;border-top:1px solid rgba(71,85,105,0.45) !important;background:rgba(10,15,26,0.98) !important;backdrop-filter:blur(12px) !important;-webkit-backdrop-filter:blur(12px) !important;}',
      '  .navbar .nav-menu.active{left:0 !important;}',
      '  .navbar .nav-link{padding:18px 24px !important;border-bottom:1px solid rgba(30,41,59,0.55) !important;text-align:left !important;font-size:1rem !important;color:rgba(255,255,255,0.88) !important;background:transparent !important;transition:color 0.2s ease !important;}',
      '  .navbar .nav-link:hover{background:transparent !important;color:#93c5fd !important;}',
      '  .navbar .nav-link.active{color:#60a5fa !important;font-weight:600 !important;background:transparent !important;border-left:none !important;}',
      '  .navbar .nav-link.active:hover{color:#60a5fa !important;}',
      '}',
      '.pbj-subscribe-overlay{position:fixed;inset:0;background:rgba(2,6,23,0.72);z-index:10020;display:none;align-items:center;justify-content:center;padding:1rem;box-sizing:border-box;}',
      '.pbj-subscribe-overlay[aria-hidden="false"]{display:flex;}',
      '.pbj-subscribe-popup{position:relative;background:#0f172a;border:1px solid rgba(51,65,85,0.65);border-radius:12px;width:100%;max-width:min(22rem,100%);max-height:calc(100vh - 2rem);overflow:auto;box-shadow:0 16px 48px rgba(0,0,0,0.45);padding:1.15rem 1.2rem 1.25rem;box-sizing:border-box;-webkit-overflow-scrolling:touch;}',
      '.pbj-subscribe-popup__close{position:absolute;top:0.55rem;right:0.55rem;width:44px;height:44px;padding:0;border:none;background:transparent;cursor:pointer;font-size:1.75rem;line-height:1;color:rgba(148,163,184,0.9);border-radius:8px;}',
      '.pbj-subscribe-popup__close:hover{color:#e2e8f0;background:rgba(99,102,241,0.15);}',
      '.pbj-subscribe-popup__close:focus-visible{outline:2px solid #818cf8;outline-offset:2px;}',
      '.pbj-subscribe-popup__title{margin:0 2rem 0.85rem 0;font-size:0.72rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:rgba(226,232,240,0.55);line-height:1.35;}',
      '.pbj-subscribe-popup__form{display:flex;flex-direction:column;gap:8px;align-items:stretch;}',
      '.pbj-subscribe-popup__label{font-size:0.8rem;font-weight:500;color:#cbd5e1;text-align:left;}',
      '.pbj-subscribe-popup__input{width:100%;padding:10px 14px;font-size:16px;min-height:44px;box-sizing:border-box;border:1px solid rgba(148,163,184,0.55);border-radius:8px;background:rgba(15,23,42,0.85);color:#f8fafc;}',
      '.pbj-subscribe-popup__input:focus{outline:none;border-color:#818cf8;box-shadow:0 0 0 3px rgba(99,102,241,0.25);}',
      '.pbj-subscribe-popup__submit{padding:12px 16px;font-size:0.875rem;font-weight:600;min-height:44px;border-radius:8px;border:1px solid rgba(100,116,139,0.55);background:rgba(30,41,59,0.65);color:rgba(226,232,240,0.92);cursor:pointer;}',
      '.pbj-subscribe-popup__submit:hover{border-color:rgba(148,163,184,0.65);background:rgba(51,65,85,0.75);color:#f8fafc;}',
      '.pbj-subscribe-popup__submit:focus-visible{outline:2px solid #818cf8;outline-offset:2px;}',
      '.pbj-subscribe-popup__submit:disabled{opacity:0.65;cursor:wait;}',
      '.pbj-subscribe-popup__msg{margin:0.65rem 0 0;font-size:0.8rem;line-height:1.4;text-align:left;}',
      '.pbj-subscribe-popup__msg--ok{color:rgba(134,239,172,0.95);}',
      '.pbj-subscribe-popup__msg--err{color:rgba(248,113,113,0.95);}',
      '.pbj-correction-popup__intro{margin:0 0 0.85rem;font-size:0.85rem;line-height:1.45;color:rgba(203,213,225,0.88);}',
      '.pbj-correction-popup__textarea{width:100%;min-height:7rem;padding:10px 14px;font-size:16px;box-sizing:border-box;border:1px solid rgba(148,163,184,0.55);border-radius:8px;background:rgba(15,23,42,0.85);color:#f8fafc;resize:vertical;font-family:inherit;}',
      '.pbj-correction-popup__textarea:focus{outline:none;border-color:#818cf8;box-shadow:0 0 0 3px rgba(99,102,241,0.25);}'
    ].join('');
    document.head.appendChild(style);
  }

  function ensureSubscribeModal() {
    if (document.getElementById('pbj-subscribe-overlay')) return;
    var overlay = document.createElement('div');
    overlay.id = 'pbj-subscribe-overlay';
    overlay.className = 'pbj-subscribe-overlay';
    overlay.setAttribute('aria-hidden', 'true');
    overlay.innerHTML =
      '<div class="pbj-subscribe-popup" role="dialog" aria-modal="true" aria-labelledby="pbj-subscribe-popup-title">' +
      '<button type="button" class="pbj-subscribe-popup__close" aria-label="Close">&times;</button>' +
      '<h2 id="pbj-subscribe-popup-title" class="pbj-subscribe-popup__title">Get staffing data updates</h2>' +
      '<form id="pbj-subscribe-popup-form" class="pbj-subscribe-popup__form" action="/subscribe" method="POST" novalidate>' +
      '<input type="hidden" name="csrf_token" id="pbj-subscribe-csrf" value="">' +
      '<input type="hidden" name="source" value="footer_modal">' +
      '<label class="pbj-subscribe-popup__label" for="pbj-subscribe-email">Email address</label>' +
      '<input type="email" class="pbj-subscribe-popup__input" id="pbj-subscribe-email" name="email" placeholder="Enter your email" required autocomplete="email">' +
      '<button type="submit" class="pbj-subscribe-popup__submit">Subscribe</button>' +
      '</form>' +
      '<p class="pbj-subscribe-popup__msg pbj-subscribe-popup__msg--ok" id="pbj-subscribe-success" hidden></p>' +
      '<p class="pbj-subscribe-popup__msg pbj-subscribe-popup__msg--err" id="pbj-subscribe-error" hidden></p>' +
      '</div>';
    document.body.appendChild(overlay);
  }

  function subscribeModalEls() {
    return {
      overlay: document.getElementById('pbj-subscribe-overlay'),
      dialog: document.querySelector('#pbj-subscribe-overlay .pbj-subscribe-popup'),
      form: document.getElementById('pbj-subscribe-popup-form'),
      csrf: document.getElementById('pbj-subscribe-csrf'),
      email: document.getElementById('pbj-subscribe-email'),
      submit: document.querySelector('#pbj-subscribe-popup-form .pbj-subscribe-popup__submit'),
      success: document.getElementById('pbj-subscribe-success'),
      error: document.getElementById('pbj-subscribe-error')
    };
  }

  function subscribeStatusMessage(status) {
    if (status === 'already') {
      return 'That email is already on the staffing updates list.';
    }
    if (status === 'subscribed') {
      return "You're subscribed. We'll email you when we publish staffing updates.";
    }
    if (status === 'csrf') {
      return 'Your session expired. Close this dialog, refresh the page, and try again.';
    }
    if (status === 'invalid') {
      return 'Please enter a valid email address.';
    }
    return 'Something went wrong. Try again later.';
  }

  function resetSubscribeModalForm() {
    var el = subscribeModalEls();
    if (!el.form) return;
    if (el.success) {
      el.success.hidden = true;
      el.success.textContent = '';
    }
    if (el.error) {
      el.error.hidden = true;
      el.error.textContent = '';
    }
    if (el.form) el.form.style.display = '';
    if (el.submit) {
      el.submit.disabled = false;
      el.submit.textContent = 'Subscribe';
    }
  }

  function showSubscribeModalStatus(status) {
    var el = subscribeModalEls();
    var msg = subscribeStatusMessage(status);
    if (status === 'subscribed' || status === 'already') {
      if (el.form) el.form.style.display = 'none';
      if (el.error) el.error.hidden = true;
      if (el.success) {
        el.success.textContent = msg;
        el.success.hidden = false;
      }
      return;
    }
    if (el.error) {
      el.error.textContent = msg;
      el.error.hidden = false;
    }
    if (el.submit) {
      el.submit.disabled = false;
      el.submit.textContent = 'Subscribe';
    }
  }

  function loadSubscribeCsrf() {
    var el = subscribeModalEls();
    if (!el.csrf) return Promise.resolve();
    var homeCsrf = document.querySelector('#hero-subscribe-form input[name="csrf_token"]');
    if (homeCsrf && homeCsrf.value) {
      el.csrf.value = homeCsrf.value;
      return Promise.resolve();
    }
    return fetch('/api/subscribe/csrf', { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (data && data.csrf_token) el.csrf.value = data.csrf_token;
      })
      .catch(function () {});
  }

  function closeSubscribeModal() {
    var el = subscribeModalEls();
    if (!el.overlay) return;
    el.overlay.setAttribute('aria-hidden', 'true');
    document.documentElement.style.overflow = '';
  }

  function openSubscribeModal() {
    ensureSubscribeModal();
    var el = subscribeModalEls();
    if (!el.overlay || !el.dialog) return;
    resetSubscribeModalForm();
    loadSubscribeCsrf().then(function () {
      el.overlay.setAttribute('aria-hidden', 'false');
      document.documentElement.style.overflow = 'hidden';
      if (el.email) {
        try {
          el.email.focus();
        } catch (err) {}
      }
    });
  }

  function submitSubscribeModal(ev) {
    if (ev && ev.preventDefault) ev.preventDefault();
    var el = subscribeModalEls();
    if (!el.form || !el.email) return;
    var email = (el.email.value || '').trim();
    if (!email) {
      showSubscribeModalStatus('invalid');
      return;
    }
    if (el.submit) {
      el.submit.disabled = true;
      el.submit.textContent = 'Subscribing…';
    }
    if (el.error) el.error.hidden = true;
    var body = new URLSearchParams(new FormData(el.form));
    fetch('/subscribe', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: body.toString()
    })
      .then(function (r) {
        return r.json().then(function (data) {
          return { ok: r.ok, data: data };
        });
      })
      .then(function (res) {
        var status = (res.data && res.data.status) || (res.ok ? 'subscribed' : 'error');
        showSubscribeModalStatus(status);
      })
      .catch(function () {
        showSubscribeModalStatus('error');
      });
  }

  function bindSubscribeModal() {
    ensureSubscribeModal();
    var el = subscribeModalEls();
    if (!el.overlay) return;

    var closeBtn = el.overlay.querySelector('.pbj-subscribe-popup__close');
    if (closeBtn && !closeBtn.getAttribute('data-pbj-bound')) {
      closeBtn.setAttribute('data-pbj-bound', '1');
      closeBtn.addEventListener('click', function (e) {
        e.preventDefault();
        closeSubscribeModal();
      });
    }
    if (el.overlay && !el.overlay.getAttribute('data-pbj-bound')) {
      el.overlay.setAttribute('data-pbj-bound', '1');
      el.overlay.addEventListener('click', function (e) {
        if (e.target === el.overlay) closeSubscribeModal();
      });
    }
    if (el.form && !el.form.getAttribute('data-pbj-bound')) {
      el.form.setAttribute('data-pbj-bound', '1');
      el.form.addEventListener('submit', submitSubscribeModal);
    }
    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape') return;
      if (el.overlay && el.overlay.getAttribute('aria-hidden') === 'false') {
        closeSubscribeModal();
      }
      var corr = document.getElementById('pbj-correction-overlay');
      if (corr && corr.getAttribute('aria-hidden') === 'false') {
        closeCorrectionModal();
      }
    });
  }

  function isSubscribeFooterLink(node) {
    if (!node || !node.closest) return null;
    return node.closest(
      '[data-pbj-subscribe-open], a[href="/updates"], a[href="/#updates"], a[href$="#updates"]'
    );
  }

  function ensureCorrectionModal() {
    if (document.getElementById('pbj-correction-overlay')) return;
    var overlay = document.createElement('div');
    overlay.id = 'pbj-correction-overlay';
    overlay.className = 'pbj-subscribe-overlay';
    overlay.setAttribute('aria-hidden', 'true');
    overlay.innerHTML =
      '<div class="pbj-subscribe-popup" role="dialog" aria-modal="true" aria-labelledby="pbj-correction-popup-title">' +
      '<button type="button" class="pbj-subscribe-popup__close" aria-label="Close">&times;</button>' +
      '<h2 id="pbj-correction-popup-title" class="pbj-subscribe-popup__title">Corrections</h2>' +
      '<p class="pbj-correction-popup__intro">See something wrong? Tell us what to fix.</p>' +
      '<form id="pbj-correction-popup-form" class="pbj-subscribe-popup__form" action="/corrections" method="POST" novalidate>' +
      '<input type="hidden" name="csrf_token" id="pbj-correction-csrf" value="">' +
      '<input type="hidden" name="next" value="">' +
      '<input type="hidden" name="page_url" id="pbj-correction-page-url" value="">' +
      '<label class="pbj-subscribe-popup__label" for="pbj-correction-name">Name</label>' +
      '<input type="text" class="pbj-subscribe-popup__input" id="pbj-correction-name" name="name" required autocomplete="name" maxlength="200">' +
      '<label class="pbj-subscribe-popup__label" for="pbj-correction-email">Email</label>' +
      '<input type="email" class="pbj-subscribe-popup__input" id="pbj-correction-email" name="email" required autocomplete="email">' +
      '<label class="pbj-subscribe-popup__label" for="pbj-correction-issue">What\'s wrong?</label>' +
      '<textarea class="pbj-correction-popup__textarea" id="pbj-correction-issue" name="issue" required maxlength="10000" placeholder="Describe the error. Include a source or link if you have one."></textarea>' +
      '<button type="submit" class="pbj-subscribe-popup__submit">Submit</button>' +
      '</form>' +
      '<p class="pbj-subscribe-popup__msg pbj-subscribe-popup__msg--ok" id="pbj-correction-success" hidden></p>' +
      '<p class="pbj-subscribe-popup__msg pbj-subscribe-popup__msg--err" id="pbj-correction-error" hidden></p>' +
      '</div>';
    document.body.appendChild(overlay);
  }

  function correctionModalEls() {
    return {
      overlay: document.getElementById('pbj-correction-overlay'),
      form: document.getElementById('pbj-correction-popup-form'),
      csrf: document.getElementById('pbj-correction-csrf'),
      pageUrl: document.getElementById('pbj-correction-page-url'),
      name: document.getElementById('pbj-correction-name'),
      email: document.getElementById('pbj-correction-email'),
      issue: document.getElementById('pbj-correction-issue'),
      submit: document.querySelector('#pbj-correction-popup-form .pbj-subscribe-popup__submit'),
      success: document.getElementById('pbj-correction-success'),
      error: document.getElementById('pbj-correction-error')
    };
  }

  function resetCorrectionModal() {
    var el = correctionModalEls();
    if (!el.form) return;
    if (el.success) {
      el.success.hidden = true;
      el.success.textContent = '';
    }
    if (el.error) {
      el.error.hidden = true;
      el.error.textContent = '';
    }
    el.form.style.display = '';
    if (el.submit) {
      el.submit.disabled = false;
      el.submit.textContent = 'Submit';
    }
    if (el.pageUrl) {
      el.pageUrl.value = (typeof location !== 'undefined' && location.href)
        ? location.href.split('#')[0]
        : '';
    }
  }

  function showCorrectionStatus(status) {
    var el = correctionModalEls();
    if (status === 'sent') {
      if (el.form) el.form.style.display = 'none';
      if (el.error) el.error.hidden = true;
      if (el.success) {
        el.success.textContent = 'Thanks — we received your correction.';
        el.success.hidden = false;
      }
      return;
    }
    var msg = 'Something went wrong. Try again or email us.';
    if (status === 'invalid') msg = 'Please fill in name, email, and what\'s wrong.';
    if (status === 'csrf') msg = 'Session expired. Refresh the page and try again.';
    if (el.error) {
      el.error.textContent = msg;
      el.error.hidden = false;
    }
    if (el.submit) {
      el.submit.disabled = false;
      el.submit.textContent = 'Submit';
    }
  }

  function loadCorrectionCsrf() {
    var el = correctionModalEls();
    if (!el.csrf) return Promise.resolve();
    var tokenInput = document.querySelector('input[name="csrf_token"]');
    if (tokenInput && tokenInput.value) {
      el.csrf.value = tokenInput.value;
      return Promise.resolve();
    }
    return fetch('/api/subscribe/csrf', { credentials: 'same-origin', headers: { Accept: 'application/json' } })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (data && data.csrf_token) el.csrf.value = data.csrf_token;
      })
      .catch(function () {});
  }

  function closeCorrectionModal() {
    var el = correctionModalEls();
    if (!el.overlay) return;
    el.overlay.setAttribute('aria-hidden', 'true');
    document.documentElement.style.overflow = '';
  }

  function openCorrectionModal() {
    ensureCorrectionModal();
    var el = correctionModalEls();
    if (!el.overlay) return;
    resetCorrectionModal();
    loadCorrectionCsrf().then(function () {
      el.overlay.setAttribute('aria-hidden', 'false');
      document.documentElement.style.overflow = 'hidden';
      if (el.name) {
        try {
          el.name.focus();
        } catch (err) {}
      }
    });
  }

  function submitCorrectionModal(ev) {
    if (ev && ev.preventDefault) ev.preventDefault();
    var el = correctionModalEls();
    if (!el.form) return;
    if (el.submit) {
      el.submit.disabled = true;
      el.submit.textContent = 'Sending…';
    }
    if (el.error) el.error.hidden = true;
    var body = new URLSearchParams(new FormData(el.form));
    fetch('/corrections', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        Accept: 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'Content-Type': 'application/x-www-form-urlencoded'
      },
      body: body.toString()
    })
      .then(function (r) {
        return r.json().then(function (data) {
          return { ok: r.ok, data: data };
        });
      })
      .then(function (res) {
        var status = (res.data && res.data.status) || (res.ok ? 'sent' : 'error');
        showCorrectionStatus(status);
      })
      .catch(function () {
        showCorrectionStatus('error');
      });
  }

  function bindCorrectionModal() {
    ensureCorrectionModal();
    var el = correctionModalEls();
    if (!el.overlay) return;
    var closeBtn = el.overlay.querySelector('.pbj-subscribe-popup__close');
    if (closeBtn && !closeBtn.getAttribute('data-pbj-bound')) {
      closeBtn.setAttribute('data-pbj-bound', '1');
      closeBtn.addEventListener('click', function (e) {
        e.preventDefault();
        closeCorrectionModal();
      });
    }
    if (!el.overlay.getAttribute('data-pbj-bound')) {
      el.overlay.setAttribute('data-pbj-bound', '1');
      el.overlay.addEventListener('click', function (e) {
        if (e.target === el.overlay) closeCorrectionModal();
      });
    }
    if (el.form && !el.form.getAttribute('data-pbj-bound')) {
      el.form.setAttribute('data-pbj-bound', '1');
      el.form.addEventListener('submit', submitCorrectionModal);
    }
  }

  function isCorrectionsFooterLink(node) {
    if (!node || !node.closest) return null;
    return node.closest('[data-pbj-corrections-open], a[href="/corrections"]');
  }

  function bindCorrectionsFooterLinks() {
    document.addEventListener('click', function (e) {
      var a = isCorrectionsFooterLink(e.target);
      if (!a) return;
      e.preventDefault();
      openCorrectionModal();
    });
  }

  /** Provider subtitle Owners modal — delegated (mobile-safe; no inline script). */
  function bindProviderOwnersModals() {
    var openModal = null;
    var openBtn = null;
    var ignoreBackdropUntil = 0;

    document.querySelectorAll('.pbj-provider-owners-modal[data-pbj-owners-modal]').forEach(function (modal) {
      if (modal.parentNode !== document.body) {
        document.body.appendChild(modal);
      }
    });

    function closeOwnersModal() {
      if (!openModal) return;
      openModal.setAttribute('aria-hidden', 'true');
      if (openBtn) openBtn.setAttribute('aria-expanded', 'false');
      document.documentElement.style.overflow = '';
      openModal = null;
      openBtn = null;
    }

    function openOwnersModal(modal, btn) {
      if (!modal || !btn) return;
      closeOwnersModal();
      openModal = modal;
      openBtn = btn;
      modal.setAttribute('aria-hidden', 'false');
      btn.setAttribute('aria-expanded', 'true');
      document.documentElement.style.overflow = 'hidden';
      ignoreBackdropUntil = Date.now() + 500;
    }

    document.addEventListener(
      'click',
      function (e) {
        var btn =
          e.target && e.target.closest ? e.target.closest('.pbj-provider-owners-btn') : null;
        if (btn) {
          var modalId = btn.getAttribute('aria-controls') || '';
          var modal = modalId ? document.getElementById(modalId) : null;
          if (modal) {
            e.preventDefault();
            e.stopPropagation();
            openOwnersModal(modal, btn);
          }
          return;
        }
        if (!openModal) return;
        if (e.target && e.target.closest && e.target.closest('[data-pbj-owners-close]')) {
          e.preventDefault();
          closeOwnersModal();
          return;
        }
        if (e.target === openModal && Date.now() >= ignoreBackdropUntil) {
          closeOwnersModal();
        }
      },
      true
    );

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && openModal) closeOwnersModal();
    });
  }

  function scrollToHomeUpdates() {
    var el = document.getElementById('updates');
    if (!el) return false;
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    try {
      history.replaceState(null, '', '/#updates');
    } catch (e) {
      window.location.hash = 'updates';
    }
    return true;
  }

  function bindSubscribeFooterLinks() {
    document.addEventListener('click', function (e) {
      var a = isSubscribeFooterLink(e.target);
      if (!a) return;
      e.preventDefault();
      openSubscribeModal();
    });
    var params = new URLSearchParams(window.location.search || '');
    if (params.get('open_subscribe') === '1') {
      var openFromQuery = function () {
        openSubscribeModal();
        try {
          var u = new URL(window.location.href);
          u.searchParams.delete('open_subscribe');
          history.replaceState(null, '', u.pathname + u.search + u.hash);
        } catch (err) {}
      };
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', openFromQuery);
      } else {
        openFromQuery();
      }
    }
    if (window.location.hash === '#updates') {
      var runScroll = function () {
        var path = window.location.pathname || '/';
        if (path === '/' || path === '/index.html') {
          scrollToHomeUpdates();
        } else {
          openSubscribeModal();
        }
      };
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', runScroll);
      } else {
        runScroll();
      }
    }
  }

  function run() {
    preloadNavFavicon();
    purgeLegacyFooterMarkup(document);
    var footer = document.getElementById('site-footer');
    injectFooterStyles();
    if (footer) injectFooter(footer);
    injectSiteShellStyles();
    normalizeSiteNavbar();
    bindMobileNavToggle();
    markActiveNavLink();
    injectContactCtaStyles();
    bindContactFallbacks();
    bindSourcesDialogs();
    bindProviderOwnersModals();
    bindSubscribeModal();
    bindSubscribeFooterLinks();
    bindCorrectionModal();
    bindCorrectionsFooterLinks();
  }

  if (typeof window !== 'undefined') {
    window.PBJ320_CONTACT = CONTACT;
    window.PBJ320_openContactModal = openContactModal;
    window.PBJ320_openSubscribeModal = openSubscribeModal;
    window.PBJ320_openCorrectionModal = openCorrectionModal;
    window.PBJ320_copyEmail = copyEmailAndNotify;
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', run);
    } else {
      run();
    }
  }
})();
