import React, { useEffect, useState } from 'react';
import { WrappedCard } from '../WrappedCard';
import { useTypingEffect } from '../../../hooks/useTypingEffect';
import type { PBJWrappedData } from '../../../lib/wrapped/wrappedTypes';

interface WhatIsPBJCardProps {
  data: PBJWrappedData;
}

/* ----------------------------------
   Utilities
----------------------------------- */

const STATE_ABBR_TO_NAME: Record<string, string> = {
  al: 'Alabama', ak: 'Alaska', az: 'Arizona', ar: 'Arkansas', ca: 'California',
  co: 'Colorado', ct: 'Connecticut', de: 'Delaware', fl: 'Florida', ga: 'Georgia',
  hi: 'Hawaii', id: 'Idaho', il: 'Illinois', in: 'Indiana', ia: 'Iowa',
  ks: 'Kansas', ky: 'Kentucky', la: 'Louisiana', me: 'Maine', md: 'Maryland',
  ma: 'Massachusetts', mi: 'Michigan', mn: 'Minnesota', ms: 'Mississippi', mo: 'Missouri',
  mt: 'Montana', ne: 'Nebraska', nv: 'Nevada', nh: 'New Hampshire', nj: 'New Jersey',
  nm: 'New Mexico', ny: 'New York', nc: 'North Carolina', nd: 'North Dakota', oh: 'Ohio',
  ok: 'Oklahoma', or: 'Oregon', pa: 'Pennsylvania', pr: 'Puerto Rico', ri: 'Rhode Island',
  sc: 'South Carolina', sd: 'South Dakota', tn: 'Tennessee', tx: 'Texas', ut: 'Utah',
  vt: 'Vermont', va: 'Virginia', wa: 'Washington', wv: 'West Virginia',
  wi: 'Wisconsin', wy: 'Wyoming', dc: 'District of Columbia',
};

const getStateFullName = (abbr: string) =>
  STATE_ABBR_TO_NAME[abbr.toLowerCase()] ?? abbr;

const formatNumber = (value: number, decimals = 0) =>
  value.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

/* ----------------------------------
   Component
----------------------------------- */

export const WhatIsPBJCard: React.FC<WhatIsPBJCardProps> = ({ data }) => {
  const facilities = formatNumber(data.facilityCount);

  // Build answer text based on scope
  let answerText = '';
  switch (data.scope) {
    case 'state':
      const stateName = getStateFullName(data.identifier);
      answerText = `PBJ (Payroll-Based Journal) is a federal dataset tracking staffing in ${stateName}'s ${facilities} nursing homes.`;
      break;
    case 'region':
      // Extract region number from identifier (e.g., "region1" -> "1")
      const regionNum = data.identifier.replace(/^region/i, '');
      answerText = `PBJ (Payroll-Based Journal) is a federal dataset tracking staffing in Region ${regionNum}'s ${facilities} nursing homes.`;
      break;
    case 'usa':
      answerText = `PBJ (Payroll-Based Journal) is a federal dataset tracking staffing in the ${facilities} nursing homes in the United States.`;
      break;
    default:
      answerText = `PBJ (Payroll-Based Journal) is a federal dataset tracking staffing in the ${facilities} nursing homes in the United States.`;
      break;
  }

  const typedAnswer = useTypingEffect(answerText, 30, 300);

  // 0 = nothing, 1 = why it matters
  const [revealStage, setRevealStage] = useState(0);

  useEffect(() => {
    if (typedAnswer.length < answerText.length) {
      setRevealStage(0);
      return;
    }

    const timer = setTimeout(() => setRevealStage(1), 1000);

    return () => clearTimeout(timer);
  }, [typedAnswer.length, answerText.length]);

  return (
    <div className="flex flex-col items-center justify-center w-full h-full">
      <WrappedCard title="What is PBJ?" hideBadge>
        <div className="space-y-3 text-left">
          {/* Main definition with context */}
          <div className="bg-blue-500/10 border-l-4 border-blue-400 pl-4 py-3 rounded">
            <p className="text-gray-200 text-sm md:text-base leading-relaxed">
              {typedAnswer}
              {typedAnswer.length < answerText.length && (
                <span className="inline-block w-0.5 h-4 bg-blue-300 ml-1 animate-pulse" />
              )}
            </p>
          </div>

          {/* Why it matters */}
          {revealStage >= 1 && (
            <p className="pt-3 text-xs text-gray-400 animate-fade-in-up">
              <strong className="text-blue-300">Why it matters:</strong> PBJ makes staffing measurable,
              comparable, and auditable—revealing trends that would otherwise stay hidden.
            </p>
          )}

          {/* Definitions and Source */}
          <div className="pt-3 border-t border-gray-700">
            <p className="text-[10px] text-gray-500 leading-relaxed">
              <span>HPRD</span> = Hours Per Resident Per Day ·
              <span> Total Nurse</span> = RNs, LPNs, Aides ·
              <span> Direct Care</span> = Staff excl. Admin/DONs ·
              <span> RN</span> = Registered Nurse
            </p>
            <p className="text-xs text-gray-500 text-center mt-3">
              Source: CMS Payroll-Based Journal (Q2 2025)
            </p>
            <p className="text-[10px] text-gray-500 text-center italic mt-2">
              Note: CMS PBJ excludes providers with missing or invalid data.
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

