import React from 'react';
import { WrappedCard } from '../WrappedCard';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';

interface MoversCardProps {
  data: PBJWrappedData;
}

export const MoversCard: React.FC<MoversCardProps> = ({ data }) => {
  const formatChange = (change: number): string => {
    const sign = change >= 0 ? '+' : '';
    return `${sign}${change.toFixed(2)}`;
  };

  const renderItem = (item: typeof data.movers.risersByHPRD[0], isDirectCare: boolean = false) => {
    // Check if it's a StateChange (has 'state' but no 'provnum', or has 'stateName')
    const isState = ('state' in item && !('provnum' in item)) || 'stateName' in item;
    const change = isDirectCare ? (item as any).directCareChange : item.change;
    const q1Value = isDirectCare ? (item as any).q1DirectCare : item.q1Value;
    const q2Value = isDirectCare ? (item as any).q2DirectCare : item.q2Value;
    
    if (isState) {
      const stateItem = item as any;
      const stateName = stateItem.stateName || stateItem.state;
      const isInternalLink = stateItem.link && stateItem.link.startsWith('/wrapped/');
      // Determine if this is a riser or decliner for color coding
      const isRiser = change > 0;
      const isDecliner = change < 0;
      
      const handleStateClick = (e: React.MouseEvent) => {
        if (isInternalLink) {
          e.preventDefault();
          window.location.href = stateItem.link;
        }
      };
      
      return (
        <div key={stateItem.state} className="py-2 md:py-1.5 border-b border-gray-700 last:border-0">
          <div className="flex justify-between items-start">
            {isInternalLink ? (
              <a
                href={stateItem.link}
                onClick={handleStateClick}
                className="text-blue-300 hover:text-blue-200 underline font-medium text-sm flex-1 cursor-pointer"
              >
                {stateName}
              </a>
            ) : (
              <a
                href={stateItem.link}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-300 hover:text-blue-200 underline font-medium text-sm flex-1"
              >
                {stateName}
              </a>
            )}
            <div className="text-right ml-2">
              <div className={`text-sm font-semibold ${isRiser ? 'text-green-400' : isDecliner ? 'text-red-400' : 'text-white'}`}>
                {formatChange(change)}
              </div>
              <div className="text-xs text-gray-500">
                {q1Value.toFixed(2)} → {q2Value.toFixed(2)}
              </div>
            </div>
          </div>
        </div>
      );
    } else {
      const facility = item as any;
      // For state pages, show only city. For region/USA pages, show state.
      const location = data.scope === 'state' && facility.city 
        ? facility.city
        : facility.state;
      
      // Determine if this is a riser or decliner for color coding
      const isRiser = change > 0;
      const isDecliner = change < 0;
      
      return (
        <div key={facility.provnum} className="py-2 md:py-1.5 border-b border-gray-700 last:border-0">
          <div className="flex justify-between items-start">
            <div className="flex-1 min-w-0">
              <a
                href={facility.link}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-300 hover:text-blue-200 underline font-medium text-sm block truncate"
              >
                {facility.name}
              </a>
              <div className="text-xs text-gray-500 truncate">{location}</div>
            </div>
            <div className="text-right ml-2 flex-shrink-0">
              <div className={`text-sm font-semibold ${isRiser ? 'text-green-400' : isDecliner ? 'text-red-400' : 'text-white'}`}>
                {formatChange(change)}
              </div>
              <div className="text-xs text-gray-500">
                {q1Value.toFixed(2)} → {q2Value.toFixed(2)}
              </div>
            </div>
          </div>
        </div>
      );
    }
  };

  return (
    <WrappedCard title="Biggest Movers">
      <div className="space-y-4 text-left">
        <div>
          <h3 className="text-lg font-bold text-white mb-2">Biggest Risers</h3>
          
          <div className="mb-3">
            <h4 className="text-xs font-semibold text-gray-400 mb-1.5 uppercase tracking-wide">By total HPRD</h4>
            <div className="space-y-0.5">
              {data.movers.risersByHPRD.slice(0, 3).map(f => renderItem(f))}
            </div>
          </div>
          
          <div>
            <h4 className="text-xs font-semibold text-gray-400 mb-1.5 uppercase tracking-wide">By direct care HPRD</h4>
            <div className="space-y-0.5">
              {data.movers.risersByDirectCare.slice(0, 3).map(f => renderItem(f, true))}
            </div>
          </div>
        </div>
        
        <div className="pt-2 border-t border-gray-700">
          <h3 className="text-lg font-bold text-white mb-2">Biggest Decliners</h3>
          
          <div className="mb-3">
            <h4 className="text-xs font-semibold text-gray-400 mb-1.5 uppercase tracking-wide">By total HPRD</h4>
            <div className="space-y-0.5">
              {data.movers.declinersByHPRD.slice(0, 3).map(f => renderItem(f))}
            </div>
          </div>
          
          <div>
            <h4 className="text-xs font-semibold text-gray-400 mb-1.5 uppercase tracking-wide">By direct care HPRD</h4>
            <div className="space-y-0.5">
              {data.movers.declinersByDirectCare.slice(0, 3).map(f => renderItem(f, true))}
            </div>
          </div>
        </div>
      </div>
    </WrappedCard>
  );
};

