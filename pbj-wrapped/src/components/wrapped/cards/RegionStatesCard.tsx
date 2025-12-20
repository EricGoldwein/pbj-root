import React from 'react';
import { WrappedCard } from '../WrappedCard';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';
import { useNavigate } from 'react-router-dom';

interface RegionStatesCardProps {
  data: PBJWrappedData;
}

export const RegionStatesCard: React.FC<RegionStatesCardProps> = ({ data }) => {
  const navigate = useNavigate();
  
  if (data.scope !== 'region' || !data.regionStates) {
    return null;
  }

  const formatHPRD = (num: number): string => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  };

  const handleStateClick = (e: React.MouseEvent, stateCode: string) => {
    e.preventDefault();
    navigate(`/${stateCode.toLowerCase()}`);
  };

  // Sort states by total HPRD (descending)
  const sortedStates = [...data.regionStates].sort((a, b) => b.totalHPRD - a.totalHPRD);

  return (
    <WrappedCard title="States in This Region">
      <div className="space-y-2 text-left">
        {sortedStates.map((stateInfo) => (
          <div 
            key={stateInfo.state} 
            className="py-2 border-b border-gray-600 last:border-0"
          >
            <div className="flex justify-between items-start mb-1">
              <a
                href={`/${stateInfo.state.toLowerCase()}`}
                onClick={(e) => handleStateClick(e, stateInfo.state)}
                className="text-blue-300 hover:text-blue-200 underline font-medium text-sm cursor-pointer"
              >
                {stateInfo.stateName}
              </a>
              <div className="text-right ml-2">
                <div className="text-white font-bold text-sm">
                  {formatHPRD(stateInfo.totalHPRD)} HPRD
                </div>
              </div>
            </div>
            {stateInfo.stateMinimum && (
              <div className="text-xs text-gray-400 mt-0.5">
                State minimum: {stateInfo.stateMinimum.minHPRD.toFixed(2)} HPRD
              </div>
            )}
          </div>
        ))}
      </div>
    </WrappedCard>
  );
};

