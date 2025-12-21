import React from 'react';
import { WrappedCard } from '../WrappedCard';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';

interface SFFCardNewsProps {
  data: PBJWrappedData;
}

export const SFFCardNews: React.FC<SFFCardNewsProps> = ({ data }) => {
  if (data.scope !== 'usa') {
    return null;
  }

  const totalSFFAndCandidates = data.sff.currentSFFs + data.sff.candidates;
  const sffPercentage = data.facilityCount > 0 
    ? ((totalSFFAndCandidates / data.facilityCount) * 100).toFixed(1)
    : '0.0';

  return (
    <WrappedCard title="SFF Concentration" hideBadge>
      <div className="space-y-6 md:space-y-8 text-center">
        <div className="space-y-2">
          <div className="text-5xl md:text-6xl lg:text-7xl font-bold text-orange-400">
            {totalSFFAndCandidates.toLocaleString()}
          </div>
          <div className="text-gray-300 text-lg md:text-xl">
            facilities flagged by CMS
          </div>
        </div>
        
        <div className="space-y-2 pt-4 border-t border-gray-600">
          <div className="text-4xl md:text-5xl lg:text-6xl font-bold text-white">
            {sffPercentage}%
          </div>
          <div className="text-gray-300 text-base md:text-lg">
            of all nursing homes
          </div>
        </div>
        
        <div className="pt-4 border-t border-gray-600">
          <p className="text-gray-300 text-sm md:text-base leading-relaxed">
            These are the facilities CMS already flags—staffing still lags.
          </p>
        </div>
      </div>
    </WrappedCard>
  );
};

