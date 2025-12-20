import React from 'react';
import { WrappedCard } from '../WrappedCard';
import { wrappedCopy } from '../../../lib/wrapped/wrappedCopy';

interface TotalMetricCardProps {
  total{{METRIC_NAME}}: number;
  {{DISTANCE_FIELD}}?: number;
  avatarUrl?: string;
  username?: string;
}

export const TotalMetricCard: React.FC<TotalMetricCardProps> = ({
  total{{METRIC_NAME}},
  {{DISTANCE_FIELD}},
  avatarUrl,
  username,
}) => {
  return (
    <WrappedCard className="relative" username={username}>
      <div className="space-y-4 md:space-y-6 relative z-10">
        {/* User avatar */}
        {avatarUrl && (
          <div className="flex justify-center mb-4 md:mb-6">
            <img
              src={avatarUrl}
              alt="User avatar"
              className="w-32 h-32 md:w-40 md:h-40 rounded-full object-cover border-4 border-{{ACCENT_COLOR}}-400 shadow-2xl"
              style={{ objectPosition: 'center top' }}
              onError={(e) => {
                const target = e.target as HTMLImageElement;
                target.src = '/avatars/default.png';
              }}
            />
          </div>
        )}
        
        <div className="text-7xl md:text-8xl lg:text-9xl font-bold bg-gradient-to-r from-{{ACCENT_COLOR}}-300 via-{{ACCENT_COLOR}}-200 to-{{ACCENT_COLOR}}-200 bg-clip-text text-transparent mb-4 md:mb-6 drop-shadow-2xl break-words">
          {total{{METRIC_NAME}}.toLocaleString()}
        </div>
        <p className="text-lg md:text-xl lg:text-2xl text-{{ACCENT_COLOR}}-200 font-bold mb-3 md:mb-4 drop-shadow-lg px-2">
          {wrappedCopy.cards.totalMetric.title}
        </p>
        {{{DISTANCE_FIELD}} !== undefined && {{DISTANCE_FIELD}} > 0 && (
          <div className="bg-{{ACCENT_COLOR}}-500/20 backdrop-blur-sm rounded-xl p-3 md:p-4 border-2 border-{{ACCENT_COLOR}}-400/50">
            <p className="text-base md:text-lg lg:text-xl text-{{ACCENT_COLOR}}-200 font-semibold">
              {wrappedCopy.cards.totalMetric.distance.replace('{km}', {{DISTANCE_FIELD}}.toFixed(2))}
            </p>
          </div>
        )}
      </div>
    </WrappedCard>
  );
};

