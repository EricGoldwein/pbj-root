import React from 'react';
import { WrappedCard } from '../WrappedCard';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';

interface NavigationCardNewsProps {
  data: PBJWrappedData;
  onReplay?: () => void;
}

export const NavigationCardNews: React.FC<NavigationCardNewsProps> = ({ data, onReplay }) => {
  if (data.scope !== 'usa') {
    return null;
  }

  return (
    <WrappedCard title="Explore the Data" hideBadge>
      <div className="space-y-4 text-center">
        <p className="text-gray-300 text-sm md:text-base leading-relaxed mb-4">
          This is public federal data. Explore the full PBJ dashboard to see facility-level details, state comparisons, and historical trends.
        </p>
        
        <div className="space-y-3">
          <a
            href="https://pbj320.com/report"
            target="_blank"
            rel="noopener noreferrer"
            className="block w-full py-3 px-6 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition-all duration-200 text-center shadow-lg hover:shadow-xl"
          >
            View Full PBJ Dashboard →
          </a>
          
          <a
            href="https://pbjdashboard.com"
            target="_blank"
            rel="noopener noreferrer"
            className="block w-full py-3 px-6 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-lg transition-all duration-200 text-center"
          >
            Explore State Dashboards →
          </a>
          
          {onReplay && (
            <button
              onClick={onReplay}
              className="block w-full py-2 px-6 text-gray-400 hover:text-gray-300 text-sm transition-colors"
            >
              Replay Presentation
            </button>
          )}
        </div>
        
        <p className="text-xs text-gray-500 text-center pt-3 border-t border-gray-700">
          Source: CMS Payroll-Based Journal, Q2 2025
        </p>
      </div>
    </WrappedCard>
  );
};

