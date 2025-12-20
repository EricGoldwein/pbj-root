import React, { useState, useEffect } from 'react';
import { WrappedCard } from '../WrappedCard';
import { useTypingEffect } from '../../../hooks/useTypingEffect';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';

interface WhatIsPBJCardProps {
  data: PBJWrappedData;
}

export const WhatIsPBJCard: React.FC<WhatIsPBJCardProps> = ({ data }) => {
  const baseText = "PBJ stands for Payroll-Based Journal—a federal reporting system requiring nursing homes to submit daily staffing and census data to CMS.";
  
  // Add context based on scope - make it more specific
  let contextText = "";
  if (data.scope === 'state') {
    // data.name is the state abbreviation (e.g., "NY"), convert to full name
    const stateAbbrToName: Record<string, string> = {
      'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
      'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia',
      'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa',
      'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
      'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi', 'MO': 'Missouri',
      'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey',
      'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio',
      'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
      'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont',
      'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming',
      'DC': 'District of Columbia'
    };
    const stateName = stateAbbrToName[data.name.toUpperCase()] || data.name;
    const facilityCount = data.facilityCount.toLocaleString();
    const residentCount = Math.round(data.avgDailyResidents).toLocaleString();
    contextText = ` This Q2 2025 data shows staffing levels across ${stateName}'s ${facilityCount} nursing homes and ${residentCount} residents.`;
  } else if (data.scope === 'region') {
    contextText = ` This Q2 2025 data shows staffing levels across ${data.facilityCount} nursing homes in ${data.name}, serving ${Math.round(data.avgDailyResidents).toLocaleString()} residents daily.`;
  } else if (data.scope === 'usa') {
    contextText = ` This Q2 2025 data shows staffing levels across ${data.facilityCount.toLocaleString()} nursing homes nationwide, serving ${Math.round(data.avgDailyResidents).toLocaleString()} residents daily.`;
  }
  
  const answerText = baseText + contextText;
  const typedAnswer = useTypingEffect(answerText, 30, 300);
  const [showWhyItMatters, setShowWhyItMatters] = useState(false);
  
  // Show "Why it matters" only after typing is fully complete with a delay
  useEffect(() => {
    if (typedAnswer.length >= answerText.length) {
      const timer = setTimeout(() => {
        setShowWhyItMatters(true);
      }, 500); // 500ms delay after typing completes
      return () => clearTimeout(timer);
    } else {
      setShowWhyItMatters(false);
    }
  }, [typedAnswer.length, answerText.length]);

  return (
    <WrappedCard title="What is PBJ?" hideBadge>
      <div className="space-y-3 text-left">
        <div className="bg-blue-500/10 border-l-4 border-blue-400 pl-3 md:pl-4 py-2 rounded">
          <p className="text-gray-200 text-xs md:text-sm leading-relaxed">
            {typedAnswer}
            {typedAnswer.length < answerText.length && (
              <span className="inline-block w-0.5 h-4 bg-blue-300 ml-1 animate-pulse" />
            )}
          </p>
        </div>
        
        {showWhyItMatters && (
          <div className="pt-3 border-t border-gray-700">
            <p className="text-gray-300 text-xs md:text-sm leading-relaxed">
              <strong className="text-blue-300">Why it matters:</strong> Staffing levels directly impact care quality. PBJ provides the most accurate, transparent view of nursing home staffing nationwide, empowering families to make informed decisions and enabling regulators to hold facilities accountable.
            </p>
          </div>
        )}
      </div>
    </WrappedCard>
  );
};

