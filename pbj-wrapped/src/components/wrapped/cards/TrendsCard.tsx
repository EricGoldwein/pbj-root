import React from 'react';
import { WrappedCard } from '../WrappedCard';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';
import { TrendArrow } from '../TrendArrow';

interface TrendsCardProps {
  data: PBJWrappedData;
}

export const TrendsCard: React.FC<TrendsCardProps> = ({ data }) => {
  const formatChange = (change: number, isPercent: boolean = false): string => {
    const sign = change >= 0 ? '+' : '';
    const formatted = change.toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return `${sign}${formatted}${isPercent ? '%' : ''}`;
  };

  // Check if all trends are exactly 0.00 (likely means Q1 data is missing)
  // This is a heuristic - if all four metrics are exactly 0.00, Q1 data is probably missing
  const allZero = data.trends.totalHPRDChange === 0 && 
                  data.trends.directCareHPRDChange === 0 && 
                  data.trends.rnHPRDChange === 0 &&
                  data.trends.contractPercentChange === 0;

  return (
    <WrappedCard title="Trends">
      <p className="text-gray-300 mb-3 text-sm">
        Changes from Q1 2025 to Q2 2025
      </p>
      
      {allZero && (
        <div className="mb-3 p-2.5 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
          <p className="text-yellow-300 text-xs leading-relaxed">
            <strong>Note:</strong> Q1 2025 data may not be available. If all trends show 0.00, check that{' '}
            {data.scope === 'region' ? (
              <>
                <code className="text-yellow-200">region_q1.json</code> contains Q1 data for this region
              </>
            ) : (
              <>
                <code className="text-yellow-200">state_q1.json</code> contains Q1 data for this state
              </>
            )}.
          </p>
        </div>
      )}
      
      <div className="space-y-3 text-left">
        <div className="py-1.5 border-b border-gray-600">
          <div className="flex justify-between items-center">
            <span className="text-gray-300">Total staffing HPRD</span>
            <div className="flex items-center gap-3">
              <span className={`font-bold text-lg ${data.trends.totalHPRDChange > 0 ? 'text-green-400' : data.trends.totalHPRDChange < 0 ? 'text-red-400' : 'text-white'}`}>
                {formatChange(data.trends.totalHPRDChange)}
              </span>
              <TrendArrow change={data.trends.totalHPRDChange} size={36} />
            </div>
          </div>
        </div>
        
        <div className="py-1.5 border-b border-gray-600">
          <div className="flex justify-between items-center">
            <span className="text-gray-300">Direct care HPRD</span>
            <div className="flex items-center gap-3">
              <span className={`font-bold text-lg ${data.trends.directCareHPRDChange > 0 ? 'text-green-400' : data.trends.directCareHPRDChange < 0 ? 'text-red-400' : 'text-white'}`}>
                {formatChange(data.trends.directCareHPRDChange)}
              </span>
              <TrendArrow change={data.trends.directCareHPRDChange} size={36} />
            </div>
          </div>
        </div>
        
        <div className="py-1.5 border-b border-gray-600">
          <div className="flex justify-between items-center">
            <span className="text-gray-300">RN staffing</span>
            <div className="flex items-center gap-3">
              <span className={`font-bold text-lg ${data.trends.rnHPRDChange > 0 ? 'text-green-400' : data.trends.rnHPRDChange < 0 ? 'text-red-400' : 'text-white'}`}>
                {formatChange(data.trends.rnHPRDChange)}
              </span>
              <TrendArrow change={data.trends.rnHPRDChange} size={36} />
            </div>
          </div>
        </div>
        
        <div className="py-1.5">
          <div className="flex justify-between items-center">
            <span className="text-gray-300">Contract staffing %</span>
            <div className="flex items-center gap-3">
              <span className="font-bold text-lg text-white">
                {formatChange(data.trends.contractPercentChange, true)}
              </span>
              <div className="flex items-center justify-center rounded-full w-9 h-9 bg-gray-700/50 border-2 border-gray-600">
                <span className="font-bold text-lg text-gray-300">
                  {data.trends.contractPercentChange > 0 ? '↑' : data.trends.contractPercentChange < 0 ? '↓' : '→'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </WrappedCard>
  );
};

