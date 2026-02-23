import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { WrappedImage } from '../components/wrapped/WrappedImage';
import { USMap } from '../components/wrapped/USMap';
import { SiteNavbar } from '../components/SiteNavbar';
import { SiteFooter } from '../components/SiteFooter';
import { getAssetPath } from '../utils/assets';
import { updateSEO, getWrappedLandingSEO } from '../utils/seo';
import { trackDashboardLinkClick } from '../utils/analytics';

const Index: React.FC = () => {
  const navigate = useNavigate();
  const [selectedState, setSelectedState] = useState<string>('');
  const [selectedRegion, setSelectedRegion] = useState<string>('');

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
      <SiteNavbar onDashboardClick={() => trackDashboardLinkClick('Navigation', 'Index Page')} />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 md:py-6">
        {/* Hero Section - Polished Header */}
        <div className="text-center mb-4 md:mb-5">
          {/* HeaderContainer: Single flex row with perfect alignment */}
          <div className="flex items-center justify-center gap-3 mb-3 py-2" style={{ lineHeight: '1.5' }}>
            {/* AvatarWrapper: Reduced size ~10%, nudged down more for better alignment with text baseline */}
            <div className="relative w-10 h-10 md:w-11 md:h-11 rounded-lg overflow-visible flex-shrink-0" style={{ transform: 'translateY(6px)', opacity: 0.9 }}>
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
            <select
              value={selectedState}
              onChange={(e) => {
                setSelectedState(e.target.value);
                handleStateSelect(e.target.value);
              }}
              className="w-full px-3 py-2 text-sm bg-gray-900 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent appearance-none cursor-pointer hover:bg-gray-800/70"
            >
              <option value="">Select a state</option>
              {states.map((state) => (
                <option key={state.code} value={state.code}>
                  {state.name} ({state.code})
                </option>
              ))}
            </select>
          </div>

          {/* Region Dropdown */}
          <div className="bg-black/40 backdrop-blur-sm border-2 border-blue-500/30 rounded-xl p-3 md:p-4">
            <select
              value={selectedRegion}
              onChange={(e) => {
                setSelectedRegion(e.target.value);
                if (e.target.value) {
                  handleRegionSelect(parseInt(e.target.value));
                }
              }}
              className="w-full px-3 py-2 text-sm bg-gray-900 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent appearance-none cursor-pointer hover:bg-gray-800/70"
            >
              <option value="">Select a region</option>
              {regions.map((region) => (
                <option key={region.num} value={region.num.toString()}>
                  Region {region.num} — {region.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <SiteFooter />
      </div>
    </div>
  );
};

export default Index;
