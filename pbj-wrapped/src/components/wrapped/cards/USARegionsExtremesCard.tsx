import React from 'react';
import { WrappedCard } from '../WrappedCard';
import type { PBJWrappedData, Facility } from '../../../lib/wrapped/wrappedTypes';

interface USARegionsExtremesCardProps {
  data: PBJWrappedData;
}

export const USARegionsExtremesCard: React.FC<USARegionsExtremesCardProps> = ({ data }) => {
  const formatNumber = (num: number, decimals: number = 1): string => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const renderRegion = (facility: Facility) => {
    // Extract region number from provnum (e.g., "region1" -> "1") or state (e.g., "Region 1" -> "1")
    const regionNumber = facility.provnum?.replace(/region/i, '') || 
                        facility.state?.replace(/region/i, '').trim() || '';
    const regionName = facility.name; // e.g., "Boston"
    const displayName = regionNumber ? `CMS Region ${regionNumber} (${regionName})` : regionName;
    
    return (
      <div key={facility.provnum} className="py-1.5 border-b border-gray-700 last:border-0">
        <div className="flex justify-between items-center">
          <a
            href={facility.link}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-300 hover:text-blue-200 underline font-medium text-sm flex-1"
          >
            {displayName}
          </a>
          <div className="text-right ml-2 flex-shrink-0">
            <div className="text-sm text-white font-semibold">
              {formatNumber(facility.value, 2)}
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <WrappedCard title="CMS Region Rankings">
      <div className="space-y-3 text-left">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <div className="flex justify-between items-center mb-1">
              <h4 className="text-xs font-semibold text-red-400 uppercase tracking-wide whitespace-nowrap">Bottom 3</h4>
              <span className="text-xs text-gray-500">HPRD</span>
            </div>
            <div className="space-y-0.5">
              {data.extremes.bottomRegionsByHPRD?.slice(0, 3).map(f => renderRegion(f)) || []}
            </div>
          </div>
          <div>
            <div className="flex justify-between items-center mb-1">
              <h4 className="text-xs font-semibold text-green-400 uppercase tracking-wide whitespace-nowrap">Top 3</h4>
              <span className="text-xs text-gray-500">HPRD</span>
            </div>
            <div className="space-y-0.5">
              {data.extremes.topRegionsByHPRD?.slice(0, 3).map(f => renderRegion(f)) || []}
            </div>
          </div>
        </div>
      </div>
    </WrappedCard>
  );
};

