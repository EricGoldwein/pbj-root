import React from 'react';
import { WrappedCard } from '../WrappedCard';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';
import { useAnimatedNumber } from '../../../hooks/useAnimatedNumber';

interface USANationalScaleCardNewsProps {
  data: PBJWrappedData;
}

export const USANationalScaleCardNews: React.FC<USANationalScaleCardNewsProps> = ({ data }) => {
  if (data.scope !== 'usa') {
    return null;
  }

  const formatNumber = (num: number, decimals: number = 0): string => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const animatedResidents = useAnimatedNumber(Math.round(data.avgDailyResidents), 1200, 0);
  const animatedFacilities = useAnimatedNumber(data.facilityCount, 1200, 0);

  // Calculate total staff hours (approximate: HPRD * residents * days in quarter)
  const daysInQuarter = 91; // Q2 2025
  const totalStaffHours = (data.totalHPRD * data.avgDailyResidents * daysInQuarter) / 1000000; // In millions
  const animatedStaffHours = useAnimatedNumber(totalStaffHours, 1200, 1);

  return (
    <WrappedCard title="Scale" hideBadge>
      <div className="space-y-6 md:space-y-8 text-center">
        <div className="space-y-2">
          <div className="text-5xl md:text-6xl lg:text-7xl font-bold text-white">
            {formatNumber(animatedFacilities)}
          </div>
          <div className="text-gray-300 text-lg md:text-xl">nursing homes</div>
        </div>
        
        <div className="space-y-2">
          <div className="text-5xl md:text-6xl lg:text-7xl font-bold text-white">
            {formatNumber(animatedResidents)}
          </div>
          <div className="text-gray-300 text-lg md:text-xl">residents daily</div>
        </div>
        
        <div className="space-y-2 pt-4 border-t border-gray-600">
          <div className="text-5xl md:text-6xl lg:text-7xl font-bold text-white">
            {formatNumber(animatedStaffHours, 1)}M
          </div>
          <div className="text-gray-300 text-lg md:text-xl">staff hours per quarter</div>
        </div>
      </div>
    </WrappedCard>
  );
};

