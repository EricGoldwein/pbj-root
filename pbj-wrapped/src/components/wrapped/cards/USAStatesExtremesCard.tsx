import React from 'react';
import { useNavigate } from 'react-router-dom';
import { WrappedCard } from '../WrappedCard';
import type { PBJWrappedData, Facility } from '../../../lib/wrapped/wrappedTypes';

interface USAStatesExtremesCardProps {
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

export const USAStatesExtremesCard: React.FC<USAStatesExtremesCardProps> = ({ data }) => {
  const navigate = useNavigate();
  
  const formatNumber = (num: number, decimals: number = 1): string => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const renderState = (facility: Facility) => {
    const stateName = getStateFullName(facility.state);
    const isInternalLink = facility.link.startsWith('/wrapped/');
    
    const handleStateClick = (e: React.MouseEvent) => {
      if (isInternalLink) {
        e.preventDefault();
        navigate(facility.link);
      }
    };
    
    return (
      <div key={facility.provnum} className="py-1.5 border-b border-gray-700 last:border-0">
        <div className="flex justify-between items-center">
          {isInternalLink ? (
            <a
              href={facility.link}
              onClick={handleStateClick}
              className="text-blue-300 hover:text-blue-200 underline font-medium text-sm flex-1 cursor-pointer"
            >
              {stateName}
            </a>
          ) : (
            <a
              href={facility.link}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-300 hover:text-blue-200 underline font-medium text-sm flex-1"
            >
              {stateName}
            </a>
          )}
          <div className="text-right ml-2 flex-shrink-0">
            <div className="text-sm text-white font-semibold">
              {formatNumber(facility.value, 2)} HPRD
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <WrappedCard title="Staffing Extremes — States">
      <div className="space-y-3 text-left">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <h4 className="text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wide">Top Total HPRD</h4>
            <div className="space-y-0.5">
              {data.extremes.topStatesByHPRD?.slice(0, 3).map(f => renderState(f)) || []}
            </div>
          </div>
          <div>
            <h4 className="text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wide">Bottom Total HPRD</h4>
            <div className="space-y-0.5">
              {data.extremes.bottomStatesByHPRD?.slice(0, 3).map(f => renderState(f)) || []}
            </div>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3 pt-2 border-t border-gray-700">
          <div>
            <h4 className="text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wide">Top Direct Care</h4>
            <div className="space-y-0.5">
              {data.extremes.topStatesByDirectCare?.slice(0, 3).map(f => renderState(f)) || []}
            </div>
          </div>
          <div>
            <h4 className="text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wide">Bottom Direct Care</h4>
            <div className="space-y-0.5">
              {data.extremes.bottomStatesByDirectCare?.slice(0, 3).map(f => renderState(f)) || []}
            </div>
          </div>
        </div>
      </div>
    </WrappedCard>
  );
};

