import React, { useState } from 'react';

interface WrappedImageProps {
  src: string;
  alt: string;
  className?: string;
  style?: React.CSSProperties;
  fallbackSrc?: string;
  onError?: (e: React.SyntheticEvent<HTMLImageElement, Event>) => void;
  containerClassName?: string;
  aspectRatio?: string; // e.g., "16/9", "1/1", "4/3"
  maxHeight?: string | number;
  maxWidth?: string | number;
}

export const WrappedImage: React.FC<WrappedImageProps> = ({
  src,
  alt,
  className = '',
  style = {},
  fallbackSrc,
  onError,
  containerClassName = '',
  aspectRatio,
  maxHeight,
  maxWidth,
}) => {
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);
  const [currentSrc, setCurrentSrc] = useState(src);

  const handleLoad = () => {
    setIsLoading(false);
  };

  const handleError = (e: React.SyntheticEvent<HTMLImageElement, Event>) => {
    setIsLoading(false);
    
    // Try fallback if available and not already using it
    if (fallbackSrc && currentSrc !== fallbackSrc) {
      setCurrentSrc(fallbackSrc);
      setHasError(false);
      return;
    }
    
    setHasError(true);
    if (onError) {
      onError(e);
    }
  };

  const containerStyle: React.CSSProperties = {
    position: 'relative',
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    ...(aspectRatio && {
      aspectRatio,
    }),
    ...(maxHeight && { maxHeight }),
    ...(maxWidth && { maxWidth }),
  };

  return (
    <div className={containerClassName} style={containerStyle}>
      {/* Loading placeholder */}
      {isLoading && !hasError && (
        <div 
          className="absolute inset-0 bg-{{ACCENT_COLOR}}/20 animate-pulse rounded-2xl"
          style={{
            borderRadius: 'inherit',
          }}
        />
      )}
      
      {/* Image */}
      <img
        src={currentSrc}
        alt={alt}
        className={`${className} ${isLoading ? 'opacity-0' : 'opacity-100'} transition-opacity duration-300`}
        style={{
          ...style,
          position: 'relative',
          zIndex: 1,
        }}
        onLoad={handleLoad}
        onError={handleError}
        loading="eager"
      />
      
      {/* Error state - hidden by default, can be styled if needed */}
      {hasError && !fallbackSrc && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/20 rounded-2xl">
          <span className="text-{{ACCENT_COLOR}}/50 text-xs">Image unavailable</span>
        </div>
      )}
    </div>
  );
};

