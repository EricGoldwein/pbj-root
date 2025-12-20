import React from 'react';
import { useNavigate } from 'react-router-dom';
import { WrappedCard } from '../WrappedCard';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';

interface ExtremesCardProps {
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

export const ExtremesCard: React.FC<ExtremesCardProps> = ({ data }) => {
  const navigate = useNavigate();
  
  const formatNumber = (num: number, decimals: number = 1): string => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const renderFacility = (facility: typeof data.extremes.lowestByHPRD[0], showPercent: boolean = false) => {
    const isStateOrRegion = data.scope === 'usa' && (facility.name === facility.state || facility.name.startsWith('Region') || facility.name === getStateFullName(facility.state));
    // For state pages, show only city. For region/USA pages, show state (but not for states/regions themselves).
    let location: string | null = null;
    if (data.scope === 'state' && facility.city) {
      location = facility.city;
    } else if (data.scope === 'usa' && isStateOrRegion) {
      // Don't show location for states/regions on USA page - name is already the full state name
      location = null;
    } else if (data.scope !== 'usa' && facility.state) {
      location = facility.state;
    }
    
    // For USA page states, link should be internal (wrapped page), not external
    const isInternalLink = data.scope === 'usa' && isStateOrRegion && facility.link.startsWith('/wrapped/');
    
    const handleStateClick = (e: React.MouseEvent, link: string) => {
      if (isInternalLink) {
        e.preventDefault();
        navigate(link);
      }
    };
    
    return (
      <div key={facility.provnum} className="py-2 md:py-1.5 border-b border-gray-700 last:border-0">
        <div className="flex justify-between items-start">
          {isInternalLink ? (
            <a
              href={facility.link}
              onClick={(e) => handleStateClick(e, facility.link)}
              className="text-blue-300 hover:text-blue-200 underline font-medium text-sm flex-1 cursor-pointer"
            >
              {facility.name}
            </a>
          ) : (
            <a
              href={facility.link}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-300 hover:text-blue-200 underline font-medium text-sm flex-1"
            >
              {facility.name}
            </a>
          )}
          <div className="text-right ml-2 flex-shrink-0">
            <div className="text-sm text-white font-semibold">
              {showPercent ? `${formatNumber(facility.value, 1)}%` : formatNumber(facility.value, 2)} HPRD
            </div>
          </div>
        </div>
        {location && (
          <div className="text-xs text-gray-500 mt-0.5">{location}</div>
        )}
      </div>
    );
  };

  if (data.scope === 'usa') {
    // USA shows top/bottom states and regions - compact layout
    return (
      <WrappedCard title="Staffing Extremes">
        <div className="space-y-4 text-left">
          {/* Top/Bottom States - Side by side */}
          <div>
            <h3 className="text-base font-bold text-white mb-2">States</h3>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <h4 className="text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wide">Top Total HPRD</h4>
                <div className="space-y-0.5">
                  {data.extremes.topStatesByHPRD?.slice(0, 3).map(f => renderFacility(f)) || []}
                </div>
              </div>
              <div>
                <h4 className="text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wide">Bottom Total HPRD</h4>
                <div className="space-y-0.5">
                  {data.extremes.bottomStatesByHPRD?.slice(0, 3).map(f => renderFacility(f)) || []}
                </div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 mt-2">
              <div>
                <h4 className="text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wide">Top Direct Care</h4>
                <div className="space-y-0.5">
                  {data.extremes.topStatesByDirectCare?.slice(0, 3).map(f => renderFacility(f)) || []}
                </div>
              </div>
              <div>
                <h4 className="text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wide">Bottom Direct Care</h4>
                <div className="space-y-0.5">
                  {data.extremes.bottomStatesByDirectCare?.slice(0, 3).map(f => renderFacility(f)) || []}
                </div>
              </div>
            </div>
          </div>
          
          {/* Top/Bottom Regions - Side by side */}
          <div className="pt-2 border-t border-gray-700">
            <h3 className="text-base font-bold text-white mb-2">CMS Regions</h3>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <h4 className="text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wide">Top Total HPRD</h4>
                <div className="space-y-0.5">
                  {data.extremes.topRegionsByHPRD?.slice(0, 3).map(f => renderFacility(f)) || []}
                </div>
              </div>
              <div>
                <h4 className="text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wide">Bottom Total HPRD</h4>
                <div className="space-y-0.5">
                  {data.extremes.bottomRegionsByHPRD?.slice(0, 3).map(f => renderFacility(f)) || []}
                </div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 mt-2">
              <div>
                <h4 className="text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wide">Top Direct Care</h4>
                <div className="space-y-0.5">
                  {data.extremes.topRegionsByDirectCare?.slice(0, 3).map(f => renderFacility(f)) || []}
                </div>
              </div>
              <div>
                <h4 className="text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wide">Bottom Direct Care</h4>
                <div className="space-y-0.5">
                  {data.extremes.bottomRegionsByDirectCare?.slice(0, 3).map(f => renderFacility(f)) || []}
                </div>
              </div>
            </div>
          </div>
          
          {/* Facility extremes */}
          {data.extremes.lowestByHPRD.length > 0 && (
            <div className="pt-2 border-t border-gray-700">
              <h3 className="text-base font-bold text-white mb-2">Nursing Homes</h3>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <h4 className="text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wide">Lowest</h4>
                  <div className="space-y-0.5">
                    {data.extremes.lowestByHPRD.slice(0, 3).map(f => renderFacility(f))}
                  </div>
                </div>
                <div>
                  <h4 className="text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wide">Highest</h4>
                  <div className="space-y-0.5">
                    {data.extremes.highestByHPRD.slice(0, 3).map(f => renderFacility(f))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </WrappedCard>
    );
  }

  // State and Region pages show facility extremes
  return (
    <WrappedCard title="Staffing Extremes">
      <div className="space-y-5">
        <div>
          <h3 className="text-lg font-bold text-white mb-2">Lowest Staffing</h3>
          
          <div className="mb-3">
            <h4 className="text-xs font-semibold text-gray-400 mb-1.5 uppercase tracking-wide">By total HPRD</h4>
            <div className="space-y-0.5">
              {data.extremes.lowestByHPRD.slice(0, 3).map(f => renderFacility(f))}
            </div>
          </div>
          
          {data.extremes.lowestByPercentExpected.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-400 mb-1.5 uppercase tracking-wide">By % of case-mix expected</h4>
              <div className="space-y-0.5">
                {data.extremes.lowestByPercentExpected.slice(0, 3).map(f => renderFacility(f, true))}
              </div>
            </div>
          )}
        </div>
        
        <div className="pt-2 border-t border-gray-700">
          <h3 className="text-lg font-bold text-white mb-2">Highest Staffing</h3>
          
          <div className="mb-3">
            <h4 className="text-xs font-semibold text-gray-400 mb-1.5 uppercase tracking-wide">By total HPRD</h4>
            <div className="space-y-0.5">
              {data.extremes.highestByHPRD.slice(0, 3).map(f => renderFacility(f))}
            </div>
          </div>
          
          {data.extremes.highestByPercentExpected.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-gray-400 mb-1.5 uppercase tracking-wide">By % of case-mix expected</h4>
              <div className="space-y-0.5">
                {data.extremes.highestByPercentExpected.slice(0, 3).map(f => renderFacility(f, true))}
              </div>
            </div>
          )}
        </div>
      </div>
    </WrappedCard>
  );
};

