import React from 'react';
import { WrappedCard } from '../WrappedCard';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';

interface RankingsCardProps {
  data: PBJWrappedData;
}

export const RankingsCard: React.FC<RankingsCardProps> = ({ data }) => {
  // USA doesn't have rankings (it's the aggregate)
  if (data.scope === 'usa') {
    return (
      <WrappedCard title="Rankings">
        <p className="text-gray-300">
          National aggregate data is not ranked against states or regions.
        </p>
      </WrappedCard>
    );
  }

  const comparisonGroup = data.scope === 'state' ? 'U.S. states' : 'CMS regions';
  const totalCount = data.scope === 'state' ? 51 : 10;

  return (
    <WrappedCard title="Rankings">
      <p className="text-gray-400 mb-4 text-xs">
        Ranked against all {comparisonGroup}
      </p>
      
      <div className="space-y-3 text-left">
        <div className="py-2 border-b border-gray-600">
          <div className="flex justify-between items-center">
            <span className="text-gray-300 text-sm">Total staff HPRD</span>
            <div className="text-right">
              <span className="text-white font-bold text-lg">#{data.rankings.totalHPRDRank}</span>
              <span className="text-gray-400 text-sm ml-2">of {totalCount}</span>
            </div>
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {data.totalHPRD.toFixed(2)} HPRD
          </div>
        </div>
        
        <div className="py-2 border-b border-gray-600">
          <div className="flex justify-between items-center">
            <span className="text-gray-300 text-sm">Direct care HPRD</span>
            <div className="text-right">
              <span className="text-white font-bold text-lg">#{data.rankings.directCareHPRDRank}</span>
              <span className="text-gray-400 text-sm ml-2">of {totalCount}</span>
            </div>
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {data.directCareHPRD.toFixed(2)} HPRD
          </div>
        </div>
        
        <div className="py-2">
          <div className="flex justify-between items-center">
            <span className="text-gray-300 text-sm">RN staff HPRD</span>
            <div className="text-right">
              <span className="text-white font-bold text-lg">#{data.rankings.rnHPRDRank}</span>
              <span className="text-gray-400 text-sm ml-2">of {totalCount}</span>
            </div>
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {data.rnHPRD.toFixed(2)} HPRD
          </div>
        </div>
      </div>
    </WrappedCard>
  );
};


