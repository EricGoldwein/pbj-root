import React from 'react';
import { WrappedCard } from '../WrappedCard';
import { WrappedImage } from '../WrappedImage';
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
      subtitle={name ? `${name} • 2025` : "2025"}
      className="relative overflow-hidden"
      hideBadge={true}
      noContainer={true}
    >
      <div className="space-y-4 md:space-y-5 relative z-10">
        {isState && stateCode ? (
          <div className="flex flex-col items-center gap-4 md:gap-5">
            <WrappedImage
              src={getAssetPath('/images/phoebe-wrapped-wide.png')}
              alt="PBJ Wrapped"
              className="block relative rounded-lg shadow-lg"
              style={{ 
                maxHeight: '140px', 
                maxWidth: '100%',
                height: 'auto',
                width: 'auto',
                objectFit: 'contain',
              }}
              maxHeight="140px"
            />
            <a
              href="https://pbj320.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-300 hover:text-blue-200 transition-colors duration-200 text-base md:text-lg font-semibold hover:underline"
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
                className="block relative rounded-2xl shadow-xl"
                style={{ 
                  maxHeight: '280px', 
                  maxWidth: '100%',
                  height: 'auto',
                  width: 'auto',
                  objectFit: 'contain',
                  borderRadius: '1rem',
                }}
                maxHeight="280px"
              />
            </div>
            <div className="text-center">
              <a
                href="https://pbj320.com"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-block text-blue-300 hover:text-blue-200 transition-colors duration-200 text-lg md:text-xl font-semibold hover:underline px-4 py-2 rounded-lg hover:bg-blue-500/10"
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

