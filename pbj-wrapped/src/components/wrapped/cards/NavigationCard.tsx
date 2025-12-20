import React from 'react';
import { useNavigate } from 'react-router-dom';
import { WrappedCard } from '../WrappedCard';
import { WrappedImage } from '../WrappedImage';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';
import { getAssetPath } from '../../../utils/assets';

interface NavigationCardProps {
  data: PBJWrappedData;
  onReplay: () => void;
}

export const NavigationCard: React.FC<NavigationCardProps> = ({ data, onReplay }) => {
  const navigate = useNavigate();

  const handleStateSelect = () => {
    navigate('/');
  };

  const handleUSA = () => {
    navigate('/usa');
  };

  const handleReport = () => {
    window.open('https://pbj320.com/report', '_blank');
  };

  // Get display name for replay button
  const getReplayLabel = () => {
    if (data.scope === 'state') {
      const stateAbbrToName: Record<string, string> = {
        'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
        'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia',
        'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa',
        'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
        'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi', 'MO': 'Missouri',
        'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey',
        'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio',
        'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
        'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont',
        'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming',
        'DC': 'District of Columbia'
      };
      return stateAbbrToName[data.name.toUpperCase()] || data.name;
    } else if (data.scope === 'region') {
      return data.name;
    } else {
      return 'USA';
    }
  };

  return (
    <WrappedCard title="Explore More" hideBadge>
      <div className="mb-4 flex justify-center">
        <WrappedImage 
          src={getAssetPath('/images/phoebe-wrapped-wide.png')} 
          alt="PBJ Wrapped" 
          className="max-w-[140px] md:max-w-[160px] h-auto opacity-85"
        />
      </div>
      <div className="space-y-3">
        {/* Replay button - primary action */}
        <button
          onClick={onReplay}
          className="w-full py-3 md:py-3.5 px-4 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-600 text-white font-semibold rounded-lg transition-all duration-200 text-sm shadow-lg hover:shadow-xl hover:scale-[1.02] active:scale-[0.98] touch-manipulation flex items-center justify-center gap-2"
          style={{ minHeight: '48px' }}
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span>Replay {getReplayLabel()}</span>
        </button>
        
        {/* Secondary actions */}
        <div className="space-y-2">
          {data.scope !== 'usa' && (
            <button
              onClick={handleUSA}
              className="w-full py-2.5 md:py-3 px-4 bg-blue-500/20 hover:bg-blue-500/30 border border-blue-500/50 hover:border-blue-400 text-blue-300 font-medium rounded-lg transition-all duration-200 text-sm hover:scale-[1.01] active:scale-[0.99] touch-manipulation"
              style={{ minHeight: '44px' }}
            >
              View USA Wrapped
            </button>
          )}
          
          <button
            onClick={handleStateSelect}
            className="w-full py-2.5 md:py-3 px-4 bg-gray-700/50 hover:bg-gray-600/60 border border-gray-600/50 hover:border-gray-500 text-gray-200 font-medium rounded-lg transition-all duration-200 text-sm hover:scale-[1.01] active:scale-[0.99] touch-manipulation"
            style={{ minHeight: '44px' }}
          >
            Choose Another State or Region
          </button>
          
          <button
            onClick={handleReport}
            className="w-full py-2.5 md:py-3 px-4 bg-gray-700/50 hover:bg-gray-600/60 border border-gray-600/50 hover:border-gray-500 text-gray-200 font-medium rounded-lg transition-all duration-200 text-sm hover:scale-[1.01] active:scale-[0.99] touch-manipulation"
            style={{ minHeight: '44px' }}
          >
            View Full Report
          </button>
        </div>
      </div>
    </WrappedCard>
  );
};

