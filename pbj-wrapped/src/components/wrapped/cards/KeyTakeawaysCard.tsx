import React from 'react';
import { WrappedCard } from '../WrappedCard';
import { getAssetPath } from '../../../utils/assets';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';

interface KeyTakeawaysCardProps {
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
  // If it's already a full state name, return it with proper case
  const lowerAbbr = abbr.toLowerCase();
  const fullName = STATE_ABBR_TO_NAME[lowerAbbr];
  if (fullName) {
    return fullName;
  }
  // If it's a full state name (not an abbreviation), try to find it
  const foundEntry = Object.entries(STATE_ABBR_TO_NAME).find(([_, name]) => 
    name.toLowerCase() === lowerAbbr
  );
  if (foundEntry) {
    return foundEntry[1]; // Return the properly cased name
  }
  // Fallback: try to title case the input, handling special cases
  const words = abbr.split(' ');
  return words.map((word, index) => {
    const lowerWord = word.toLowerCase();
    // Handle special cases
    if (lowerWord === 'of' && index > 0 && index < words.length - 1) {
      return 'of'; // Keep "of" lowercase in "District of Columbia"
    }
    return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
  }).join(' ');
}

export const KeyTakeawaysCard: React.FC<KeyTakeawaysCardProps> = ({ data }) => {
  const formatNumber = (num: number, decimals: number = 0): string => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const formatHPRD = (num: number): string => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  };

  // Generate conversational takeaways with JSX formatting
  const renderTakeaway = () => {
    if (data.scope === 'usa') {
      const trends = data.trends;
      const nurseAideChange = 'nurseAideHPRDChange' in trends ? trends.nurseAideHPRDChange : undefined;
      
      // Find the most noticeable national trend (largest absolute change)
      // Exclude contract staff and SFF - prioritize staffing metrics
      // Ensure all values are numbers (not null/undefined)
      const trendMetrics: Array<{ name: string; value: number; label: string; isPercent?: boolean }> = [
        { name: 'total staff', value: typeof trends.totalHPRDChange === 'number' ? trends.totalHPRDChange : 0, label: 'Total HPRD' },
        { name: 'direct care', value: typeof trends.directCareHPRDChange === 'number' ? trends.directCareHPRDChange : 0, label: 'Direct Care HPRD' },
        { name: 'RN staff', value: typeof trends.rnHPRDChange === 'number' ? trends.rnHPRDChange : 0, label: 'RN HPRD' },
        ...(nurseAideChange !== undefined && typeof nurseAideChange === 'number'
          ? [{ name: 'nurse aide', value: nurseAideChange, label: 'Nurse Aide HPRD' }]
          : []
        ),
      ];
      
      // Sort by absolute value to find most noticeable change
      const sortedTrends = [...trendMetrics].sort((a, b) => {
        const aValue = typeof a.value === 'number' ? a.value : 0;
        const bValue = typeof b.value === 'number' ? b.value : 0;
        return Math.abs(bValue) - Math.abs(aValue);
      });
      const mostNoticeable = sortedTrends[0];
      
      const facilityCount = formatNumber(data.facilityCount);
      const residentCount = Math.round(data.avgDailyResidents);
      const residentCountFormatted = residentCount >= 1000000 
        ? `${(residentCount / 1000000).toFixed(1)} million`
        : formatNumber(residentCount, 0);
      
      const totalHPRDValue = typeof data.totalHPRD === 'number' ? data.totalHPRD : 0;
      
      // Check for ownership disparity
      const hasOwnershipDisparity = data.ownership?.forProfit?.medianHPRD !== undefined && 
                                   data.ownership?.nonProfit?.medianHPRD !== undefined &&
                                   data.ownership.forProfit.medianHPRD < data.ownership.nonProfit.medianHPRD - 0.2;
      
      return (
        <>
          <p className="mb-2">
            Nationwide, PBJ reports <strong className="text-white">{facilityCount}</strong> nursing homes and <strong className="text-white">{residentCountFormatted}</strong> residents in the United States with a ratio of <strong className="text-white">{formatHPRD(totalHPRDValue)}</strong> staffing hours per resident day.
          </p>
          {hasOwnershipDisparity && data.ownership && (
            <p className="mb-2">
              For-profit facilities average <strong className="text-white">{formatHPRD(data.ownership.forProfit.medianHPRD!)} HPRD</strong>, while non-profits average <strong className="text-white">{formatHPRD(data.ownership.nonProfit.medianHPRD!)} HPRD</strong>. The ownership model directly impacts staffing levels.
            </p>
          )}
          {mostNoticeable && typeof mostNoticeable.value === 'number' && !isNaN(mostNoticeable.value) && Math.abs(mostNoticeable.value) > 0.01 && (() => {
            const value = mostNoticeable.value;
            return (
            <p className="mb-2">
                From Q1 to Q2 2025, <strong className="text-white">{mostNoticeable.name}</strong> {value > 0 ? 'increased' : 'decreased'} by{' '}
                <strong className={value > 0 ? 'text-white' : 'text-white'}>
                {mostNoticeable.isPercent 
                    ? `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
                    : `${value > 0 ? '+' : ''}${formatHPRD(Math.abs(value))} HPRD`
                }
              </strong>.
            </p>
            );
          })()}
        </>
      );
    } else if (data.scope === 'state') {
      const stateName = data.name;
      const stateFullName = getStateFullName(stateName);
      const rnRank = data.rankings.rnHPRDRank;
      const totalRank = data.rankings.totalHPRDRank;
      const trend = typeof data.trends.totalHPRDChange === 'number' ? data.trends.totalHPRDChange : 0;
      const rnHPRDValue = typeof data.rnHPRD === 'number' ? data.rnHPRD : 0;
      const totalHPRDValue = typeof data.totalHPRD === 'number' ? data.totalHPRD : 0;
      
      return (
        <>
          <p className="mb-2">
            <strong className="text-white">{stateFullName}</strong> ranks{' '}
            <strong className="text-white">
              #{rnRank} of 51
            </strong>
            {' '}for RN (<strong className="text-white">{formatHPRD(rnHPRDValue)} HPRD</strong>) and{' '}
            <strong className="text-white">
              #{totalRank}
            </strong>
            {' '}for total (<strong className="text-white">{formatHPRD(totalHPRDValue)} HPRD</strong>).
          </p>
          {data.compliance && data.compliance.facilitiesBelowTotalMinimum > 0 && (
            <p className="mb-2">
              In Q2 2025, <strong className="text-red-300">{data.compliance.facilitiesBelowTotalMinimum}</strong> of {stateFullName}'s facilities ({data.compliance.facilitiesBelowTotalMinimumPercent}%) fell below the state minimum of <strong className="text-white">{data.stateMinimum?.minHPRD.toFixed(2)} HPRD</strong>.
            </p>
          )}
          {trend !== 0 && (
            <p className="mb-2">
              Staffing {trend > 0 ? (
                <>increased from Q1 to Q2 by <strong className="text-white">{formatHPRD(trend)} HPRD</strong>.</>
              ) : (
                <>decreased from Q1 to Q2 by <strong className="text-white">{formatHPRD(Math.abs(trend))} HPRD</strong>.</>
              )}
            </p>
          )}
          {data.compliance && data.compliance.facilitiesBelowTotalMinimumPercent > 0 && data.compliance.facilitiesBelowTotalMinimumPercent >= 10 && (
            <p>
              <strong className="text-red-300">{data.compliance.facilitiesBelowTotalMinimumPercent}%</strong> of facilities fell below the state minimum staffing requirement.
            </p>
          )}
          {data.averageOverallRating !== undefined && (
            <p className="mt-2 text-sm text-gray-300">
              Average overall rating: <strong className="text-white">{data.averageOverallRating.toFixed(1)}★</strong>
            </p>
          )}
        </>
      );
    } else if (data.scope === 'region') {
      const biggestRiser = data.movers.risersByHPRD?.[0] as any;
      const biggestDecliner = data.movers.declinersByHPRD?.[0] as any;
      const trend = typeof data.trends.totalHPRDChange === 'number' ? data.trends.totalHPRDChange : 0;
      const totalHPRDValue = typeof data.totalHPRD === 'number' ? data.totalHPRD : 0;
      
      // Extract region number from identifier (e.g., "region1" -> "1")
      const regionNumber = data.identifier?.replace(/region/i, '') || '';
      const regionName = data.name; // e.g., "Boston"
      const displayName = regionNumber ? `CMS Region ${regionNumber} (${regionName})` : data.name;
      
      // Format resident count properly
      const residentCount = Math.round(data.avgDailyResidents);
      const residentCountFormatted = formatNumber(residentCount, 0);
      
      return (
        <>
          <p className="mb-2">
            <strong className="text-white">{displayName}</strong> reports <strong className="text-white">{formatNumber(data.facilityCount)}</strong> nursing homes and <strong className="text-white">{residentCountFormatted}</strong> residents with a regional staffing ratio of <strong className="text-white">{formatHPRD(totalHPRDValue)} HPRD</strong>.
            {data.averageOverallRating !== undefined && (
              <span className="block mt-1 text-sm text-gray-300">
                Average overall rating: <strong className="text-white">{data.averageOverallRating.toFixed(1)}★</strong>
              </span>
            )}
          </p>
          {trend !== 0 && (
            <p className="mb-2">
              {trend > 0 ? (
                <>Increased by <strong className="text-white">{formatHPRD(trend)} HPRD</strong> from Q1 to Q2.</>
              ) : (
                <>Decreased by <strong className="text-white">{formatHPRD(Math.abs(trend))} HPRD</strong> from Q1 to Q2.</>
              )}
            </p>
          )}
          {biggestRiser && biggestDecliner && typeof biggestRiser.change === 'number' && typeof biggestDecliner.change === 'number' && (
            <p className="mb-2">
              <strong className="text-white">{getStateFullName(biggestRiser.stateName || biggestRiser.state)}</strong> saw the biggest increase (<strong className="text-white">+{formatHPRD(biggestRiser.change)} HPRD</strong>), while <strong className="text-white">{getStateFullName(biggestDecliner.stateName || biggestDecliner.state)}</strong> declined the most (<strong className="text-white">{formatHPRD(Math.abs(biggestDecliner.change))} HPRD</strong>).
            </p>
          )}
          {data.sff.currentSFFs > 0 && (
            <p>
              <strong className="text-white">{data.sff.currentSFFs}</strong> Special Focus Facilities.
            </p>
          )}
        </>
      );
    }
    return null;
  };

  return (
    <WrappedCard title="Phoebe J Takeaway" hideBadge>
      <div className="space-y-3">
        <div className="flex items-center justify-center gap-2 mb-3">
          <a 
            href="https://www.320insight.com/phoebe" 
            target="_blank" 
            rel="noopener noreferrer"
            className="flex-shrink-0"
          >
            <img 
              src={getAssetPath('/phoebe.png')} 
              alt="Phoebe J" 
              className="w-10 h-10 md:w-12 md:h-12 rounded-full border-2 border-blue-400/50 hover:border-blue-400 transition-colors"
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = 'none';
              }}
            />
          </a>
          <div className="text-sm md:text-base font-semibold text-blue-300">
            Phoebe J's Takeaway
          </div>
        </div>
        <div className="bg-blue-500/10 border-l-4 border-blue-400 pl-3 md:pl-4 py-2 rounded text-gray-200 text-xs md:text-sm leading-relaxed">
          {renderTakeaway()}
        </div>
      </div>
    </WrappedCard>
  );
};
