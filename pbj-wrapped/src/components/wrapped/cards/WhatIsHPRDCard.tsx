import React from 'react';
import { WrappedCard } from '../WrappedCard';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';

interface WhatIsHPRDCardProps {
  data?: PBJWrappedData;
}

export const WhatIsHPRDCard: React.FC<WhatIsHPRDCardProps> = ({ data }) => {
  return (
    <WrappedCard title="What is HPRD?" hideBadge>
      <div className="space-y-3 text-left">
        <div className="bg-blue-500/10 border-l-4 border-blue-400 pl-3 md:pl-4 py-2 rounded">
          <p className="text-gray-200 text-xs md:text-sm leading-relaxed">
            <strong className="text-blue-300">HPRD</strong> stands for <strong className="text-white">Hours Per Resident Per Day</strong>—the average hours of nursing care each resident receives daily.
          </p>
        </div>
        
        <div className="space-y-2 pt-1">
          <div className="flex items-start gap-2">
            <span className="text-blue-400 font-bold text-xs mt-0.5">•</span>
            <div className="text-gray-300 text-xs flex-1">
              <strong className="text-white">Total HPRD:</strong> All nursing staff hours
            </div>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-blue-400 font-bold text-xs mt-0.5">•</span>
            <div className="text-gray-300 text-xs flex-1">
              <strong className="text-white">Direct Care HPRD:</strong> Hands-on care (RNs, LPNs, CNAs). Excludes Admin/DON staff.
            </div>
          </div>
          <div className="flex items-start gap-2">
            <span className="text-blue-400 font-bold text-xs mt-0.5">•</span>
            <div className="text-gray-300 text-xs flex-1">
              <strong className="text-white">RN HPRD:</strong> Registered nurse hours
            </div>
          </div>
        </div>
        
        {data?.scope === 'state' && data?.stateMinimum && (
          <div className="pt-2 border-t border-gray-700">
            <p className="text-gray-300 text-xs leading-relaxed">
              <strong className="text-red-300">State Minimum:</strong> {data.stateMinimum.minHPRD.toFixed(2)} HPRD
              {data.stateMinimum.isRange && data.stateMinimum.maxHPRD && (
                <span className="text-gray-400"> (range: {data.stateMinimum.minHPRD.toFixed(2)}-{data.stateMinimum.maxHPRD.toFixed(2)})</span>
              )}
            </p>
          </div>
        )}
        
        <div className="pt-2 border-t border-gray-700">
          <p className="text-gray-400 text-xs leading-relaxed">
            <strong className="text-blue-300">Why it matters:</strong> Higher HPRD indicates more staff time per resident, which correlates with care quality outcomes.
          </p>
        </div>
      </div>
    </WrappedCard>
  );
};

