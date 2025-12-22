import React from 'react';
import { WrappedCard } from '../WrappedCard';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';
import { OwnershipPieChart } from '../OwnershipPieChart';

interface USAOwnershipCardProps {
  data: PBJWrappedData;
}

export const USAOwnershipCard: React.FC<USAOwnershipCardProps> = ({ data }) => {
  if (data.scope !== 'usa' || !data.ownership) {
    return null;
  }

  const formatNumber = (num: number, decimals: number = 0): string => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const formatHPRD = (num: number | undefined): string => {
    if (num === undefined) return 'N/A';
    return formatNumber(num, 2);
  };

  const hasStaffingData = data.ownership.forProfit.medianHPRD !== undefined ||
                          data.ownership.nonProfit.medianHPRD !== undefined ||
                          data.ownership.government.medianHPRD !== undefined;

  return (
    <WrappedCard title="Ownership Breakdown">
      <div className="space-y-4">
        <p className="text-gray-300 text-xs md:text-sm text-center mb-3">
          Ownership types nationwide
        </p>
        
        <div className="flex flex-col md:flex-row items-center justify-center gap-4 md:gap-6">
          <div className="flex-shrink-0">
            <OwnershipPieChart ownership={data.ownership} size={160} />
          </div>
          
          <div className="flex-1 space-y-2 min-w-0">
            <div className="flex justify-between items-center py-1.5 border-b border-gray-600">
              <div className="flex items-center gap-2 md:gap-3">
                <div className="w-3 h-3 md:w-4 md:h-4 rounded-sm bg-blue-400 flex-shrink-0"></div>
                <span className="text-gray-300 text-sm md:text-base md:whitespace-nowrap">For-Profit</span>
              </div>
              <div className="text-right ml-4">
                <span className="text-white font-bold text-lg">
                  {formatNumber(data.ownership.forProfit.count)}
                </span>
                <span className="text-gray-400 text-sm ml-2">
                  ({data.ownership.forProfit.percentage}%)
                </span>
              </div>
            </div>
            
            <div className="flex justify-between items-center py-1.5 border-b border-gray-600">
              <div className="flex items-center gap-2 md:gap-3">
                <div className="w-3 h-3 md:w-4 md:h-4 rounded-sm bg-green-400 flex-shrink-0"></div>
                <span className="text-gray-300 text-sm md:text-base">Non-Profit</span>
              </div>
              <div className="text-right">
                <span className="text-white font-bold text-lg">
                  {formatNumber(data.ownership.nonProfit.count)}
                </span>
                <span className="text-gray-400 text-sm ml-2">
                  ({data.ownership.nonProfit.percentage}%)
                </span>
              </div>
            </div>
            
            <div className="flex justify-between items-center py-1.5">
              <div className="flex items-center gap-2 md:gap-3">
                <div className="w-3 h-3 md:w-4 md:h-4 rounded-sm bg-purple-400 flex-shrink-0"></div>
                <span className="text-gray-300 text-sm md:text-base">Government</span>
              </div>
              <div className="text-right">
                <span className="text-white font-bold text-lg">
                  {formatNumber(data.ownership.government.count)}
                </span>
                <span className="text-gray-400 text-sm ml-2">
                  ({data.ownership.government.percentage}%)
                </span>
              </div>
            </div>
          </div>
        </div>

        <p className="text-xs text-gray-500 text-center mt-4 pt-3 border-t border-gray-700">
          Source: CMS PBJ Q2 2025
        </p>
      </div>
    </WrappedCard>
  );
};

