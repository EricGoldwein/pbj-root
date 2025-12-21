import React, { useState, useEffect } from 'react';
import { WrappedCard } from '../WrappedCard';
import { useTypingEffect } from '../../../hooks/useTypingEffect';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';

interface WhatIsPBJCardProps {
  data: PBJWrappedData;
}

export const WhatIsPBJCard: React.FC<WhatIsPBJCardProps> = () => {
  const baseText = "PBJ stands for Payroll-Based Journal—a federal reporting system for nursing home staffing data.";
  
  const answerText = baseText;
  const typedAnswer = useTypingEffect(answerText, 30, 300);
  const [showNote, setShowNote] = useState(false);
  
  // Show note after typing completes
  useEffect(() => {
    if (typedAnswer.length >= answerText.length) {
      const timer = setTimeout(() => {
        setShowNote(true);
      }, 1000);
      
      return () => clearTimeout(timer);
    } else {
      setShowNote(false);
    }
  }, [typedAnswer.length, answerText.length]);

  return (
    <div className="flex flex-col items-center justify-center w-full h-full">
      <WrappedCard title="What is PBJ?" hideBadge>
        <div className="space-y-4 text-center">
          <div className="bg-blue-500/10 border-l-4 border-blue-400 pl-4 md:pl-5 py-3 md:py-4 rounded">
            <p className="text-gray-200 text-sm md:text-base leading-relaxed">
              {typedAnswer}
              {typedAnswer.length < answerText.length && (
                <span className="inline-block w-0.5 h-4 bg-blue-300 ml-1 animate-pulse" />
              )}
            </p>
          </div>
          
          {showNote && (
            <div className="pt-3 border-t border-gray-700 animate-fade-in-up">
              <p className="text-xs text-gray-400 leading-relaxed">
                CMS PBJ excludes nursing homes with incomplete or misreported data.
              </p>
            </div>
          )}
          
          <div className="pt-3 border-t border-gray-700">
            <p className="text-xs text-gray-500 leading-relaxed">
              <strong className="text-gray-400">HPRD</strong> = Hours Per Resident Per Day. <strong className="text-gray-400">Total Nurse:</strong> All nursing staff. <strong className="text-gray-400">Direct Care:</strong> Hands-on care (RNs, LPNs, CNAs). <strong className="text-gray-400">RN:</strong> Registered Nurse.
            </p>
          </div>
        </div>
      </WrappedCard>
      <p className="text-xs text-gray-400 text-center italic mt-4">
        Click or tap anywhere to continue
      </p>
    </div>
  );
};

