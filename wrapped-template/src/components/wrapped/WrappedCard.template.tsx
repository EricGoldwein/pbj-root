import React from 'react';
import { useWrappedContext } from './WrappedContext';

interface WrappedCardProps {
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
  username?: string; // Optional override, otherwise uses context
  hideBadge?: boolean; // Hide the {{BRAND_NAME}} badge
  noContainer?: boolean; // Skip the inner container styling for full-width content
}

export const WrappedCard: React.FC<WrappedCardProps> = ({
  title,
  subtitle,
  children,
  icon,
  className = '',
  username: usernameProp,
  hideBadge = false,
  noContainer = false,
}) => {
  // Try to get username from context, fallback to prop
  let username: string | undefined;
  try {
    const context = useWrappedContext();
    username = usernameProp || context.username;
  } catch {
    // Not in context, use prop
    username = usernameProp;
  }
  return (
    <div
      className={`flex flex-col items-center justify-center w-full px-4 md:px-6 py-2 max-w-full md:max-w-[480px] mx-auto relative ${className}`}
      style={{ minHeight: '100%' }}
    >
      <div className="relative z-10 w-full flex flex-col justify-center" style={{ minHeight: '100%', paddingBottom: '8px' }}>
        {/* {{BRAND_NAME}} branding badge */}
        {!hideBadge && (
          <div className="text-center mb-3 flex-shrink-0">
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-{{ACCENT_COLOR}}/20 backdrop-blur-sm rounded-full border-2 border-{{ACCENT_COLOR}}/50 shadow-lg">
              <span className="text-sm md:text-base text-{{ACCENT_COLOR}}-300 font-bold tracking-wide">
                {{BRAND_NAME}}
              </span>
            </div>
          </div>
        )}
        
        <div className="flex-1 flex flex-col justify-center">
          {icon && <div className="mb-3 md:mb-4 flex justify-center flex-shrink-0">{icon}</div>}
          {title && (
            <h1 className={`text-3xl md:text-4xl lg:text-5xl font-bold text-center mb-2 md:mb-3 flex-shrink-0 px-2 drop-shadow-2xl ${
              noContainer 
                ? 'bg-gradient-to-r from-{{ACCENT_COLOR}}-300 via-{{ACCENT_COLOR}}-200 to-{{ACCENT_COLOR}}-200 bg-clip-text text-transparent mt-4 md:mt-6'
                : 'bg-gradient-to-r from-white via-gray-100 to-gray-200 bg-clip-text text-transparent break-words'
            }`}>
              {title}
            </h1>
          )}
          {subtitle && (
            <p className="text-base md:text-lg lg:text-xl text-center text-gray-300 mb-3 md:mb-4 font-medium drop-shadow-lg flex-shrink-0 px-2">
              {subtitle}
            </p>
          )}
          {noContainer ? (
            <div className="flex-shrink-0">
              {children}
            </div>
          ) : (
            <div className="text-center text-base md:text-lg bg-black/70 backdrop-blur-md rounded-3xl p-5 md:p-6 lg:p-8 shadow-2xl border-2 border-{{ACCENT_COLOR}}/50 flex-shrink-0">
              {children}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

