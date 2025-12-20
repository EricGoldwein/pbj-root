import React from 'react';
import { WrappedCard } from '../WrappedCard';
import { WrappedImage } from '../WrappedImage';
import { StateOutline } from '../StateOutline';
import { useWrappedContext } from '../WrappedContext';
import { getAssetPath } from '../../../utils/assets';

interface HeaderCardProps {
  name: string;
}

export const HeaderCard: React.FC<HeaderCardProps> = ({ name }) => {
  const context = useWrappedContext();
  const isState = context.scope === 'state';
  const stateCode = isState ? name.toUpperCase() : null;

  return (
    <WrappedCard
      title="PBJ Wrapped"
      subtitle={name ? `${name} • Q2 2025` : "Q2 2025"}
      className="relative overflow-hidden"
      hideBadge={true}
      noContainer={true}
    >
      {/* State SVG border for state pages */}
      {isState && stateCode && (
        <div className="absolute inset-0 pointer-events-none opacity-10 z-0">
          <StateOutline stateCode={stateCode} className="w-full h-full" />
        </div>
      )}
      
      <div className="space-y-3 md:space-y-4 relative z-10">
        {isState && stateCode ? (
          <div className="flex flex-col items-center gap-3 md:gap-4">
            <WrappedImage
              src={getAssetPath('/images/phoebe-wrapped-wide.png')}
              alt="PBJ Wrapped"
              className="block relative rounded-lg"
              style={{ 
                maxHeight: '120px', 
                maxWidth: '100%',
                height: 'auto',
                width: 'auto',
                objectFit: 'contain',
              }}
              maxHeight="120px"
            />
            <a
              href="https://pbj320.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-300 hover:text-blue-200 underline text-base md:text-lg font-medium"
            >
              pbj320.com
            </a>
          </div>
        ) : (
          <>
            <div className="flex justify-center">
              <WrappedImage
                src={getAssetPath('/images/phoebe-wrapped-wide.png')}
                alt="PBJ Wrapped"
                className="block relative rounded-lg"
                style={{ 
                  maxHeight: '250px', 
                  maxWidth: '100%',
                  height: 'auto',
                  width: 'auto',
                  objectFit: 'contain',
                }}
                maxHeight="250px"
              />
            </div>
            <div className="text-center">
              <a
                href="https://pbj320.com"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-300 hover:text-blue-200 underline text-base md:text-lg font-medium"
              >
                pbj320.com
              </a>
            </div>
          </>
        )}
      </div>
    </WrappedCard>
  );
};

