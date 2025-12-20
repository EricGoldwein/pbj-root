import React from 'react';
import { WrappedCard } from '../WrappedCard';
import { useTypingEffect } from '../../../hooks/useTypingEffect';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';

interface WhatIsPBJCardProps {
  data: PBJWrappedData;
}

export const WhatIsPBJCard: React.FC<WhatIsPBJCardProps> = ({ data }) => {
  const baseText = "PBJ stands for Payroll-Based Journal—a federal reporting system requiring nursing homes to submit daily staffing and census data to CMS.";
  
  // Add context based on scope
  let contextText = "";
  if (data.scope === 'state') {
    contextText = ` This data shows staffing levels for ${data.name}.`;
  } else if (data.scope === 'region') {
    contextText = ` This data shows staffing levels for ${data.name}.`;
  }
  
  const answerText = baseText + contextText;
  const typedAnswer = useTypingEffect(answerText, 15, 300);
  const isComplete = typedAnswer.length >= answerText.length;

  return (
    <WrappedCard title="What is PBJ?" hideBadge>
      <div className="space-y-3 text-left">
        <div className="bg-blue-500/10 border-l-4 border-blue-400 pl-3 md:pl-4 py-2 rounded min-h-[60px]">
          <p className="text-gray-200 text-xs md:text-sm leading-relaxed">
            {typedAnswer}
            {!isComplete && (
              <span className="inline-block w-0.5 h-4 bg-blue-300 ml-1 animate-pulse" />
            )}
          </p>
        </div>
        
        {isComplete && (
          <>
            <p className="text-gray-300 text-xs md:text-sm leading-relaxed">
              This provides the most accurate view of nursing home staffing levels nationwide, updated quarterly.
            </p>
            
            <div className="pt-2 border-t border-gray-700">
              <p className="text-gray-400 text-xs leading-relaxed">
                <strong className="text-blue-300">Why it matters:</strong> Staffing levels directly impact care quality. PBJ enables transparency and accountability for families, regulators, and policymakers.
              </p>
            </div>
          </>
        )}
      </div>
    </WrappedCard>
  );
};

