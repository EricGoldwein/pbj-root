import React from 'react';
import { WrappedCard } from '../WrappedCard';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';
import { useAnimatedNumber } from '../../../hooks/useAnimatedNumber';

interface StateOverviewCardProps {
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
  return STATE_ABBR_TO_NAME[abbr.toLowerCase()] || abbr;
}

export const StateOverviewCard: React.FC<StateOverviewCardProps> = ({ data }) => {
  if (data.scope !== 'state') {
    return null;
  }

  const formatNumber = (num: number, decimals: number = 0): string => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const animatedResidents = useAnimatedNumber(Math.round(data.avgDailyResidents), 1200, 0);
  const animatedFacilities = useAnimatedNumber(data.facilityCount, 1200, 0);
  const animatedHPRD = useAnimatedNumber(data.totalHPRD, 1200, 2);

  const rank = data.rankings.totalHPRDRank;
  const percentile = data.rankings.totalHPRDPercentile;
  const isTopHalf = percentile >= 50;

  // Convert state name to full name if it's an abbreviation
  const stateFullName = getStateFullName(data.name);

  return (
    <WrappedCard title={`${stateFullName} at a Glance`} hideBadge>
      <div className="space-y-3 md:space-y-4 text-center pb-2">
        <div className="space-y-1.5 md:space-y-2">
          <p className="text-gray-200 text-base md:text-lg leading-relaxed">
            In Q2 2025, <strong className="text-white text-xl md:text-2xl">{stateFullName}</strong> had
          </p>
          
          <div className="flex flex-col items-center gap-1 md:gap-1.5 py-2 md:py-2.5">
            <div className="text-3xl md:text-4xl lg:text-5xl font-bold text-white">
              {formatNumber(animatedResidents, 0)}
            </div>
            <div className="text-gray-300 text-sm md:text-base">residents daily</div>
          </div>
          
          <p className="text-gray-200 text-sm md:text-base leading-relaxed">
            across <strong className="text-white text-lg md:text-xl lg:text-2xl">{formatNumber(animatedFacilities)}</strong> nursing homes
          </p>
        </div>

        <div className="pt-2 md:pt-3 border-t border-gray-600 space-y-2 md:space-y-3">
          <div className="space-y-1 md:space-y-1.5">
            <div className="text-gray-300 text-xs uppercase tracking-wide">Staffing Level</div>
            <div className="text-2xl md:text-3xl lg:text-4xl font-bold text-white">
              {formatNumber(animatedHPRD, 2)} HPRD
            </div>
          </div>
          
          <div className="flex items-center justify-center pt-1">
            <div className={`px-4 py-2 rounded-lg border-2 ${
              isTopHalf 
                ? 'bg-green-500/10 border-green-500/50' 
                : 'bg-orange-500/10 border-orange-500/50'
            }`}>
              <div className="text-xs text-gray-400 mb-0.5">National Rank</div>
              <div className={`text-2xl font-bold ${
                isTopHalf ? 'text-green-300' : 'text-orange-300'
              }`}>
                #{rank}
              </div>
              <div className="text-xs text-gray-500 mt-0.5">of 51 states</div>
            </div>
          </div>
        </div>
      </div>
    </WrappedCard>
  );
};

