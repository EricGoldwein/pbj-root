import React from 'react';
import { WrappedCard } from '../WrappedCard';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';
import { trackFacilityLinkClick } from '../../../utils/analytics';

interface StateFacilitySpotlightCardProps {
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
  'ok': 'Oklahoma', 'or': 'Oregon', 'pa': 'Pennsylvania', 'pr': 'Puerto Rico', 'ri': 'Rhode Island', 'sc': 'South Carolina',
  'sd': 'South Dakota', 'tn': 'Tennessee', 'tx': 'Texas', 'ut': 'Utah', 'vt': 'Vermont',
  'va': 'Virginia', 'wa': 'Washington', 'wv': 'West Virginia', 'wi': 'Wisconsin', 'wy': 'Wyoming',
  'dc': 'District of Columbia'
};

function getStateFullName(abbr: string): string {
  const lowerAbbr = abbr.toLowerCase();
  const fullName = STATE_ABBR_TO_NAME[lowerAbbr];
  if (fullName) {
    return fullName;
  }
  const foundEntry = Object.entries(STATE_ABBR_TO_NAME).find(([_, name]) => 
    name.toLowerCase() === lowerAbbr
  );
  if (foundEntry) {
    return foundEntry[1];
  }
  const words = abbr.split(' ');
  return words.map((word, index) => {
    const lowerWord = word.toLowerCase();
    if (lowerWord === 'of' && index > 0 && index < words.length - 1) {
      return 'of';
    }
    return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
  }).join(' ');
}

/**
 * Break facility name into two lines more evenly
 * Tries to break before common phrases like "Rehabilitation Center"
 */
function breakFacilityName(name: string): { line1: string; line2: string } {
  const commonPhrases = [
    'Rehabilitation Center',
    'Rehab Center',
    'Nursing Center',
    'Care Center',
    'Health Center',
    'Medical Center',
    'Living Center',
    'Rehabilitation',
    'Healthcare',
    'Health Care'
  ];
  
  // Try to find a common phrase at the end
  for (const phrase of commonPhrases) {
    const index = name.lastIndexOf(phrase);
    if (index > 0) {
      // Found a phrase, break before it
      const line1 = name.substring(0, index).trim();
      const line2 = name.substring(index).trim();
      // Only break if both parts have reasonable length (at least 3 chars)
      if (line1.length >= 3 && line2.length >= 3) {
        return { line1, line2 };
      }
    }
  }
  
  // If no common phrase found, try to break at "and" if it's near the middle
  const andIndex = name.indexOf(' and ');
  if (andIndex > 5 && andIndex < name.length - 10) {
    const line1 = name.substring(0, andIndex + 4).trim(); // Include "and"
    const line2 = name.substring(andIndex + 5).trim();
    if (line1.length >= 3 && line2.length >= 3) {
      return { line1, line2 };
    }
  }
  
  // Fallback: split roughly in the middle
  const words = name.split(' ');
  if (words.length > 1) {
    const mid = Math.floor(words.length / 2);
    const line1 = words.slice(0, mid).join(' ');
    const line2 = words.slice(mid).join(' ');
    return { line1, line2 };
  }
  
  // Single word or empty - don't break
  return { line1: name, line2: '' };
}

