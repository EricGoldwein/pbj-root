import React from 'react';
import { WrappedCard } from '../WrappedCard';

export const WhatIsSFFCard: React.FC = () => {
  return (
    <WrappedCard title="What is a Special Focus Facility?" hideBadge>
      <div className="space-y-3 text-left">
        <div className="bg-orange-500/10 border-l-4 border-orange-400 pl-3 md:pl-4 py-2 rounded">
          <p className="text-gray-200 text-xs md:text-sm leading-relaxed">
            <strong className="text-orange-300">Special Focus Facilities (SFFs)</strong> are nursing homes with a history of serious quality problems. They receive more frequent inspections and enhanced oversight from CMS.
          </p>
        </div>
        
        <div className="bg-yellow-500/10 border-l-4 border-yellow-400 pl-3 md:pl-4 py-2 rounded">
          <p className="text-gray-200 text-xs md:text-sm leading-relaxed">
            <strong className="text-yellow-300">SFF Candidates</strong> are nursing homes being monitored for potential SFF designation due to patterns of quality concerns.
          </p>
        </div>
        
        <div className="pt-2 border-t border-gray-700">
          <p className="text-gray-400 text-xs leading-relaxed">
            <strong className="text-orange-300">Why it matters:</strong> These nursing homes represent the most serious quality challenges in the nursing home system. Enhanced oversight aims to improve care quality or lead to closure if improvements aren't made.
          </p>
        </div>
      </div>
    </WrappedCard>
  );
};

