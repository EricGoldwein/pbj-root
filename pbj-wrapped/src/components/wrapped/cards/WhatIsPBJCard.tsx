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

  // Build location text based on scope
  let locationText = '';
  switch (data.scope) {
    case 'state':
      locationText = getStateFullName(data.identifier);
      break;
    case 'region':
      // Extract region number from identifier (e.g., "region1" -> "1")
      const regionNum = data.identifier.replace(/^region/i, '');
      locationText = `Region ${regionNum}`;
      break;
    case 'usa':
      locationText = 'the United States';
      break;
    default:
      locationText = 'the United States';
      break;
  }

  const answerText =
    `PBJ (Payroll-Based Journal) is a federal dataset tracking staffing in the ${facilities} nursing homes in ${locationText}.`;

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
              <strong className="text-gray-300">Why it matters:</strong> PBJ makes staffing measurable,
              comparable, and auditable—revealing trends that would otherwise stay hidden.
              <br />
              <span className="text-gray-500 italic">Note: Providers with missing or invalid PBJ data are excluded.</span>
            </p>
          )}

          {/* Definitions */}
          <div className="pt-3 border-t border-gray-700">
            <p className="text-[10px] text-gray-500 leading-relaxed">
              <span>HPRD</span> = Hours Per Resident Per Day ·
              <span> Total Nurse</span> = All nursing staff ·
              <span> Direct Care</span> = RNs, LPNs, CNAs ·
              <span> RN</span> = Registered Nurse
            </p>
          </div>

          <p className="text-xs text-gray-500 text-center pt-3 border-t border-gray-700">
            Source: CMS Payroll-Based Journal (Q2 2025)
          </p>
        </div>
      </WrappedCard>

      <p className="text-xs text-gray-400 text-center italic mt-4">
        Click or tap anywhere to continue
      </p>
    </div>
  );
};

