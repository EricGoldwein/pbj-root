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
  const [searchQuery, setSearchQuery] = useState('');
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

  const filteredStates = states.filter(state =>
    state.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    state.code.toLowerCase().includes(searchQuery.toLowerCase())
  );

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
                href="https://pbj320.com/report" 
                className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-200 shadow-md hover:shadow-lg whitespace-nowrap"
              >
                Sign Up
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
                href="https://pbj320.com/report" 
                className="block px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-center font-semibold transition-colors"
                onClick={() => setMobileMenuOpen(false)}
              >
                Sign Up
              </a>
            </div>
          )}
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 md:py-6">
        {/* Hero Section */}
        <div className="text-center mb-4 md:mb-6">
          <div className="flex justify-center mb-3 md:mb-4">
            <WrappedImage
              src={getAssetPath('/images/phoebe-wrapped-wide.png')}
              alt="PBJ Wrapped"
              className="max-w-[200px] md:max-w-[280px] h-auto"
            />
          </div>
          <h1 className="text-3xl md:text-4xl lg:text-5xl font-bold mb-2 md:mb-3 bg-gradient-to-r from-blue-300 via-blue-200 to-blue-100 bg-clip-text text-transparent">
            PBJ Wrapped — Q2 2025
          </h1>
          <p className="text-base md:text-lg text-gray-300 max-w-2xl mx-auto mb-2">
            Explore nursing home staffing data across the United States
          </p>
        </div>

        {/* Interactive Map Section */}
        <div className="mb-4 md:mb-6">
          <h2 className="text-xl md:text-2xl font-bold mb-2 md:mb-3 text-blue-300 text-center">
            Click a State to Explore
          </h2>
          <div className="bg-black/40 backdrop-blur-sm border-2 border-blue-500/30 rounded-xl p-3 md:p-4 shadow-2xl">
            <USMap className="w-full" />
            <p className="text-center text-gray-400 text-xs md:text-sm mt-2 md:mt-3">
              Hover over a state to see its name, then click to view its Q2 2025 staffing data
            </p>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="grid md:grid-cols-3 gap-3 md:gap-4 mb-4 md:mb-6">
          {/* USA Card */}
          <button
            onClick={() => navigate('/usa')}
            className="group bg-gradient-to-br from-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-600 text-white font-bold py-4 md:py-5 px-4 rounded-xl text-base md:text-lg transition-all duration-300 shadow-xl hover:shadow-2xl transform hover:-translate-y-1"
          >
            <div className="text-3xl md:text-4xl mb-2">🇺🇸</div>
            <div className="text-lg md:text-xl mb-1">United States</div>
            <div className="text-xs md:text-sm font-normal text-blue-100">National Overview</div>
          </button>

          {/* State Dropdown */}
          <div className="bg-black/40 backdrop-blur-sm border-2 border-blue-500/30 rounded-xl p-3 md:p-4">
            <label className="block text-xs md:text-sm font-semibold text-blue-300 mb-2">
              Or Select a State
            </label>
            <div className="space-y-2">
              <input
                type="text"
                placeholder="Search states..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full px-3 py-1.5 text-sm bg-gray-800/50 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <select
                value={selectedState}
                onChange={(e) => {
                  setSelectedState(e.target.value);
                  handleStateSelect(e.target.value);
                }}
                className="w-full px-3 py-2 text-sm bg-gray-800/50 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent appearance-none cursor-pointer"
              >
                <option value="">Choose a state...</option>
                {filteredStates.map((state) => (
                  <option key={state.code} value={state.code}>
                    {state.name} ({state.code})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Region Dropdown */}
          <div className="bg-black/40 backdrop-blur-sm border-2 border-blue-500/30 rounded-xl p-3 md:p-4">
            <label className="block text-xs md:text-sm font-semibold text-blue-300 mb-2">
              Or Select a CMS Region
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

        {/* Regions Grid */}
        <div className="mb-4 md:mb-6">
          <h2 className="text-xl md:text-2xl font-bold mb-2 md:mb-3 text-blue-300">
            CMS Regions
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 md:gap-3">
            {regions.map((region) => (
              <button
                key={region.num}
                onClick={() => navigate(`/region${region.num}`)}
                className="group bg-gray-700/50 hover:bg-blue-600/80 text-white font-semibold py-3 md:py-4 px-3 rounded-lg transition-all duration-200 hover:scale-105 hover:shadow-xl border border-gray-600/50 hover:border-blue-400"
              >
                <div className="text-base md:text-lg mb-0.5">Region {region.num}</div>
                <div className="text-xs md:text-sm text-gray-300 group-hover:text-white">{region.name}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Footer */}
        <footer className="mt-6 md:mt-8 pt-6 md:pt-8 border-t border-gray-700/50 text-center">
          <p className="text-gray-300 text-sm md:text-base mb-3 md:mb-4" style={{ color: 'rgba(255,255,255,0.7)', fontStyle: 'italic', lineHeight: '1.6', maxWidth: '800px', margin: '0 auto' }}>
            The <strong>PBJ Dashboard</strong> is a free public resource providing longitudinal staffing data at 15,000 US nursing homes. It has been featured in <a href="https://www.publichealth.columbia.edu/news/alumni-make-data-shine-public-health-dashboards" target="_blank" rel="noopener noreferrer" style={{ color: '#60a5fa', textDecoration: 'none' }}>Columbia Public Health</a>, <a href="https://www.retirementlivingsourcebook.com/videos/why-nursing-home-staffing-data-matters-for-1-2-million-residents-and-beyond" target="_blank" rel="noopener noreferrer" style={{ color: '#60a5fa', textDecoration: 'none' }}>Positive Aging</a>, and <a href="https://aginginamerica.news/2025/09/16/crunching-the-nursing-home-data/" target="_blank" rel="noopener noreferrer" style={{ color: '#60a5fa', textDecoration: 'none' }}>Aging in America News</a>.
          </p>
          <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', marginTop: '1.5rem', paddingTop: '1.5rem', maxWidth: '800px', marginLeft: 'auto', marginRight: 'auto' }}>
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
