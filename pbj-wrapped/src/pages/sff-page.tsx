import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { loadAllData } from '../lib/wrapped/dataLoader';
import { toTitleCase } from '../lib/wrapped/dataProcessor';
import { getAssetPath } from '../utils/assets';
import type { FacilityLiteRow, ProviderInfoRow } from '../lib/wrapped/wrappedTypes';

interface SFFFacility {
  provnum: string;
  name: string;
  state: string;
  city?: string;
  county?: string;
  sffStatus: string;
  totalHPRD: number;
  directCareHPRD: number;
  rnHPRD: number;
  isNewSFF: boolean;
  isNewCandidate: boolean;
  wasCandidate: boolean;
  wasSFF: boolean;
}

export default function SFFPage() {
  const { scope } = useParams<{ scope?: string }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sffData, setSffData] = useState<{
    sffs: SFFFacility[];
    candidates: SFFFacility[];
  } | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        setError(null);

        const data = await loadAllData('/data', 'usa', undefined);
        
        // Get Q1 and Q2 provider info
        const providerInfoQ1 = data.providerInfo.q1 || [];
        const providerInfoQ2 = data.providerInfo.q2 || [];
        const facilityQ2 = data.facilityData.q2 || [];

        // Create maps for quick lookup
        const facilityMap = new Map<string, FacilityLiteRow>(facilityQ2.map((f: FacilityLiteRow) => [f.PROVNUM, f]));
        const q1StatusMap = new Map<string, string>(
          providerInfoQ1.map((p: ProviderInfoRow) => [p.PROVNUM, p.sff_status?.trim().toUpperCase() || ''])
        );

        const sffs: SFFFacility[] = [];
        const candidates: SFFFacility[] = [];

        for (const provider of providerInfoQ2) {
          if (!provider.sff_status) continue;
          
          const status = provider.sff_status?.trim().toUpperCase() || '';
          const isSFF = status === 'SFF' || status === 'SPECIAL FOCUS FACILITY' || (typeof status === 'string' && status.includes('SFF') && !status.includes('CANDIDATE'));
          const isCandidate = status === 'SFF CANDIDATE' || status === 'CANDIDATE' || 
                             (typeof status === 'string' && status.includes('CANDIDATE') && !status.includes('SFF'));

          if (isSFF || isCandidate) {
            const facility = facilityMap.get(provider.PROVNUM);
            if (!facility) continue;

            const q1Status = q1StatusMap.get(provider.PROVNUM) || '';
            const wasSFF = q1Status === 'SFF' || q1Status === 'SPECIAL FOCUS FACILITY' || (typeof q1Status === 'string' && q1Status.includes('SFF') && !q1Status.includes('CANDIDATE'));
            const wasCandidate = q1Status === 'SFF CANDIDATE' || q1Status === 'CANDIDATE' || 
                                (typeof q1Status === 'string' && q1Status.includes('CANDIDATE') && !q1Status.includes('SFF'));
            const isNewSFF = isSFF && !wasSFF && !wasCandidate;
            const isNewCandidate = isCandidate && !wasCandidate && !wasSFF;

            const sffFacility: SFFFacility = {
              provnum: provider.PROVNUM,
              name: toTitleCase(provider.PROVNAME),
              state: provider.STATE,
              city: provider.CITY,
              county: provider.COUNTY_NAME,
              sffStatus: provider.sff_status,
              totalHPRD: facility.Total_Nurse_HPRD || 0,
              directCareHPRD: facility.Nurse_Care_HPRD || 0,
              rnHPRD: (facility as FacilityLiteRow & { RN_HPRD?: number }).RN_HPRD || 0,
              isNewSFF,
              isNewCandidate,
              wasCandidate,
              wasSFF,
            };

            if (isSFF) {
              sffs.push(sffFacility);
            } else {
              candidates.push(sffFacility);
            }
          }
        }

        // Filter by state if scope is a state code
        let filteredSFFs = sffs;
        let filteredCandidates = candidates;
        
        if (scope && scope !== 'usa' && scope.length === 2) {
          const stateCode = scope.toUpperCase();
          filteredSFFs = sffs.filter(f => f.state === stateCode);
          filteredCandidates = candidates.filter(f => f.state === stateCode);
        }

        // Sort by state, then by name
        filteredSFFs.sort((a, b) => {
          if (a.state !== b.state) return a.state.localeCompare(b.state);
          return a.name.localeCompare(b.name);
        });
        filteredCandidates.sort((a, b) => {
          if (a.state !== b.state) return a.state.localeCompare(b.state);
          return a.name.localeCompare(b.name);
        });

        setSffData({ sffs: filteredSFFs, candidates: filteredCandidates });
      } catch (err) {
        console.error('Error loading SFF data:', err);
        setError(err instanceof Error ? err.message : 'Failed to load SFF data');
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [scope]);

  const formatNumber = (num: number, decimals: number = 2): string => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const getStateName = (code: string): string => {
    const stateMap: Record<string, string> = {
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
    return stateMap[code] || code;
  };

  const pageTitle = scope === 'usa' 
    ? 'Special Focus Facilities & Candidates — United States'
    : scope 
    ? `Special Focus Facilities & Candidates — ${getStateName(scope.toUpperCase())}`
    : 'Special Focus Facilities & Candidates';

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-blue-900 to-gray-900 text-white flex items-center justify-center">
        <div className="text-center">
          <div className="text-xl mb-2">Loading SFF data...</div>
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-500/30 border-t-blue-500 mx-auto"></div>
        </div>
      </div>
    );
  }

  if (error || !sffData) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-blue-900 to-gray-900 text-white flex items-center justify-center">
        <div className="text-center">
          <div className="text-xl mb-2 text-red-400">Error</div>
          <div className="text-sm text-gray-400">{error || 'Failed to load SFF data'}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-blue-900 to-gray-900 text-white">
      {/* Header Navigation */}
      <nav className="sticky top-0 z-50 bg-[#0f172a] border-b-2 border-blue-600 shadow-lg">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-14 md:h-16">
            <a 
              href="https://pbj320.com" 
              className="text-white font-bold text-lg md:text-xl hover:text-blue-300 transition-colors flex items-center gap-2"
            >
              <img src={getAssetPath('/pbj_favicon.png')} alt="PBJ320" className="h-6 md:h-8 w-auto" onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }} />
              <span><span className="text-white">PBJ</span><span className="text-blue-400">320</span></span>
            </a>
            <div className="hidden md:flex items-center gap-4 lg:gap-6">
              <a href="https://pbj320.com/about" className="text-gray-300 hover:text-blue-300 text-sm md:text-base font-medium transition-colors">About</a>
              <a href="https://pbjdashboard.com/" className="text-gray-300 hover:text-blue-300 text-sm md:text-base font-medium transition-colors">Dashboard</a>
              <a href="https://pbj320.com/insights" className="text-gray-300 hover:text-blue-300 text-sm md:text-base font-medium transition-colors">Insights</a>
              <a href="https://pbj320.com/report" className="text-gray-300 hover:text-blue-300 text-sm md:text-base font-medium transition-colors">Report</a>
            </div>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 md:py-8">
        <div className="mb-6 md:mb-8">
          <h1 className="text-2xl md:text-3xl lg:text-4xl font-bold mb-2 md:mb-3">{pageTitle}</h1>
          <p className="text-gray-300 text-sm md:text-base mb-2">
            Q2 2025 • CMS Payroll-Based Journal
          </p>
          <p className="text-gray-400 text-xs md:text-sm leading-relaxed max-w-3xl">
            Special Focus Facilities (SFFs) are nursing homes with a history of serious quality problems. 
            SFF Candidates are facilities being considered for SFF status. 
            <span className="text-orange-400 font-semibold"> New</span> indicates facilities that became SFFs or candidates in Q2 2025.
          </p>
        </div>

        {/* SFFs Section */}
        <div className="mb-8 md:mb-10">
          <h2 className="text-xl md:text-2xl font-bold mb-3 md:mb-4">
            Special Focus Facilities ({sffData.sffs.length.toLocaleString()})
          </h2>
          {sffData.sffs.length === 0 ? (
            <div className="rounded-lg border border-gray-700 bg-[#0f172a]/60 p-8 text-center">
              <p className="text-gray-400">No Special Focus Facilities found for this scope.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-gray-700 bg-[#0f172a]/60 shadow-lg">
              <table className="w-full border-collapse min-w-[640px]">
                <thead>
                  <tr className="bg-blue-600/20 border-b border-blue-500/30">
                    <th className="px-3 md:px-4 py-2 md:py-3 text-left text-xs md:text-sm font-semibold text-blue-300">Facility</th>
                    <th className="px-3 md:px-4 py-2 md:py-3 text-left text-xs md:text-sm font-semibold text-blue-300">Location</th>
                    <th className="px-2 md:px-4 py-2 md:py-3 text-center text-xs md:text-sm font-semibold text-blue-300 whitespace-nowrap">Total HPRD</th>
                    <th className="px-2 md:px-4 py-2 md:py-3 text-center text-xs md:text-sm font-semibold text-blue-300 whitespace-nowrap">Direct Care</th>
                    <th className="px-2 md:px-4 py-2 md:py-3 text-center text-xs md:text-sm font-semibold text-blue-300 whitespace-nowrap">RN HPRD</th>
                    <th className="px-3 md:px-4 py-2 md:py-3 text-center text-xs md:text-sm font-semibold text-blue-300">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {sffData.sffs.map((facility) => (
                    <tr key={facility.provnum} className="border-b border-gray-700/50 hover:bg-gray-800/30 transition-colors">
                      <td className="px-3 md:px-4 py-2 md:py-3">
                        <a
                          href={`https://pbjdashboard.com/?facility=${facility.provnum}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-300 hover:text-blue-200 underline font-medium text-sm md:text-base break-words"
                        >
                          {facility.name}
                        </a>
                      </td>
                      <td className="px-3 md:px-4 py-2 md:py-3 text-gray-300 text-xs md:text-sm">
                        {facility.city ? `${facility.city}, ${facility.state}` : facility.state}
                        {facility.county && <span className="text-gray-500 text-xs ml-1 hidden md:inline">({facility.county})</span>}
                      </td>
                      <td className="px-2 md:px-4 py-2 md:py-3 text-center text-white font-semibold text-sm md:text-base">{formatNumber(facility.totalHPRD)}</td>
                      <td className="px-2 md:px-4 py-2 md:py-3 text-center text-gray-300 text-sm md:text-base">{formatNumber(facility.directCareHPRD)}</td>
                      <td className="px-2 md:px-4 py-2 md:py-3 text-center text-gray-300 text-sm md:text-base">{formatNumber(facility.rnHPRD)}</td>
                      <td className="px-3 md:px-4 py-2 md:py-3 text-center">
                        {facility.isNewSFF && (
                          <span className="inline-block px-2 py-1 bg-orange-500/20 text-orange-300 text-xs font-semibold rounded whitespace-nowrap">
                            New SFF
                          </span>
                        )}
                        {!facility.isNewSFF && facility.wasCandidate && (
                          <span className="inline-block px-2 py-1 bg-yellow-500/20 text-yellow-300 text-xs font-semibold rounded whitespace-nowrap">
                            Was Candidate
                          </span>
                        )}
                        {!facility.isNewSFF && !facility.wasCandidate && (
                          <span className="text-gray-500 text-xs">Existing</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Candidates Section */}
        <div>
          <h2 className="text-xl md:text-2xl font-bold mb-3 md:mb-4">
            SFF Candidates ({sffData.candidates.length.toLocaleString()})
          </h2>
          {sffData.candidates.length === 0 ? (
            <div className="rounded-lg border border-gray-700 bg-[#0f172a]/60 p-8 text-center">
              <p className="text-gray-400">No SFF Candidates found for this scope.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-gray-700 bg-[#0f172a]/60 shadow-lg">
              <table className="w-full border-collapse min-w-[640px]">
                <thead>
                  <tr className="bg-yellow-600/20 border-b border-yellow-500/30">
                    <th className="px-3 md:px-4 py-2 md:py-3 text-left text-xs md:text-sm font-semibold text-yellow-300">Facility</th>
                    <th className="px-3 md:px-4 py-2 md:py-3 text-left text-xs md:text-sm font-semibold text-yellow-300">Location</th>
                    <th className="px-2 md:px-4 py-2 md:py-3 text-center text-xs md:text-sm font-semibold text-yellow-300 whitespace-nowrap">Total HPRD</th>
                    <th className="px-2 md:px-4 py-2 md:py-3 text-center text-xs md:text-sm font-semibold text-yellow-300 whitespace-nowrap">Direct Care</th>
                    <th className="px-2 md:px-4 py-2 md:py-3 text-center text-xs md:text-sm font-semibold text-yellow-300 whitespace-nowrap">RN HPRD</th>
                    <th className="px-3 md:px-4 py-2 md:py-3 text-center text-xs md:text-sm font-semibold text-yellow-300">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {sffData.candidates.map((facility) => (
                    <tr key={facility.provnum} className="border-b border-gray-700/50 hover:bg-gray-800/30 transition-colors">
                      <td className="px-3 md:px-4 py-2 md:py-3">
                        <a
                          href={`https://pbjdashboard.com/?facility=${facility.provnum}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-300 hover:text-blue-200 underline font-medium text-sm md:text-base break-words"
                        >
                          {facility.name}
                        </a>
                      </td>
                      <td className="px-3 md:px-4 py-2 md:py-3 text-gray-300 text-xs md:text-sm">
                        {facility.city ? `${facility.city}, ${facility.state}` : facility.state}
                        {facility.county && <span className="text-gray-500 text-xs ml-1 hidden md:inline">({facility.county})</span>}
                      </td>
                      <td className="px-2 md:px-4 py-2 md:py-3 text-center text-white font-semibold text-sm md:text-base">{formatNumber(facility.totalHPRD)}</td>
                      <td className="px-2 md:px-4 py-2 md:py-3 text-center text-gray-300 text-sm md:text-base">{formatNumber(facility.directCareHPRD)}</td>
                      <td className="px-2 md:px-4 py-2 md:py-3 text-center text-gray-300 text-sm md:text-base">{formatNumber(facility.rnHPRD)}</td>
                      <td className="px-3 md:px-4 py-2 md:py-3 text-center">
                        {facility.isNewCandidate && (
                          <span className="inline-block px-2 py-1 bg-orange-500/20 text-orange-300 text-xs font-semibold rounded whitespace-nowrap">
                            New Candidate
                          </span>
                        )}
                        {!facility.isNewCandidate && (
                          <span className="text-gray-500 text-xs">Existing</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="mt-8 md:mt-10 pt-6 border-t border-gray-700 text-center text-xs md:text-sm text-gray-400">
          <p>Source: CMS Payroll-Based Journal, Q2 2025</p>
        </div>
      </div>
    </div>
  );
}

