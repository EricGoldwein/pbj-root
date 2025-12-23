import React from 'react';
import { WrappedCard } from '../WrappedCard';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';
import { TrendArrow } from '../TrendArrow';

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
  return STATE_ABBR_TO_NAME[abbr.toLowerCase()] || abbr;
}

interface TrendsCardProps {
  data: PBJWrappedData;
}

export const TrendsCard: React.FC<TrendsCardProps> = ({ data }) => {
  const formatChange = (change: number, isPercent: boolean = false): string => {
    const sign = change >= 0 ? '+' : '';
    const formatted = change.toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return `${sign}${formatted}${isPercent ? '%' : ''}`;
  };

  // Dynamic title based on scope
  const getTitle = () => {
    if (data.scope === 'state') {
      return `${getStateFullName(data.identifier)} Trends`;
    } else if (data.scope === 'region') {
      const regionNum = data.identifier.replace(/^region/i, '');
      return `CMS Region ${regionNum} Trends`;
    }
    return "Trends";
  };

  return (
    <WrappedCard title={getTitle()}>
      <p className="text-gray-300 mb-3 text-sm">
        Changes from Q1 2025 to Q2 2025
      </p>
      
      
      <div className="space-y-3 text-left">
        <div className="py-1.5 border-b border-gray-600">
          <div className="flex justify-between items-center">
            <span className="text-gray-300">Total staff HPRD</span>
            <div className="flex items-center gap-3">
              <span className={`font-bold text-lg ${data.trends.totalHPRDChange > 0 ? 'text-green-400' : data.trends.totalHPRDChange < 0 ? 'text-red-400' : 'text-white'}`}>
                {formatChange(data.trends.totalHPRDChange)}
              </span>
              <TrendArrow change={data.trends.totalHPRDChange} size={36} />
            </div>
          </div>
        </div>
        
        <div className="py-1.5 border-b border-gray-600">
          <div className="flex justify-between items-center">
            <span className="text-gray-300">Direct care HPRD</span>
            <div className="flex items-center gap-3">
              <span className={`font-bold text-lg ${data.trends.directCareHPRDChange > 0 ? 'text-green-400' : data.trends.directCareHPRDChange < 0 ? 'text-red-400' : 'text-white'}`}>
                {formatChange(data.trends.directCareHPRDChange)}
              </span>
              <TrendArrow change={data.trends.directCareHPRDChange} size={36} />
            </div>
          </div>
        </div>
        
        <div className="py-1.5 border-b border-gray-600">
          <div className="flex justify-between items-center">
            <span className="text-gray-300">RN staff HPRD</span>
            <div className="flex items-center gap-3">
              <span className={`font-bold text-lg ${data.trends.rnHPRDChange > 0 ? 'text-green-400' : data.trends.rnHPRDChange < 0 ? 'text-red-400' : 'text-white'}`}>
                {formatChange(data.trends.rnHPRDChange)}
              </span>
              <TrendArrow change={data.trends.rnHPRDChange} size={36} />
            </div>
          </div>
        </div>
        
        <div className="py-1.5">
          <div className="flex justify-between items-center">
            <span className="text-gray-300">Contract staff %</span>
            <div className="flex items-center gap-3">
              <span className="font-bold text-lg text-white">
                {formatChange(data.trends.contractPercentChange, true)}
              </span>
              <div className="flex items-center justify-center rounded-full w-9 h-9 bg-gray-700/50 border-2 border-gray-600">
                <span className="font-bold text-lg text-gray-300">
                  {data.trends.contractPercentChange > 0 ? '↑' : data.trends.contractPercentChange < 0 ? '↓' : '→'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </WrappedCard>
  );
};

