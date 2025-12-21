import React from 'react';
import { WrappedCard } from '../WrappedCard';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';
import { useAnimatedNumber } from '../../../hooks/useAnimatedNumber';

interface StaffingIllusionCardProps {
  data: PBJWrappedData;
}

export const StaffingIllusionCard: React.FC<StaffingIllusionCardProps> = ({ data }) => {
  if (data.scope !== 'usa') {
    return null;
  }

  const formatNumber = (num: number, decimals: number = 2): string => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const animatedTotalHPRD = useAnimatedNumber(data.totalHPRD, 1200, 2);
  const animatedRNHPRD = useAnimatedNumber(data.rnHPRD, 1200, 2);
  const rnPercentage = (data.rnHPRD / data.totalHPRD) * 100;
  const animatedRNPercentage = useAnimatedNumber(rnPercentage, 1200, 1);

  return (
    <WrappedCard title="The Illusion" hideBadge>
      <div className="space-y-6 md:space-y-8 text-center">
        <div className="space-y-3">
          <div className="text-gray-400 text-sm uppercase tracking-wide">Average Total Staffing</div>
          <div className="text-4xl md:text-5xl lg:text-6xl font-bold text-white">
            {formatNumber(animatedTotalHPRD)} HPRD
          </div>
        </div>
        
        <div className="text-3xl text-gray-500">vs</div>
        
        <div className="space-y-3">
          <div className="text-gray-400 text-sm uppercase tracking-wide">Registered Nurses Only</div>
          <div className="text-4xl md:text-5xl lg:text-6xl font-bold text-orange-400">
            {formatNumber(animatedRNHPRD)} HPRD
          </div>
          <div className="text-lg text-gray-400">
            ({formatNumber(animatedRNPercentage)}% of total)
          </div>
        </div>
        
        <div className="pt-4 border-t border-gray-600">
          <p className="text-gray-300 text-sm md:text-base leading-relaxed">
            The gap between total staffing and RN staffing reveals where care quality actually sits.
          </p>
        </div>
      </div>
    </WrappedCard>
  );
};

