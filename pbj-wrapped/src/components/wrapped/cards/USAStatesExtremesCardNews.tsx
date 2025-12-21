import React from 'react';
import { useNavigate } from 'react-router-dom';
import { WrappedCard } from '../WrappedCard';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';

interface USAStatesExtremesCardNewsProps {
  data: PBJWrappedData;
}

// State abbreviation to full name mapping
const STATE_ABBR_TO_NAME: Record<string, string> = {
  'al': 'Alabama', 'ak': 'Alaska', 'az': 'Arizona', 'ar': 'Arkansas', 'ca': 'California',
  'co': 'Colorado', 'ct': 'Connecticut', 'de': 'Delaware', 'fl': 'Florida', 'ga': 'Georgia',
  'hi': 'Hawaii', 'id': 'Idaho', 'il': 'Illinois', 'in': 'Indiana', 'ia': 'Iowa',
  'ks': 'Kansas', 'ky': 'Kentucky', 'la': 'Louisiana', 'me': 'Maine', 'md': 'Maryland',
  'ma': 'Massachusetts', 'mi': 'Michigan', 'mn': 'Minnesota', 'ms': 'Mississippi', 'mo': 'Missouri',
  'mt': 'Montana', 'ne': 'Nebraska', 'nv': 'Nevada', 'nh': 'New Hampshire', 'nj': 'New Jersey',
  'nm': 'New Mexico', 'ny': 'New York', 'nc': 'North Carolina', 'nd': 'North Dakota', 'oh': 'Ohio',
  'ok': 'Oklahoma', 'or': 'Oregon', 'pa': 'Pennsylvania', 'ri': 'Rhode Island', 'sc': 'South Carolina',
  'sd': 'South Dakota', 'tn': 'Tennessee', 'tx': 'Texas', 'ut': 'Utah', 'vt': 'Vermont',
  'va': 'Virginia', 'wa': 'Washington', 'wv': 'West Virginia', 'wi': 'Wisconsin', 'wy': 'Wyoming',
  'dc': 'District of Columbia'
};

function getStateFullName(abbr: string): string {
  const lowerAbbr = abbr.toLowerCase();
  return STATE_ABBR_TO_NAME[lowerAbbr] || abbr.toUpperCase();
}

export const USAStatesExtremesCardNews: React.FC<USAStatesExtremesCardNewsProps> = ({ data }) => {
  const navigate = useNavigate();
  
  const formatNumber = (num: number, decimals: number = 2): string => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const bottomStates = data.extremes.bottomStatesByHPRD?.slice(0, 3) || [];
  const topStates = data.extremes.topStatesByHPRD?.slice(0, 3) || [];

  const renderState = (state: typeof bottomStates[0], rank: number, isBottom: boolean) => {
    const stateName = getStateFullName(state.state);
    const isInternalLink = state.link.startsWith('/wrapped/');
    
    const handleStateClick = (e: React.MouseEvent) => {
      if (isInternalLink) {
        e.preventDefault();
        navigate(state.link);
      }
    };
    
    return (
      <div key={state.provnum} className="flex justify-between items-center py-2 border-b border-gray-700 last:border-0">
        <div className="flex items-center gap-3">
          <div className={`text-2xl md:text-3xl font-bold ${isBottom ? 'text-red-400' : 'text-green-400'}`}>
            #{rank}
          </div>
          {isInternalLink ? (
            <a
              href={state.link}
              onClick={handleStateClick}
              className="text-blue-300 hover:text-blue-200 underline font-semibold text-base md:text-lg cursor-pointer"
            >
              {stateName}
            </a>
          ) : (
            <a
              href={state.link}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-300 hover:text-blue-200 underline font-semibold text-base md:text-lg"
            >
              {stateName}
            </a>
          )}
        </div>
        <div className="text-right">
          <div className={`text-xl md:text-2xl font-bold ${isBottom ? 'text-red-300' : 'text-green-300'}`}>
            {formatNumber(state.value)}
          </div>
          <div className="text-xs text-gray-500">HPRD</div>
        </div>
      </div>
    );
  };

  return (
    <WrappedCard title="Accountability Snapshot" hideBadge>
      <div className="space-y-4 text-left">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <h4 className="text-sm font-bold text-red-400 uppercase tracking-wide mb-3">
              Consistently Understaffed
            </h4>
            <div className="space-y-1">
              {bottomStates.map((state, idx) => renderState(state, idx + 1, true))}
            </div>
          </div>
          <div>
            <h4 className="text-sm font-bold text-green-400 uppercase tracking-wide mb-3">
              Highest Staffing
            </h4>
            <div className="space-y-1">
              {topStates.map((state, idx) => renderState(state, idx + 1, false))}
            </div>
          </div>
        </div>
        <p className="text-xs text-gray-500 text-center pt-2 border-t border-gray-700">
          Source: CMS PBJ Q2 2025
        </p>
      </div>
    </WrappedCard>
  );
};

