import React from 'react';
import { WrappedCard } from '../WrappedCard';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';
import { useAnimatedNumber } from '../../../hooks/useAnimatedNumber';
import { OwnershipPieChart } from '../OwnershipPieChart';
import { StaffingBreakdownPieChart } from '../StaffingBreakdownPieChart';

interface BasicsCardProps {
  data: PBJWrappedData;
}

export const BasicsCard: React.FC<BasicsCardProps> = ({ data }) => {
  const formatNumber = (num: number, decimals: number = 0): string => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  // Animate key numbers
  const animatedFacilityCount = useAnimatedNumber(data.facilityCount, 1200, 0);
  const animatedResidents = useAnimatedNumber(data.avgDailyResidents, 1200, 1);
  const animatedTotalHPRD = useAnimatedNumber(data.totalHPRD, 1200, 2);
  const animatedDirectCareHPRD = useAnimatedNumber(data.directCareHPRD, 1200, 2);
  const animatedRNHPRD = useAnimatedNumber(data.rnHPRD, 1200, 2);
  const animatedRNDirectCareHPRD = useAnimatedNumber(data.rnDirectCareHPRD, 1200, 2);

  const showRankings = data.scope !== 'usa' && data.rankings;

  // For USA, show a cleaner, more compact layout
  if (data.scope === 'usa') {
    // Calculate LPN HPRD: Total - RN - Nurse Aide
    const lpnHPRD = Math.max(0, data.totalHPRD - data.rnHPRD - (data.nurseAideHPRD || 0));
    const staffingBreakdown = {
      rn: data.rnHPRD,
      lpn: lpnHPRD,
      nurseAide: data.nurseAideHPRD || 0,
    };
    
    return (
      <WrappedCard title="The Basics">
        <p className="text-xs text-gray-400 text-center mb-2">(Q2 2025)</p>
        <div className="space-y-4 text-left">
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div className="text-center p-2.5 bg-blue-500/10 rounded-lg border border-blue-500/30">
              <div className="text-xs text-gray-400 mb-1">Nursing Homes</div>
              <div className="text-2xl font-bold text-white">{formatNumber(animatedFacilityCount)}</div>
            </div>
            <div className="text-center p-2.5 bg-blue-500/10 rounded-lg border border-blue-500/30">
              <div className="text-xs text-gray-400 mb-1">Daily Residents</div>
              <div className="text-2xl font-bold text-white">{formatNumber(animatedResidents, 0)}</div>
            </div>
          </div>
          
          {/* Staffing Breakdown Pie Chart */}
          <div className="pt-2 pb-3 border-t border-gray-600">
            <h3 className="text-base font-semibold text-gray-200 mb-3 text-center">Staffing Breakdown</h3>
            <div className="flex items-start gap-4">
              <StaffingBreakdownPieChart breakdown={staffingBreakdown} size={100} />
              <div className="flex-1 space-y-1.5">
                <div className="flex justify-between items-center py-1">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-sm bg-blue-400 flex-shrink-0"></div>
                    <span className="text-gray-300 text-sm">RN</span>
                  </div>
                  <span className="text-white font-semibold text-sm">
                    {formatNumber(data.rnHPRD, 2)} HPRD
                  </span>
                </div>
                <div className="flex justify-between items-center py-1">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-sm bg-green-400 flex-shrink-0"></div>
                    <span className="text-gray-300 text-sm">LPN</span>
                  </div>
                  <span className="text-white font-semibold text-sm">
                    {formatNumber(lpnHPRD, 2)} HPRD
                  </span>
                </div>
                <div className="flex justify-between items-center py-1">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-sm bg-orange-400 flex-shrink-0"></div>
                    <span className="text-gray-300 text-sm">Nurse Aide</span>
                  </div>
                  <span className="text-white font-semibold text-sm">
                    {formatNumber(data.nurseAideHPRD || 0, 2)} HPRD
                  </span>
                </div>
              </div>
            </div>
          </div>
          
          <div className="space-y-2">
            <div className="py-1.5 border-b border-gray-600">
              <div className="flex justify-between items-center mb-1">
                <span className="text-gray-300 text-sm">Total staffing HPRD</span>
                <span className="text-white font-bold text-lg">{formatNumber(animatedTotalHPRD, 2)}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400 text-xs">Direct care HPRD</span>
                <span className="text-gray-300 font-semibold text-sm">{formatNumber(animatedDirectCareHPRD, 2)}</span>
              </div>
            </div>
            
            {data.medianHPRD !== undefined && (
              <div className="flex justify-between items-center py-1.5">
                <span className="text-gray-300 text-sm">Median HPRD</span>
                <span className="text-white font-bold text-lg">{formatNumber(data.medianHPRD, 2)}</span>
              </div>
            )}
          </div>
        </div>
      </WrappedCard>
    );
  }

  return (
    <WrappedCard title="The Basics">
        <p className="text-xs text-gray-400 text-center mb-2">(Q2 2025)</p>
        <div className="space-y-1.5 md:space-y-3 text-left">
        <div className="flex justify-between items-center py-1 md:py-2 border-b border-gray-600">
          <span className="text-gray-300 text-sm md:text-base">Number of nursing homes</span>
          <span className="text-white font-bold text-base md:text-xl">{formatNumber(animatedFacilityCount)}</span>
        </div>
        
        <div className="flex justify-between items-center py-1 md:py-1.5 border-b border-gray-600">
          <span className="text-gray-300 text-sm md:text-base">Average daily residents</span>
          <span className="text-white font-bold text-base md:text-xl">{formatNumber(animatedResidents, 1)}</span>
        </div>
        
        <div className="py-1 md:py-1.5 border-b border-gray-600">
          <div className="flex justify-between items-center mb-1">
            <div className="flex flex-col">
              <span className="text-gray-300 text-sm md:text-base">Total staffing HPRD</span>
              {showRankings && (
                <span className="text-xs text-gray-500 mt-0.5">
                  Rank #{data.rankings.totalHPRDRank} ({data.rankings.totalHPRDPercentile}th percentile)
                </span>
              )}
              {data.scope === 'state' && data.stateMinimum && (
                <span className="text-xs text-red-400 mt-0.5">
                  State minimum: {data.stateMinimum.minHPRD.toFixed(2)} HPRD
                </span>
              )}
            </div>
            <span className="text-white font-bold text-base md:text-xl">{formatNumber(animatedTotalHPRD, 2)}</span>
          </div>
          {data.scope === 'state' && data.compliance && (
            <div className="pt-1.5 md:pt-2 border-t border-gray-700">
              <div className="text-xs text-gray-400 space-y-0.5 md:space-y-1">
                <div>
                  <span className="text-red-300 font-semibold">
                    {data.compliance.facilitiesBelowTotalMinimum}
                  </span>
                  {' '}facilities ({data.compliance.facilitiesBelowTotalMinimumPercent}%) 
                  below state minimum
                </div>
                {data.compliance.facilitiesBelowDirectCareMinimum !== undefined && (
                  <div>
                    <span className="text-red-300 font-semibold">
                      {data.compliance.facilitiesBelowDirectCareMinimum}
                    </span>
                    {' '}facilities ({data.compliance.facilitiesBelowDirectCareMinimumPercent}%) 
                    below state minimum (using direct care HPRD)
                  </div>
                )}
              </div>
            </div>
          )}
          <div className="flex justify-between items-center mt-1">
            <div className="flex flex-col">
              <span className="text-gray-400 text-xs md:text-sm">Direct care HPRD</span>
              {showRankings && (
                <span className="text-xs text-gray-500 mt-0.5">
                  Rank #{data.rankings.directCareHPRDRank} ({data.rankings.directCareHPRDPercentile}th percentile)
                </span>
              )}
            </div>
            <span className="text-gray-300 font-semibold text-sm md:text-lg">{formatNumber(animatedDirectCareHPRD, 2)}</span>
          </div>
        </div>
        
        <div className="py-1 md:py-1.5 border-b border-gray-600">
          <div className="flex justify-between items-center mb-1">
            <div className="flex flex-col">
              <span className="text-gray-300 text-sm md:text-base">RN HPRD</span>
              {showRankings && (
                <span className="text-xs text-gray-500 mt-0.5">
                  Rank #{data.rankings.rnHPRDRank} ({data.rankings.rnHPRDPercentile}th percentile)
                </span>
              )}
            </div>
            <span className="text-white font-bold text-base md:text-xl">{formatNumber(animatedRNHPRD, 2)}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-gray-400 text-xs md:text-sm">RN direct care HPRD</span>
            <span className="text-gray-300 font-semibold text-sm md:text-lg">{formatNumber(animatedRNDirectCareHPRD, 2)}</span>
          </div>
        </div>
        
        {/* Ownership breakdown for state and region */}
        {data.ownership && (data.scope === 'state' || data.scope === 'region') && (
          <div className="pt-2 md:pt-3 mt-2 md:mt-3 border-t border-gray-600">
            <h3 className="text-sm md:text-base font-semibold text-gray-200 mb-2 md:mb-3">Ownership Type</h3>
            <div className="flex items-start gap-4">
              <OwnershipPieChart ownership={data.ownership} size={100} />
              <div className="flex-1 space-y-1.5">
                <div className="flex justify-between items-center py-1">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-sm bg-blue-400 flex-shrink-0"></div>
                    <span className="text-gray-300 text-sm">For-Profit</span>
                  </div>
                  <span className="text-white font-semibold text-sm">
                    {formatNumber(data.ownership.forProfit.count)} ({data.ownership.forProfit.percentage}%)
                  </span>
                </div>
                <div className="flex justify-between items-center py-1">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-sm bg-green-400 flex-shrink-0"></div>
                    <span className="text-gray-300 text-sm">Non-Profit</span>
                  </div>
                  <span className="text-white font-semibold text-sm">
                    {formatNumber(data.ownership.nonProfit.count)} ({data.ownership.nonProfit.percentage}%)
                  </span>
                </div>
                <div className="flex justify-between items-center py-1">
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-sm bg-purple-400 flex-shrink-0"></div>
                    <span className="text-gray-300 text-sm">Government</span>
                  </div>
                  <span className="text-white font-semibold text-sm">
                    {formatNumber(data.ownership.government.count)} ({data.ownership.government.percentage}%)
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </WrappedCard>
  );
};

