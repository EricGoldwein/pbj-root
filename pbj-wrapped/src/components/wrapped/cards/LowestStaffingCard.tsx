import React from 'react';
import { WrappedCard } from '../WrappedCard';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';
import { shortenProviderName } from '../../../lib/wrapped/dataProcessor';

interface LowestStaffingCardProps {
  data: PBJWrappedData;
}

export const LowestStaffingCard: React.FC<LowestStaffingCardProps> = ({ data }) => {
  
  const formatNumber = (num: number, decimals: number = 1): string => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const renderFacility = (facility: typeof data.extremes.lowestByHPRD[0], showPercent: boolean = false, hideHPRDLabel: boolean = false) => {
    // For state pages, show only city. For region pages, show state.
    let location: string | null = null;
    if (data.scope === 'state' && facility.city) {
      location = facility.city;
    } else if (data.scope === 'region' && facility.state) {
      location = facility.state;
    }
    
    return (
      <div key={facility.provnum} className="py-2 md:py-1.5 border-b border-gray-700 last:border-0">
        <div className="flex justify-between items-start">
          <a
            href={facility.link}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-300 hover:text-blue-200 underline font-medium text-sm flex-1 truncate"
            title={facility.name}
          >
            {shortenProviderName(facility.name, 35)}
          </a>
          <div className="text-right ml-2 flex-shrink-0">
            <div className="text-sm text-white font-semibold">
              {showPercent 
                ? `${formatNumber(facility.value, 1)}%` 
                : `${formatNumber(facility.value, 2)}${hideHPRDLabel ? '' : ' HPRD'}`
              }
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          {location && (
            <div className="text-xs text-gray-500">{location}</div>
          )}
          {facility.staffingRating && (
            <div className="text-xs text-gray-400">
              Staffing: {facility.staffingRating}★
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <WrappedCard title="Lowest Staffing">
      <div className="space-y-3 text-left">
        <div>
          <h4 className="text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wide">By total HPRD</h4>
          <div className="space-y-0.5">
            {data.extremes.lowestByHPRD.slice(0, 3).map(f => renderFacility(f, false, true))}
          </div>
        </div>
        
        {data.extremes.lowestByPercentExpected.length > 0 && (
          <div>
            <h4 className="text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wide">By % of case-mix expected</h4>
            <div className="space-y-0.5">
              {data.extremes.lowestByPercentExpected.slice(0, 3).map(f => renderFacility(f, true))}
            </div>
          </div>
        )}
        
        {data.scope === 'state' && data.stateMinimum && (
          <div className="mt-3 pt-3 border-t border-gray-700">
            <div className="flex items-center gap-2 text-xs">
              <div className="w-8 h-0.5 bg-blue-400"></div>
              <span className="text-blue-300">
                State minimum: {data.stateMinimum.minHPRD.toFixed(2)} HPRD
              </span>
            </div>
          </div>
        )}
      </div>
    </WrappedCard>
  );
};

