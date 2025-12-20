import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { WrappedImage } from '../components/wrapped/WrappedImage';
import { USMap } from '../components/wrapped/USMap';
import { updateSEO, getWrappedLandingSEO } from '../utils/seo';
import { getAssetPath } from '../utils/assets';

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
      navigate(`/${stateCode.toLowerCase()}`);
    }
  };

  const handleRegionSelect = (regionNum: number) => {
    navigate(`/region${regionNum}`);
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
        {/* Hero Section - Enhanced */}
        <div className="text-center mb-4 md:mb-5">
          <div className="flex justify-center items-center gap-3 md:gap-4 mb-3">
            <div className="relative">
              <div className="absolute inset-0 bg-gradient-to-r from-blue-500 via-blue-400 to-blue-300 rounded-lg blur-sm opacity-50"></div>
              <div className="relative bg-gray-900/80 p-2 md:p-2.5 rounded-lg border-2 border-blue-400/60 shadow-xl">
                <WrappedImage
                  src={getAssetPath('/images/phoebe-wrapped-wide.png')}
                  alt="PBJ Wrapped"
                  className="h-8 md:h-10 w-auto"
                />
              </div>
            </div>
            <h1 className="text-2xl md:text-3xl lg:text-4xl font-bold bg-gradient-to-r from-blue-300 via-blue-200 to-blue-100 bg-clip-text text-transparent">
              Q2 2025
            </h1>
          </div>
        </div>

        {/* Interactive Map Section */}
        <div className="mb-4 md:mb-5">
          <div className="bg-black/40 backdrop-blur-sm border-2 border-blue-500/30 rounded-xl p-3 md:p-4 shadow-2xl relative">
            {/* USA Badge - positioned in top right */}
            <button
              onClick={() => navigate('/usa')}
              className="absolute top-3 right-3 md:top-4 md:right-4 z-10 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-600 text-white font-semibold py-1.5 px-3 md:py-2 md:px-4 rounded-lg text-xs md:text-sm transition-all duration-200 shadow-md hover:shadow-lg hover:scale-105 active:scale-95"
            >
              USA Wrapped
            </button>
            <USMap className="w-full" />
          </div>
        </div>

        {/* Quick Actions - State and Region in same row */}
        <div className="grid md:grid-cols-2 gap-3 md:gap-4 mb-4 md:mb-5">
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
