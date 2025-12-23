import React from 'react';
import { useNavigate } from 'react-router-dom';
import { WrappedCard } from '../WrappedCard';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';

interface SFFCardProps {
  data: PBJWrappedData;
}

export const SFFCard: React.FC<SFFCardProps> = ({ data }) => {
  const navigate = useNavigate();
  
  // Determine the SFF page path based on scope
  const getSFFPagePath = () => {
    if (data.scope === 'usa') {
      return '/sff/usa';
    } else if (data.scope === 'state') {
      const stateCode = data.name.toUpperCase();
      return `/sff/${stateCode.toLowerCase()}`;
    } else if (data.scope === 'region') {
      // identifier is like "region1", "region2", etc.
      return `/sff/${data.identifier}`;
    }
    return '/sff';
  };

  const handleSFFClick = (e: React.MouseEvent) => {
    e.preventDefault();
    navigate(getSFFPagePath());
  };

  // Get link text based on scope
  const getLinkText = () => {
    if (data.scope === 'usa') {
      return "View United States' SFF List →";
    } else if (data.scope === 'state') {
      return `View ${data.name}'s SFF List →`;
    } else if (data.scope === 'region') {
      return `View ${data.name}'s SFF List →`;
    }
    return "Learn more about SFFs →";
  };

  return (
    <WrappedCard title="Special Focus Facilities">
      <div className="space-y-1.5 md:space-y-2">
        <div className="bg-orange-500/10 border-l-4 border-orange-400 pl-2 md:pl-3 py-1 md:py-1.5 rounded mb-1 md:mb-1.5">
          <p className="text-gray-200 text-xs leading-relaxed">
            <strong className="text-orange-300">Special Focus Facilities</strong> are nursing homes with a history of serious quality problems. They receive more frequent inspections and enhanced oversight from CMS.
          </p>
        </div>
        
        <div className="flex justify-between items-center py-0.5 md:py-1 border-b border-gray-600">
          <span className="text-gray-300 text-sm">Special Focus Facilities</span>
          <span className="text-white font-bold text-base md:text-lg">{data.sff.currentSFFs}</span>
        </div>
        
        <div className="flex justify-between items-center py-0.5 md:py-1 border-b border-gray-600">
          <span className="text-gray-300 text-sm">SFF Candidates</span>
          <span className="text-white font-bold text-base md:text-lg">{data.sff.candidates}</span>
        </div>
        
          <div className="mt-2 pt-1.5 border-t border-gray-600">
          <button
            onClick={handleSFFClick}
            className="block w-full py-2 px-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-all duration-200 text-center shadow-lg hover:shadow-xl text-xs cursor-pointer"
            >
            {getLinkText()}
          </button>
          </div>
      </div>
    </WrappedCard>
  );
};

