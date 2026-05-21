/**
 * Site-wide footer. Single source of truth for PBJ320 footer.
 * Keep in sync with pbj-site-universal.js (static HTML pages).
 */

import React from 'react';

const FOOTER_PHONE_DISPLAY = '(929) 804-4996';
const FOOTER_SMS_HREF = 'sms:+19298084996';

const FOOTER_BLURB =
  'PBJ320 is a nursing-home data platform from 320 Consulting LLC, built from CMS Payroll-Based Journal and other public federal and state datasets.';

const linkStyle = { color: 'rgba(148, 163, 184, 0.95)' };
const signoffLinkStyle = {
  color: 'rgba(203, 213, 225, 0.78)',
  textDecoration: 'underline',
  textUnderlineOffset: '3px',
};

export const SiteFooter: React.FC = () => {
  const year = new Date().getFullYear();
  return (
    <footer
      className="footer text-center w-full box-border"
      style={{
        background: '#0a0f1a',
        padding: '32px 20px 40px',
        marginTop: 0,
        borderTop: '1px solid rgba(255, 255, 255, 0.08)',
        color: '#94a3b8',
        fontSize: '0.9rem',
      }}
    >
      <p
        className="footer-boilerplate"
        style={{
          margin: '0 0 0.65rem 0',
          fontSize: '0.75rem',
          lineHeight: 1.5,
          textAlign: 'center',
          color: 'rgba(148, 163, 184, 0.82)',
          maxWidth: 720,
          marginLeft: 'auto',
          marginRight: 'auto',
        }}
      >
        {FOOTER_BLURB}
      </p>

      <p
        className="footer-trust-links footer-nav-links"
        style={{
          margin: '0 0 0.35rem 0',
          fontSize: '0.75rem',
          textAlign: 'center',
          color: 'rgba(148, 163, 184, 0.95)',
        }}
      >
        <a href="/about" style={linkStyle}>About</a>
        {' · '}
        <a href="/premium" style={linkStyle}>Premium</a>
        {' · '}
        <a href="/press" style={linkStyle}>Press</a>
        {' · '}
        <a href="/contact" style={linkStyle}>Contact</a>
        {' · '}
        <a href="/data-sources" style={linkStyle}>Sources</a>
      </p>

      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          gap: '20px',
          marginTop: '0.5rem',
        }}
      >
        <a
          href="mailto:eric@320insight.com"
          style={{ display: 'inline-block', transition: 'opacity 0.3s ease' }}
          title="Email: eric@320insight.com"
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ opacity: 0.7 }}>
            <path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z" fill="#60a5fa" />
          </svg>
        </a>
        <a
          href={FOOTER_SMS_HREF}
          style={{ display: 'inline-block', transition: 'opacity 0.3s ease' }}
          title={`SMS: ${FOOTER_PHONE_DISPLAY}`}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ opacity: 0.7 }}>
            <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z" fill="#60a5fa" />
          </svg>
        </a>
        <a
          href="https://www.linkedin.com/in/eric-goldwein/"
          target="_blank"
          rel="noopener noreferrer"
          style={{ display: 'inline-block', transition: 'opacity 0.3s ease' }}
          title="LinkedIn"
        >
          <img src="/LI-In-Bug.png" alt="LinkedIn" style={{ width: 24, height: 24, objectFit: 'contain', opacity: 0.7, transition: 'opacity 0.3s ease' }} />
        </a>
        <a
          href="https://320insight.substack.com/"
          target="_blank"
          rel="noopener noreferrer"
          style={{ display: 'inline-block', transition: 'opacity 0.3s ease' }}
          title="The 320 Newsletter"
        >
          <img src="/substack.png" alt="Substack" style={{ width: 24, height: 24, objectFit: 'contain', opacity: 0.7, transition: 'opacity 0.3s ease' }} />
        </a>
      </div>

      <p className="footer-signoff">
        © {year},{' '}
        <a
          href="https://www.320insight.com/"
          target="_blank"
          rel="noopener noreferrer"
          className="footer-signoff-brand"
        >
          320 Consulting
        </a>
        {' · '}
        <a href="/terms" className="footer-signoff-link" style={signoffLinkStyle}>
          Terms
        </a>
        {' · '}
        <a href="/privacy" className="footer-signoff-link" style={signoffLinkStyle}>
          Privacy
        </a>
      </p>
    </footer>
  );
};
