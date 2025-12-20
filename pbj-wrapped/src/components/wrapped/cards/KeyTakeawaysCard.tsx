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
  'ok': 'Oklahoma', 'or': 'Oregon', 'pa': 'Pennsylvania', 'ri': 'Rhode Island', 'sc': 'South Carolina',
  'sd': 'South Dakota', 'tn': 'Tennessee', 'tx': 'Texas', 'ut': 'Utah', 'vt': 'Vermont',
  'va': 'Virginia', 'wa': 'Washington', 'wv': 'West Virginia', 'wi': 'Wisconsin', 'wy': 'Wyoming',
  'dc': 'District of Columbia'
};

function getStateFullName(abbr: string): string {
  return STATE_ABBR_TO_NAME[abbr.toLowerCase()] || abbr.toUpperCase();
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

  // Helper to determine if a rank is noteworthy (low = bottom 10, high = top 10)
  const isLowRank = (rank: number, total: number) => rank > total - 10;
  const isHighRank = (rank: number) => rank <= 10;

  // Generate conversational takeaways with JSX formatting
  const renderTakeaway = () => {
    if (data.scope === 'usa') {
      const topState = data.extremes.topStatesByHPRD?.[0];
      const bottomState = data.extremes.bottomStatesByHPRD?.[0];
      const biggestRiser = data.movers.risersByHPRD?.[0] as any;
      const biggestDecliner = data.movers.declinersByHPRD?.[0] as any;
      
      return (
        <>
          <p className="mb-2">
            Nationwide, <strong className="text-white">{formatNumber(data.facilityCount)}</strong> nursing homes are serving <strong className="text-white">{formatNumber(Math.round(data.avgDailyResidents), 0)}</strong> residents daily with an average of <strong className="text-white">{formatHPRD(data.totalHPRD)} HPRD</strong>.
          </p>
          {topState && bottomState && (
            <p className="mb-2">
              The gap between states is striking: <strong className="text-white">{getStateFullName(bottomState.state)}</strong> sits at <strong className="text-white">{formatHPRD(bottomState.value)} HPRD</strong> (lowest), while <strong className="text-white">{getStateFullName(topState.state)}</strong> leads with <strong className="text-white">{formatHPRD(topState.value)} HPRD</strong> (highest).
            </p>
          )}
          {biggestRiser && biggestDecliner && (
            <p className="mb-2">
              <strong className="text-white">{getStateFullName(biggestRiser.stateName || biggestRiser.state)}</strong> saw the biggest Q1 to Q2 increase (<strong className="text-white">+{formatHPRD(biggestRiser.change)} HPRD</strong>), while <strong className="text-white">{getStateFullName(biggestDecliner.stateName || biggestDecliner.state)}</strong> declined the most (<strong className="text-white">{formatHPRD(Math.abs(biggestDecliner.change))} HPRD</strong>).
            </p>
          )}
          {data.sff.currentSFFs > 0 && (
            <p>
              <strong className="text-white">{data.sff.currentSFFs}</strong> facilities are currently in the Special Focus Facility program, with <strong className="text-white">{data.sff.candidates}</strong> additional candidates requiring enhanced oversight.
            </p>
          )}
        </>
      );
    } else if (data.scope === 'state') {
      const stateName = data.name;
      const rnRank = data.rankings.rnHPRDRank;
      const totalRank = data.rankings.totalHPRDRank;
      const trend = data.trends.totalHPRDChange;
      
      return (
        <>
          <p className="mb-2">
            <strong className="text-white">{stateName}</strong> ranks{' '}
            <strong className="text-white">
              #{rnRank} of 51
            </strong>
            {' '}for RN staffing (<strong className="text-white">{formatHPRD(data.rnHPRD)} HPRD</strong>) and{' '}
            <strong className="text-white">
              #{totalRank}
            </strong>
            {' '}for total staffing (<strong className="text-white">{formatHPRD(data.totalHPRD)} HPRD</strong>).
          </p>
          {trend !== 0 && (
            <p className="mb-2">
              Staffing {trend > 0 ? (
                <>increased from Q1 to Q2 by <strong className="text-white">{formatHPRD(trend)} HPRD</strong>.</>
              ) : (
                <>decreased from Q1 to Q2 by <strong className="text-white">{formatHPRD(Math.abs(trend))} HPRD</strong>.</>
              )}
            </p>
          )}
          {data.sff.currentSFFs > 0 && (
            <p>
              <strong className="text-white">{data.sff.currentSFFs}</strong> Special Focus Facilities.
            </p>
          )}
        </>
      );
    } else if (data.scope === 'region') {
      const biggestRiser = data.movers.risersByHPRD?.[0] as any;
      const biggestDecliner = data.movers.declinersByHPRD?.[0] as any;
      const trend = data.trends.totalHPRDChange;
      
      return (
        <>
          <p className="mb-2">
            <strong className="text-white">{data.name}</strong> has <strong className="text-white">{formatNumber(data.facilityCount)}</strong> nursing homes serving <strong className="text-white">{formatNumber(Math.round(data.avgDailyResidents), 0)}</strong> residents with an average of <strong className="text-white">{formatHPRD(data.totalHPRD)} HPRD</strong>.
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
          {biggestRiser && biggestDecliner && (
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
