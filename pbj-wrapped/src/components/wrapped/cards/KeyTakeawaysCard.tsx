import React from 'react';
import { WrappedCard } from '../WrappedCard';
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

  // Generate key takeaways based on scope
  const getTakeaways = () => {
    if (data.scope === 'usa') {
      const topState = data.extremes.topStatesByHPRD?.[0];
      const bottomState = data.extremes.bottomStatesByHPRD?.[0];
      const biggestRiser = data.movers.risersByHPRD?.[0] as any;
      const biggestDecliner = data.movers.declinersByHPRD?.[0] as any;
      const topRegion = data.extremes.topRegionsByHPRD?.[0];
      
      return [
        {
          label: 'Scale',
          value: `${formatNumber(data.facilityCount)} nursing homes`,
          description: `Serving ${formatNumber(Math.round(data.avgDailyResidents), 0)} residents daily. National average: ${formatHPRD(data.totalHPRD)} HPRD`,
        },
        topState && bottomState && {
          label: 'State Range',
          value: `${formatHPRD(topState.value)} vs ${formatHPRD(bottomState.value)}`,
          description: `${getStateFullName(topState.state)} (highest) vs ${getStateFullName(bottomState.state)} (lowest)`,
        },
        topRegion && {
          label: 'Top Region',
          value: topRegion.name,
          description: `${formatHPRD(topRegion.value)} HPRD — highest regional average`,
        },
        biggestRiser && biggestDecliner && {
          label: 'Q1 to Q2 Change',
          value: `${biggestRiser.stateName || biggestRiser.state} +${formatHPRD(biggestRiser.change)}`,
          description: `Biggest gain. ${biggestDecliner.stateName || biggestDecliner.state} declined ${formatHPRD(Math.abs(biggestDecliner.change))}`,
        },
        data.sff.currentSFFs > 0 && {
          label: 'Special Focus',
          value: `${data.sff.currentSFFs} nursing homes`,
          description: `${data.sff.candidates} candidates requiring enhanced oversight`,
        },
      ].filter(Boolean);
    } else if (data.scope === 'state') {
      const rnRank = data.rankings.rnHPRDRank;
      const totalRank = data.rankings.totalHPRDRank;
      const isLowRNRank = rnRank > 25; // Bottom half
      const trend = data.trends.totalHPRDChange;
      
      return [
        {
          label: 'RN Staffing Rank',
          value: `#${rnRank} of 51`,
          description: `RN HPRD: ${formatHPRD(data.rnHPRD)}. Total staffing rank: #${totalRank}`,
          highlight: isLowRNRank,
        },
        {
          label: 'Staffing Level',
          value: `${formatHPRD(data.totalHPRD)} HPRD`,
          description: `${formatNumber(data.facilityCount)} nursing homes serving ${formatNumber(Math.round(data.avgDailyResidents), 0)} residents daily`,
        },
        trend !== 0 && {
          label: 'Q1 to Q2 Trend',
          value: trend > 0 ? `+${formatHPRD(trend)}` : formatHPRD(trend),
          description: trend > 0 ? 'State staffing increased Q1 to Q2' : 'State staffing decreased Q1 to Q2',
          highlight: trend < 0,
        },
        data.sff.currentSFFs > 0 && {
          label: 'Special Focus',
          value: `${data.sff.currentSFFs} nursing homes`,
          description: data.sff.newThisQuarter.length > 0 
            ? `${data.sff.newThisQuarter.length} newly designated this quarter`
            : 'Under enhanced oversight',
        },
      ].filter(Boolean);
    } else if (data.scope === 'region') {
      const biggestRiser = data.movers.risersByHPRD?.[0] as any;
      const biggestDecliner = data.movers.declinersByHPRD?.[0] as any;
      const trend = data.trends.totalHPRDChange;
      
      return [
        {
          label: 'Regional Overview',
          value: `${formatHPRD(data.totalHPRD)} HPRD`,
          description: `${formatNumber(data.facilityCount)} nursing homes across ${data.name}`,
        },
        trend !== 0 && {
          label: 'Quarter Trend',
          value: trend > 0 ? `+${formatHPRD(trend)}` : formatHPRD(trend),
          description: trend > 0 ? 'Regional staffing increased Q1 to Q2' : 'Regional staffing decreased Q1 to Q2',
          highlight: trend < 0,
        },
        biggestRiser && biggestDecliner && {
          label: 'State Changes',
          value: `${biggestRiser.stateName || biggestRiser.state}`,
          description: `+${formatHPRD(biggestRiser.change)} HPRD. ${biggestDecliner.stateName || biggestDecliner.state} declined ${formatHPRD(Math.abs(biggestDecliner.change))}`,
        },
        data.sff.currentSFFs > 0 && {
          label: 'Special Focus',
          value: `${data.sff.currentSFFs} nursing homes`,
          description: data.sff.newThisQuarter.length > 0 
            ? `${data.sff.newThisQuarter.length} newly designated this quarter`
            : 'Under enhanced oversight',
        },
      ].filter(Boolean);
    }
    return [];
  };

  const takeaways = getTakeaways();

  // For odd number of items, make the last one span full width on desktop
  const isOdd = takeaways.length % 2 === 1;
  const lastIndex = takeaways.length - 1;

  return (
    <WrappedCard title="Key Takeaways">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 md:gap-3">
        {takeaways.map((takeaway: any, index) => {
          // Make Q1 to Q2 Trend more compact
          const isTrend = takeaway?.label?.includes('Trend') || takeaway?.label?.includes('Change');
          
          return (
            <div
              key={index}
              className={`p-2.5 md:p-3 rounded-lg border-2 transition-all duration-200 ${
                index === lastIndex && isOdd ? 'md:col-span-2' : ''
              } ${
                takeaway?.highlight
                  ? 'bg-red-500/10 border-red-500/50 hover:bg-red-500/15'
                  : 'bg-blue-500/10 border-blue-500/30 hover:bg-blue-500/15'
              }`}
            >
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-0.5">
                {takeaway.label}
              </div>
              <div className={`${isTrend ? 'text-lg md:text-xl' : 'text-xl md:text-2xl'} font-bold mb-0.5 ${
                takeaway?.highlight ? 'text-red-300' : 'text-white'
              }`}>
                {takeaway.value}
              </div>
              <div className="text-xs text-gray-400 leading-snug line-clamp-2">
                {takeaway.description}
              </div>
            </div>
          );
        })}
      </div>
    </WrappedCard>
  );
};
