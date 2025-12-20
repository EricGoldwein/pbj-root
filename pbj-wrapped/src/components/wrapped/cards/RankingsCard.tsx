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
  const showPercentile = data.scope === 'state';

  return (
    <WrappedCard title="Rankings">
      <p className="text-gray-400 mb-3 text-xs">
        Ranked against all {comparisonGroup}
      </p>
      
      <div className="space-y-4 text-left">
        <div className="py-2 border-b border-gray-600">
          <div className="flex justify-between items-center mb-3">
            <span className="text-gray-300 text-sm">Total staffing HPRD</span>
            <div className="text-right">
              <span className="text-white font-bold text-lg">#{data.rankings.totalHPRDRank}</span>
              <span className="text-gray-400 text-sm ml-2">of {totalCount}</span>
              <span className="text-gray-400 text-sm ml-2">({data.totalHPRD.toFixed(2)})</span>
            </div>
          </div>
          {showPercentile && (
            <div className="flex items-center gap-2">
              <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-blue-500 rounded-full transition-all duration-500"
                  style={{ width: `${data.rankings.totalHPRDPercentile}%` }}
                />
              </div>
              <span className="text-xs text-gray-400 min-w-[50px] text-right">
                {data.rankings.totalHPRDPercentile}th percentile
              </span>
            </div>
          )}
        </div>
        
        <div className="py-2 border-b border-gray-600">
          <div className="flex justify-between items-center mb-3">
            <span className="text-gray-300 text-sm">Direct care HPRD</span>
            <div className="text-right">
              <span className="text-white font-bold text-lg">#{data.rankings.directCareHPRDRank}</span>
              <span className="text-gray-400 text-sm ml-2">of {totalCount}</span>
              <span className="text-gray-400 text-sm ml-2">({data.directCareHPRD.toFixed(2)})</span>
            </div>
          </div>
          {showPercentile && (
            <div className="flex items-center gap-2">
              <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-green-500 rounded-full transition-all duration-500"
                  style={{ width: `${data.rankings.directCareHPRDPercentile}%` }}
                />
              </div>
              <span className="text-xs text-gray-400 min-w-[50px] text-right">
                {data.rankings.directCareHPRDPercentile}th percentile
              </span>
            </div>
          )}
        </div>
        
        <div className="py-2">
          <div className="flex justify-between items-center mb-3">
            <span className="text-gray-300 text-sm">RN staffing HPRD</span>
            <div className="text-right">
              <span className="text-white font-bold text-lg">#{data.rankings.rnHPRDRank}</span>
              <span className="text-gray-400 text-sm ml-2">of {totalCount}</span>
              <span className="text-gray-400 text-sm ml-2">({data.rnHPRD.toFixed(2)})</span>
            </div>
          </div>
          {showPercentile && (
            <div className="flex items-center gap-2">
              <div className="flex-1 h-2 bg-gray-700 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-purple-500 rounded-full transition-all duration-500"
                  style={{ width: `${data.rankings.rnHPRDPercentile}%` }}
                />
              </div>
              <span className="text-xs text-gray-400 min-w-[50px] text-right">
                {data.rankings.rnHPRDPercentile}th percentile
              </span>
            </div>
          )}
        </div>
      </div>
    </WrappedCard>
  );
};

