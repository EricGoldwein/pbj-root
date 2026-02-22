/**
 * Site-wide navbar. Single source of truth for PBJ320 nav.
 * Matches index.html: About, Dashboard, Insights, Report, PBJ Explained, Ownership.
 * Use this on Index, SFF, and any other page that needs the main nav.
 */

import React, { useState } from 'react';
import { getAssetPath } from '../utils/assets';

const BASE = 'https://pbj320.com';

const NAV_LINKS: { href: string; label: string; external?: boolean }[] = [
  { href: `${BASE}/about`, label: 'About' },
  { href: `${BASE}/`, label: 'Dashboard' },
  { href: `${BASE}/insights`, label: 'Insights' },
  { href: `${BASE}/report`, label: 'Report' },
  { href: '/phoebe', label: 'PBJ Explained', external: true },
  { href: `${BASE}/owners`, label: 'Ownership' },
];

interface SiteNavbarProps {
  /** Called when a link is clicked (e.g. to close mobile menu) */
  onLinkClick?: () => void;
  /** Optional tracking when Dashboard link is clicked */
  onDashboardClick?: () => void;
}

export const SiteNavbar: React.FC<SiteNavbarProps> = ({ onLinkClick, onDashboardClick }) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const closeMobile = () => {
    setMobileMenuOpen(false);
    onLinkClick?.();
  };

  const linkClass = 'text-gray-300 hover:text-blue-300 text-sm md:text-base font-medium transition-colors';
  const mobileLinkClass = 'block px-4 py-2 text-gray-300 hover:text-blue-300 hover:bg-gray-800/50 rounded transition-colors';

  return (
    <nav className="sticky top-0 z-50 bg-[#0f172a] border-b-2 border-blue-600 shadow-lg">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-14 md:h-16">
          <a
            href={BASE}
            className="text-white font-bold text-lg md:text-xl hover:text-blue-300 transition-colors flex items-center gap-2"
            onClick={onLinkClick}
          >
            <img src={getAssetPath('/pbj_favicon.png')} alt="PBJ320" className="h-6 md:h-8 w-auto" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
            <span><span className="text-white">PBJ</span><span className="text-blue-400">320</span></span>
          </a>
          {/* Desktop */}
          <div className="hidden md:flex items-center gap-4 lg:gap-6">
            {NAV_LINKS.map(({ href, label, external }) => (
              <a
                key={label}
                href={href}
                className={linkClass}
                target={external ? '_blank' : undefined}
                rel={external ? 'noopener noreferrer' : undefined}
                onClick={label === 'Dashboard' ? onDashboardClick : undefined}
              >
                {label}
              </a>
            ))}
          </div>
          {/* Mobile menu button */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden p-2 text-gray-300 hover:text-white transition-colors"
            aria-label="Toggle menu"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {mobileMenuOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>
        {/* Mobile menu */}
        {mobileMenuOpen && (
          <div className="md:hidden border-t border-gray-700 py-3 space-y-2">
            {NAV_LINKS.map(({ href, label, external }) => (
              <a
                key={label}
                href={href}
                className={mobileLinkClass}
                target={external ? '_blank' : undefined}
                rel={external ? 'noopener noreferrer' : undefined}
                onClick={closeMobile}
              >
                {label}
              </a>
            ))}
          </div>
        )}
      </div>
    </nav>
  );
};
