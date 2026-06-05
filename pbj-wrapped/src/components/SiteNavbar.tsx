/**
 * Site-wide navbar. Matches index.html + pbj-site-universal.js SITE_NAV_ITEMS.
 */

import React, { useEffect } from 'react';

const NAV_LINKS: { href: string; label: string }[] = [
  { href: '/about', label: 'About' },
  { href: '/report', label: 'Report' },
  { href: '/insights', label: 'Insights' },
  { href: '/phoebe', label: 'PBJ Explained' },
  { href: '/premium', label: 'Premium' },
];

function navPathActive(path: string, href: string): boolean {
  const linkPath = href.replace(/\/$/, '') || '/';
  const normalized = path.replace(/\/$/, '') || '/';
  if (normalized === linkPath) return true;
  if (linkPath === '/insights' && normalized.startsWith('/insights')) return true;
  if (linkPath === '/report' && normalized.startsWith('/report')) return true;
  if (linkPath === '/phoebe' && normalized.startsWith('/phoebe')) return true;
  if (linkPath === '/about' && normalized.startsWith('/about')) return true;
  if (linkPath === '/premium' && normalized.startsWith('/premium')) return true;
  return false;
}

interface SiteNavbarProps {
  onLinkClick?: () => void;
  onDashboardClick?: () => void;
}

export const SiteNavbar: React.FC<SiteNavbarProps> = ({ onLinkClick, onDashboardClick }) => {
  const path = typeof window !== 'undefined' ? window.location.pathname : '/';

  useEffect(() => {
    const toggle = document.getElementById('navToggle');
    const menu = document.getElementById('navMenu');
    if (!toggle || !menu) return;

    const onToggle = () => {
      const open = menu.classList.toggle('active');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    };
    toggle.addEventListener('click', onToggle);

    const links = menu.querySelectorAll('a[href]');
    const closeMenu = () => {
      menu.classList.remove('active');
      toggle.setAttribute('aria-expanded', 'false');
      onLinkClick?.();
    };
    links.forEach((link) => link.addEventListener('click', closeMenu));

    return () => {
      toggle.removeEventListener('click', onToggle);
      links.forEach((link) => link.removeEventListener('click', closeMenu));
    };
  }, [onLinkClick]);

  return (
    <nav className="navbar">
      <div className="nav-container">
        <div className="nav-brand" style={{ color: 'inherit' }}>
          <a
            href="/"
            style={{ color: 'inherit', textDecoration: 'none', display: 'flex', alignItems: 'center' }}
            onClick={onLinkClick}
          >
            <img
              src="/pbj_favicon.png"
              alt=""
              width={32}
              height={32}
              decoding="async"
              fetchPriority="high"
              style={{ height: 32, width: 32, verticalAlign: 'middle', marginRight: 8 }}
            />
            <span>
              <span style={{ color: '#e2e8f0' }}>PBJ</span>
              <span style={{ color: '#818cf8' }}>320</span>
            </span>
          </a>
        </div>
        <div className="nav-menu" id="navMenu">
          {NAV_LINKS.map(({ href, label }) => (
            <a
              key={href}
              href={href}
              className={`nav-link${navPathActive(path, href) ? ' active' : ''}`}
              onClick={onDashboardClick}
            >
              {label}
            </a>
          ))}
        </div>
        <button
          type="button"
          className="nav-toggle"
          id="navToggle"
          aria-label="Open menu"
          aria-expanded="false"
          aria-controls="navMenu"
        >
          <span aria-hidden="true" />
          <span aria-hidden="true" />
          <span aria-hidden="true" />
        </button>
      </div>
    </nav>
  );
};
