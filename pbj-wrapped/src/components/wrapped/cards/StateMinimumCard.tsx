import React from 'react';
import { WrappedCard } from '../WrappedCard';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';

interface StateMinimumCardProps {
  data: PBJWrappedData;
}

export const StateMinimumCard: React.FC<StateMinimumCardProps> = ({ data }) => {
  if (!data.stateMinimum || data.scope !== 'state') {
    return null;
  }

  const formatHPRD = (num: number): string => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  };

  return (
    <WrappedCard title="State Minimum">
      <div className="space-y-3 text-center">
        <div className="bg-blue-500/10 border-2 border-blue-500/50 rounded-lg p-4 md:p-5">
          <div className="text-xs md:text-sm text-gray-400 uppercase tracking-wide mb-2">
            Required Minimum
          </div>
          <div className="text-3xl md:text-4xl font-bold text-white mb-2">
            {data.stateMinimum.isRange 
              ? `${formatHPRD(data.stateMinimum.minHPRD)}-${formatHPRD(data.stateMinimum.maxHPRD!)}`
              : formatHPRD(data.stateMinimum.minHPRD)
            } HPRD
          </div>
          <div className="text-xs md:text-sm text-gray-300">
            {data.stateMinimum.isRange 
              ? `Range: ${formatHPRD(data.stateMinimum.minHPRD)} to ${formatHPRD(data.stateMinimum.maxHPRD!)} hours per resident per day`
              : `${formatHPRD(data.stateMinimum.minHPRD)} hours per resident per day`
            }
          </div>
        </div>
        
        <div className="pt-2 border-t border-gray-700">
          <p className="text-xs text-gray-400 leading-relaxed">
            This state has a minimum staffing requirement above the federal standard (0.30 HPRD). 
            Nursing homes must meet or exceed this level.
          </p>
        </div>
      </div>
    </WrappedCard>
  );
};

