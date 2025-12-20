import React from 'react';
import { WrappedCard } from '../WrappedCard';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';
import { useAnimatedNumber } from '../../../hooks/useAnimatedNumber';

interface USANationalScaleCardProps {
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
  return STATE_ABBR_TO_NAME[abbr.toLowerCase()] || abbr.toUpperCase();
}

export const USANationalScaleCard: React.FC<USANationalScaleCardProps> = ({ data }) => {
  if (data.scope !== 'usa') {
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

  // Get lowest and highest states - verify which is which
  const topStateCandidate = data.extremes.topStatesByHPRD?.[0];
  const bottomStateCandidate = data.extremes.bottomStatesByHPRD?.[0];
  
  // Determine which is actually lowest and highest by comparing values
  const lowestState = topStateCandidate && bottomStateCandidate
    ? (topStateCandidate.value < bottomStateCandidate.value ? topStateCandidate : bottomStateCandidate)
    : bottomStateCandidate || topStateCandidate;
  const highestState = topStateCandidate && bottomStateCandidate
    ? (topStateCandidate.value > bottomStateCandidate.value ? topStateCandidate : bottomStateCandidate)
    : topStateCandidate || bottomStateCandidate;
  
  const bottomState = lowestState; // Lowest HPRD (e.g., Illinois)
  const topState = highestState; // Highest HPRD (e.g., Alaska)
  const stateRange = topState && bottomState 
    ? (topState.value - bottomState.value).toFixed(2)
    : null;

  return (
    <WrappedCard title="The National Picture" hideBadge>
      <div className="space-y-4 md:space-y-5 text-center">
        <div className="space-y-3 md:space-y-4">
          <p className="text-gray-200 text-base md:text-lg lg:text-xl leading-relaxed">
            In Q2 2025, nursing homes across the United States had
          </p>
          
          <div className="flex flex-col items-center gap-1.5 md:gap-2 py-3 md:py-4">
            <div className="text-4xl md:text-5xl lg:text-6xl font-bold text-white">
              {formatNumber(animatedResidents)}
            </div>
            <div className="text-gray-300 text-base md:text-lg">residents daily</div>
          </div>
          
          <p className="text-gray-200 text-base md:text-lg lg:text-xl leading-relaxed">
            across <strong className="text-white text-xl md:text-2xl lg:text-3xl">{formatNumber(animatedFacilities)}</strong> nursing homes
          </p>
        </div>

        <div className="pt-3 md:pt-4 border-t border-gray-600 space-y-3 md:space-y-4">
          <div className="space-y-1.5 md:space-y-2">
            <div className="text-gray-300 text-xs md:text-sm uppercase tracking-wide">National Average Staffing</div>
            <div className="text-3xl md:text-4xl lg:text-5xl font-bold text-white">
              {formatNumber(animatedHPRD, 2)} HPRD
            </div>
          </div>
          
          {stateRange && topState && bottomState && (
            <div className="pt-2 md:pt-3 space-y-1.5 md:space-y-2">
              <div className="text-gray-400 text-sm">State Range</div>
              <div className="flex items-center justify-center gap-3 text-sm">
                <div className="px-3 py-1.5 bg-orange-500/10 border border-orange-500/30 rounded">
                  <div className="text-orange-300 font-semibold">{getStateFullName(bottomState.state)}</div>
                  <div className="text-white">{bottomState.value.toFixed(2)}</div>
                </div>
                <div className="text-gray-500">to</div>
                <div className="px-3 py-1.5 bg-green-500/10 border border-green-500/30 rounded">
                  <div className="text-green-300 font-semibold">{getStateFullName(topState.state)}</div>
                  <div className="text-white">{topState.value.toFixed(2)}</div>
                </div>
              </div>
              <div className="text-xs text-gray-500 pt-1">
                A difference of {stateRange} HPRD between lowest and highest states
              </div>
            </div>
          )}
        </div>
      </div>
    </WrappedCard>
  );
};

