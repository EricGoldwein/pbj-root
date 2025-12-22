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
  const { scope } = useParams<{ scope?: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [allFacilities, setAllFacilities] = useState<SFFFacility[]>([]);
  const [candidateJSON, setCandidateJSON] = useState<SFFCandidateJSON | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>('all');
  const [sortField, setSortField] = useState<SortField>('totalHPRD');
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc');
  const [currentPage, setCurrentPage] = useState(1);
  const [showMethodology, setShowMethodology] = useState(false);
  const itemsPerPage = 50;

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

        // Validate facility data to detect CSV column shifts
        // Returns true if data appears valid, false if columns are shifted
        const isValidFacilityData = (facility: FacilityLiteRow): boolean => {
          const totalHPRD = typeof facility.Total_Nurse_HPRD === 'number' 
            ? facility.Total_Nurse_HPRD 
            : (parseFloat(String(facility.Total_Nurse_HPRD)) || 0);
          const directCareHPRD = typeof facility.Nurse_Care_HPRD === 'number' 
            ? facility.Nurse_Care_HPRD 
            : (parseFloat(String(facility.Nurse_Care_HPRD)) || 0);
          const rnHPRD = typeof facility.Total_RN_HPRD === 'number' 
            ? facility.Total_RN_HPRD 
            : (parseFloat(String(facility.Total_RN_HPRD)) || 0);
          
          // CRITICAL: If Total_Nurse_HPRD is 0 but Direct Care or RN HPRD have values,
          // this indicates a CSV column shift - reject this facility data
          if (totalHPRD === 0 && (directCareHPRD > 0 || rnHPRD > 0)) {
            return false; // Column shift detected
          }
          
          // Additional validation: Direct Care HPRD should not exceed Total HPRD
          if (totalHPRD > 0 && directCareHPRD > totalHPRD * 1.1) { // Allow 10% tolerance for rounding
            return false; // Likely column shift
          }
          
          return true; // Data appears valid
        };

        // STRICT matching: Only use normalized 6-digit CCN
        const findFacilityByCCN = (ccn: string): FacilityLiteRow | undefined => {
          const normalized = normalizeCCN(ccn);
          if (!normalized) return undefined;
          
          // Try map first (fastest)
          const found = facilityMap.get(normalized);
          if (found) {
            // Validate the facility data before returning
            if (isValidFacilityData(found)) {
              return found;
            } else {
              console.warn(`[CSV Shift Detected] CCN=${ccn} (normalized=${normalized}) has shifted columns - rejecting facility data`);
              return undefined;
            }
          }
          
          // If not in map, search array directly (shouldn't happen if map is built correctly)
          const foundInArray = facilityQ2.find((f: FacilityLiteRow) => {
            if (f.CY_Qtr && f.CY_Qtr !== '2025Q2') return false;
            const fProvNum = f.PROVNUM?.toString().trim() || '';
            if (!fProvNum) return false;
            return normalizeCCN(fProvNum) === normalized;
          });
          
          if (foundInArray && isValidFacilityData(foundInArray)) {
            return foundInArray;
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
        let skippedInvalidFacilities = 0;
        facilityQ2.forEach((f: FacilityLiteRow) => {
          const provNum = f.PROVNUM?.toString().trim() || '';
          if (!provNum) return;
          
          // Only include Q2 2025 data
          if (f.CY_Qtr && f.CY_Qtr !== '2025Q2') return;
          
          // Validate facility data to detect CSV column shifts
          if (!isValidFacilityData(f)) {
            skippedInvalidFacilities++;
            console.warn(`[CSV Shift] Skipping facility with shifted columns: PROVNUM=${provNum}, Name=${f.PROVNAME || 'Unknown'}`);
            return; // Skip this facility - it has shifted columns
          }
          
          // STRICT: Only use normalized 6-digit CCN as key
          const normalized = normalizeCCN(provNum);
          if (normalized) {
            // If key already exists, log a warning (shouldn't happen with strict matching)
            if (facilityMap.has(normalized)) {
              console.warn(`[Duplicate CCN] PROVNUM=${provNum} (normalized=${normalized}) already in map - keeping first entry`);
            } else {
              facilityMap.set(normalized, f);
            }
          }
        });
        
        console.log(`[Matching] Created facilityMap with ${facilityMap.size} entries from ${facilityQ2.length} Q2 facilities (skipped ${skippedInvalidFacilities} with shifted columns)`);
        
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
              
              // Final validation: If we have facility data, ensure it's still valid (double-check)
              if (facility && !isValidFacilityData(facility)) {
                console.warn(`[CSV Shift] Facility data for CCN=${ccn} failed validation - using provider data only`);
                facility = undefined; // Reject shifted facility data
              }
              
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
                // NOTE: Facility data has already been validated by isValidFacilityData() before being added to map
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

  const formatNumber = (num: number, decimals: number = 2): string => {
    return num.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const formatCensus = (num: number | undefined): string => {
    if (num === undefined || isNaN(num)) return 'N/A';
    return num.toLocaleString('en-US', {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
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
    if (!allFacilities.length || scope !== 'usa') return [];
    const stateSet = new Set<string>();
    allFacilities.forEach(f => stateSet.add(f.state));
    return Array.from(stateSet).sort();
  }, [allFacilities, scope]);

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
    if (!allFacilities.length || !regionStateMapping || scope !== 'usa') return [];
    const regionsWithData: number[] = [];
    for (let i = 1; i <= 10; i++) {
      const regionStates = regionStateMapping.get(i);
      if (regionStates) {
        const hasSFFs = allFacilities.some(f => regionStates.has(f.state));
        if (hasSFFs) {
          regionsWithData.push(i);
        }
      }
    }
    return regionsWithData;
  }, [allFacilities, regionStateMapping, scope]);

  const pageTitle = scope === 'usa' 
    ? 'Special Focus Facilities Program — United States'
    : scope && scope.startsWith('region')
    ? (() => {
        const regionNum = parseInt(scope.replace(/^region-?/, ''));
        return `Special Focus Facilities Program — CMS Region ${regionNum} (${getRegionName(regionNum)})`;
      })()
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
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-3">
            <h1 className="text-2xl md:text-3xl lg:text-4xl font-bold">{pageTitle}</h1>
            {(scope && scope !== 'usa') && (
              <button
                onClick={() => navigate('/sff/usa')}
                className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/50 rounded-lg text-blue-300 hover:text-blue-200 transition-colors text-sm font-medium whitespace-nowrap self-start sm:self-auto"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                </svg>
                View All USA SFFs
              </button>
            )}
          </div>
          <p className="text-gray-300 text-sm md:text-base mb-2">
            {candidateJSON?.document_date ? `${candidateJSON.document_date.month_name} ${candidateJSON.document_date.year}` : 'December 2025'} • CMS Special Focus Facility Program
          </p>
          <p className="text-gray-400 text-xs md:text-sm leading-relaxed max-w-3xl">
            Complete list of Special Focus Facilities (SFFs), SFF Candidates, Graduates, and facilities no longer participating in Medicare/Medicaid from the CMS SFF posting.
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
                  <label htmlFor="region-select" className="block text-sm font-semibold text-blue-300 mb-2">CMS Region</label>
                  <select
                    id="region-select"
                    value=""
                    onChange={(e) => {
                      if (e.target.value) {
                        navigate(`/sff/region${e.target.value}`);
                      }
                    }}
                    className="w-full px-4 py-2 bg-[#0f172a]/60 border border-blue-500/50 rounded text-blue-300 hover:bg-blue-600/20 focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer"
                  >
                    <option value="" className="bg-[#0f172a] text-blue-300">Select a region...</option>
                    {regionsWithSFFs.map(regionNum => (
                      <option key={`region${regionNum}`} value={regionNum} className="bg-[#0f172a] text-blue-300">
                        Region {regionNum} ({getRegionName(regionNum)})
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          </div>
        )}

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
        <div className="mb-8 md:mb-10">
          {sortedFacilities.length === 0 ? (
            <div className="rounded-lg border border-gray-700 bg-[#0f172a]/60 p-8 text-center">
              <p className="text-gray-400">No facilities found for this filter.</p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto rounded-lg border border-gray-700 bg-[#0f172a]/60 shadow-lg">
                <table className="w-full border-collapse min-w-[700px]">
                  <thead>
                    <tr className="bg-blue-600/20 border-b border-blue-500/30">
                      <th className="px-2 md:px-3 py-2 text-left text-xs font-semibold text-blue-300">Facility</th>
                      <th className="px-2 md:px-3 py-2 text-left text-xs font-semibold text-blue-300">Location</th>
                      <SortableHeader field="sffStatus" className="px-1 md:px-2 py-2 text-center text-xs font-semibold text-blue-300 whitespace-nowrap">Status</SortableHeader>
                      <SortableHeader field="census" className="px-1 md:px-2 py-2 text-center text-xs font-semibold text-blue-300 whitespace-nowrap">Census</SortableHeader>
                      <SortableHeader field="monthsAsSFF" className="px-1 md:px-2 py-2 text-center text-xs font-semibold text-blue-300">
                        <span className="hidden md:inline">Months as SFF</span>
                        <span className="md:hidden block leading-tight">
                          <span className="block">Months</span>
                          <span className="block">as SFF</span>
                        </span>
                      </SortableHeader>
                      <SortableHeader field="totalHPRD" className="px-1 md:px-2 py-2 text-center text-xs font-semibold text-blue-300">
                        <span className="hidden md:inline">Total HPRD</span>
                        <span className="md:hidden block leading-tight">
                          <span className="block">Total</span>
                          <span className="block">HPRD</span>
                        </span>
                      </SortableHeader>
                      <SortableHeader field="directCareHPRD" className="px-1 md:px-2 py-2 text-center text-xs font-semibold text-blue-300 hidden sm:table-cell">
                        <span className="hidden md:inline">Direct HPRD</span>
                        <span className="md:hidden block leading-tight">
                          <span className="block">Direct</span>
                          <span className="block">HPRD</span>
                        </span>
                      </SortableHeader>
                      <SortableHeader field="rnHPRD" className="px-1 md:px-2 py-2 text-center text-xs font-semibold text-blue-300 hidden md:table-cell">
                        <span className="hidden lg:inline">RN HPRD</span>
                        <span className="lg:hidden block leading-tight">
                          <span className="block">RN</span>
                          <span className="block">HPRD</span>
                        </span>
                      </SortableHeader>
                      <SortableHeader field="percentOfCaseMix" className="px-1 md:px-2 py-2 text-center text-xs font-semibold text-blue-300 hidden lg:table-cell">
                        <span className="hidden xl:inline">% Case-Mix</span>
                        <span className="xl:hidden block leading-tight">
                          <span className="block">%</span>
                          <span className="block">Case-Mix</span>
                        </span>
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
                          <td className="px-2 md:px-3 py-2">
                            <a
                              href={`https://pbjdashboard.com/?facility=${encodeURIComponent(facility.provnum || '')}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-300 hover:text-blue-200 underline font-medium text-xs md:text-sm break-words"
                            >
                              {facility.name}
                            </a>
                          </td>
                          <td className="px-2 md:px-3 py-2 text-gray-300 text-xs">
                            {facility.city ? `${facility.city}, ${facility.state}` : facility.state}
                          </td>
                          <td className="px-1 md:px-2 py-2 text-center">
                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusColors[facility.sffStatus]}`}>
                              {facility.sffStatus}
                            </span>
                          </td>
                          <td className="px-1 md:px-2 py-2 text-center text-gray-300 text-xs">{formatCensus(facility.census)}</td>
                          <td className="px-1 md:px-2 py-2 text-center text-gray-300 text-xs">
                            {facility.monthsAsSFF !== undefined ? facility.monthsAsSFF : '—'}
                          </td>
                          <td className="px-1 md:px-2 py-2 text-center text-white font-semibold text-xs">{formatNumber(facility.totalHPRD)}</td>
                          <td className="px-1 md:px-2 py-2 text-center text-gray-300 text-xs hidden sm:table-cell">{formatNumber(facility.directCareHPRD)}</td>
                          <td className="px-1 md:px-2 py-2 text-center text-gray-300 text-xs hidden md:table-cell">{formatNumber(facility.rnHPRD)}</td>
                          <td className="px-1 md:px-2 py-2 text-center text-gray-300 text-xs hidden lg:table-cell">
                            {formatPercent(facility.percentOfCaseMix)}
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
          <div className="text-center text-xs text-gray-400 mb-4">
            <p>Source: <a href="https://www.cms.gov/files/document/sff-posting-candidate-list-november-2025.pdf" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300 underline">CMS SFF Posting</a> ({candidateJSON?.document_date ? `${candidateJSON.document_date.month_name} ${candidateJSON.document_date.year}` : 'December 2025'})</p>
            {candidateJSON && (
              <p className="mt-1">
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
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
