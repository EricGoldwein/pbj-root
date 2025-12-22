import React from 'react';
import { WrappedCard } from '../WrappedCard';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';

interface USAOwnershipStaffingCardProps {
  data: PBJWrappedData;
}

export const USAOwnershipStaffingCard: React.FC<USAOwnershipStaffingCardProps> = ({ data }) => {
  if (data.scope !== 'usa' || !data.ownership) {
    return null;
  }

  const formatNumber = (num: number, decimals: number = 2): string => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const hasStaffingData = data.ownership.forProfit.medianHPRD !== undefined ||
                          data.ownership.nonProfit.medianHPRD !== undefined ||
                          data.ownership.government.medianHPRD !== undefined;

  if (!hasStaffingData) {
    return null;
  }

  return (
    <WrappedCard title="Staffing by Ownership">
      <div className="space-y-4">
        <p className="text-gray-300 text-xs md:text-sm text-center mb-3">
          Median total HPRD by ownership type
        </p>
        
        <div className="space-y-3">
          {data.ownership.forProfit.medianHPRD !== undefined && (
            <div className="flex justify-between items-center py-2 border-b border-gray-600">
              <div className="flex items-center gap-3">
                <div className="w-4 h-4 rounded-sm bg-blue-400 flex-shrink-0"></div>
                <span className="text-gray-300 text-sm md:text-base">For-Profit</span>
              </div>
              <span className="text-white font-bold text-lg md:text-xl">
                {formatNumber(data.ownership.forProfit.medianHPRD, 2)} HPRD
              </span>
            </div>
          )}
          
          {data.ownership.nonProfit.medianHPRD !== undefined && (
            <div className="flex justify-between items-center py-2 border-b border-gray-600">
              <div className="flex items-center gap-3">
                <div className="w-4 h-4 rounded-sm bg-green-400 flex-shrink-0"></div>
                <span className="text-gray-300 text-sm md:text-base">Non-Profit</span>
              </div>
              <span className="text-white font-bold text-lg md:text-xl">
                {formatNumber(data.ownership.nonProfit.medianHPRD, 2)} HPRD
              </span>
            </div>
          )}
          
          {data.ownership.government.medianHPRD !== undefined && (
            <div className="flex justify-between items-center py-2">
              <div className="flex items-center gap-3">
                <div className="w-4 h-4 rounded-sm bg-purple-400 flex-shrink-0"></div>
                <span className="text-gray-300 text-sm md:text-base">Government</span>
              </div>
              <span className="text-white font-bold text-lg md:text-xl">
                {formatNumber(data.ownership.government.medianHPRD, 2)} HPRD
              </span>
            </div>
          )}
        </div>
        
        <p className="text-xs text-gray-500 text-center mt-3 pt-2 border-t border-gray-700">
          A 2001 federal study recommended 4.1 total HPRD as the amount needed for quality care.
        </p>
        <p className="text-xs text-gray-500 text-center mt-2 pt-2 border-t border-gray-700">
          Source: CMS PBJ Q2 2025
        </p>
      </div>
    </WrappedCard>
  );
};

