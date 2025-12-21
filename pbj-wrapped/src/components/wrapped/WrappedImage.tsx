import React, { useState } from 'react';

interface WrappedImageProps {
  src: string;
  alt: string;
  className?: string;
  style?: React.CSSProperties;
  fallbackSrc?: string;
  onError?: (e: React.SyntheticEvent<HTMLImageElement, Event>) => void;
  containerClassName?: string;
  aspectRatio?: string;
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
      {isLoading && !hasError && (
        <div 
          className="absolute inset-0 bg-blue-500/20 animate-pulse rounded-2xl"
          style={{
            borderRadius: 'inherit',
          }}
        />
      )}
      
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
      
      {hasError && !fallbackSrc && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/20 rounded-2xl">
          <span className="text-blue-500/50 text-xs">Image unavailable</span>
        </div>
      )}
    </div>
  );
};


