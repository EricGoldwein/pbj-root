import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { WrappedImage } from '../components/wrapped/WrappedImage';
import { USMap } from '../components/wrapped/USMap';
import { updateSEO, getWrappedLandingSEO } from '../utils/seo';
import { getAssetPath } from '../utils/assets';
import { trackDashboardLinkClick } from '../utils/analytics';

const Index: React.FC = () => {
  const navigate = useNavigate();
  const [selectedState, setSelectedState] = useState<string>('');
  const [selectedRegion, setSelectedRegion] = useState<string>('');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Update SEO on mount
  useEffect(() => {
    updateSEO(getWrappedLandingSEO('2025'));
  }, []);

  const states = [
    { code: 'AL', name: 'Alabama' }, { code: 'AK', name: 'Alaska' }, { code: 'AZ', name: 'Arizona' },
    { code: 'AR', name: 'Arkansas' }, { code: 'CA', name: 'California' }, { code: 'CO', name: 'Colorado' },
    { code: 'CT', name: 'Connecticut' }, { code: 'DE', name: 'Delaware' }, { code: 'FL', name: 'Florida' },
    { code: 'GA', name: 'Georgia' }, { code: 'HI', name: 'Hawaii' }, { code: 'ID', name: 'Idaho' },
    { code: 'IL', name: 'Illinois' }, { code: 'IN', name: 'Indiana' }, { code: 'IA', name: 'Iowa' },
    { code: 'KS', name: 'Kansas' }, { code: 'KY', name: 'Kentucky' }, { code: 'LA', name: 'Louisiana' },
    { code: 'ME', name: 'Maine' }, { code: 'MD', name: 'Maryland' }, { code: 'MA', name: 'Massachusetts' },
    { code: 'MI', name: 'Michigan' }, { code: 'MN', name: 'Minnesota' }, { code: 'MS', name: 'Mississippi' },
    { code: 'MO', name: 'Missouri' }, { code: 'MT', name: 'Montana' }, { code: 'NE', name: 'Nebraska' },
    { code: 'NV', name: 'Nevada' }, { code: 'NH', name: 'New Hampshire' }, { code: 'NJ', name: 'New Jersey' },
    { code: 'NM', name: 'New Mexico' }, { code: 'NY', name: 'New York' }, { code: 'NC', name: 'North Carolina' },
    { code: 'ND', name: 'North Dakota' }, { code: 'OH', name: 'Ohio' }, { code: 'OK', name: 'Oklahoma' },
    { code: 'OR', name: 'Oregon' }, { code: 'PA', name: 'Pennsylvania' }, { code: 'RI', name: 'Rhode Island' },
    { code: 'SC', name: 'South Carolina' }, { code: 'SD', name: 'South Dakota' }, { code: 'TN', name: 'Tennessee' },
    { code: 'TX', name: 'Texas' }, { code: 'UT', name: 'Utah' }, { code: 'VT', name: 'Vermont' },
    { code: 'VA', name: 'Virginia' }, { code: 'WA', name: 'Washington' }, { code: 'WV', name: 'West Virginia' },
    { code: 'WI', name: 'Wisconsin' }, { code: 'WY', name: 'Wyoming' }, { code: 'DC', name: 'District of Columbia' },
  ];

  const regions = [
    { num: 1, name: 'Boston' },
    { num: 2, name: 'New York' },
    { num: 3, name: 'Philadelphia' },
    { num: 4, name: 'Atlanta' },
    { num: 5, name: 'Chicago' },
    { num: 6, name: 'Dallas' },
    { num: 7, name: 'Kansas City' },
    { num: 8, name: 'Denver' },
    { num: 9, name: 'San Francisco' },
    { num: 10, name: 'Seattle' },
  ];

  const handleStateSelect = (stateCode: string) => {
    if (stateCode) {
      navigate(`/wrapped/${stateCode.toLowerCase()}`);
    }
  };

  const handleRegionSelect = (regionNum: number) => {
    navigate(`/wrapped/region${regionNum}`);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-blue-900 to-gray-900 text-white">
      {/* Header Navigation */}
      <nav className="sticky top-0 z-50 bg-[#0f172a] border-b-2 border-blue-600 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-14 md:h-16">
            <a 
              href="https://pbj320.com" 
              className="text-white font-bold text-lg md:text-xl hover:text-blue-300 transition-colors flex items-center gap-2"
            >
              <img src={getAssetPath('/pbj_favicon.png')} alt="PBJ320" className="h-6 md:h-8 w-auto" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
              <span><span className="text-white">PBJ</span><span className="text-blue-400">320</span></span>
            </a>
            {/* Desktop Navigation */}
            <div className="hidden md:flex items-center gap-4 lg:gap-6">
              <a 
                href="https://pbj320.com/about" 
                className="text-gray-300 hover:text-blue-300 text-sm md:text-base font-medium transition-colors"
              >
                About
              </a>
              <a 
                href="https://pbjdashboard.com/" 
                className="text-gray-300 hover:text-blue-300 text-sm md:text-base font-medium transition-colors"
                onClick={() => trackDashboardLinkClick('Navigation', 'Index Page')}
              >
                Dashboard
              </a>
              <a 
                href="https://pbj320.com/insights" 
                className="text-gray-300 hover:text-blue-300 text-sm md:text-base font-medium transition-colors"
              >
                Insights
              </a>
              <a 
                href="https://pbj320.com/report" 
                className="text-gray-300 hover:text-blue-300 text-sm md:text-base font-medium transition-colors"
              >
                Report
              </a>
              <a 
                href="https://www.320insight.com/phoebe" 
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-300 hover:text-blue-300 text-sm md:text-base font-medium transition-colors"
              >
                Phoebe J
              </a>
              <a 
                href="https://pbj320.vercel.app/" 
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-300 hover:text-blue-300 text-sm md:text-base font-medium transition-colors"
              >
                PBJ Converter
              </a>
            </div>
            {/* Mobile Menu Button */}
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
          {/* Mobile Menu */}
          {mobileMenuOpen && (
            <div className="md:hidden border-t border-gray-700 py-3 space-y-2">
              <a 
                href="https://pbj320.com/about" 
                className="block px-4 py-2 text-gray-300 hover:text-blue-300 hover:bg-gray-800/50 rounded transition-colors"
                onClick={() => setMobileMenuOpen(false)}
              >
                About
              </a>
              <a 
                href="https://pbjdashboard.com/" 
                className="block px-4 py-2 text-gray-300 hover:text-blue-300 hover:bg-gray-800/50 rounded transition-colors"
                onClick={() => setMobileMenuOpen(false)}
              >
                Dashboard
              </a>
              <a 
                href="https://pbj320.com/insights" 
                className="block px-4 py-2 text-gray-300 hover:text-blue-300 hover:bg-gray-800/50 rounded transition-colors"
                onClick={() => setMobileMenuOpen(false)}
              >
                Insights
              </a>
              <a 
                href="https://pbj320.com/report" 
                className="block px-4 py-2 text-gray-300 hover:text-blue-300 hover:bg-gray-800/50 rounded transition-colors"
                onClick={() => setMobileMenuOpen(false)}
              >
                Report
              </a>
              <a 
                href="https://www.320insight.com/phoebe" 
                target="_blank"
                rel="noopener noreferrer"
                className="block px-4 py-2 text-gray-300 hover:text-blue-300 hover:bg-gray-800/50 rounded transition-colors"
                onClick={() => setMobileMenuOpen(false)}
              >
                Phoebe J
              </a>
              <a 
                href="https://pbj320.vercel.app/" 
                target="_blank"
                rel="noopener noreferrer"
                className="block px-4 py-2 text-gray-300 hover:text-blue-300 hover:bg-gray-800/50 rounded transition-colors"
                onClick={() => setMobileMenuOpen(false)}
              >
                PBJ Converter
              </a>
            </div>
          )}
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 md:py-6">
        {/* Hero Section - Polished Header */}
        <div className="text-center mb-4 md:mb-5">
          {/* HeaderContainer: Single flex row with perfect alignment */}
          <div className="flex items-center justify-center gap-3 mb-3 py-2" style={{ lineHeight: '1.5' }}>
            {/* AvatarWrapper: Reduced size ~10%, nudged down 2px for optical alignment with text baseline */}
            <div className="relative w-10 h-10 md:w-11 md:h-11 rounded-lg overflow-visible flex-shrink-0" style={{ transform: 'translateY(2px)', opacity: 0.9 }}>
              <WrappedImage
                src={getAssetPath('/images/phoebe-wrapped-wide.png')}
                alt="PBJ Wrapped"
                className="w-full h-full"
                style={{
                  objectFit: 'contain',
                  objectPosition: 'center bottom',
                }}
              />
            </div>
            {/* TitleText: Optically aligned with avatar centerline */}
            <h1 className="text-2xl md:text-3xl lg:text-4xl font-bold bg-gradient-to-r from-blue-300 via-blue-200 to-blue-100 bg-clip-text text-transparent leading-none">
              PBJ Wrapped 2025
            </h1>
          </div>
        </div>

        {/* Interactive Map Section */}
        <div className="mb-4 md:mb-5">
          <div className="bg-black/40 backdrop-blur-sm border-2 border-blue-500/30 rounded-xl p-3 md:p-4 pt-4 md:pt-6 shadow-2xl relative">
            {/* USA Wrapped Button - Centered above map */}
            <div className="absolute top-2 left-1/2 -translate-x-1/2 z-20">
              <button
                onClick={() => navigate('/wrapped/usa')}
                className="bg-gradient-to-r from-blue-600 via-blue-500 to-blue-600 hover:from-blue-500 hover:via-blue-400 hover:to-blue-500 text-white font-bold py-2.5 px-6 md:py-3 md:px-8 rounded-lg text-sm md:text-base transition-all duration-300 shadow-2xl hover:shadow-blue-500/50 hover:scale-105 active:scale-95 transform relative overflow-hidden"
                style={{
                  background: 'linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%)',
                  boxShadow: '0 4px 15px rgba(96, 165, 250, 0.3)',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.transform = 'translateY(-2px)';
                  e.currentTarget.style.boxShadow = '0 6px 20px rgba(96, 165, 250, 0.4)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.boxShadow = '0 4px 15px rgba(96, 165, 250, 0.3)';
                }}
              >
                <span className="relative z-10">USA Wrapped</span>
              </button>
            </div>
            <div className="mt-12 md:mt-14">
              <USMap className="w-full" />
            </div>
          </div>
        </div>

        {/* Quick Actions - State and Region in same row */}
        <div className="grid grid-cols-2 md:grid-cols-2 gap-3 md:gap-4 mb-4 md:mb-5">
          {/* State Dropdown */}
          <div className="bg-black/40 backdrop-blur-sm border-2 border-blue-500/30 rounded-xl p-3 md:p-4">
            <label className="block text-xs md:text-sm font-semibold text-blue-300 mb-2">
              Select a State
            </label>
            <select
              value={selectedState}
              onChange={(e) => {
                setSelectedState(e.target.value);
                handleStateSelect(e.target.value);
              }}
              className="w-full px-3 py-2 text-sm bg-gray-800/50 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent appearance-none cursor-pointer"
            >
              <option value="">Choose a state...</option>
              {states.map((state) => (
                <option key={state.code} value={state.code}>
                  {state.name} ({state.code})
                </option>
              ))}
            </select>
          </div>

          {/* Region Dropdown */}
          <div className="bg-black/40 backdrop-blur-sm border-2 border-blue-500/30 rounded-xl p-3 md:p-4">
            <label className="block text-xs md:text-sm font-semibold text-blue-300 mb-2">
              Select a CMS Region
            </label>
            <select
              value={selectedRegion}
              onChange={(e) => {
                setSelectedRegion(e.target.value);
                if (e.target.value) {
                  handleRegionSelect(parseInt(e.target.value));
                }
              }}
              className="w-full px-3 py-2 text-sm bg-gray-800/50 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent appearance-none cursor-pointer"
            >
              <option value="">Choose a region...</option>
              {regions.map((region) => (
                <option key={region.num} value={region.num.toString()}>
                  Region {region.num} — {region.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Footer */}
        <footer className="mt-6 md:mt-8 pt-6 md:pt-8 text-center" style={{ background: '#0f172a', padding: '40px 20px', marginTop: '60px' }}>
          <p style={{ color: 'rgba(255,255,255,0.7)', margin: '0 auto', fontStyle: 'italic', lineHeight: '1.6', textAlign: 'center', maxWidth: '800px' }}>
            The <strong>PBJ Dashboard</strong> is a free public resource providing longitudinal staffing data at 15,000 US nursing homes. It has been featured in <a href="https://www.publichealth.columbia.edu/news/alumni-make-data-shine-public-health-dashboards" target="_blank" rel="noopener noreferrer" style={{ color: '#60a5fa', textDecoration: 'none' }}>Columbia Public Health</a>, <a href="https://www.retirementlivingsourcebook.com/videos/why-nursing-home-staffing-data-matters-for-1-2-million-residents-and-beyond" target="_blank" rel="noopener noreferrer" style={{ color: '#60a5fa', textDecoration: 'none' }}>Positive Aging</a>, and <a href="https://aginginamerica.news/2025/09/16/crunching-the-nursing-home-data/" target="_blank" rel="noopener noreferrer" style={{ color: '#60a5fa', textDecoration: 'none' }}>Aging in America News</a>.
          </p>
          <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', margin: '1.5rem auto 0', paddingTop: '1.5rem', maxWidth: '800px' }}>
            <p style={{ margin: 0, color: 'rgba(255,255,255,0.6)', fontStyle: 'italic', fontSize: '0.9rem', textAlign: 'center' }}>
              <a href="https://www.320insight.com" style={{ color: 'rgba(255,255,255,0.6)', textDecoration: 'none' }}>320 Consulting — Turning Spreadsheets into Stories</a>
            </p>
          </div>
        </footer>
      </div>
    </div>
  );
};

export default Index;
