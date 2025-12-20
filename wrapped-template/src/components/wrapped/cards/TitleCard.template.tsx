import React from 'react';
import { WrappedCard } from '../WrappedCard';
import { WrappedImage } from '../WrappedImage';
import { wrappedCopy } from '../../../lib/wrapped/wrappedCopy';

interface TitleCardProps {
  username: string;
  avatarUrl?: string;
}

export const TitleCard: React.FC<TitleCardProps> = ({ username, avatarUrl }) => {
  // Customize special user handling if needed
  // const isSpecialUser = username.toLowerCase().includes('special');
  
  return (
    <WrappedCard
      title={wrappedCopy.title.main}
      subtitle={wrappedCopy.title.subtitle}
      className="relative"
      username={username}
      hideBadge={true}
      noContainer={true}
    >
      <div className="space-y-4 md:space-y-6 relative z-10">
        {/* Full-size avatar image with username overlay at bottom */}
        {avatarUrl && (
          <div className="flex justify-center mb-4 md:mb-6">
            <div className="relative" style={{ maxWidth: '100%', width: 'fit-content' }}>
              <div className="absolute inset-0 bg-{{ACCENT_COLOR}}-400 blur-3xl opacity-40 animate-pulse rounded-2xl"></div>
              <div className="relative rounded-2xl border-4 border-{{ACCENT_COLOR}}-400 shadow-2xl overflow-hidden" style={{ zIndex: 1 }}>
                <WrappedImage
                  src={avatarUrl}
                  alt={`${username}'s avatar`}
                  fallbackSrc="/avatars/default.png"
                  className="block relative"
                  style={{ 
                    maxHeight: '380px', 
                    maxWidth: '100%',
                    height: 'auto',
                    width: 'auto',
                    objectFit: 'contain',
                    display: 'block',
                    zIndex: 1
                  }}
                  maxHeight="380px"
                />
                {/* Username overlay at bottom */}
                <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 via-black/70 to-transparent p-4 md:p-5" style={{ zIndex: 50 }}>
                  <div className="text-3xl md:text-4xl lg:text-5xl font-bold text-white drop-shadow-2xl break-words text-center" style={{ zIndex: 50 }}>
                    {username}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
        
        {/* Add special content for specific users if needed */}
        {/* {isSpecialUser && (
          <div className="flex justify-center mb-4 md:mb-6 relative z-50">
            <video 
              src="/special-video.MOV" 
              autoPlay 
              loop 
              muted 
              playsInline
              preload="auto"
              className="rounded-2xl border-4 border-{{ACCENT_COLOR}}-400 shadow-2xl"
              style={{ 
                maxHeight: '250px', 
                maxWidth: '100%',
                height: 'auto',
                width: 'auto',
                pointerEvents: 'auto',
                touchAction: 'manipulation'
              }}
            />
          </div>
        )} */}
      </div>
    </WrappedCard>
  );
};

