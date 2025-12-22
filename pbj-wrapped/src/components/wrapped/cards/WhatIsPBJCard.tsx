import React, { useState, useEffect } from 'react';
import { WrappedCard } from '../WrappedCard';
import { useTypingEffect } from '../../../hooks/useTypingEffect';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';

interface WhatIsPBJCardProps {
  data: PBJWrappedData;
}

const STATE_ABBR_TO_NAME: Record<string, string> = {
  'al': 'Alabama', 'ak': 'Alaska', 'az': 'Arizona', 'ar': 'Arkansas', 'ca': 'California',
  'co': 'Colorado', 'ct': 'Connecticut', 'de': 'Delaware', 'fl': 'Florida', 'ga': 'Georgia',
  'hi': 'Hawaii', 'id': 'Idaho', 'il': 'Illinois', 'in': 'Indiana', 'ia': 'Iowa',
  'ks': 'Kansas', 'ky': 'Kentucky', 'la': 'Louisiana', 'me': 'Maine', 'md': 'Maryland',
  'ma': 'Massachusetts', 'mi': 'Michigan', 'mn': 'Minnesota', 'ms': 'Mississippi', 'mo': 'Missouri',
  'mt': 'Montana', 'ne': 'Nebraska', 'nv': 'Nevada', 'nh': 'New Hampshire', 'nj': 'New Jersey',
  'nm': 'New Mexico', 'ny': 'New York', 'nc': 'North Carolina', 'nd': 'North Dakota', 'oh': 'Ohio',
  'ok': 'Oklahoma', 'or': 'Oregon', 'pa': 'Pennsylvania', 'pr': 'Puerto Rico', 'ri': 'Rhode Island', 'sc': 'South Carolina',
  'sd': 'South Dakota', 'tn': 'Tennessee', 'tx': 'Texas', 'ut': 'Utah', 'vt': 'Vermont',
  'va': 'Virginia', 'wa': 'Washington', 'wv': 'West Virginia', 'wi': 'Wisconsin', 'wy': 'Wyoming',
  'dc': 'District of Columbia'
};

function getStateFullName(abbr: string): string {
  const lowerAbbr = abbr.toLowerCase();
  return STATE_ABBR_TO_NAME[lowerAbbr] || abbr;
}

export const WhatIsPBJCard: React.FC<WhatIsPBJCardProps> = ({ data }) => {
  const baseText = "PBJ is federal payroll data that tracks nursing home staffing.";
  
  const formatNumber = (num: number, decimals: number = 0): string => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  // Build context text based on scope
  let contextText = "";
  if (data.scope === 'state') {
    const stateName = getStateFullName(data.identifier);
    contextText = `In Q2 2025, ${stateName} reported ${formatNumber(data.facilityCount)} nursing homes and ${formatNumber(Math.round(data.avgDailyResidents))} average daily residents.`;
  } else if (data.scope === 'region') {
    contextText = `In Q2 2025, this region reported ${formatNumber(data.facilityCount)} nursing homes and ${formatNumber(Math.round(data.avgDailyResidents))} average daily residents.`;
  } else if (data.scope === 'usa') {
    contextText = `In Q2 2025, the United States reported ${formatNumber(data.facilityCount)} nursing homes and ${formatNumber(Math.round(data.avgDailyResidents))} average daily residents.`;
  }
  
  const answerText = baseText;
  const typedAnswer = useTypingEffect(answerText, 30, 300);
  const [showContext, setShowContext] = useState(false);
  const [showWhyItMatters, setShowWhyItMatters] = useState(false);
  const [showNote, setShowNote] = useState(false);
  
  // Staggered reveals after typing completes
  useEffect(() => {
    if (typedAnswer.length >= answerText.length) {
      const timer1 = setTimeout(() => {
        setShowContext(true);
      }, 800);
      
      const timer2 = setTimeout(() => {
        setShowWhyItMatters(true);
      }, 1800);
      
      const timer3 = setTimeout(() => {
        setShowNote(true);
      }, 2800);
      
      return () => {
        clearTimeout(timer1);
        clearTimeout(timer2);
        clearTimeout(timer3);
      };
    } else {
      setShowContext(false);
      setShowWhyItMatters(false);
      setShowNote(false);
    }
  }, [typedAnswer.length, answerText.length]);

  return (
    <div className="flex flex-col items-center justify-center w-full h-full">
      <WrappedCard title="What is PBJ?" hideBadge>
        <div className="space-y-3 text-left">
          <div className="bg-blue-500/10 border-l-4 border-blue-400 pl-4 md:pl-5 py-3 md:py-4 rounded">
            <p className="text-gray-200 text-sm md:text-base leading-relaxed">
              {typedAnswer}
              {typedAnswer.length < answerText.length && (
                <span className="inline-block w-0.5 h-4 bg-blue-300 ml-1 animate-pulse" />
              )}
            </p>
          </div>
          
          {showContext && contextText && (
            <div className="pt-2 animate-fade-in-up">
              <p className="text-gray-300 text-xs md:text-sm leading-relaxed break-words whitespace-normal">
                {contextText}
              </p>
            </div>
          )}
          
          {showWhyItMatters && (
            <div className="pt-3 animate-fade-in-up">
              <p className="text-xs text-gray-400 leading-relaxed">
                <strong className="text-gray-300">Why it matters:</strong> PBJ provides transparency into staffing levels, helping identify facilities that may be understaffed.
              </p>
            </div>
          )}
          
          {showNote && (
            <div className="pt-3 animate-fade-in-up">
              <p className="text-xs text-gray-400 leading-relaxed">
                <strong className="text-gray-300">Note:</strong> PBJ excludes facilities with incomplete submissions.
              </p>
            </div>
          )}
          
          <div className="pt-3 border-t border-gray-700">
            <p className="text-[10px] text-gray-500 leading-relaxed">
              <span className="text-gray-500">HPRD</span> = Hours Per Resident Per Day. <span className="text-gray-500">Total Nurse:</span> All nursing staff. <span className="text-gray-500">Direct Care:</span> Hands-on care (RNs, LPNs, CNAs). <span className="text-gray-500">RN:</span> Registered Nurse.
            </p>
          </div>
          
          <p className="text-xs text-gray-500 text-center pt-3 border-t border-gray-700">
            Source: CMS Payroll-Based Journal, Q2 2025
          </p>
        </div>
      </WrappedCard>
      <p className="text-xs text-gray-400 text-center italic mt-4">
        Click or tap anywhere to continue
      </p>
    </div>
  );
};

