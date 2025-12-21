import React from 'react';
import { WrappedCard } from '../WrappedCard';
import { getAssetPath } from '../../../utils/assets';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';

interface KeyTakeawaysCardNewsProps {
  data: PBJWrappedData;
}

export const KeyTakeawaysCardNews: React.FC<KeyTakeawaysCardNewsProps> = ({ data }) => {
  if (data.scope !== 'usa') {
    return null;
  }

  const formatHPRD = (num: number): string => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  };

  // Select one strong takeaway - prioritize volatility, RN erosion, ownership divergence, or regional concentration
  const getTakeaway = () => {
    const trends = data.trends;
    const rnChange = typeof trends.rnHPRDChange === 'number' ? trends.rnHPRDChange : 0;
    const totalChange = typeof trends.totalHPRDChange === 'number' ? trends.totalHPRDChange : 0;
    
    // Check for RN erosion (declining RN while total stays flat or increases)
    if (rnChange < -0.05 && totalChange >= -0.02) {
      return {
        type: 'rn-erosion',
        text: `RN staffing declined by ${formatHPRD(Math.abs(rnChange))} HPRD while total staffing ${totalChange > 0 ? 'increased' : 'remained flat'}. Registered nurses are being replaced by lower-skilled staff.`,
      };
    }
    
    // Check for volatility (large swings)
    const maxChange = Math.max(Math.abs(rnChange), Math.abs(totalChange));
    if (maxChange > 0.1) {
      const metric = Math.abs(rnChange) > Math.abs(totalChange) ? 'RN staffing' : 'total staffing';
      const change = Math.abs(rnChange) > Math.abs(totalChange) ? rnChange : totalChange;
      return {
        type: 'volatility',
        text: `${metric.charAt(0).toUpperCase() + metric.slice(1)} swung ${change > 0 ? 'up' : 'down'} by ${formatHPRD(Math.abs(change))} HPRD from Q1 to Q2. This volatility signals systemic instability in care delivery.`,
      };
    }
    
    // Check ownership divergence (if available)
    if (data.ownership?.forProfit?.medianHPRD && data.ownership?.nonProfit?.medianHPRD) {
      const forProfit = data.ownership.forProfit.medianHPRD;
      const nonProfit = data.ownership.nonProfit.medianHPRD;
      if (forProfit < nonProfit - 0.2) {
        return {
          type: 'ownership-divergence',
          text: `For-profit facilities average ${formatHPRD(forProfit)} HPRD, while non-profits average ${formatHPRD(nonProfit)}. The ownership model directly impacts staffing levels.`,
        };
      }
    }
    
    // Default: regional concentration
    const bottomStates = data.extremes.bottomStatesByHPRD || [];
    const topStates = data.extremes.topStatesByHPRD || [];
    if (bottomStates.length > 0 && topStates.length > 0) {
      const range = topStates[0].value - bottomStates[0].value;
      return {
        type: 'regional-concentration',
        text: `The gap between highest and lowest staffing states is ${formatHPRD(range)} HPRD. Geographic location determines care quality more than federal standards.`,
      };
    }
    
    // Fallback
    return {
      type: 'default',
      text: `Nationwide staffing averages ${formatHPRD(data.totalHPRD)} HPRD, but this masks extreme variation between facilities and states.`,
    };
  };

  const takeaway = getTakeaway();

  return (
    <WrappedCard title="Phoebe J's Takeaway" hideBadge>
      <div className="space-y-4 text-center">
        <div className="flex justify-center mb-4">
          <img 
            src={getAssetPath('/images/phoebe.png')} 
            alt="Phoebe J" 
            className="w-16 h-16 md:w-20 md:h-20 rounded-full border-2 border-blue-400"
          />
        </div>
        <p className="text-gray-200 text-base md:text-lg lg:text-xl leading-relaxed font-medium">
          {takeaway.text}
        </p>
        <p className="text-xs text-gray-500 text-center pt-3 border-t border-gray-700">
          Source: CMS PBJ Q2 2025
        </p>
      </div>
    </WrappedCard>
  );
};

