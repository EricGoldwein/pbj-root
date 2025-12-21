import React from 'react';
import { WrappedCard } from '../WrappedCard';
import { WrappedImage } from '../WrappedImage';
import { getAssetPath } from '../../../utils/assets';

export const HeaderCardNews: React.FC = () => {
  return (
    <WrappedCard
      title="This is what federal nursing home staffing data actually shows."
      className="relative overflow-hidden"
      hideBadge={true}
      noContainer={true}
    >
      <div className="space-y-4 md:space-y-5 relative z-10">
        <div className="flex justify-center">
          <WrappedImage
            src={getAssetPath('/images/phoebe-wrapped-wide.png')}
            alt="PBJ Wrapped"
            className="block relative rounded-lg shadow-xl"
            style={{ 
              maxHeight: '200px', 
              maxWidth: '100%',
              height: 'auto',
              width: 'auto',
              objectFit: 'contain',
            }}
            maxHeight="200px"
          />
        </div>
        <div className="text-center">
          <p className="text-gray-300 text-sm md:text-base mt-2">
            Q2 2025 • CMS Payroll-Based Journal
          </p>
        </div>
      </div>
    </WrappedCard>
  );
};

