import React, { useState, useEffect, useRef, useImperativeHandle, forwardRef } from 'react';
import { StateOutline } from './StateOutline';

export interface WrappedNavigationRef {
  next: () => void;
  previous: () => void;
  goTo: (index: number) => void;
}

interface WrappedScreenWrapperProps {
  screens: React.ReactElement[];
  slideDurations: number[];
  scope?: 'usa' | 'state' | 'region';
  stateCode?: string;
}

export const WrappedScreenWrapper = forwardRef<WrappedNavigationRef, WrappedScreenWrapperProps>(
  ({ screens, slideDurations, scope, stateCode }, ref) => {
    const [currentIndex, setCurrentIndex] = useState(0);
    const [isPaused, setIsPaused] = useState(false);
    const timeoutRef = useRef<NodeJS.Timeout | null>(null);
    const touchStartX = useRef<number | null>(null);
    const touchEndX = useRef<number | null>(null);

    useImperativeHandle(ref, () => ({
      next: () => {
        if (currentIndex < screens.length - 1) {
          setCurrentIndex(currentIndex + 1);
        }
      },
      previous: () => {
        if (currentIndex > 0) {
          setCurrentIndex(currentIndex - 1);
        }
      },
      goTo: (index: number) => {
        if (index >= 0 && index < screens.length) {
          setCurrentIndex(index);
        }
      },
    }));

    // Auto-advance slides (only if not paused and duration is not Infinity)
    useEffect(() => {
      if (!isPaused && currentIndex < screens.length - 1) {
        const duration = slideDurations[currentIndex] || 4000;
        // Skip auto-advance if duration is Infinity (click-to-advance only)
        if (duration !== Infinity && isFinite(duration)) {
          timeoutRef.current = setTimeout(() => {
            setCurrentIndex(currentIndex + 1);
          }, duration);
        }
      }

      return () => {
        if (timeoutRef.current) {
          clearTimeout(timeoutRef.current);
        }
      };
    }, [currentIndex, screens.length, slideDurations, isPaused]);

    // Touch navigation
    const handleTouchStart = (e: React.TouchEvent) => {
      touchStartX.current = e.touches[0].clientX;
    };

    const handleTouchEnd = (e: React.TouchEvent) => {
      touchEndX.current = e.changedTouches[0].clientX;
      handleSwipe();
    };

    const handleSwipe = () => {
      if (touchStartX.current === null || touchEndX.current === null) return;

      const diff = touchStartX.current - touchEndX.current;
      const minSwipeDistance = 50;

      if (Math.abs(diff) > minSwipeDistance) {
        if (diff > 0 && currentIndex < screens.length - 1) {
          // Swipe left - next
          setCurrentIndex(currentIndex + 1);
        } else if (diff < 0 && currentIndex > 0) {
          // Swipe right - previous
          setCurrentIndex(currentIndex - 1);
        }
      }

      touchStartX.current = null;
      touchEndX.current = null;
    };

    // Handle tap/click on mobile to advance slides
    const handleScreenClick = (e: React.MouseEvent) => {
      // Only handle clicks on mobile (screen width <= 768px)
      // Don't advance if clicking on interactive elements (links, buttons, etc.)
      const target = e.target as HTMLElement;
      if (target.closest('a, button, input, select, textarea')) {
        return;
      }
      
      // Check if mobile
      if (window.innerWidth <= 768 && currentIndex < screens.length - 1) {
        setCurrentIndex(currentIndex + 1);
      }
    };

    // Keyboard navigation
    useEffect(() => {
      const handleKeyPress = (e: KeyboardEvent) => {
        if (e.key === 'ArrowRight' && currentIndex < screens.length - 1) {
          setCurrentIndex(currentIndex + 1);
        } else if (e.key === 'ArrowLeft' && currentIndex > 0) {
          setCurrentIndex(currentIndex - 1);
        } else if (e.key === ' ' || e.key === 'Space') {
          e.preventDefault();
          setIsPaused(!isPaused);
        }
      };

      window.addEventListener('keydown', handleKeyPress);
      return () => window.removeEventListener('keydown', handleKeyPress);
    }, [currentIndex, screens.length, isPaused]);

    if (screens.length === 0) {
      return null;
    }

    return (
      <div
        className="relative w-full h-full bg-gradient-to-br from-gray-900 via-blue-900 to-gray-900 overflow-hidden"
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
        style={{ height: '100dvh', maxHeight: '100dvh' }}
      >
        {/* State outline background - only for state scope */}
        {scope === 'state' && stateCode && (
          <div 
            className="absolute inset-0 flex items-center justify-center pointer-events-none z-0"
            style={{ 
              opacity: 0.15,
            }}
          >
            <div className="w-full h-full" style={{ maxWidth: '90vw', maxHeight: '90vh', minWidth: '600px', minHeight: '600px' }}>
              <StateOutline stateCode={stateCode} className="w-full h-full" />
            </div>
          </div>
        )}

        {/* Current screen with smooth slide transition */}
        <div 
          key={currentIndex}
          className={`absolute inset-0 flex items-center justify-center z-10 ${
            slideDurations[currentIndex] === Infinity && currentIndex < screens.length - 1
              ? 'cursor-pointer' 
              : currentIndex < screens.length - 1
              ? 'md:cursor-default cursor-pointer'
              : ''
          }`}
          onClick={(e) => {
            // If this slide is click-to-advance only and not the last slide, advance on click
            if (slideDurations[currentIndex] === Infinity && currentIndex < screens.length - 1) {
              setCurrentIndex(currentIndex + 1);
            } else {
              // On mobile, allow tap anywhere to advance (handled in handleScreenClick)
              handleScreenClick(e);
            }
          }}
          style={{ 
            height: '100%', 
            width: '100%',
            animation: 'slideFadeIn 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
          }}
        >
          {screens[currentIndex]}
        </div>


        {/* Navigation Controls */}
        {screens.length > 1 && (
          <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 z-20 flex items-center gap-3 md:gap-4">
            {/* Previous Button */}
            <button
              onClick={() => {
                if (currentIndex > 0) {
                  setCurrentIndex(currentIndex - 1);
                }
              }}
              disabled={currentIndex === 0}
              className={`p-2 md:p-2.5 rounded-full bg-black/60 backdrop-blur-sm border-2 transition-all duration-200 ${
                currentIndex === 0
                  ? 'border-gray-700 text-gray-600 cursor-not-allowed opacity-50'
                  : 'border-blue-500/50 text-blue-300 hover:bg-blue-500/20 hover:border-blue-400 active:scale-95'
              }`}
              aria-label="Previous slide"
            >
              <svg className="w-5 h-5 md:w-6 md:h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>

            {/* Slide Counter & Pause */}
            <div className="flex items-center gap-2 px-3 md:px-4 py-2 bg-black/60 backdrop-blur-sm border-2 border-blue-500/50 rounded-full">
              <button
                onClick={() => setIsPaused(!isPaused)}
                className="text-blue-300 hover:text-blue-200 transition-colors"
                aria-label={isPaused ? 'Play' : 'Pause'}
              >
                {isPaused ? (
                  <svg className="w-4 h-4 md:w-5 md:h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7z" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4 md:w-5 md:h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
                  </svg>
                )}
              </button>
              <span className="text-xs md:text-sm text-gray-300 font-medium min-w-[60px] md:min-w-[70px] text-center">
                {currentIndex + 1} / {screens.length}
              </span>
            </div>

            {/* Next Button */}
            <button
              onClick={() => {
                if (currentIndex < screens.length - 1) {
                  setCurrentIndex(currentIndex + 1);
                }
              }}
              disabled={currentIndex === screens.length - 1}
              className={`p-2 md:p-2.5 rounded-full bg-black/60 backdrop-blur-sm border-2 transition-all duration-200 ${
                currentIndex === screens.length - 1
                  ? 'border-gray-700 text-gray-600 cursor-not-allowed opacity-50'
                  : 'border-blue-500/50 text-blue-300 hover:bg-blue-500/20 hover:border-blue-400 active:scale-95'
              }`}
              aria-label="Next slide"
            >
              <svg className="w-5 h-5 md:w-6 md:h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        )}

        {/* Clickable Progress bar */}
        {screens.length > 1 && (
          <div 
            className="absolute bottom-0 left-0 right-0 h-2 bg-gray-800/50 z-10 cursor-pointer group"
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              const clickX = e.clientX - rect.left;
              const percentage = clickX / rect.width;
              const targetIndex = Math.min(Math.max(0, Math.floor(percentage * screens.length)), screens.length - 1);
              setCurrentIndex(targetIndex);
            }}
            title="Click to jump to any slide"
          >
            <div
              className={`h-full bg-blue-500 transition-all duration-500 ease-out ${isPaused ? 'opacity-50' : ''}`}
              style={{
                width: `${((currentIndex + 1) / screens.length) * 100}%`,
              }}
            />
            {/* Slide segment markers */}
            <div className="absolute inset-0 flex">
              {screens.map((_, index) => (
                <div
                  key={index}
                  className="flex-1 h-full border-r border-gray-700/30 last:border-r-0 hover:bg-blue-400/20 transition-colors"
                  title={`Slide ${index + 1}`}
                />
              ))}
            </div>
          </div>
        )}

        {/* Navigation hint (only show on first slide) */}
        {currentIndex === 0 && screens.length > 1 && (
          <div className="absolute top-4 right-4 z-20 bg-black/60 backdrop-blur-sm border border-blue-500/30 rounded-lg px-3 py-2 text-xs text-gray-300 animate-fade-in">
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" />
              </svg>
              <span>Use arrows or swipe to navigate</span>
            </div>
          </div>
        )}
      </div>
    );
  }
);

WrappedScreenWrapper.displayName = 'WrappedScreenWrapper';