export const StateFacilitySpotlightCard: React.FC<StateFacilitySpotlightCardProps> = ({ data }) => {
  if (data.scope !== 'state' || !data.spotlightFacility) {
    return null;
  }

  const facility = data.spotlightFacility;
  
  // Get location name for subtitle
  const stateFullName = getStateFullName(data.name);
  const subtitleText = `A ${stateFullName} facility with staffing below benchmarks`;
  
  // Break facility name for better display
  const { line1, line2 } = breakFacilityName(facility.name);

  const formatHPRD = (num: number, decimals: number = 2): string => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const formatPercent = (num: number, decimals: number = 1): string => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  return (
    <WrappedCard title="" hideBadge>
      <div className="space-y-3 text-left">
        <h2 className="text-2xl md:text-3xl font-bold text-center mb-3 text-white">
          Phoebe J's PBJ <span className="text-blue-300">Spotlight</span>
        </h2>
        <p className="text-xs text-gray-400 text-center mb-3">
          {subtitleText}
        </p>

        {/* Facility Name */}
        <div className="pb-2 border-b border-gray-700">
          <h3 className="text-lg md:text-xl font-bold text-white mb-1 text-center">
            {line2 ? (
              <>
                {line1}
                <br />
                {line2}
              </>
            ) : (
              line1
            )}
          </h3>
        </div>

        {/* Status Badges */}
        <div className="flex flex-wrap gap-2 pb-2 border-b border-gray-700 items-center">
          {facility.sffStatus && (
            <span className={`inline-block px-2 py-1 text-xs font-semibold rounded ${
              facility.sffStatus === 'SFF' 
                ? 'bg-orange-500/20 text-orange-300'
                : 'bg-yellow-500/20 text-yellow-300'
            }`}>
              {facility.sffStatus}
            </span>
          )}
          {facility.ownershipType && (
            <span className="inline-block px-2 py-1 text-xs font-semibold rounded bg-gray-700/50 text-gray-300">
              {facility.ownershipType}
            </span>
          )}
          {facility.city && (
            <span className="inline-block px-2 py-1 text-xs font-semibold rounded bg-purple-500/20 text-purple-300">
              {facility.city}
            </span>
          )}
          {facility.census !== undefined && facility.census > 0 && (
            <span className="inline-block px-2 py-1 text-xs font-semibold rounded bg-blue-500/20 text-blue-300">
              Census: {facility.census.toLocaleString()}
            </span>
          )}
        </div>

        {/* Key Metrics */}
        <div className="space-y-2">
          <div className="flex justify-between items-center py-1.5 border-b border-gray-700">
            <span className="text-gray-300 text-sm">Total Nurse HPRD (reported)</span>
            <span className="text-white font-bold text-base">{formatHPRD(facility.totalHPRD)}</span>
          </div>
          
          <div className="flex justify-between items-center py-1.5 border-b border-gray-700">
            <span className="text-gray-300 text-sm">Case-Mix (expected)</span>
            <span className="text-gray-400 font-semibold text-base">{formatHPRD(facility.caseMixExpectedHPRD)}</span>
          </div>
          
          <div className="flex justify-between items-center py-1.5 border-b border-gray-700">
            <span className="text-gray-300 text-sm">% Case-Mix</span>
            <span className="text-red-400 font-bold text-base">
              {facility.caseMixExpectedHPRD > 0 
                ? formatPercent((facility.totalHPRD / facility.caseMixExpectedHPRD) * 100, 1) + '%'
                : 'N/A'}
            </span>
          </div>
          
          {/* Only show QoQ Change if staffing decreased (negative qoqChange) */}
          {facility.qoqChange < 0 && (
            <div className="flex justify-between items-center py-1.5 border-b border-gray-700">
              <span className="text-gray-300 text-sm">QoQ Change</span>
              <span className="text-red-400 font-bold text-base flex items-center gap-1">
                <span>↓</span>
                {formatHPRD(Math.abs(facility.qoqChange))}
              </span>
            </div>
          )}
        </div>

        {/* Staffing Composition */}
        <div className="pt-2 space-y-1.5 border-t border-gray-700">
          <div className="flex justify-between items-center">
            <span className="text-gray-400 text-xs">RN HPRD</span>
            <span className="text-gray-300 text-xs font-semibold">{formatHPRD(facility.rnHPRD)}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-gray-400 text-xs">CNA HPRD</span>
            <span className="text-gray-300 text-xs font-semibold">{formatHPRD(facility.cnaHPRD)}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-gray-400 text-xs">% Contract Staff</span>
            <span className="text-gray-300 text-xs font-semibold">{formatPercent(facility.contractPercent)}%</span>
          </div>
        </div>

        {/* CTA */}
        <div className="pt-3 mt-3 border-t border-gray-700">
          <a
            href={facility.link}
            target="_blank"
            rel="noopener noreferrer"
            className="block w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-all duration-200 text-center shadow-lg hover:shadow-xl text-sm"
            onClick={() => trackFacilityLinkClick(facility.provnum, facility.name, 'State Facility Spotlight')}
          >
            View Provider's PBJ Dashboard →
          </a>
        </div>
      </div>
    </WrappedCard>
  );
};

