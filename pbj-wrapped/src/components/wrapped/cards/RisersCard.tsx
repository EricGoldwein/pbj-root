import React from 'react';
import { WrappedCard } from '../WrappedCard';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';
import { shortenProviderName } from '../../../lib/wrapped/dataProcessor';
import { trackFacilityLinkClick, trackStateLinkClick } from '../../../utils/analytics';

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

interface RisersCardProps {
  data: PBJWrappedData;
}

export const RisersCard: React.FC<RisersCardProps> = ({ data }) => {
  const formatChange = (change: number): string => {
    const sign = change >= 0 ? '+' : '';
    return `${sign}${change.toFixed(2)}`;
  };

  const renderItem = (item: typeof data.movers.risersByHPRD[0], isRNHPRD: boolean = false) => {
    // Check if it's a StateChange (has 'state' but no 'provnum', or has 'stateName')
    const isState = ('state' in item && !('provnum' in item)) || 'stateName' in item;
    const change = isRNHPRD ? (item as any).rnHPRDChange : item.change;
    const q1Value = isRNHPRD ? (item as any).q1RNHPRD : item.q1Value;
    const q2Value = isRNHPRD ? (item as any).q2RNHPRD : item.q2Value;
    
    if (isState) {
      const stateItem = item as any;
      const stateName = stateItem.stateName || stateItem.state;
      const isInternalLink = stateItem.link && stateItem.link.startsWith('/wrapped/');
      
      const handleStateClick = (e: React.MouseEvent) => {
        if (isInternalLink) {
          e.preventDefault();
          trackStateLinkClick(stateItem.state, stateName, 'Risers');
          window.location.href = stateItem.link;
        } else if (stateItem.link.includes('pbjdashboard.com')) {
          trackStateLinkClick(stateItem.state, stateName, 'Risers - Dashboard');
        }
      };
      
      return (
        <div key={stateItem.state} className="py-1.5 border-b border-gray-700 last:border-0">
          <div className="flex justify-between items-start">
            {isInternalLink ? (
              <a
                href={stateItem.link}
                onClick={handleStateClick}
                className="text-blue-300 hover:text-blue-200 underline font-medium text-sm flex-1 cursor-pointer"
              >
                {stateName}
              </a>
            ) : (
              <a
                href={stateItem.link}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-300 hover:text-blue-200 underline font-medium text-sm flex-1"
              >
                {stateName}
              </a>
            )}
            <div className="text-right ml-2">
              <div className="text-sm font-semibold text-green-400">
                {formatChange(change)}
              </div>
              <div className="text-xs text-gray-500">
                {q1Value.toFixed(2)} → {q2Value.toFixed(2)}
              </div>
            </div>
          </div>
        </div>
      );
    } else {
      const facility = item as any;
      // For state pages, show city (capitalized). For region/USA pages, show state.
      const location = data.scope === 'state' && facility.city 
        ? facility.city // Already capitalized by capitalizeCity in dataProcessor
        : facility.state;
      
      return (
        <div key={facility.provnum} className="py-2 md:py-1.5 border-b border-gray-700 last:border-0">
          <div className="flex justify-between items-start">
            <div className="flex-1 min-w-0">
              <a
                href={facility.link}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-300 hover:text-blue-200 underline font-medium text-sm block truncate"
                title={facility.name}
                onClick={() => trackFacilityLinkClick(facility.provnum, facility.name, `Risers - ${data.scope}`)}
              >
                {shortenProviderName(facility.name, 35)}
              </a>
              <div className="text-xs text-gray-500 truncate">{location}</div>
            </div>
            <div className="text-right ml-2 flex-shrink-0">
              <div className="text-sm font-semibold text-green-400">
                {formatChange(change)}
              </div>
              <div className="text-xs text-gray-500">
                {q1Value.toFixed(2)} → {q2Value.toFixed(2)}
              </div>
            </div>
          </div>
        </div>
      );
    }
  };

  // Dynamic title based on scope
  const getTitle = () => {
    if (data.scope === 'state') {
      const stateName = getStateFullName(data.identifier);
      // Handle states with apostrophes in their names (e.g., "New Hampshire's")
      const possessive = stateName.endsWith('s') ? `${stateName}'` : `${stateName}'s`;
      return `${possessive} Biggest Risers`;
    } else if (data.scope === 'region') {
      const regionNum = data.identifier.replace(/^region/i, '');
      return `Region ${regionNum}'s Biggest Risers`;
    }
    return "Biggest Risers";
  };

  return (
    <WrappedCard title={getTitle()}>
      <div className="space-y-3 text-left">
        <div>
          <h4 className="text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wide">By total HPRD</h4>
          <div className="space-y-0.5">
            {data.movers.risersByHPRD.slice(0, 3).map(f => renderItem(f))}
          </div>
        </div>
        
        <div>
          <h4 className="text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wide">By RN HPRD</h4>
          <div className="space-y-0.5">
            {data.movers.risersByRNHPRD?.slice(0, 3).map(f => renderItem(f, true)) || []}
          </div>
        </div>
      </div>
    </WrappedCard>
  );
};

