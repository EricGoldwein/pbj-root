/**
 * Single source of truth for PBJ320 site: contact number, footer, and nav.
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

  function injectFooter(el) {
    if (!el) return;
    el.innerHTML = [
      '<p class="footer-tagline" style="margin:0 0 1rem 0;font-size:0.8rem;text-align:center;letter-spacing:0.03em"><strong>320 Consulting</strong> — Turning Spreadsheets into Stories</p>',
      '<div style="display:flex;justify-content:center;align-items:center;gap:20px;margin-top:0.5rem">',
      '<a href="mailto:' + CONTACT.email + '" style="display:inline-block;transition:opacity 0.3s ease" title="Email: ' + CONTACT.email + '"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" style="opacity:0.7"><path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z" fill="#60a5fa"/></svg></a>',
      '<a href="' + CONTACT.smsHref + '" style="display:inline-block;transition:opacity 0.3s ease" title="SMS: ' + CONTACT.phoneDisplay + '"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" style="opacity:0.7"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z" fill="#60a5fa"/></svg></a>',
      '<a href="https://www.linkedin.com/in/eric-goldwein/" target="_blank" rel="noopener noreferrer" style="display:inline-block;transition:opacity 0.3s ease" title="LinkedIn"><img src="/LI-In-Bug.png" alt="LinkedIn" style="width:24px;height:24px;object-fit:contain;opacity:0.7"/></a>',
      '<a href="https://320insight.substack.com/" target="_blank" rel="noopener noreferrer" style="display:inline-block;transition:opacity 0.3s ease" title="The 320 Newsletter"><img src="/substack.png" alt="Substack" style="width:24px;height:24px;object-fit:contain;opacity:0.7"/></a>',
      '</div>'
    ].join('');
  }

  function run() {
    var footer = document.getElementById('site-footer');
    if (footer) injectFooter(footer);
  }

  if (typeof window !== 'undefined') {
    window.PBJ320_CONTACT = CONTACT;
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', run);
    } else {
      run();
    }
  }
})();
