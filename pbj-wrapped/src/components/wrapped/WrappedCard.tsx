import React from 'react';

interface WrappedCardProps {
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
  hideBadge?: boolean;
  noContainer?: boolean;
}

export const WrappedCard: React.FC<WrappedCardProps> = ({
  title,
  subtitle,
  children,
  icon,
  className = '',
  hideBadge = false,
  noContainer = false,
}) => {
  return (
    <div
      className={`flex flex-col items-center justify-center w-full h-full px-5 md:px-6 py-5 md:py-6 max-w-full md:max-w-[480px] mx-auto relative ${className}`}
      style={{ minHeight: '100%', height: '100%' }}
    >
      <div className="relative z-10 w-full flex flex-col justify-center items-center" style={{ minHeight: '100%', height: '100%', paddingBottom: '8px' }}>
        {!hideBadge && (
          <div className="text-center mb-3 flex-shrink-0 relative z-20">
            <a
              href="http://pbj320.com/wrapped"
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-500/20 backdrop-blur-sm rounded-full border-2 border-blue-500/50 shadow-lg no-underline relative z-20"
              style={{ textDecoration: 'none', pointerEvents: 'auto' }}
              onClick={(e) => e.stopPropagation()}
            >
              <span className="text-sm md:text-base text-blue-300 font-bold tracking-wide">
                PBJ Wrapped
              </span>
            </a>
          </div>
        )}
        
        <div className="flex-1 flex flex-col justify-center items-center w-full">
          {icon && <div className="mb-3 md:mb-4 flex justify-center flex-shrink-0">{icon}</div>}
          {title && (
            <h1 className={`text-3xl md:text-4xl lg:text-5xl font-bold text-center mb-2 md:mb-3 flex-shrink-0 px-2 drop-shadow-2xl leading-tight ${
              noContainer 
                ? 'bg-gradient-to-r from-blue-300 via-blue-200 to-blue-200 bg-clip-text text-transparent mt-4 md:mt-6'
                : 'bg-gradient-to-r from-white via-gray-100 to-gray-200 bg-clip-text text-transparent break-words'
            }`} style={{ lineHeight: '1.15', paddingBottom: '6px', paddingTop: '4px', marginBottom: '12px' }}>
              {title}
            </h1>
          )}
          {subtitle && (
            <p className="text-base md:text-lg lg:text-xl text-center text-gray-300 mb-3 md:mb-4 font-medium drop-shadow-lg flex-shrink-0 px-2">
              {subtitle}
            </p>
          )}
          {noContainer ? (
            <div className="flex-shrink-0 w-full">
              {children}
            </div>
          ) : (
            <div className="text-center text-base md:text-lg bg-black/70 backdrop-blur-md rounded-3xl p-4 md:p-5 lg:p-6 pb-6 md:pb-8 lg:pb-10 shadow-2xl border-2 border-blue-500/50 flex-shrink-0 w-full max-w-full overflow-y-auto max-h-[75vh] md:max-h-[80vh] scrollbar-thin scrollbar-thumb-blue-500/50 scrollbar-track-transparent transition-all duration-300 hover:border-blue-400/60 hover:shadow-blue-500/20">
              {children}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

