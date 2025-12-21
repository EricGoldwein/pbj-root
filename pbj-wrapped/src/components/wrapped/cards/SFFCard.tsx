import React from 'react';
import { useNavigate } from 'react-router-dom';
import { WrappedCard } from '../WrappedCard';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';
import { shortenProviderName } from '../../../lib/wrapped/dataProcessor';

interface SFFCardProps {
  data: PBJWrappedData;
}

export const SFFCard: React.FC<SFFCardProps> = ({ data }) => {
  const navigate = useNavigate();

  const handleSFFClick = (e: React.MouseEvent) => {
    e.preventDefault();
    navigate('/sff');
  };

  const renderFacility = (facility: typeof data.sff.newThisQuarter[0]) => {
    // For state pages, show only city. For region/USA pages, show state.
    const location = data.scope === 'state' && facility.city 
      ? facility.city
      : facility.state;
    
    return (
      <div key={facility.provnum} className="py-1.5 border-b border-gray-600 last:border-0">
        <a
          href={facility.link}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-300 hover:text-blue-200 underline font-medium block mb-1"
          title={facility.name}
        >
          {shortenProviderName(facility.name, 35)}
        </a>
        <div className="text-sm text-gray-400">{location}</div>
      </div>
    );
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
        
        {data.sff.newThisQuarter.length > 0 && (
          <div className="mt-2">
            <h3 className="text-sm font-bold text-white mb-1">
              New this quarter
            </h3>
            <div className="space-y-0.5 mb-2">
              {data.sff.newThisQuarter.slice(0, 3).map(f => renderFacility(f))}
            </div>
            {data.scope === 'usa' && (
              <div className="pt-1.5 border-t border-gray-600">
                <a
                  href="/sff"
                  onClick={handleSFFClick}
                  className="block w-full py-2 px-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-all duration-200 text-center shadow-lg hover:shadow-xl text-xs cursor-pointer"
                >
                  View SFF Wrapped →
                </a>
              </div>
            )}
          </div>
        )}
        
        {data.sff.newThisQuarter.length === 0 && data.scope === 'usa' && (
          <div className="mt-2 pt-1.5 border-t border-gray-600">
            <a
              href="/sff"
              onClick={handleSFFClick}
              className="block w-full py-2 px-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-all duration-200 text-center shadow-lg hover:shadow-xl text-xs cursor-pointer"
            >
              View SFF Wrapped →
            </a>
          </div>
        )}
        
        {data.sff.newThisQuarter.length === 0 && data.scope !== 'usa' && (
          <p className="text-gray-400 text-xs mt-1.5">
            No nursing homes became SFF this quarter.
          </p>
        )}
      </div>
    </WrappedCard>
  );
};

