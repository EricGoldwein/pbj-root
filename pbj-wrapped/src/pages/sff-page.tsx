import { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { loadAllData } from '../lib/wrapped/dataLoader';
import { toTitleCase, capitalizeCity } from '../lib/wrapped/dataProcessor';
import { getAssetPath } from '../utils/assets';
import type { FacilityLiteRow, ProviderInfoRow } from '../lib/wrapped/wrappedTypes';

// Helper to get data path with base URL
function getDataPath(path: string = ''): string {
  const baseUrl = import.meta.env.BASE_URL;
  const cleanPath = path.startsWith('/') ? path.slice(1) : path;
  return `${baseUrl}data${cleanPath ? `/${cleanPath}` : ''}`.replace(/([^:]\/)\/+/g, '$1');
}

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
  caseMixExpectedHPRD?: number;
  percentOfCaseMix?: number;
  census?: number;
  isNewSFF: boolean;
  isNewCandidate: boolean;
  wasCandidate: boolean;
  wasSFF: boolean;
  previousStatus?: string; // Store the previous status for display
}

type SortField = 'totalHPRD' | 'directCareHPRD' | 'rnHPRD' | 'percentOfCaseMix' | 'name' | 'state' | 'census';
type SortDirection = 'asc' | 'desc';

export default function SFFPage() {
  const { scope } = useParams<{ scope?: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sffData, setSffData] = useState<{
    sffs: SFFFacility[];
    candidates: SFFFacility[];
  } | null>(null);
  const [sortField, setSortField] = useState<SortField>('totalHPRD');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc'); // Default: lowest first
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 50;

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        setError(null);

        const baseDataPath = getDataPath();
        const data = await loadAllData(baseDataPath, 'usa', undefined);
        
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
            
            // Determine previous status for display
            let previousStatus: string | undefined;
            if (wasSFF) {
              previousStatus = 'Was SFF';
            } else if (wasCandidate) {
              previousStatus = 'Was Candidate';
            } else if (q1Status === '') {
              previousStatus = undefined; // Was nothing
            } else {
              previousStatus = q1Status; // Some other status
            }

            const caseMixExpected = provider.case_mix_total_nurse_hrs_per_resident_per_day;
            const totalHPRD = facility.Total_Nurse_HPRD || 0;
            const percentOfCaseMix = caseMixExpected && caseMixExpected > 0 
              ? (totalHPRD / caseMixExpected) * 100 
              : undefined;

            const sffFacility: SFFFacility = {
              provnum: provider.PROVNUM,
              name: toTitleCase(provider.PROVNAME),
              state: provider.STATE,
              city: capitalizeCity(provider.CITY),
              county: provider.COUNTY_NAME ? capitalizeCity(provider.COUNTY_NAME) : undefined,
              sffStatus: provider.sff_status,
              totalHPRD,
              directCareHPRD: facility.Nurse_Care_HPRD || 0,
              rnHPRD: (facility.Total_RN_HPRD || facility.Direct_Care_RN_HPRD || 0),
              caseMixExpectedHPRD: caseMixExpected,
              percentOfCaseMix,
              census: facility.Census,
              isNewSFF,
              isNewCandidate,
              wasCandidate,
              wasSFF,
              previousStatus,
            };

            if (isSFF) {
              sffs.push(sffFacility);
            } else {
              candidates.push(sffFacility);
            }
          }
        }

        // Filter by state or region if scope is provided
        let filteredSFFs = sffs;
        let filteredCandidates = candidates;
        
        if (scope && scope !== 'usa') {
          if (scope.length === 2) {
            // State code
            const stateCode = scope.toUpperCase();
            filteredSFFs = sffs.filter(f => f.state === stateCode);
            filteredCandidates = candidates.filter(f => f.state === stateCode);
          } else if (scope.startsWith('region')) {
            // Region (e.g., "region1", "region2")
            const regionNum = parseInt(scope.replace('region', ''));
            if (!isNaN(regionNum) && data.regionStateMapping) {
              const regionStates = data.regionStateMapping.get(regionNum) || new Set<string>();
              filteredSFFs = sffs.filter(f => regionStates.has(f.state));
              filteredCandidates = candidates.filter(f => regionStates.has(f.state));
            }
          }
        }

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

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
    setCurrentPage(1);
  };

  const sortedSFFs = useMemo(() => {
    if (!sffData) return [];
    const sorted = [...sffData.sffs].sort((a, b) => {
      let aVal: number | string = 0;
      let bVal: number | string = 0;
      
      switch (sortField) {
        case 'totalHPRD':
          aVal = a.totalHPRD;
          bVal = b.totalHPRD;
          break;
        case 'directCareHPRD':
          aVal = a.directCareHPRD;
          bVal = b.directCareHPRD;
          break;
        case 'rnHPRD':
          aVal = a.rnHPRD;
          bVal = b.rnHPRD;
          break;
        case 'percentOfCaseMix':
          aVal = a.percentOfCaseMix ?? 0;
          bVal = b.percentOfCaseMix ?? 0;
          break;
        case 'name':
          aVal = a.name;
          bVal = b.name;
          break;
        case 'state':
          aVal = a.state;
          bVal = b.state;
          break;
        case 'census':
          aVal = a.census ?? 0;
          bVal = b.census ?? 0;
          break;
      }
      
      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortDirection === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }
      return sortDirection === 'asc' ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number);
    });
    return sorted;
  }, [sffData, sortField, sortDirection]);

  const sortedCandidates = useMemo(() => {
    if (!sffData) return [];
    const sorted = [...sffData.candidates].sort((a, b) => {
      let aVal: number | string = 0;
      let bVal: number | string = 0;
      
      switch (sortField) {
        case 'totalHPRD':
          aVal = a.totalHPRD;
          bVal = b.totalHPRD;
          break;
        case 'directCareHPRD':
          aVal = a.directCareHPRD;
          bVal = b.directCareHPRD;
          break;
        case 'rnHPRD':
          aVal = a.rnHPRD;
          bVal = b.rnHPRD;
          break;
        case 'percentOfCaseMix':
          aVal = a.percentOfCaseMix ?? 0;
          bVal = b.percentOfCaseMix ?? 0;
          break;
        case 'name':
          aVal = a.name;
          bVal = b.name;
          break;
        case 'state':
          aVal = a.state;
          bVal = b.state;
          break;
        case 'census':
          aVal = a.census ?? 0;
          bVal = b.census ?? 0;
          break;
      }
      
      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortDirection === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }
      return sortDirection === 'asc' ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number);
    });
    return sorted;
  }, [sffData, sortField, sortDirection]);

  const paginatedSFFs = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return sortedSFFs.slice(start, start + itemsPerPage);
  }, [sortedSFFs, currentPage]);

  const paginatedCandidates = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return sortedCandidates.slice(start, start + itemsPerPage);
  }, [sortedCandidates, currentPage]);

  const totalPagesSFFs = Math.ceil(sortedSFFs.length / itemsPerPage);
  const totalPagesCandidates = Math.ceil(sortedCandidates.length / itemsPerPage);

  const formatNumber = (num: number, decimals: number = 2): string => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const formatPercent = (num: number | undefined, decimals: number = 1): string => {
    if (num === undefined || isNaN(num)) return 'N/A';
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }) + '%';
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
      'DC': 'District of Columbia', 'PR': 'Puerto Rico'
    };
    return stateMap[code] || code;
  };

  const getRegionName = (regionNum: number): string => {
    const regionNames: Record<number, string> = {
      1: 'Boston', 2: 'New York', 3: 'Philadelphia', 4: 'Atlanta', 5: 'Chicago',
      6: 'Dallas', 7: 'Kansas City', 8: 'Denver', 9: 'San Francisco', 10: 'Seattle'
    };
    return regionNames[regionNum] || `Region ${regionNum}`;
  };

  // Get all states with SFFs for USA page
  const statesWithSFFs = useMemo(() => {
    if (!sffData || scope !== 'usa') return [];
    const stateSet = new Set<string>();
    sffData.sffs.forEach(f => stateSet.add(f.state));
    sffData.candidates.forEach(f => stateSet.add(f.state));
    return Array.from(stateSet).sort();
  }, [sffData, scope]);

  // Get all regions with SFFs for USA page
  const [regionStateMapping, setRegionStateMapping] = useState<Map<number, Set<string>> | null>(null);
  
  useEffect(() => {
    async function loadRegionMapping() {
      try {
        const baseDataPath = getDataPath();
        const data = await loadAllData(baseDataPath, 'usa', undefined);
        if (data.regionStateMapping) {
          setRegionStateMapping(data.regionStateMapping);
        }
      } catch (err) {
        console.error('Error loading region mapping:', err);
      }
    }
    if (scope === 'usa') {
      loadRegionMapping();
    }
  }, [scope]);

  const regionsWithSFFs = useMemo(() => {
    if (!sffData || !regionStateMapping || scope !== 'usa') return [];
    const regionsWithData: number[] = [];
    for (let i = 1; i <= 10; i++) {
      const regionStates = regionStateMapping.get(i);
      if (regionStates) {
        const hasSFFs = sffData.sffs.some(f => regionStates.has(f.state)) ||
                       sffData.candidates.some(f => regionStates.has(f.state));
        if (hasSFFs) {
          regionsWithData.push(i);
        }
      }
    }
    return regionsWithData;
  }, [sffData, regionStateMapping, scope]);

  const pageTitle = scope === 'usa' 
    ? 'Special Focus Facilities & Candidates — United States'
    : scope && scope.startsWith('region')
    ? `Special Focus Facilities & Candidates — CMS Region ${scope.replace('region', '')} (${getRegionName(parseInt(scope.replace('region', '')))})`
    : scope 
    ? `Special Focus Facilities & Candidates — ${getStateName(scope.toUpperCase())}`
    : 'Special Focus Facilities & Candidates';

  const SortableHeader: React.FC<{ field: SortField; children: React.ReactNode; className?: string }> = ({ field, children, className = '' }) => {
    const isActive = sortField === field;
    return (
      <th 
        className={`${className} cursor-pointer select-none hover:bg-blue-600/30 transition-colors`}
        onClick={() => handleSort(field)}
      >
        <div className="flex items-center justify-center gap-1">
          <span>{children}</span>
          {isActive && (
            <span className="text-blue-200">{sortDirection === 'asc' ? '↑' : '↓'}</span>
          )}
        </div>
      </th>
    );
  };

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

        {/* State/Region Dropdowns for USA page */}
        {scope === 'usa' && (statesWithSFFs.length > 0 || regionsWithSFFs.length > 0) && (
          <div className="mb-6 md:mb-8">
            <div className="flex flex-col sm:flex-row gap-4">
              {statesWithSFFs.length > 0 && (
                <div className="flex-1">
                  <label htmlFor="state-select" className="block text-sm font-semibold text-blue-300 mb-2">State</label>
                  <select
                    id="state-select"
                    value=""
                    onChange={(e) => {
                      if (e.target.value) {
                        navigate(`/sff/${e.target.value.toLowerCase()}`);
                      }
                    }}
                    className="w-full px-4 py-2 bg-[#0f172a]/60 border border-blue-500/50 rounded text-blue-300 hover:bg-blue-600/20 focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer"
                  >
                    <option value="">Select a state...</option>
                    {statesWithSFFs.map(stateCode => (
                      <option key={stateCode} value={stateCode} className="bg-[#0f172a]">
                        {getStateName(stateCode)}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              {regionsWithSFFs.length > 0 && (
                <div className="flex-1">
                  <label htmlFor="region-select" className="block text-sm font-semibold text-green-300 mb-2">CMS Region</label>
                  <select
                    id="region-select"
                    value=""
                    onChange={(e) => {
                      if (e.target.value) {
                        navigate(`/sff/region${e.target.value}`);
                      }
                    }}
                    className="w-full px-4 py-2 bg-[#0f172a]/60 border border-green-500/50 rounded text-green-300 hover:bg-green-600/20 focus:outline-none focus:ring-2 focus:ring-green-500 cursor-pointer"
                  >
                    <option value="">Select a region...</option>
                    {regionsWithSFFs.map(regionNum => (
                      <option key={`region${regionNum}`} value={regionNum} className="bg-[#0f172a]">
                        Region {regionNum} ({getRegionName(regionNum)})
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          </div>
        )}

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
            <>
              <div className="overflow-x-auto rounded-lg border border-gray-700 bg-[#0f172a]/60 shadow-lg">
                <table className="w-full border-collapse min-w-[800px]">
                  <thead>
                    <tr className="bg-blue-600/20 border-b border-blue-500/30">
                      <th className="px-3 md:px-4 py-2 md:py-3 text-left text-xs md:text-sm font-semibold text-blue-300">Facility</th>
                      <th className="px-3 md:px-4 py-2 md:py-3 text-left text-xs md:text-sm font-semibold text-blue-300">Location</th>
                      <SortableHeader field="totalHPRD" className="px-2 md:px-4 py-2 md:py-3 text-center text-xs md:text-sm font-semibold text-blue-300 whitespace-nowrap">Total HPRD</SortableHeader>
                      <SortableHeader field="directCareHPRD" className="px-2 md:px-4 py-2 md:py-3 text-center text-xs md:text-sm font-semibold text-blue-300 whitespace-nowrap">Direct Care</SortableHeader>
                      <SortableHeader field="rnHPRD" className="px-2 md:px-4 py-2 md:py-3 text-center text-xs md:text-sm font-semibold text-blue-300 whitespace-nowrap">RN HPRD</SortableHeader>
                      <SortableHeader field="percentOfCaseMix" className="px-2 md:px-4 py-2 md:py-3 text-center text-xs md:text-sm font-semibold text-blue-300 whitespace-nowrap">% of Case Mix</SortableHeader>
                      <SortableHeader field="census" className="px-2 md:px-4 py-2 md:py-3 text-center text-xs md:text-sm font-semibold text-blue-300 whitespace-nowrap">Census</SortableHeader>
                      <th className="px-3 md:px-4 py-2 md:py-3 text-center text-xs md:text-sm font-semibold text-blue-300">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedSFFs.map((facility) => (
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
                        <td className="px-2 md:px-4 py-2 md:py-3 text-center text-gray-300 text-sm md:text-base">
                          {formatPercent(facility.percentOfCaseMix)}
                        </td>
                        <td className="px-2 md:px-4 py-2 md:py-3 text-center text-gray-300 text-sm md:text-base">
                          {facility.census ? facility.census.toLocaleString() : 'N/A'}
                        </td>
                        <td className="px-3 md:px-4 py-2 md:py-3 text-center">
                          {facility.isNewSFF && (
                            <span className="inline-block px-2 py-1 bg-orange-500/20 text-orange-300 text-xs font-semibold rounded whitespace-nowrap">
                              New SFF
                            </span>
                          )}
                          {!facility.isNewSFF && facility.wasSFF && (
                            <span className="text-gray-500 text-xs">Existing</span>
                          )}
                          {!facility.isNewSFF && !facility.wasSFF && facility.wasCandidate && (
                            <span className="inline-block px-2 py-1 bg-yellow-500/20 text-yellow-300 text-xs font-semibold rounded whitespace-nowrap">
                              Was Candidate
                            </span>
                          )}
                          {!facility.isNewSFF && !facility.wasSFF && !facility.wasCandidate && (
                            <span className="text-gray-500 text-xs">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {totalPagesSFFs > 1 && (
                <div className="mt-4 flex items-center justify-between">
                  <div className="text-sm text-gray-400">
                    Showing {(currentPage - 1) * itemsPerPage + 1} to {Math.min(currentPage * itemsPerPage, sortedSFFs.length)} of {sortedSFFs.length}
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                      disabled={currentPage === 1}
                      className="px-4 py-2 bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/50 rounded text-blue-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      Previous
                    </button>
                    <span className="px-4 py-2 text-gray-300">
                      Page {currentPage} of {totalPagesSFFs}
                    </span>
                    <button
                      onClick={() => setCurrentPage(p => Math.min(totalPagesSFFs, p + 1))}
                      disabled={currentPage === totalPagesSFFs}
                      className="px-4 py-2 bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/50 rounded text-blue-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </>
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
            <>
              <div className="overflow-x-auto rounded-lg border border-gray-700 bg-[#0f172a]/60 shadow-lg">
                <table className="w-full border-collapse min-w-[800px]">
                  <thead>
                    <tr className="bg-yellow-600/20 border-b border-yellow-500/30">
                      <th className="px-3 md:px-4 py-2 md:py-3 text-left text-xs md:text-sm font-semibold text-yellow-300">Facility</th>
                      <th className="px-3 md:px-4 py-2 md:py-3 text-left text-xs md:text-sm font-semibold text-yellow-300">Location</th>
                      <SortableHeader field="totalHPRD" className="px-2 md:px-4 py-2 md:py-3 text-center text-xs md:text-sm font-semibold text-yellow-300 whitespace-nowrap">Total HPRD</SortableHeader>
                      <SortableHeader field="directCareHPRD" className="px-2 md:px-4 py-2 md:py-3 text-center text-xs md:text-sm font-semibold text-yellow-300 whitespace-nowrap">Direct Care</SortableHeader>
                      <SortableHeader field="rnHPRD" className="px-2 md:px-4 py-2 md:py-3 text-center text-xs md:text-sm font-semibold text-yellow-300 whitespace-nowrap">RN HPRD</SortableHeader>
                      <SortableHeader field="percentOfCaseMix" className="px-2 md:px-4 py-2 md:py-3 text-center text-xs md:text-sm font-semibold text-yellow-300 whitespace-nowrap">% of Case Mix</SortableHeader>
                      <SortableHeader field="census" className="px-2 md:px-4 py-2 md:py-3 text-center text-xs md:text-sm font-semibold text-yellow-300 whitespace-nowrap">Census</SortableHeader>
                      <th className="px-3 md:px-4 py-2 md:py-3 text-center text-xs md:text-sm font-semibold text-yellow-300">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedCandidates.map((facility) => (
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
                        <td className="px-2 md:px-4 py-2 md:py-3 text-center text-gray-300 text-sm md:text-base">
                          {formatPercent(facility.percentOfCaseMix)}
                        </td>
                        <td className="px-2 md:px-4 py-2 md:py-3 text-center text-gray-300 text-sm md:text-base">
                          {facility.census ? facility.census.toLocaleString() : 'N/A'}
                        </td>
                        <td className="px-3 md:px-4 py-2 md:py-3 text-center">
                          {facility.isNewCandidate && (
                            <span className="inline-block px-2 py-1 bg-orange-500/20 text-orange-300 text-xs font-semibold rounded whitespace-nowrap">
                              New Candidate
                            </span>
                          )}
                          {!facility.isNewCandidate && facility.wasCandidate && (
                            <span className="text-gray-500 text-xs">Existing</span>
                          )}
                          {!facility.isNewCandidate && !facility.wasCandidate && facility.wasSFF && (
                            <span className="inline-block px-2 py-1 bg-yellow-500/20 text-yellow-300 text-xs font-semibold rounded whitespace-nowrap">
                              Was SFF
                            </span>
                          )}
                          {!facility.isNewCandidate && !facility.wasCandidate && !facility.wasSFF && (
                            <span className="text-gray-500 text-xs">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {totalPagesCandidates > 1 && (
                <div className="mt-4 flex items-center justify-between">
                  <div className="text-sm text-gray-400">
                    Showing {(currentPage - 1) * itemsPerPage + 1} to {Math.min(currentPage * itemsPerPage, sortedCandidates.length)} of {sortedCandidates.length}
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                      disabled={currentPage === 1}
                      className="px-4 py-2 bg-yellow-600/20 hover:bg-yellow-600/30 border border-yellow-500/50 rounded text-yellow-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      Previous
                    </button>
                    <span className="px-4 py-2 text-gray-300">
                      Page {currentPage} of {totalPagesCandidates}
                    </span>
                    <button
                      onClick={() => setCurrentPage(p => Math.min(totalPagesCandidates, p + 1))}
                      disabled={currentPage === totalPagesCandidates}
                      className="px-4 py-2 bg-yellow-600/20 hover:bg-yellow-600/30 border border-yellow-500/50 rounded text-yellow-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        <div className="mt-8 md:mt-10 pt-6 border-t border-gray-700 text-center text-xs md:text-sm text-gray-400">
          <p>Source: CMS Payroll-Based Journal, Q2 2025</p>
        </div>
      </div>
    </div>
  );
}
