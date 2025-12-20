import React, { useEffect, useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { loadAllData, type LoadedData } from '../lib/wrapped/dataLoader';
import { WrappedScreenWrapper } from '../components/wrapped/WrappedScreenWrapper';
import { WrappedProvider } from '../components/wrapped/WrappedContext';
import { WrappedCard } from '../components/wrapped/WrappedCard';
import { WrappedImage } from '../components/wrapped/WrappedImage';
import { toTitleCase } from '../lib/wrapped/dataProcessor';
import { WhatIsSFFCard } from '../components/wrapped/cards/WhatIsSFFCard';
import { WhatIsPBJCard } from '../components/wrapped/cards/WhatIsPBJCard';
import { updateSEO, getSFFWrappedSEO } from '../utils/seo';
import { getAssetPath } from '../utils/assets';

interface SFFFacility {
  provnum: string;
  name: string;
  state: string;
  city?: string;
  county?: string;
  sffStatus: string;
  overallRating?: string;
  totalHPRD: number;
  directCareHPRD: number;
  rnHPRD: number;
  link: string;
}

export default function SFFWrapped() {
  const year = '2025'; // Fixed year for Q2 2025
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sffData, setSffData] = useState<{
    sffs: SFFFacility[];
    candidates: SFFFacility[];
  } | null>(null);

  // Update SEO on mount
  useEffect(() => {
    updateSEO(getSFFWrappedSEO(year || '2025'));
  }, [year]);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        setError(null);

        // Load all data (we need provider info and facilities)
        // Use base path for data files
        const baseDataPath = `${import.meta.env.BASE_URL}data`.replace(/([^:]\/)\/+/g, '$1');
        const data: LoadedData = await loadAllData(baseDataPath);

        // Filter for Q2 2025 SFFs and candidates
        const providerInfoQ2 = data.providerInfo.q2;
        const facilityQ2 = data.facilityData.q2;

        // Create lookup for facilities
        const facilityMap = new Map(facilityQ2.map(f => [f.PROVNUM, f]));

        // Filter SFFs
        const sffs: SFFFacility[] = [];
        const candidates: SFFFacility[] = [];

        for (const provider of providerInfoQ2) {
          if (!provider.sff_status) continue;
          
          const status = provider.sff_status.trim().toUpperCase();
          const isSFF = status === 'SFF' || status === 'SPECIAL FOCUS FACILITY' || status.includes('SFF');
          const isCandidate = status === 'SFF CANDIDATE' || status === 'CANDIDATE' || 
                             (status.includes('CANDIDATE') && !status.includes('SFF'));

          if (isSFF || isCandidate) {
            const facility = facilityMap.get(provider.PROVNUM);
            if (!facility) continue;

            const sffFacility: SFFFacility = {
              provnum: provider.PROVNUM,
              name: toTitleCase(provider.PROVNAME),
              state: provider.STATE,
              city: provider.CITY,
              county: provider.COUNTY_NAME,
              sffStatus: provider.sff_status,
              overallRating: provider.overall_rating,
              totalHPRD: facility.Total_Nurse_HPRD,
              directCareHPRD: facility.Nurse_Care_HPRD,
              rnHPRD: (facility as any).RN_HPRD || 0,
              link: `https://pbjdashboard.com/?facility=${provider.PROVNUM}`,
            };

            if (isSFF) {
              sffs.push(sffFacility);
            } else {
              candidates.push(sffFacility);
            }
          }
        }

        // Sort by state, then by name
        sffs.sort((a, b) => {
          if (a.state !== b.state) return a.state.localeCompare(b.state);
          return a.name.localeCompare(b.name);
        });
        candidates.sort((a, b) => {
          if (a.state !== b.state) return a.state.localeCompare(b.state);
          return a.name.localeCompare(b.name);
        });

        setSffData({ sffs, candidates });
      } catch (err) {
        console.error('Error loading SFF data:', err);
        setError(err instanceof Error ? err.message : 'Failed to load SFF data');
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [year]);

  const { screens, slideDurations } = useMemo(() => {
    if (!sffData) {
      return { screens: [], slideDurations: [] };
    }

    const formatNumber = (num: number, decimals: number = 1): string => {
      return num.toLocaleString('en-US', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      });
    };

    const renderFacility = (facility: SFFFacility) => {
      const location = facility.city 
        ? `${facility.city}, ${facility.state}`
        : facility.county
        ? `${facility.county}, ${facility.state}`
        : facility.state;

      return (
        <div key={facility.provnum} className="py-1.5 border-b border-gray-700 last:border-0">
          <div className="flex justify-between items-start gap-2">
            <div className="flex-1 min-w-0">
              <a
                href={facility.link}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-300 hover:text-blue-200 underline font-medium text-xs md:text-sm block mb-0.5"
              >
                {facility.name}
              </a>
              <div className="text-xs text-gray-400">{location}</div>
              {facility.overallRating && (
                <div className="text-xs text-gray-500 mt-0.5">
                  Rating: {facility.overallRating}
                </div>
              )}
            </div>
            <div className="text-right ml-2 flex-shrink-0">
              <div className="text-xs text-gray-400 mb-0.5">Total HPRD</div>
              <div className="text-sm text-white font-semibold">
                {formatNumber(facility.totalHPRD, 2)}
              </div>
              <div className="text-xs text-gray-500 mt-0.5">
                Direct: {formatNumber(facility.directCareHPRD, 2)}
              </div>
              <div className="text-xs text-gray-500">
                RN: {formatNumber(facility.rnHPRD, 2)}
              </div>
            </div>
          </div>
        </div>
      );
    };

    const screensArray: React.ReactElement[] = [
      // Header
      <WrappedCard
        key="header"
        title="PBJ Wrapped — Q2 2025"
        subtitle="Special Focus Facilities"
        hideBadge={true}
        noContainer={true}
      >
        <div className="space-y-3 md:space-y-4">
          <div className="flex justify-center">
            <WrappedImage
              src={getAssetPath('/images/phoebe-wrapped-wide.png')}
              alt="PBJ Wrapped"
              className="block relative rounded-lg"
              style={{ 
                maxHeight: '200px', 
                maxWidth: '100%',
                height: 'auto',
                width: 'auto',
                objectFit: 'contain',
              }}
              maxHeight="200px"
            />
          </div>
          <div className="text-center">
            <a
              href="https://pbj320.com"
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-300 hover:text-blue-200 underline text-base md:text-lg font-medium"
            >
              pbj320.com
            </a>
          </div>
        </div>
      </WrappedCard>,

      <WhatIsSFFCard key="what-is-sff" />,
      <WhatIsPBJCard 
        key="what-is-pbj" 
        data={{
          scope: 'usa',
          identifier: 'sff',
          name: 'Special Focus Facilities',
          facilityCount: sffData.sffs.length + sffData.candidates.length,
          avgDailyResidents: 0,
          totalHPRD: 0,
          directCareHPRD: 0,
          rnHPRD: 0,
          rnDirectCareHPRD: 0,
          rankings: {
            totalHPRDRank: 0,
            totalHPRDPercentile: 0,
            directCareHPRDRank: 0,
            directCareHPRDPercentile: 0,
            rnHPRDRank: 0,
            rnHPRDPercentile: 0,
          },
          extremes: {
            lowestByHPRD: [],
            lowestByPercentExpected: [],
            highestByHPRD: [],
            highestByPercentExpected: [],
          },
          sff: {
            currentSFFs: sffData.sffs.length,
            candidates: sffData.candidates.length,
            newThisQuarter: [],
          },
          trends: {
            totalHPRDChange: 0,
            directCareHPRDChange: 0,
            rnHPRDChange: 0,
            contractPercentChange: 0,
          },
          movers: {
            risersByHPRD: [],
            risersByDirectCare: [],
            declinersByHPRD: [],
            declinersByDirectCare: [],
          },
          ownership: undefined,
        }}
      />,

      // Overview
      <WrappedCard key="overview" title="Overview">
        <div className="space-y-3">
          <div className="flex justify-between items-center py-2 border-b border-gray-600">
            <span className="text-gray-300 text-base md:text-lg">Current SFFs</span>
            <span className="text-white font-bold text-2xl md:text-3xl">{sffData.sffs.length}</span>
          </div>
          <div className="flex justify-between items-center py-2 border-b border-gray-600">
            <span className="text-gray-300 text-base md:text-lg">SFF Candidates</span>
            <span className="text-white font-bold text-2xl md:text-3xl">{sffData.candidates.length}</span>
          </div>
        </div>
      </WrappedCard>,

      // Calculate median HPRD for SFFs and candidates
      (() => {
        const sffsWithHPRD = sffData.sffs.filter(f => f.totalHPRD > 0);
        const candidatesWithHPRD = sffData.candidates.filter(f => f.totalHPRD > 0);
        
        const calculateMedian = (arr: number[]): number => {
          if (arr.length === 0) return 0;
          const sorted = [...arr].sort((a, b) => a - b);
          const mid = Math.floor(sorted.length / 2);
          return sorted.length % 2 === 0 
            ? (sorted[mid - 1] + sorted[mid]) / 2 
            : sorted[mid];
        };
        
        const sffHPRDs = sffsWithHPRD.map(f => f.totalHPRD);
        const candidateHPRDs = candidatesWithHPRD.map(f => f.totalHPRD);
        const medianSFFHPRD = calculateMedian(sffHPRDs);
        const medianCandidateHPRD = calculateMedian(candidateHPRDs);
        
        return (
          <WrappedCard key="sff-staffing" title="Staffing Overview">
            <div className="space-y-3">
              <p className="text-gray-300 text-xs md:text-sm text-center mb-3">
                Median staffing levels for facilities with reported HPRD data
              </p>
              
              <div className="space-y-2.5">
                <div className="p-2.5 md:p-3 bg-orange-500/10 border border-orange-500/30 rounded-lg">
                  <div className="text-xs text-gray-400 mb-0.5">SFFs</div>
                  <div className="text-lg md:text-xl font-bold text-white">
                    {formatNumber(medianSFFHPRD, 2)} HPRD
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5">
                    {sffsWithHPRD.length} of {sffData.sffs.length} facilities with data
                  </div>
                </div>
                
                <div className="p-2.5 md:p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                  <div className="text-xs text-gray-400 mb-0.5">SFF Candidates</div>
                  <div className="text-lg md:text-xl font-bold text-white">
                    {formatNumber(medianCandidateHPRD, 2)} HPRD
                  </div>
                  <div className="text-xs text-gray-500 mt-0.5">
                    {candidatesWithHPRD.length} of {sffData.candidates.length} facilities with data
                  </div>
                </div>
              </div>
              
              {(sffData.sffs.length - sffsWithHPRD.length > 0 || sffData.candidates.length - candidatesWithHPRD.length > 0) && (
                <p className="text-xs text-gray-500 text-center pt-1.5 border-t border-gray-700">
                  Note: Some facilities do not report staffing data in PBJ, so they are excluded from median calculations.
                </p>
              )}
            </div>
          </WrappedCard>
        );
      })(),

      // SFFs (split into multiple slides if needed)
      ...(sffData.sffs.length > 0 ? [
        <WrappedCard key="sffs" title={`Special Focus Facilities (${sffData.sffs.length})`}>
          <p className="text-gray-400 text-xs mb-2 text-center">
            Showing facilities with reported staffing data
          </p>
          <div className="space-y-0.5 max-h-[60vh] md:max-h-[55vh] overflow-y-auto">
            {sffData.sffs.filter(f => f.totalHPRD > 0).slice(0, 8).map(f => renderFacility(f))}
            {sffData.sffs.filter(f => f.totalHPRD > 0).length > 8 && (
              <div className="text-xs text-gray-500 text-center pt-2">
                Showing 8 of {sffData.sffs.filter(f => f.totalHPRD > 0).length} facilities with data
              </div>
            )}
          </div>
        </WrappedCard>
      ] : []),

      // Candidates
      ...(sffData.candidates.length > 0 ? [
        <WrappedCard key="candidates" title={`SFF Candidates (${sffData.candidates.length})`}>
          <p className="text-gray-400 text-xs mb-2 text-center">
            Showing facilities with reported staffing data
          </p>
          <div className="space-y-0.5 max-h-[60vh] md:max-h-[55vh] overflow-y-auto">
            {sffData.candidates.filter(f => f.totalHPRD > 0).slice(0, 8).map(f => renderFacility(f))}
            {sffData.candidates.filter(f => f.totalHPRD > 0).length > 8 && (
              <div className="text-xs text-gray-500 text-center pt-2">
                Showing 8 of {sffData.candidates.filter(f => f.totalHPRD > 0).length} facilities with data
              </div>
            )}
          </div>
        </WrappedCard>
      ] : []),

      // Navigation
      <WrappedCard key="navigation" title="Explore More">
        <div className="space-y-4">
          <div className="flex justify-center mb-4">
            <WrappedImage
              src={getAssetPath('/images/phoebe-wrapped-wide.png')}
              alt="PBJ Wrapped"
              className="block relative rounded-lg"
              style={{ 
                maxHeight: '150px', 
                maxWidth: '100%',
                height: 'auto',
                width: 'auto',
                objectFit: 'contain',
              }}
              maxHeight="150px"
            />
          </div>
          <div className="space-y-3">
            <button
              onClick={() => navigate('/usa')}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors"
            >
              View USA Wrapped
            </button>
            <button
              onClick={() => navigate('/')}
              className="w-full bg-gray-700 hover:bg-gray-600 text-white font-semibold py-3 px-6 rounded-lg transition-colors"
            >
              Choose Another State or Region
            </button>
            <a
              href="https://pbj320.com/report"
              target="_blank"
              rel="noopener noreferrer"
              className="block w-full bg-gray-800 hover:bg-gray-700 text-white font-semibold py-3 px-6 rounded-lg transition-colors text-center"
            >
              View Full Report on pbj320.com
            </a>
          </div>
        </div>
      </WrappedCard>,
    ];

    const slideDurationsArray = screensArray.map(() => 5000);

    return { screens: screensArray, slideDurations: slideDurationsArray };
  }, [sffData, navigate]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center">
        <div className="text-center">
          <div className="text-xl mb-2">Loading PBJ Wrapped...</div>
          <div className="text-sm text-gray-400">Loading SFF data...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center">
        <div className="text-center">
          <div className="text-xl mb-2 text-red-400">Error</div>
          <div className="text-sm text-gray-400">{error}</div>
        </div>
      </div>
    );
  }

  if (!sffData) {
    return null;
  }

  return (
    <WrappedProvider scope="sff" name="Special Focus Facilities">
      <WrappedScreenWrapper screens={screens} slideDurations={slideDurations} />
    </WrappedProvider>
  );
}

