import React from 'react';
import { useNavigate } from 'react-router-dom';
import { WrappedCard } from '../WrappedCard';
import { WrappedImage } from '../WrappedImage';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';
import { getAssetPath } from '../../../utils/assets';

interface NavigationCardProps {
  data: PBJWrappedData;
  onReplay: () => void;
}

export const NavigationCard: React.FC<NavigationCardProps> = ({ onReplay }) => {
  const navigate = useNavigate();

  const handleStateSelect = () => {
    navigate('/');
  };

  const handleUSA = () => {
    navigate('/usa');
  };

  const handleReport = () => {
    window.open('https://pbj320.com/report', '_blank');
  };

  return (
    <WrappedCard title="Explore More" hideBadge>
      <div className="mb-3 flex justify-center">
        <WrappedImage 
          src={getAssetPath('/images/phoebe-wrapped-wide.png')} 
          alt="Phoebe" 
          className="max-w-[140px] md:max-w-[160px] h-auto opacity-85"
        />
      </div>
      <div className="space-y-2.5">
        <button
          onClick={onReplay}
          className="w-full py-2.5 md:py-3 px-4 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-600 active:from-blue-700 active:to-blue-800 text-white font-semibold rounded-lg transition-all duration-200 text-sm shadow-md hover:shadow-lg hover:scale-[1.01] active:scale-[0.99] touch-manipulation"
          style={{ minHeight: '44px' }}
        >
          ↻ Replay
        </button>
        
        <button
          onClick={handleUSA}
          className="w-full py-2.5 md:py-3 px-4 bg-gradient-to-r from-blue-500/90 to-blue-600/90 hover:from-blue-500 hover:to-blue-600 active:from-blue-600 active:to-blue-700 text-white font-semibold rounded-lg transition-all duration-200 text-sm shadow-md hover:shadow-lg hover:scale-[1.01] active:scale-[0.99] touch-manipulation"
          style={{ minHeight: '44px' }}
        >
          View USA Wrapped
        </button>
        
        <button
          onClick={handleStateSelect}
          className="w-full py-2.5 md:py-3 px-4 bg-gray-700/80 hover:bg-gray-600 active:bg-gray-500 text-white font-semibold rounded-lg transition-all duration-200 text-sm shadow-md hover:shadow-lg hover:scale-[1.01] active:scale-[0.99] touch-manipulation border border-gray-600/50 hover:border-gray-500"
          style={{ minHeight: '44px' }}
        >
          Choose Another State or Region
        </button>
        
        <button
          onClick={handleReport}
          className="w-full py-2.5 md:py-3 px-4 bg-gray-600/80 hover:bg-gray-500 active:bg-gray-400 text-white font-semibold rounded-lg transition-all duration-200 text-sm shadow-md hover:shadow-lg hover:scale-[1.01] active:scale-[0.99] touch-manipulation border border-gray-500/50 hover:border-gray-400"
          style={{ minHeight: '44px' }}
        >
          View Full Report
        </button>
      </div>
    </WrappedCard>
  );
};

