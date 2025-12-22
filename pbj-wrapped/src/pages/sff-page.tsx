import { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { loadAllData } from '../lib/wrapped/dataLoader';
import { toTitleCase, capitalizeCity } from '../lib/wrapped/dataProcessor';
import { getAssetPath } from '../utils/assets';
import { updateSEO } from '../utils/seo';
import { StateOutline } from '../components/wrapped/StateOutline';
import type { FacilityLiteRow, ProviderInfoRow } from '../lib/wrapped/wrappedTypes';

// Helper to get data path with base URL
function getDataPath(path: string = ''): string {
  const baseUrl = import.meta.env.BASE_URL;
  const cleanPath = path.startsWith('/') ? path.slice(1) : path;
  return `${baseUrl}data${cleanPath ? `/${cleanPath}` : ''}`.replace(/([^:]\/)\/+/g, '$1');
}

interface PDFFacilityData {
  provider_number: string;
  facility_name: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  zip: string | null;
  phone_number: string | null;
  most_recent_inspection: string | null;
  met_survey_criteria: string | null;
  months_as_sff: number | null;
}

interface SFFCandidateJSON {
  document_date: {
    month: number;
    year: number;
    month_name: string;
  };
  table_a_current_sff: PDFFacilityData[];
  table_b_graduated: PDFFacilityData[];
  table_c_no_longer_participating: PDFFacilityData[];
  table_d_candidates: PDFFacilityData[];
  summary: {
    current_sff_count: number;
    graduated_count: number;
    no_longer_participating_count: number;
    candidates_count: number;
    total_count: number;
  };
}

type SFFStatus = 'SFF' | 'Candidate' | 'Graduate' | 'Terminated';

interface SFFFacility {
  provnum: string;
  name: string;
  state: string;
  city?: string;
  county?: string;
  sffStatus: SFFStatus; // New: Categorized status
  totalHPRD: number;
  directCareHPRD: number;
  rnHPRD: number;
  caseMixExpectedHPRD?: number;
  percentOfCaseMix?: number;
  census?: number;
  monthsAsSFF?: number; // From PDF
  mostRecentInspection?: string; // From PDF
  metSurveyCriteria?: string; // From PDF
  isNewSFF: boolean;
  isNewCandidate: boolean;
  wasCandidate: boolean;
  wasSFF: boolean;
  previousStatus?: string;
}

type SortField = 'totalHPRD' | 'directCareHPRD' | 'rnHPRD' | 'percentOfCaseMix' | 'name' | 'state' | 'census' | 'monthsAsSFF' | 'sffStatus';
type SortDirection = 'asc' | 'desc';
type CategoryFilter = 'all' | 'sffs-and-candidates' | 'sffs-only' | 'graduates' | 'terminated';

export default function SFFPage() {
  const { scope: scopeParam } = useParams<{ scope?: string }>();
  const location = useLocation();
  
  // Determine scope from URL path since /sff/usa is a specific route
  const scope = scopeParam || (location.pathname === '/sff/usa' ? 'usa' : location.pathname.replace('/sff/', '') || undefined);
  
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [allFacilities, setAllFacilities] = useState<SFFFacility[]>([]);
  const [candidateJSON, setCandidateJSON] = useState<SFFCandidateJSON | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>('all');
  const [sortField, setSortField] = useState<SortField>('name');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [currentPage, setCurrentPage] = useState(1);
  const [showMethodology, setShowMethodology] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const itemsPerPage = 50;

  // Helper function for state names (needed for SEO)
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

  // Update SEO/OG tags based on page scope
  useEffect(() => {
    const baseUrl = 'https://pbj320.com';
    const currentPath = scope === 'usa' ? '/sff/usa' : scope ? `/sff/${scope}` : '/sff';
    const fullUrl = `${baseUrl}${currentPath}`;
    
    let title = 'Special Focus Facilities Program | PBJ320';
    let description = 'Complete list of Special Focus Facilities (SFFs), SFF Candidates, Graduates, and facilities no longer participating in Medicare/Medicaid. Source: CMS SFF Posting Dec. 2025; CMS PBJ (Q2 2025).';
    
    if (scope === 'usa') {
      title = 'Special Focus Facilities Program — United States | PBJ320';
      description = 'United States Special Focus Facilities (SFFs) and SFF Candidates. Complete list with staffing data from CMS PBJ Q2 2025.';
    } else if (scope && scope.startsWith('region')) {
      const regionNum = parseInt(scope.replace(/^region-?/, ''));
      title = `Special Focus Facilities Program — CMS Region ${regionNum} | PBJ320`;
      description = `CMS Region ${regionNum} Special Focus Facilities (SFFs) and SFF Candidates. Complete list with staffing data from CMS PBJ Q2 2025.`;
    } else if (scope) {
      const stateName = getStateName(scope.toUpperCase());
      title = `Special Focus Facilities Program — ${stateName} | PBJ320`;
      description = `${stateName} Special Focus Facilities (SFFs) and SFF Candidates. Complete list with staffing data from CMS PBJ Q2 2025.`;
    }
    
    updateSEO({
      title,
      description,
      keywords: 'special focus facilities, SFF, nursing home staffing, CMS PBJ, Q2 2025, nursing home quality, long-term care',
      ogTitle: title.replace(' | PBJ320', ''),
      ogDescription: description,
      ogImage: `${baseUrl}/images/phoebe-wrapped-wide.png`,
      ogUrl: fullUrl,
      canonical: fullUrl,
    });
  }, [scope]);

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        setError(null);

        // Load SFF JSON file (combined from all 4 CSV tables with category field)
        const baseUrl = import.meta.env.BASE_URL;
        const jsonPath = `${baseUrl}sff-facilities.json`.replace(/([^:]\/)\/+/g, '$1');
        let sffFacilitiesData: { facilities: Array<PDFFacilityData & { category: string }>, document_date?: any, summary?: any } | null = null;
        
        try {
          const jsonResponse = await fetch(jsonPath);
          if (jsonResponse.ok) {
            const jsonData = await jsonResponse.json();
            if (jsonData && jsonData.facilities && Array.isArray(jsonData.facilities)) {
              sffFacilitiesData = jsonData;
              
              // Set candidateJSON for display (legacy format for UI)
              const tableA = jsonData.facilities.filter((f: any) => f.category === 'SFF');
              const tableB = jsonData.facilities.filter((f: any) => f.category === 'Graduate');
              const tableC = jsonData.facilities.filter((f: any) => f.category === 'Terminated');
              const tableD = jsonData.facilities.filter((f: any) => f.category === 'Candidate');
              
              setCandidateJSON({
                document_date: jsonData.document_date || { month: 12, year: 2025, month_name: 'December' },
                table_a_current_sff: tableA,
                table_b_graduated: tableB,
                table_c_no_longer_participating: tableC,
                table_d_candidates: tableD,
                summary: jsonData.summary || {
                  current_sff_count: tableA.length,
                  graduated_count: tableB.length,
                  no_longer_participating_count: tableC.length,
                  candidates_count: tableD.length,
                  total_count: jsonData.facilities.length
                }
              });
              
              console.log(`Loaded SFF JSON: ${jsonData.facilities.length} total facilities (SFF: ${tableA.length}, Graduate: ${tableB.length}, Terminated: ${tableC.length}, Candidate: ${tableD.length})`);
            } else {
              console.warn('SFF JSON file has unexpected structure');
            }
          } else {
            console.warn(`Could not load SFF JSON file: ${jsonResponse.status}`);
          }
        } catch (err) {
          console.warn('Error loading SFF JSON file:', err);
        }

        const baseDataPath = getDataPath();
        const data = await loadAllData(baseDataPath, 'usa', undefined);
        
        // Get provider info for status comparison
        // Q1 data used for determining previous status (from provider info file, typically from earlier period)
        // Q2 data used for current staffing metrics (from Q2 2025 PBJ data)
        const providerInfoQ1 = data.providerInfo.q1 || [];
        const providerInfoQ2 = data.providerInfo.q2 || [];
        const facilityQ2 = data.facilityData.q2 || [];
        
        // Debug: Log data counts for troubleshooting
        console.log(`[SFF Page] Data loaded: Provider Q2=${providerInfoQ2.length}, Facility Q2=${facilityQ2.length}, Provider Q1=${providerInfoQ1.length}`);
        
        // STRICT CCN normalization: pad to exactly 6 digits, no variations
        const normalizeCCN = (ccn: string): string => {
          if (!ccn) return '';
          const str = ccn.toString().trim().replace(/[^0-9]/g, ''); // Remove non-digits
          if (!str) return '';
          return str.padStart(6, '0');
        };

        // Auto-correct CSV column shifts: If Total_Nurse_HPRD is 0 but Nurse_Care_HPRD has a value,
        // shift all columns to the right (this is a common PapaParse misalignment issue)
        const correctColumnShift = (facility: FacilityLiteRow): FacilityLiteRow => {
          const totalHPRD = typeof facility.Total_Nurse_HPRD === 'number' 
            ? facility.Total_Nurse_HPRD 
            : (parseFloat(String(facility.Total_Nurse_HPRD)) || 0);
          const directCareHPRD = typeof facility.Nurse_Care_HPRD === 'number' 
            ? facility.Nurse_Care_HPRD 
            : (parseFloat(String(facility.Nurse_Care_HPRD)) || 0);
          const rnHPRD = typeof facility.Total_RN_HPRD === 'number' 
            ? facility.Total_RN_HPRD 
            : (parseFloat(String(facility.Total_RN_HPRD)) || 0);
          
          // Detect shift: Total_Nurse_HPRD is 0 but Nurse_Care_HPRD has a value (> 0.5 to avoid false positives)
          if (totalHPRD === 0 && directCareHPRD > 0.5) {
            console.log(`[Auto-Correcting Shift] PROVNUM=${facility.PROVNUM}, shifting columns right`);
            
            // Shift columns: each field gets the value from the next field
            return {
              ...facility,
              Total_Nurse_HPRD: directCareHPRD, // Nurse_Care_HPRD -> Total_Nurse_HPRD
              Nurse_Care_HPRD: rnHPRD, // Total_RN_HPRD -> Nurse_Care_HPRD
              Total_RN_HPRD: typeof facility.Direct_Care_RN_HPRD === 'number' 
                ? facility.Direct_Care_RN_HPRD 
                : (parseFloat(String(facility.Direct_Care_RN_HPRD)) || 0), // Direct_Care_RN_HPRD -> Total_RN_HPRD
              Direct_Care_RN_HPRD: typeof facility.Contract_Percentage === 'number'
                ? facility.Contract_Percentage
                : (parseFloat(String(facility.Contract_Percentage)) || 0), // Contract_Percentage -> Direct_Care_RN_HPRD
              // Note: Contract_Percentage and Census may also shift, but we'll keep them as-is for now
            };
          }
          
          return facility; // No shift detected, return as-is
        };

        // STRICT matching: Only use normalized 6-digit CCN
        const findFacilityByCCN = (ccn: string): FacilityLiteRow | undefined => {
          const normalized = normalizeCCN(ccn);
          if (!normalized) return undefined;
          
          // Try map first (fastest) - data is already corrected in the map
          const found = facilityMap.get(normalized);
          if (found) {
            return found;
          }
          
          // If not in map, search array directly and auto-correct if needed
          const foundInArray = facilityQ2.find((f: FacilityLiteRow) => {
            if (f.CY_Qtr && f.CY_Qtr !== '2025Q2') return false;
            const fProvNum = f.PROVNUM?.toString().trim() || '';
            if (!fProvNum) return false;
            return normalizeCCN(fProvNum) === normalized;
          });
          
          if (foundInArray) {
            // Auto-correct any column shifts before returning
            return correctColumnShift(foundInArray);
          }
          
          return undefined;
        };
        
        // STRICT matching: Only use normalized 6-digit CCN
        const findProviderByCCN = (ccn: string): ProviderInfoRow | undefined => {
          const normalized = normalizeCCN(ccn);
          if (!normalized) return undefined;
          
          // Try map first (fastest)
          const found = providerMap.get(normalized);
          if (found) return found;
          
          // If not in map, search array directly
          return providerInfoQ2.find(p => {
            const provNum = p.PROVNUM?.toString().trim() || '';
            if (!provNum) return false;
            return normalizeCCN(provNum) === normalized;
          });
        };

        // Create maps for quick lookup - STRICT: Only use normalized 6-digit CCN as key
        // This prevents false matches from CCN variations
        const facilityMap = new Map<string, FacilityLiteRow>();
        let correctedShifts = 0;
        facilityQ2.forEach((f: FacilityLiteRow) => {
          const provNum = f.PROVNUM?.toString().trim() || '';
          if (!provNum) return;
          
          // Only include Q2 2025 data
          if (f.CY_Qtr && f.CY_Qtr !== '2025Q2') return;
          
          // Auto-correct CSV column shifts before adding to map
          const corrected = correctColumnShift(f);
          if (corrected !== f) {
            correctedShifts++;
          }
          
          // STRICT: Only use normalized 6-digit CCN as key
          const normalized = normalizeCCN(provNum);
          if (normalized) {
            // If key already exists, log a warning (shouldn't happen with strict matching)
            if (facilityMap.has(normalized)) {
              console.warn(`[Duplicate CCN] PROVNUM=${provNum} (normalized=${normalized}) already in map - keeping first entry`);
            } else {
              facilityMap.set(normalized, corrected);
            }
          }
        });
        
        console.log(`[Matching] Created facilityMap with ${facilityMap.size} entries from ${facilityQ2.length} Q2 facilities (auto-corrected ${correctedShifts} shifted columns)`);
        
        const providerMap = new Map<string, ProviderInfoRow>();
        providerInfoQ2.forEach((p: ProviderInfoRow) => {
          const provNum = p.PROVNUM?.toString().trim() || '';
          if (!provNum) return;
          
          // STRICT: Only use normalized 6-digit CCN as key
          const normalized = normalizeCCN(provNum);
          if (normalized) {
            // If key already exists, log a warning (shouldn't happen with strict matching)
            if (providerMap.has(normalized)) {
              console.warn(`[Duplicate CCN] PROVNUM=${provNum} (normalized=${normalized}) already in map - keeping first entry`);
            } else {
              providerMap.set(normalized, p);
            }
          }
        });
        
        console.log(`[Matching] Created providerMap with ${providerMap.size} entries from ${providerInfoQ2.length} Q2 providers`);
        
        const q1StatusMap = new Map<string, string>();
        providerInfoQ1.forEach((p: ProviderInfoRow) => {
          const status = p.sff_status?.trim().toUpperCase() || '';
          const normalized = normalizeCCN(p.PROVNUM);
          if (normalized) {
            q1StatusMap.set(normalized, status);
          }
        });

        const allFacilitiesList: SFFFacility[] = [];
        const processedCCNs = new Set<string>();
        let skippedNoCCN = 0;
        let skippedDuplicates = 0;
        let totalFromJSON = 0;

        // Process all facilities from JSON (already has category field from the 4 CSVs)
        if (sffFacilitiesData && sffFacilitiesData.facilities) {
          // Use facilities directly - they already have category field
          const allPDFFacilities: Array<PDFFacilityData & { status: SFFStatus }> = sffFacilitiesData.facilities.map(f => ({
            ...f,
            status: (f.category === 'SFF' ? 'SFF' : 
                     f.category === 'Graduate' ? 'Graduate' : 
                     f.category === 'Terminated' ? 'Terminated' : 
                     'Candidate') as SFFStatus
          }));

          totalFromJSON = allPDFFacilities.length;
          console.log(`[Processing] Total facilities from JSON: ${totalFromJSON}`);
          
          for (const pdfFacility of allPDFFacilities) {
            const ccn = pdfFacility.provider_number?.toString().trim();
            if (!ccn) {
              skippedNoCCN++;
              console.warn('PDF facility missing provider_number:', pdfFacility);
              continue;
            }
            
            // Skip if already processed
            if (processedCCNs.has(ccn)) {
              skippedDuplicates++;
              console.log(`[Duplicate] Skipping duplicate CCN: ${ccn}, Facility: ${pdfFacility.facility_name}`);
              continue;
            }
            
            // Debug: Log specific facilities that user mentioned
            const isProblematicFacility = ccn === '165344' || ccn === '155857' || ccn === '175172' || ccn === '235187' || 
                                         pdfFacility.facility_name?.toLowerCase().includes('aspire') ||
                                         pdfFacility.facility_name?.toLowerCase().includes('tranquility') ||
                                         pdfFacility.facility_name?.toLowerCase().includes('excel healthcare') ||
                                         pdfFacility.facility_name?.toLowerCase().includes('mission point');
            
            // Debug: Log first few facilities to see what we're processing
            if (allFacilitiesList.length < 5 || isProblematicFacility) {
              console.log(`[Processing] CCN=${ccn}, Name=${pdfFacility.facility_name || 'MISSING'}, Status=${pdfFacility.status}, Months=${pdfFacility.months_as_sff}`);
            }
            
            // PRIORITY 1: Find facility data FIRST using CCN directly (HPRD, Census are most important)
            // STRICT: Only normalized 6-digit CCN matching
            let facility = findFacilityByCCN(ccn);
            
            // PRIORITY 2: Find provider info using CCN (for name, location, case-mix)
            // STRICT: Only normalized 6-digit CCN matching
            let provider = findProviderByCCN(ccn);

            // If we found facility but not provider, try to find provider using facility's PROVNUM
            if (facility && !provider) {
              const facilityProvNum = facility.PROVNUM?.toString().trim() || '';
              if (facilityProvNum) {
                provider = findProviderByCCN(facilityProvNum);
              }
            }

            const normalizedCCN = normalizeCCN(ccn);

            if (facility || provider) {
              // If we have a provider but no facility, try to find facility using provider's PROVNUM
              if (!facility && provider) {
                const provNum = provider.PROVNUM?.toString().trim() || '';
                if (provNum) {
                  facility = findFacilityByCCN(provNum);
                }
              }
              
              // Facility data is already auto-corrected in the map, no need for additional validation
              
              const q1Status = normalizedCCN ? (q1StatusMap.get(normalizedCCN) || '') : '';
              const status = provider?.sff_status?.trim().toUpperCase() || '';
              const isSFF = status === 'SFF' || status === 'SPECIAL FOCUS FACILITY' || (typeof status === 'string' && status.includes('SFF') && !status.includes('CANDIDATE'));
              const isCandidate = status === 'SFF CANDIDATE' || status === 'CANDIDATE' || 
                                 (typeof status === 'string' && status.includes('CANDIDATE') && !status.includes('SFF'));

              // If not explicitly SFF or candidate in data, treat as candidate (from JSON)
              const effectiveIsCandidate = !isSFF && (isCandidate || true);
              const effectiveIsSFF = isSFF;

              const wasSFF = q1Status === 'SFF' || q1Status === 'SPECIAL FOCUS FACILITY' || (typeof q1Status === 'string' && q1Status.includes('SFF') && !q1Status.includes('CANDIDATE'));
              const wasCandidate = q1Status === 'SFF CANDIDATE' || q1Status === 'CANDIDATE' || 
                                  (typeof q1Status === 'string' && q1Status.includes('CANDIDATE') && !q1Status.includes('SFF'));
              const isNewSFF = effectiveIsSFF && !wasSFF && !wasCandidate;
              const isNewCandidate = effectiveIsCandidate && !wasCandidate && !wasSFF;
              
              let previousStatus: string | undefined;
              if (wasSFF) {
                previousStatus = 'Was SFF';
              } else if (wasCandidate) {
                previousStatus = 'Was Candidate';
              } else if (q1Status === '') {
                previousStatus = undefined;
              } else {
                previousStatus = q1Status;
              }

              const caseMixExpected = provider?.case_mix_total_nurse_hrs_per_resident_per_day;
              // Correct HPRD field mapping:
              // Total_Nurse_HPRD = total nurse HPRD (all nurses)
              // Nurse_Care_HPRD = direct care nurse HPRD (nurses providing direct care)
              // Total_RN_HPRD = total RN HPRD (all RNs)
              // Direct_Care_RN_HPRD = direct care RN HPRD (RNs providing direct care)
              
              // CRITICAL: Ensure we're reading the correct fields - check for data misalignment
              let totalHPRD = 0;
              let directCareHPRD = 0;
              let rnHPRD = 0;
              let census: number | undefined = undefined;
              
              if (facility) {
                // Read values directly from facility object
                // NOTE: Facility data has already been auto-corrected for column shifts before being added to map
                totalHPRD = typeof facility.Total_Nurse_HPRD === 'number' ? facility.Total_Nurse_HPRD : (parseFloat(String(facility.Total_Nurse_HPRD)) || 0);
                directCareHPRD = typeof facility.Nurse_Care_HPRD === 'number' ? facility.Nurse_Care_HPRD : (parseFloat(String(facility.Nurse_Care_HPRD)) || 0);
                rnHPRD = typeof facility.Total_RN_HPRD === 'number' ? facility.Total_RN_HPRD : (parseFloat(String(facility.Total_RN_HPRD)) || 0);
                census = typeof facility.Census === 'number' ? facility.Census : (parseFloat(String(facility.Census)) || undefined);
                
                // Final safety check: If validation somehow failed, log and zero out values
                if (totalHPRD === 0 && (directCareHPRD > 0 || rnHPRD > 0)) {
                  console.error(`[CRITICAL: Data Misalignment] CCN=${ccn}, Name=${pdfFacility.facility_name}, Facility PROVNUM=${facility.PROVNUM}`);
                  console.error(`  This facility passed initial validation but shows column shift - zeroing out values`);
                  console.error(`  Values: TotalHPRD=${totalHPRD}, DirectCare=${directCareHPRD}, RN=${rnHPRD}, Census=${census}`);
                  // Zero out the misaligned values to prevent displaying wrong data
                  totalHPRD = 0;
                  directCareHPRD = 0;
                  rnHPRD = 0;
                  census = undefined;
                }
              }
              
              const percentOfCaseMix = caseMixExpected && caseMixExpected > 0 && totalHPRD > 0
                ? (totalHPRD / caseMixExpected) * 100 
                : undefined;

              // ALWAYS prioritize provider data for names/locations (it's more reliable than PDF extraction)
              // Only use PDF name if provider name is missing AND PDF name doesn't look like a table header
              const pdfName = pdfFacility.facility_name?.trim();
              const isTableHeader = pdfName && (
                pdfName.toLowerCase().includes('table') ||
                pdfName.toLowerCase().includes('sff candidate list') ||
                pdfName.toLowerCase().includes('current sff facilities') ||
                pdfName.toLowerCase().includes('graduated') ||
                pdfName.toLowerCase().includes('no longer participating')
              );
              
              const facilityName = provider?.PROVNAME && provider.PROVNAME.trim()
                ? toTitleCase(provider.PROVNAME.trim())
                : (pdfName && !isTableHeader
                    ? toTitleCase(pdfName)
                    : 'Unknown Facility');

              // ALWAYS use provider state/city if available
              const facilityState = provider?.STATE && provider.STATE.trim() 
                ? provider.STATE.trim().toUpperCase()
                : (pdfFacility.state && pdfFacility.state.trim() ? pdfFacility.state.trim().toUpperCase() : 'UN');
              
              const facilityCity = provider?.CITY && provider.CITY.trim()
                ? capitalizeCity(provider.CITY.trim())
                : (pdfFacility.city && pdfFacility.city.trim() ? capitalizeCity(pdfFacility.city.trim()) : undefined);

              const sffFacility: SFFFacility = {
                provnum: (provider?.PROVNUM || ccn || pdfFacility.provider_number?.toString().trim() || '').replace(/[^0-9]/g, ''),
                name: facilityName,
                state: facilityState,
                city: facilityCity,
                county: provider?.COUNTY_NAME ? capitalizeCity(provider.COUNTY_NAME) : undefined,
                sffStatus: pdfFacility.status,
                totalHPRD,
                directCareHPRD,
                rnHPRD,
                caseMixExpectedHPRD: caseMixExpected,
                percentOfCaseMix,
                census: facility?.Census,
                monthsAsSFF: pdfFacility.months_as_sff !== null && pdfFacility.months_as_sff !== undefined ? pdfFacility.months_as_sff : undefined,
                mostRecentInspection: pdfFacility.most_recent_inspection ?? undefined,
                metSurveyCriteria: pdfFacility.met_survey_criteria ?? undefined,
                isNewSFF,
                isNewCandidate,
                wasCandidate,
                wasSFF,
                previousStatus
              };

              allFacilitiesList.push(sffFacility);
              if (provider?.PROVNUM) processedCCNs.add(provider.PROVNUM);
              processedCCNs.add(ccn);
              processedCCNs.add(normalizedCCN);
            } else {
              // Provider not found in Q2 - still create facility entry using CSV data
              // This is important for facilities that may have closed or stopped reporting
              console.warn(`[No Provider Match] CCN=${ccn}, Name=${pdfFacility.facility_name}, Status=${pdfFacility.status} - Creating entry from CSV data only`);
              
              // Try Q1 provider data as fallback - STRICT matching only
              const normalized = normalizeCCN(ccn);
              let provider = normalized ? providerInfoQ1.find(p => {
                const provNum = p.PROVNUM?.toString().trim() || '';
                if (!provNum) return false;
                return normalizeCCN(provNum) === normalized;
              }) : undefined;
              
              // CRITICAL FIX: Try to find facility data from Q2 FIRST (even if no provider found)
              // Facility data exists in facility_lite_metrics.csv even if provider info doesn't exist
              let facility = findFacilityByCCN(ccn);
              
              // If not found in Q2, try Q1 facility data (if provider found in Q1) - STRICT matching
              if (!facility && provider) {
                const provNum = provider.PROVNUM?.toString().trim() || '';
                if (provNum) {
                  const normalizedProvNum = normalizeCCN(provNum);
                  facility = normalizedProvNum ? data.facilityData.q1?.find((f: FacilityLiteRow) => {
                    const fProvNum = f.PROVNUM?.toString().trim() || '';
                    if (!fProvNum) return false;
                    return normalizeCCN(fProvNum) === normalizedProvNum;
                  }) : undefined;
                }
              }
              
              // Clean up PDF name - remove table headers
              let pdfName = pdfFacility.facility_name?.trim();
              const isTableHeader = pdfName && (
                pdfName.toLowerCase().includes('table') ||
                pdfName.toLowerCase().includes('sff candidate list') ||
                pdfName.toLowerCase().includes('current sff facilities') ||
                pdfName.toLowerCase().includes('graduated') ||
                pdfName.toLowerCase().includes('no longer participating')
              );
              
              // Use provider name if found, otherwise use CSV facility name
              const facilityName = provider?.PROVNAME && provider.PROVNAME.trim()
                ? toTitleCase(provider.PROVNAME.trim())
                : (pdfName && !isTableHeader 
                    ? toTitleCase(pdfName) 
                    : (pdfFacility.facility_name && pdfFacility.facility_name.trim()
                        ? toTitleCase(pdfFacility.facility_name.trim())
                        : `Facility ${ccn}`)); // Use CCN as fallback instead of "Unknown Facility"
              
              const facilityState = provider?.STATE && provider.STATE.trim()
                ? provider.STATE.trim().toUpperCase()
                : (pdfFacility.state && pdfFacility.state.trim() ? pdfFacility.state.trim().toUpperCase() : 'UN');
              
              const facilityCity = provider?.CITY && provider.CITY.trim()
                ? capitalizeCity(provider.CITY.trim())
                : (pdfFacility.city && pdfFacility.city.trim() ? capitalizeCity(pdfFacility.city.trim()) : undefined);
              
              // Use facility data if found, otherwise use 0 values
              // CRITICAL: Read values explicitly to ensure correct mapping (no misalignment)
              let totalHPRD = 0;
              let directCareHPRD = 0;
              let rnHPRD = 0;
              let census: number | undefined = undefined;
              
              if (facility) {
                // Explicitly read each field to prevent any misalignment
                totalHPRD = facility.Total_Nurse_HPRD ?? 0;
                directCareHPRD = facility.Nurse_Care_HPRD ?? 0;
                rnHPRD = facility.Total_RN_HPRD ?? 0;
                census = facility.Census;
                
                // Debug: Log first few facilities to catch misalignment
                if (allFacilitiesList.length < 10) {
                  console.log(`[Else Block] CCN=${ccn}, Name=${pdfFacility.facility_name}`);
                  console.log(`  Raw: Total_Nurse_HPRD=${facility.Total_Nurse_HPRD}, Nurse_Care_HPRD=${facility.Nurse_Care_HPRD}, Total_RN_HPRD=${facility.Total_RN_HPRD}, Census=${facility.Census}`);
                  console.log(`  Assigned: totalHPRD=${totalHPRD}, directCareHPRD=${directCareHPRD}, rnHPRD=${rnHPRD}, census=${census}`);
                }
              }
              
              // Log unmatched facilities for debugging (always for these specific facilities)
              if (!provider && (ccn === '265379' || ccn === '675595' || ccn === '195454')) {
                console.warn(`Facility not found in Q1 or Q2 provider data: CCN=${ccn}, Name=${pdfName}, Status=${pdfFacility.status}, Months=${pdfFacility.months_as_sff}`);
                
                // For specific facilities, do a deep search - STRICT matching
                if (ccn === '265379' || ccn === '675595' || ccn === '195454') {
                  const normalized = normalizeCCN(ccn);
                  console.log(`  Deep search for CCN=${ccn} (normalized=${normalized}):`);
                  
                  // Check providerInfoQ2
                  const q2Match = findProviderByCCN(ccn);
                  console.log(`  - Q2 provider match: ${q2Match ? `YES - ${q2Match.PROVNAME} (${q2Match.PROVNUM})` : 'NO'}`);
                  
                  // Check facilityQ2
                  const q2FacMatch = findFacilityByCCN(ccn);
                  console.log(`  - Q2 facility match: ${q2FacMatch ? `YES - Census=${q2FacMatch.Census}, HPRD=${q2FacMatch.Total_Nurse_HPRD}` : 'NO'}`);
                  
                  // Check providerInfoQ1 - STRICT matching
                  const q1Match = normalized ? providerInfoQ1.find(p => {
                    const provNum = p.PROVNUM?.toString().trim() || '';
                    if (!provNum) return false;
                    return normalizeCCN(provNum) === normalized;
                  }) : undefined;
                  console.log(`  - Q1 provider match: ${q1Match ? `YES - ${q1Match.PROVNAME} (${q1Match.PROVNUM})` : 'NO'}`);
                  
                  // Show sample provider numbers for comparison
                  console.log(`  - Sample Q2 provider numbers:`, providerInfoQ2.slice(0, 10).map(p => p.PROVNUM));
                  console.log(`  - Sample Q2 facility numbers:`, facilityQ2.slice(0, 10).map((f: FacilityLiteRow) => f.PROVNUM));
                }
              }
              
              const sffFacility: SFFFacility = {
                provnum: (ccn || pdfFacility.provider_number?.toString().trim() || provider?.PROVNUM?.toString().trim() || '').replace(/[^0-9]/g, ''), // Ensure only digits
                name: facilityName,
                state: facilityState,
                city: facilityCity,
                county: provider?.COUNTY_NAME ? capitalizeCity(provider.COUNTY_NAME) : undefined,
                sffStatus: pdfFacility.status,
                totalHPRD,
                directCareHPRD,
                rnHPRD,
                caseMixExpectedHPRD: provider?.case_mix_total_nurse_hrs_per_resident_per_day,
                percentOfCaseMix: provider?.case_mix_total_nurse_hrs_per_resident_per_day && provider.case_mix_total_nurse_hrs_per_resident_per_day > 0 && totalHPRD > 0
                  ? (totalHPRD / provider.case_mix_total_nurse_hrs_per_resident_per_day) * 100
                  : undefined,
                census,
                monthsAsSFF: pdfFacility.months_as_sff !== null && pdfFacility.months_as_sff !== undefined ? pdfFacility.months_as_sff : undefined,
                mostRecentInspection: pdfFacility.most_recent_inspection ?? undefined,
                metSurveyCriteria: pdfFacility.met_survey_criteria ?? undefined,
                isNewSFF: false,
                isNewCandidate: false,
                wasCandidate: false,
                wasSFF: false
              };
              allFacilitiesList.push(sffFacility);
              processedCCNs.add(ccn);
              processedCCNs.add(normalizedCCN);
            }
          }
        }

        // Filter by state or region if scope is provided
        let filteredFacilities = allFacilitiesList;
        
        if (scope && scope !== 'usa') {
          if (scope.length === 2) {
            const stateCode = scope.toUpperCase();
            filteredFacilities = allFacilitiesList.filter(f => f.state === stateCode);
          } else if (scope.startsWith('region')) {
            const regionNum = parseInt(scope.replace(/^region-?/, ''));
            if (!isNaN(regionNum) && data.regionStateMapping) {
              const regionStates = data.regionStateMapping.get(regionNum) || new Set<string>();
              filteredFacilities = allFacilitiesList.filter(f => regionStates.has(f.state));
            }
          }
        }

        console.log(`[Final Count] Processed: ${allFacilitiesList.length}, Skipped (no CCN): ${skippedNoCCN}, Skipped (duplicates): ${skippedDuplicates}, Total from JSON: ${totalFromJSON}`);
        setAllFacilities(filteredFacilities);
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

  // Filter by category
  const filteredFacilities = useMemo(() => {
    if (!allFacilities.length) return [];
    
    switch (categoryFilter) {
      case 'sffs-and-candidates':
        return allFacilities.filter(f => f.sffStatus === 'SFF' || f.sffStatus === 'Candidate');
      case 'sffs-only':
        return allFacilities.filter(f => f.sffStatus === 'SFF');
      case 'graduates':
        return allFacilities.filter(f => f.sffStatus === 'Graduate');
      case 'terminated':
        return allFacilities.filter(f => f.sffStatus === 'Terminated');
      default:
        return allFacilities;
    }
  }, [allFacilities, categoryFilter]);

  // Sort facilities
  const sortedFacilities = useMemo(() => {
    if (!filteredFacilities.length) return [];
    const sorted = [...filteredFacilities].sort((a, b) => {
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
        case 'monthsAsSFF':
          aVal = a.monthsAsSFF ?? 0;
          bVal = b.monthsAsSFF ?? 0;
          break;
        case 'sffStatus':
          aVal = a.sffStatus;
          bVal = b.sffStatus;
          break;
      }
      
      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortDirection === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }
      return sortDirection === 'asc' ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number);
    });
    return sorted;
  }, [filteredFacilities, sortField, sortDirection]);

  const paginatedFacilities = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return sortedFacilities.slice(start, start + itemsPerPage);
  }, [sortedFacilities, currentPage]);

  const totalPages = Math.ceil(sortedFacilities.length / itemsPerPage);

  const formatCensus = (num: number | undefined): string => {
    if (num === undefined || isNaN(num) || num === 0) return 'N/A';
    return num.toLocaleString('en-US', {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    });
  };
  
  const formatHPRD = (num: number | undefined): string => {
    if (num === undefined || isNaN(num) || num === 0) return 'N/A';
    return num.toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  };

  const formatPercent = (num: number | undefined, decimals: number = 1): string => {
    if (num === undefined || isNaN(num)) return 'N/A';
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }) + '%';
  };


  // Get all states for dropdown - always return full list so dropdown shows all states
  const allStates = useMemo(() => {
    const allStatesList = [
      'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
      'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
      'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
      'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
      'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'
    ];
    // Always return full list - show all states in dropdown regardless of whether they have SFFs
    return allStatesList;
  }, []);



  const pageTitle = scope === 'usa' 
    ? 'Special Focus Facilities Program'
    : scope && scope.startsWith('region')
    ? (() => {
        const regionNum = parseInt(scope.replace(/^region-?/, ''));
        return `Special Focus Facilities Program — CMS Region ${regionNum} (${getRegionName(regionNum)})`;
      })()
    : scope 
    ? `Special Focus Facilities Program — ${getStateName(scope.toUpperCase())}`
    : 'Special Focus Facilities Program';

  // Mobile title (abbreviated)
  const mobileTitle = scope === 'usa'
    ? 'Special Focus Facilities Program'
    : scope && scope.startsWith('region')
    ? (() => {
        const regionNum = parseInt(scope.replace(/^region-?/, ''));
        return `SFF Program: Region ${regionNum}`;
      })()
    : scope
    ? `SFF Program: ${getStateName(scope.toUpperCase())}`
    : 'Special Focus Facilities Program';

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

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-blue-900 to-gray-900 text-white flex items-center justify-center">
        <div className="text-center">
          <div className="text-xl mb-2 text-red-400">Error</div>
          <div className="text-sm text-gray-400">{error}</div>
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
            {/* Desktop Navigation */}
            <div className="hidden md:flex items-center gap-4 lg:gap-6">
              <a 
                href="https://pbj320.com/about" 
                className="text-gray-300 hover:text-blue-300 text-sm md:text-base font-medium transition-colors"
              >
                About
              </a>
              <a 
                href="https://pbjdashboard.com/" 
                className="text-gray-300 hover:text-blue-300 text-sm md:text-base font-medium transition-colors"
              >
                Dashboard
              </a>
              <a 
                href="https://pbj320.com/insights" 
                className="text-gray-300 hover:text-blue-300 text-sm md:text-base font-medium transition-colors"
              >
                Insights
              </a>
              <a 
                href="https://pbj320.com/report" 
                className="text-gray-300 hover:text-blue-300 text-sm md:text-base font-medium transition-colors"
              >
                Report
              </a>
              <a 
                href="https://www.320insight.com/phoebe" 
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-300 hover:text-blue-300 text-sm md:text-base font-medium transition-colors"
              >
                Phoebe J
              </a>
              <a 
                href="https://pbj320.vercel.app/" 
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-300 hover:text-blue-300 text-sm md:text-base font-medium transition-colors"
              >
                PBJ Converter
              </a>
            </div>
            {/* Mobile Menu Button */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-2 text-gray-300 hover:text-white transition-colors"
              aria-label="Toggle menu"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {mobileMenuOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
          </div>
          {/* Mobile Menu */}
          {mobileMenuOpen && (
            <div className="md:hidden border-t border-gray-700 py-4">
              <div className="flex flex-col space-y-3">
                <a 
                  href="https://pbj320.com/about" 
                  className="text-gray-300 hover:text-blue-300 text-sm font-medium transition-colors px-4"
                >
                  About
                </a>
                <a 
                  href="https://pbjdashboard.com/" 
                  className="text-gray-300 hover:text-blue-300 text-sm font-medium transition-colors px-4"
                >
                  Dashboard
                </a>
                <a 
                  href="https://pbj320.com/insights" 
                  className="text-gray-300 hover:text-blue-300 text-sm font-medium transition-colors px-4"
                >
                  Insights
                </a>
                <a 
                  href="https://pbj320.com/report" 
                  className="text-gray-300 hover:text-blue-300 text-sm font-medium transition-colors px-4"
                >
                  Report
                </a>
                <a 
                  href="https://www.320insight.com/phoebe" 
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-gray-300 hover:text-blue-300 text-sm font-medium transition-colors px-4"
                >
                  Phoebe J
                </a>
                <a 
                  href="https://pbj320.vercel.app/" 
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-gray-300 hover:text-blue-300 text-sm font-medium transition-colors px-4"
                >
                  PBJ Converter
                </a>
              </div>
            </div>
          )}
        </div>
      </nav>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 md:py-8">
        <div className="mb-6 md:mb-8 relative">
          {/* State outline background - only for state pages */}
          {scope && scope !== 'usa' && !scope.startsWith('region') && (
            <div 
              className="absolute top-0 right-0 w-64 h-64 md:w-80 md:h-80 pointer-events-none z-0 opacity-10"
              style={{ 
                transform: 'translate(20%, -20%)',
              }}
            >
              <StateOutline stateCode={scope.toUpperCase()} className="w-full h-full" />
            </div>
          )}
          <div className="relative z-10">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-3">
              <h1 className="text-2xl md:text-3xl lg:text-4xl font-bold">
                <span className="md:hidden">{mobileTitle}</span>
                <span className="hidden md:inline">{pageTitle}</span>
              </h1>
            {(scope && scope !== 'usa') && (
              <button
                onClick={() => navigate('/sff/usa')}
                className="inline-flex items-center gap-2 px-3 md:px-4 py-2 bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/50 rounded-lg text-blue-300 hover:text-blue-200 transition-colors text-xs md:text-sm font-medium whitespace-nowrap self-start sm:self-auto"
              >
                <svg className="w-4 h-4 hidden md:block" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
                <span className="md:hidden">All SFFs</span>
                <span className="hidden md:inline">View All USA SFFs</span>
              </button>
            )}
          </div>
            <p className="text-gray-300 text-xs md:text-sm mb-2 whitespace-nowrap">
              Source: CMS SFF Posting (Dec. 2025); CMS PBJ (Q2 2025)
            </p>
          </div>
        </div>

        {/* State Dropdown and Filters - Desktop: dropdown on right, Mobile: dropdown and button on same row */}
        {(() => {
          const isUSA = scope === 'usa';
          const isState = scope && scope.length === 2 && !scope.startsWith('region');
          const shouldShow = isUSA || isState;
          
          return shouldShow ? (
            <div className="mb-4 md:mb-6">
              {/* Mobile: Dropdown and "All SFFs" button on same row */}
              <div className="md:hidden flex items-end gap-2 mb-4">
                <div className="flex-1">
                  <label htmlFor="state-select" className="block text-sm font-semibold text-blue-300 mb-2">Select State</label>
                  <select
                    id="state-select"
                    value={isState ? scope.toUpperCase() : ''}
                    onChange={(e) => {
                      const selectedState = e.target.value;
                      if (selectedState) {
                        navigate(`/sff/${selectedState.toLowerCase()}`);
                      }
                    }}
                    className="w-full px-3 py-2 bg-[#0f172a]/60 border border-blue-500/50 rounded text-blue-300 hover:bg-blue-600/20 focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer text-xs"
                  >
                    <option value="">Select a state...</option>
                    {allStates.map(stateCode => (
                      <option key={stateCode} value={stateCode} className="bg-[#0f172a]">
                        {getStateName(stateCode)}
                      </option>
                    ))}
                  </select>
                </div>
                {(scope && scope !== 'usa') && (
                  <button
                    onClick={() => navigate('/sff/usa')}
                    className="px-3 py-2 bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/50 rounded-lg text-blue-300 hover:text-blue-200 transition-colors text-xs font-medium whitespace-nowrap"
                  >
                    All SFFs
                  </button>
                )}
              </div>

              {/* Desktop: Dropdown aligned right with filters */}
              <div className="hidden md:flex md:items-end md:justify-between md:gap-4">
                <div className="flex-1"></div>
                <div className="max-w-xs">
                  <label htmlFor="state-select-desktop" className="block text-sm font-semibold text-blue-300 mb-2">Select State</label>
                  <select
                    id="state-select-desktop"
                    value={isState ? scope.toUpperCase() : ''}
                    onChange={(e) => {
                      const selectedState = e.target.value;
                      if (selectedState) {
                        navigate(`/sff/${selectedState.toLowerCase()}`);
                      }
                    }}
                    className="w-full px-4 py-2 bg-[#0f172a]/60 border border-blue-500/50 rounded text-blue-300 hover:bg-blue-600/20 focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer"
                  >
                    <option value="">Select a state...</option>
                    {allStates.map(stateCode => (
                      <option key={stateCode} value={stateCode} className="bg-[#0f172a]">
                        {getStateName(stateCode)}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          ) : null;
        })()}

        {/* Category Filter Toggles */}
        <div className="mb-4 md:mb-6">
          <div className="flex flex-wrap gap-2 md:gap-3">
            <button
              onClick={() => { setCategoryFilter('all'); setCurrentPage(1); }}
              className={`px-3 md:px-4 py-1.5 md:py-2 rounded text-xs md:text-sm font-medium transition-colors ${
                categoryFilter === 'all'
                  ? 'bg-blue-600 text-white'
                  : 'bg-[#0f172a]/60 text-gray-300 hover:bg-blue-600/20 border border-blue-500/50'
              }`}
            >
              All ({allFacilities.length})
            </button>
            <button
              onClick={() => { setCategoryFilter('sffs-and-candidates'); setCurrentPage(1); }}
              className={`px-3 md:px-4 py-1.5 md:py-2 rounded text-xs md:text-sm font-medium transition-colors ${
                categoryFilter === 'sffs-and-candidates'
                  ? 'bg-blue-600 text-white'
                  : 'bg-[#0f172a]/60 text-gray-300 hover:bg-blue-600/20 border border-blue-500/50'
              }`}
            >
              SFFs & Candidates ({allFacilities.filter(f => f.sffStatus === 'SFF' || f.sffStatus === 'Candidate').length})
            </button>
            <button
              onClick={() => { setCategoryFilter('sffs-only'); setCurrentPage(1); }}
              className={`px-3 md:px-4 py-1.5 md:py-2 rounded text-xs md:text-sm font-medium transition-colors ${
                categoryFilter === 'sffs-only'
                  ? 'bg-blue-600 text-white'
                  : 'bg-[#0f172a]/60 text-gray-300 hover:bg-blue-600/20 border border-blue-500/50'
              }`}
            >
              SFFs Only ({allFacilities.filter(f => f.sffStatus === 'SFF').length})
            </button>
            <button
              onClick={() => { setCategoryFilter('graduates'); setCurrentPage(1); }}
              className={`px-3 md:px-4 py-1.5 md:py-2 rounded text-xs md:text-sm font-medium transition-colors ${
                categoryFilter === 'graduates'
                  ? 'bg-blue-600 text-white'
                  : 'bg-[#0f172a]/60 text-gray-300 hover:bg-blue-600/20 border border-blue-500/50'
              }`}
            >
              Graduates ({allFacilities.filter(f => f.sffStatus === 'Graduate').length})
            </button>
            <button
              onClick={() => { setCategoryFilter('terminated'); setCurrentPage(1); }}
              className={`px-3 md:px-4 py-1.5 md:py-2 rounded text-xs md:text-sm font-medium transition-colors ${
                categoryFilter === 'terminated'
                  ? 'bg-blue-600 text-white'
                  : 'bg-[#0f172a]/60 text-gray-300 hover:bg-blue-600/20 border border-blue-500/50'
              }`}
            >
              Terminated ({allFacilities.filter(f => f.sffStatus === 'Terminated').length})
            </button>
          </div>
        </div>

        {/* Merged Table */}
        <div className="mb-4 md:mb-10">
          {sortedFacilities.length === 0 ? (
            <div className="rounded-lg border border-gray-700 bg-[#0f172a]/60 p-8 text-center">
              <p className="text-gray-400">No facilities found for this filter.</p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto rounded-lg border border-gray-700 bg-[#0f172a]/60 shadow-lg -mx-2 md:mx-0">
                <table className="w-full border-collapse min-w-[500px] md:min-w-[700px]">
                  <thead>
                    <tr className="bg-blue-600/20 border-b border-blue-500/30">
                      <th className="px-1 md:px-2 py-2 text-left text-xs font-semibold text-blue-300 max-w-[120px] md:max-w-none">Provider</th>
                      <th className="px-1 md:px-2 py-2 text-left text-xs font-semibold text-blue-300 max-w-[80px] md:max-w-none">
                        {scope && scope !== 'usa' && !scope.startsWith('region') ? 'City' : 'Location'}
                      </th>
                      <SortableHeader field="sffStatus" className="px-1 md:px-2 py-2 text-center text-xs font-semibold text-blue-300 whitespace-nowrap">Status</SortableHeader>
                      <SortableHeader field="census" className="px-1 md:px-2 py-2 text-center text-xs font-semibold text-blue-300 whitespace-nowrap">Census</SortableHeader>
                      <SortableHeader field="monthsAsSFF" className="px-1 md:px-2 py-2 text-center text-xs font-semibold text-blue-300">
                        <div className="block leading-tight">
                          <span className="block">Months</span>
                          <span className="block">as SFF</span>
                        </div>
                      </SortableHeader>
                      <SortableHeader field="totalHPRD" className="px-1 md:px-2 py-2 text-center text-xs font-semibold text-blue-300">
                        <div className="block leading-tight">
                          <span className="block">Total</span>
                          <span className="block">HPRD</span>
                        </div>
                      </SortableHeader>
                      <SortableHeader field="directCareHPRD" className="px-1 md:px-2 py-2 text-center text-xs font-semibold text-blue-300 hidden sm:table-cell">
                        <div className="block leading-tight">
                          <span className="block">Direct</span>
                          <span className="block">HPRD</span>
                        </div>
                      </SortableHeader>
                      <SortableHeader field="rnHPRD" className="px-1 md:px-2 py-2 text-center text-xs font-semibold text-blue-300 hidden md:table-cell">
                        <div className="block leading-tight">
                          <span className="block">RN</span>
                          <span className="block">HPRD</span>
                        </div>
                      </SortableHeader>
                      <SortableHeader field="percentOfCaseMix" className="px-1 md:px-2 py-2 text-center text-xs font-semibold text-blue-300">
                        <div className="block leading-tight">
                          <span className="block">% Case</span>
                          <span className="block">Mix</span>
                        </div>
                      </SortableHeader>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedFacilities.map((facility) => {
                      const statusColors: Record<SFFStatus, string> = {
                        'SFF': 'bg-red-500/20 text-red-300',
                        'Candidate': 'bg-yellow-500/20 text-yellow-300',
                        'Graduate': 'bg-green-500/20 text-green-300',
                        'Terminated': 'bg-gray-500/20 text-gray-300'
                      };
                      return (
                        <tr key={facility.provnum} className="border-b border-gray-700/50 hover:bg-gray-800/30 transition-colors">
                          <td className="px-1 md:px-2 py-2 max-w-[120px] md:max-w-none">
                            <a
                              href={`https://pbjdashboard.com/?facility=${encodeURIComponent(facility.provnum || '')}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-300 hover:text-blue-200 underline font-medium text-xs leading-tight block"
                              style={{ 
                                display: '-webkit-box',
                                WebkitLineClamp: 2,
                                WebkitBoxOrient: 'vertical',
                                overflow: 'hidden',
                                wordBreak: 'break-word'
                              }}
                            >
                              {facility.name}
                            </a>
                          </td>
                          <td className="px-1 md:px-2 py-2 text-gray-300 text-xs max-w-[80px] md:max-w-none">
                            <span className="block leading-tight" style={{ 
                              display: '-webkit-box',
                              WebkitLineClamp: 2,
                              WebkitBoxOrient: 'vertical',
                              overflow: 'hidden',
                              wordBreak: 'break-word'
                            }}>
                              {scope && scope !== 'usa' && !scope.startsWith('region') 
                                ? (facility.city || facility.county || '—')
                                : (facility.city ? `${facility.city}, ${facility.state}` : facility.state)
                              }
                            </span>
                          </td>
                          <td className="px-1 md:px-2 py-2 text-center">
                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusColors[facility.sffStatus]}`}>
                              <span className="md:hidden">
                                {facility.sffStatus === 'Candidate' ? 'Cand.' : 
                                 facility.sffStatus === 'Graduate' ? 'Grad.' :
                                 facility.sffStatus === 'Terminated' ? 'Term.' :
                                 facility.sffStatus}
                              </span>
                              <span className="hidden md:inline">{facility.sffStatus}</span>
                            </span>
                          </td>
                          <td className="px-1 md:px-2 py-2 text-center text-gray-300 text-xs">{formatCensus(facility.census)}</td>
                          <td className="px-1 md:px-2 py-2 text-center text-gray-300 text-xs">
                            {facility.monthsAsSFF !== undefined ? facility.monthsAsSFF : '—'}
                          </td>
                          <td className="px-1 md:px-2 py-2 text-center text-white font-semibold text-xs">{formatHPRD(facility.totalHPRD)}</td>
                          <td className="px-1 md:px-2 py-2 text-center text-gray-300 text-xs hidden sm:table-cell">{formatHPRD(facility.directCareHPRD)}</td>
                          <td className="px-1 md:px-2 py-2 text-center text-gray-300 text-xs hidden md:table-cell">{formatHPRD(facility.rnHPRD)}</td>
                          <td className="px-1 md:px-2 py-2 text-center text-gray-300 text-xs">
                            {facility.percentOfCaseMix === undefined || isNaN(facility.percentOfCaseMix) || facility.percentOfCaseMix === 0 ? 'N/A' : formatPercent(facility.percentOfCaseMix)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              {totalPages > 1 && (
                <div className="mt-3 flex flex-col sm:flex-row items-center justify-between gap-2">
                  <div className="text-xs text-gray-400">
                    {(currentPage - 1) * itemsPerPage + 1}-{Math.min(currentPage * itemsPerPage, sortedFacilities.length)} of {sortedFacilities.length}
                  </div>
                  <div className="flex gap-1.5">
                    <button
                      onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                      disabled={currentPage === 1}
                      className="px-3 py-1 bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/50 rounded text-blue-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-xs"
                    >
                      Prev
                    </button>
                    <span className="px-3 py-1 text-gray-300 text-xs">
                      {currentPage}/{totalPages}
                    </span>
                    <button
                      onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                      disabled={currentPage === totalPages}
                      className="px-3 py-1 bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/50 rounded text-blue-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-xs"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        <div className="mt-8 md:mt-10 pt-6 border-t border-gray-700">
          <div className="text-left text-xs text-gray-200 mb-4">
            <p className="mb-1">
              Source: <a href="https://www.cms.gov/files/document/sff-posting-candidate-list-november-2025.pdf" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300 underline">CMS SFF Posting</a> (Dec. 2025); CMS PBJ (Q2 2025)
            </p>
            {candidateJSON && (
              <p className="text-gray-200">
                Complete list: {candidateJSON.summary.current_sff_count} SFFs, {candidateJSON.summary.candidates_count} Candidates, {candidateJSON.summary.graduated_count} Graduates, {candidateJSON.summary.no_longer_participating_count} Terminated ({candidateJSON.summary.total_count} total)
              </p>
            )}
          </div>

          {/* Methodology Section */}
          <div className="mt-6">
            <button
              onClick={() => setShowMethodology(!showMethodology)}
              className="w-full text-left px-4 py-2 bg-[#0f172a]/60 hover:bg-[#0f172a]/80 border border-gray-700 rounded text-gray-300 text-xs font-medium transition-colors flex items-center justify-between"
            >
              <span>Methodology & Definitions</span>
              <span className="text-gray-500">{showMethodology ? '−' : '+'}</span>
            </button>
            {showMethodology && (
              <div className="mt-2 p-4 bg-[#0f172a]/60 border border-gray-700 rounded text-xs text-gray-300 space-y-3">
                <div>
                  <strong className="text-blue-300">Current SFF Facilities:</strong> Nursing homes currently in the SFF program. The date of the most recent inspection is posted. Results are noted as "Met" or "Not Met". "Met" means the facility met graduation criteria on their most recent survey and is on track for graduation. SFF facilities must meet graduation criteria on 2 consecutive surveys to be eligible for graduation. "Not Met" means the facility did not meet graduation criteria and must restart the process.
                </div>
                <div>
                  <strong className="text-green-300">Facilities That Have Graduated:</strong> These nursing homes sustained improvement for about 12 months (through two standard health surveys) while in the SFF program. CMS lists their names as "graduates" for three years after they graduate so that anyone tracking their progress will be informed. "Graduation" does not mean there may not be problems in quality of care but does generally indicate an upward trend in quality improvement compared to the nursing home's prior history.
                </div>
                <div>
                  <strong className="text-gray-300">No Longer in Medicare and Medicaid:</strong> These are nursing homes that were either terminated by CMS from participation in Medicare and Medicaid within the past few months or voluntarily chose not to continue such participation. In most cases, the nursing homes will have closed, although some nursing homes that leave Medicare later seek to show better quality and re-enter the Medicare program after demonstrating their ability to comply with all Federal health and safety requirements.
                </div>
                <div>
                  <strong className="text-yellow-300">SFF Candidate List:</strong> These are nursing homes that qualify to be selected as an SFF. The number of nursing homes on the candidate list is based on five candidates for each SFF slot, with a minimum candidate pool of five nursing homes and a maximum of 30 per State.
                </div>
                <div className="pt-2 border-t border-gray-700">
                  <strong className="text-blue-300">Data Availability:</strong> Some facilities may not have Q2 2025 PBJ data available, which is why certain metrics (Census, HPRD, % Case-Mix) may show as "N/A" for those facilities.
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="mt-6 md:mt-8 pt-6 md:pt-8 text-center" style={{ background: '#0f172a', padding: '40px 20px', marginTop: '60px' }}>
        <p style={{ color: 'rgba(255,255,255,0.7)', margin: '0 auto', fontStyle: 'italic', lineHeight: '1.6', textAlign: 'center', maxWidth: '800px' }}>
          The <strong>PBJ Dashboard</strong> is a free public resource providing longitudinal staffing data at 15,000 US nursing homes. It has been featured in <a href="https://www.publichealth.columbia.edu/news/alumni-make-data-shine-public-health-dashboards" target="_blank" rel="noopener noreferrer" style={{ color: '#60a5fa', textDecoration: 'none' }}>Columbia Public Health</a>, <a href="https://www.retirementlivingsourcebook.com/videos/why-nursing-home-staffing-data-matters-for-1-2-million-residents-and-beyond" target="_blank" rel="noopener noreferrer" style={{ color: '#60a5fa', textDecoration: 'none' }}>Positive Aging</a>, and <a href="https://aginginamerica.news/2025/09/16/crunching-the-nursing-home-data/" target="_blank" rel="noopener noreferrer" style={{ color: '#60a5fa', textDecoration: 'none' }}>Aging in America News</a>.
        </p>
        <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', margin: '1.5rem auto 0', paddingTop: '1.5rem', maxWidth: '800px' }}>
          <p style={{ margin: 0, color: 'rgba(255,255,255,0.6)', fontStyle: 'italic', fontSize: '0.9rem', textAlign: 'center' }}>
            <a href="https://www.320insight.com" style={{ color: 'rgba(255,255,255,0.6)', textDecoration: 'none' }}>320 Consulting — Turning Spreadsheets into Stories</a>
          </p>
        </div>
      </footer>
    </div>
  );
}
