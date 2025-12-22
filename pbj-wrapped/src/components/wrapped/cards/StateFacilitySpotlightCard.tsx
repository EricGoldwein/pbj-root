import React from 'react';
import { WrappedCard } from '../WrappedCard';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';
import { trackFacilityLinkClick } from '../../../utils/analytics';

interface StateFacilitySpotlightCardProps {
  data: PBJWrappedData;
}

export const StateFacilitySpotlightCard: React.FC<StateFacilitySpotlightCardProps> = ({ data }) => {
  if (data.scope !== 'state' || !data.spotlightFacility) {
    return null;
  }

  const facility = data.spotlightFacility;

  const formatHPRD = (num: number, decimals: number = 2): string => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const formatPercent = (num: number, decimals: number = 1): string => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  return (
    <WrappedCard title="" hideBadge>
      <div className="space-y-3 text-left">
        <h2 className="text-2xl md:text-3xl font-bold text-center mb-3 text-white">
          Phoebe J's PBJ <span className="text-blue-300">Spotlight</span>
        </h2>
        <p className="text-xs text-gray-400 text-center mb-3">
          One facility where staffing fell below expectations
        </p>

        {/* Facility Name & City */}
        <div className="pb-2 border-b border-gray-700">
          <h3 className="text-lg md:text-xl font-bold text-white mb-1">
            <span className="hidden md:inline">{facility.name}{facility.city ? ` (${facility.city})` : ''}</span>
            <span className="md:hidden">{facility.name}</span>
          </h3>
          {facility.city && (
            <p className="text-sm text-gray-300 md:hidden">{facility.city}</p>
          )}
        </div>

        {/* Status Badges */}
        <div className="flex flex-wrap gap-2 pb-2 border-b border-gray-700">
          {facility.sffStatus && (
            <span className={`inline-block px-2 py-1 text-xs font-semibold rounded ${
              facility.sffStatus === 'SFF' 
                ? 'bg-orange-500/20 text-orange-300'
                : 'bg-yellow-500/20 text-yellow-300'
            }`}>
              {facility.sffStatus}
            </span>
          )}
          {facility.ownershipType && (
            <span className="inline-block px-2 py-1 text-xs font-semibold rounded bg-gray-700/50 text-gray-300">
              {facility.ownershipType}
            </span>
          )}
        </div>

        {/* Key Metrics */}
        <div className="space-y-2">
          <div className="flex justify-between items-center py-1.5 border-b border-gray-700">
            <span className="text-gray-300 text-sm">Total Nurse HPRD (reported)</span>
            <span className="text-white font-bold text-base">{formatHPRD(facility.totalHPRD)}</span>
          </div>
          
          <div className="flex justify-between items-center py-1.5 border-b border-gray-700">
            <span className="text-gray-300 text-sm">Case-mix expected HPRD</span>
            <span className="text-gray-400 font-semibold text-base">{formatHPRD(facility.caseMixExpectedHPRD)}</span>
          </div>
          
          <div className="flex justify-between items-center py-1.5 border-b border-gray-700">
            <span className="text-gray-300 text-sm">% case-mix</span>
            <span className="text-red-400 font-bold text-base">
              {facility.caseMixExpectedHPRD > 0 
                ? formatPercent((facility.totalHPRD / facility.caseMixExpectedHPRD) * 100, 1) + '%'
                : 'N/A'}
            </span>
          </div>
          
          <div className="flex justify-between items-center py-1.5 border-b border-gray-700">
            <span className="text-gray-300 text-sm">QoQ change in total nurse HPRD</span>
            <span className="text-red-400 font-bold text-base flex items-center gap-1">
              <span>↓</span>
              {formatHPRD(Math.abs(facility.qoqChange))}
            </span>
          </div>
        </div>

        {/* Staffing Composition */}
        <div className="pt-2 space-y-1.5 border-t border-gray-700">
          <div className="flex justify-between items-center">
            <span className="text-gray-400 text-xs">RN HPRD</span>
            <span className="text-gray-300 text-xs font-semibold">{formatHPRD(facility.rnHPRD)}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-gray-400 text-xs">CNA HPRD</span>
            <span className="text-gray-300 text-xs font-semibold">{formatHPRD(facility.cnaHPRD)}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-gray-400 text-xs">% contract staffing</span>
            <span className="text-gray-300 text-xs font-semibold">{formatPercent(facility.contractPercent)}%</span>
          </div>
        </div>

        {/* CTA */}
        <div className="pt-3 mt-3 border-t border-gray-700">
          <a
            href={facility.link}
            target="_blank"
            rel="noopener noreferrer"
            className="block w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-all duration-200 text-center shadow-lg hover:shadow-xl text-sm"
            onClick={() => trackFacilityLinkClick(facility.provnum, facility.name, 'State Facility Spotlight')}
          >
            View full staffing history →
          </a>
        </div>
      </div>
    </WrappedCard>
  );
};

