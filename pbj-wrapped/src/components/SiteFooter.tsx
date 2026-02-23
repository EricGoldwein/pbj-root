/**
 * Site-wide footer. Single source of truth for PBJ320 footer.
 * Matches index.html: 320 Consulting tagline, email, SMS (929), LinkedIn, Substack.
 */

import React from 'react';

const FOOTER_PHONE_DISPLAY = '(929) 804-4996';
const FOOTER_SMS_HREF = 'sms:+19298084996';

export const SiteFooter: React.FC = () => (
  <footer
    className="mt-6 md:mt-8 pt-6 md:pt-8 text-center"
    style={{ background: '#0f172a', padding: '1.25rem 1rem', marginTop: '60px' }}
  >
    {/* Brand */}
    <p
      style={{
        margin: '0 0 1rem 0',
        color: 'rgba(255,255,255,0.55)',
        fontSize: '0.8rem',
        textAlign: 'center',
        letterSpacing: '0.03em',
      }}
    >
      <strong>320 Consulting</strong>: Turning Spreadsheets into Stories.
    </p>

    {/* Social Icons */}
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
  </footer>
);
