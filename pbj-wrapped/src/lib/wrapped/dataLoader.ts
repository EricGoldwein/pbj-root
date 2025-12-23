/**
 * Data loading and parsing for PBJ Wrapped
 */

import Papa from 'papaparse';
import type {
  StateQuarterlyRow,
  RegionQuarterlyRow,
  NationalQuarterlyRow,
  FacilityLiteRow,
  ProviderInfoRow,
} from './wrappedTypes';

export interface RegionStateMapping {
  regionNumber: number;
  stateCodes: Set<string>;
}

export interface StateStandardRow {
  State: string;
  Total_Estimated_Staffing_Requirements: string;
  Min_Staffing: number;
  Max_Staffing: number;
  Value_Type: string;
  Is_Federal_Minimum: string;
  Display_Text: string;
}

export interface SFFFacilityData {
  provider_number: string;
  facility_name?: string;
  address?: string;
  city?: string;
  state?: string;
  zip?: string;
  phone_number?: string;
  category: 'SFF' | 'Graduate' | 'Terminated' | 'Candidate';
  months_as_sff?: number | null;
  most_recent_inspection?: string | null;
  met_survey_criteria?: string | null;
  date_of_graduation?: string | null;
  date_of_termination?: string | null;
}

export interface SFFData {
  facilities: SFFFacilityData[];
  document_date?: {
    month: number;
    year: number;
    month_name: string;
  };
  summary?: {
    current_sff_count: number;
    graduated_count: number;
    no_longer_participating_count: number;
    candidates_count: number;
    total_count: number;
  };
}

export interface LoadedData {
  stateData: {
    q1: StateQuarterlyRow[];
    q2: StateQuarterlyRow[];
  };
  regionData: {
    q1: RegionQuarterlyRow[];
    q2: RegionQuarterlyRow[];
  };
  nationalData: {
    q1: NationalQuarterlyRow | null;
    q2: NationalQuarterlyRow | null;
  };
  facilityData: {
    q1: FacilityLiteRow[];
    q2: FacilityLiteRow[];
  };
  providerInfo: {
    q1: ProviderInfoRow[];
    q2: ProviderInfoRow[];
  };
  regionStateMapping: Map<number, Set<string>>;
  stateStandards: Map<string, StateStandardRow>; // Map state code to standard
  sffData: SFFData | null; // SFF data from sff-facilities.json
}

/**
 * Parse CSV file
 */
function parseCSV<T>(csvText: string): Promise<T[]> {
  return new Promise((resolve, reject) => {
    Papa.parse<T>(csvText, {
      header: true,
      skipEmptyLines: true,
      transformHeader: (header) => header.trim(),
      // Ensure proper handling of quoted fields with commas
      // PapaParse handles quoted fields automatically, but we can be more explicit
      complete: (results) => {
        if (results.errors.length > 0) {
          console.warn('CSV parsing warnings:', results.errors);
          // Log first few errors in detail for debugging
          if (results.errors.length > 0 && results.errors.length <= 10) {
            results.errors.slice(0, 5).forEach((err, idx) => {
              console.warn(`  CSV Error ${idx + 1}:`, err);
            });
          }
        }
        
        // Log parsing stats for facility CSV to help debug misalignment issues
        if (results.data.length > 0 && 'PROVNUM' in (results.data[0] as any)) {
          const problematicCCNs = ['265379', '675595', '195454', '205077', '355031', '305051'];
          const problematicRows = results.data.filter((row: any) => 
            problematicCCNs.includes(String(row.PROVNUM || row['PROVNUM'] || '').trim())
          );
          if (problematicRows.length > 0) {
            console.log(`[CSV Parse] Found ${problematicRows.length} problematic facilities in parsed data`);
            problematicRows.slice(0, 3).forEach((row: any) => {
              const ccn = String(row.PROVNUM || row['PROVNUM'] || '').trim();
              console.log(`  CCN=${ccn}: Total_Nurse_HPRD=${row.Total_Nurse_HPRD}, Nurse_Care_HPRD=${row.Nurse_Care_HPRD}`);
            });
          }
        }
        
        resolve(results.data);
      },
      error: (error: Error) => {
        reject(error);
      },
    });
  });
}

/**
 * Load CSV file from path
 */
async function loadCSV(path: string): Promise<string> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Failed to load ${path}: ${response.statusText}`);
  }
  return response.text();
}

/**
 * Load JSON file from path (faster than CSV)
 * @param silent If true, suppress console errors for 404s (for optional files)
 */
async function loadJSON<T>(path: string, silent: boolean = false): Promise<T | null> {
  try {
    const response = await fetch(path);
    if (!response.ok || response.status === 404) {
      // Browser will log 404 - this is unavoidable for HTTP errors
      // We handle it gracefully by returning null
      return null;
    }
    const contentType = response.headers.get('content-type');
    // Check if response is actually JSON, not HTML (404 page)
    if (!contentType || !contentType.includes('application/json')) {
      return null;
    }
    const text = await response.text();
    // Check if it's HTML (starts with <)
    if (text.trim().startsWith('<')) {
      return null;
    }
    return JSON.parse(text);
  } catch {
    return null;
  }
}

/**
 * Filter rows by quarter
 */
function filterByQuarter<T extends { CY_Qtr: string }>(
  rows: T[],
  quarters: string[]
): T[] {
  const normalizedQuarters = quarters.map(q => q.toUpperCase().replace(/\s+/g, ''));
  return rows.filter((row) => {
    if (!row.CY_Qtr) return false;
    const q = row.CY_Qtr.trim().toUpperCase().replace(/\s+/g, '');
    return q && normalizedQuarters.includes(q);
  });
}

/**
 * Parse numeric fields from CSV rows
 */
function parseStateRow(row: any): StateQuarterlyRow {
  return {
    ...row,
    facility_count: parseFloat(row.facility_count) || 0,
    avg_days_reported: parseFloat(row.avg_days_reported) || 0,
    total_resident_days: parseFloat(row.total_resident_days) || 0,
    avg_daily_census: parseFloat(row.avg_daily_census) || 0,
    MDScensus: parseFloat(row.MDScensus) || 0,
    Total_Nurse_Hours: parseFloat(row.Total_Nurse_Hours) || 0,
    Total_RN_Hours: parseFloat(row.Total_RN_Hours) || 0,
    Total_Nurse_Care_Hours: parseFloat(row.Total_Nurse_Care_Hours) || 0,
    Total_RN_Care_Hours: parseFloat(row.Total_RN_Care_Hours) || 0,
    Total_Nurse_Assistant_Hours: parseFloat(row.Total_Nurse_Assistant_Hours) || 0,
    Total_Contract_Hours: parseFloat(row.Total_Contract_Hours) || 0,
    Total_Nurse_HPRD: parseFloat(row.Total_Nurse_HPRD) || 0,
    RN_HPRD: parseFloat(row.RN_HPRD) || 0,
    Nurse_Care_HPRD: parseFloat(row.Nurse_Care_HPRD) || 0,
    RN_Care_HPRD: parseFloat(row.RN_Care_HPRD) || 0,
    Nurse_Assistant_HPRD: parseFloat(row.Nurse_Assistant_HPRD) || 0,
    Contract_Percentage: parseFloat(row.Contract_Percentage) || 0,
    Direct_Care_Percentage: parseFloat(row.Direct_Care_Percentage) || 0,
    Total_RN_Percentage: parseFloat(row.Total_RN_Percentage) || 0,
    Nurse_Aide_Percentage: parseFloat(row.Nurse_Aide_Percentage) || 0,
  };
}

function parseRegionRow(row: any): RegionQuarterlyRow {
  return {
    ...row,
    REGION_NUMBER: parseInt(row.REGION_NUMBER, 10) || 0,
    facility_count: parseFloat(row.facility_count) || 0,
    avg_days_reported: parseFloat(row.avg_days_reported) || 0,
    total_resident_days: parseFloat(row.total_resident_days) || 0,
    avg_daily_census: parseFloat(row.avg_daily_census) || 0,
    MDScensus: parseFloat(row.MDScensus) || 0,
    Total_Nurse_Hours: parseFloat(row.Total_Nurse_Hours) || 0,
    Total_RN_Hours: parseFloat(row.Total_RN_Hours) || 0,
    Total_Nurse_Care_Hours: parseFloat(row.Total_Nurse_Care_Hours) || 0,
    Total_RN_Care_Hours: parseFloat(row.Total_RN_Care_Hours) || 0,
    Total_Nurse_Assistant_Hours: parseFloat(row.Total_Nurse_Assistant_Hours) || 0,
    Total_Contract_Hours: parseFloat(row.Total_Contract_Hours) || 0,
    Total_Nurse_HPRD: parseFloat(row.Total_Nurse_HPRD) || 0,
    RN_HPRD: parseFloat(row.RN_HPRD) || 0,
    Nurse_Care_HPRD: parseFloat(row.Nurse_Care_HPRD) || 0,
    RN_Care_HPRD: parseFloat(row.RN_Care_HPRD) || 0,
    Nurse_Assistant_HPRD: parseFloat(row.Nurse_Assistant_HPRD) || 0,
    Contract_Percentage: parseFloat(row.Contract_Percentage) || 0,
    Direct_Care_Percentage: parseFloat(row.Direct_Care_Percentage) || 0,
    Total_RN_Percentage: parseFloat(row.Total_RN_Percentage) || 0,
    Nurse_Aide_Percentage: parseFloat(row.Nurse_Aide_Percentage) || 0,
  };
}

function parseNationalRow(row: any): NationalQuarterlyRow {
  return {
    ...row,
    facility_count: parseFloat(row.facility_count) || 0,
    avg_days_reported: parseFloat(row.avg_days_reported) || 0,
    total_resident_days: parseFloat(row.total_resident_days) || 0,
    avg_daily_census: parseFloat(row.avg_daily_census) || 0,
    MDScensus: parseFloat(row.MDScensus) || 0,
    Total_Nurse_Hours: parseFloat(row.Total_Nurse_Hours) || 0,
    Total_RN_Hours: parseFloat(row.Total_RN_Hours) || 0,
    Total_Nurse_Care_Hours: parseFloat(row.Total_Nurse_Care_Hours) || 0,
    Total_RN_Care_Hours: parseFloat(row.Total_RN_Care_Hours) || 0,
    Total_Nurse_Assistant_Hours: parseFloat(row.Total_Nurse_Assistant_Hours) || 0,
    Total_Contract_Hours: parseFloat(row.Total_Contract_Hours) || 0,
    Total_Nurse_HPRD: parseFloat(row.Total_Nurse_HPRD) || 0,
    RN_HPRD: parseFloat(row.RN_HPRD) || 0,
    Nurse_Care_HPRD: parseFloat(row.Nurse_Care_HPRD) || 0,
    RN_Care_HPRD: parseFloat(row.RN_Care_HPRD) || 0,
    Nurse_Assistant_HPRD: parseFloat(row.Nurse_Assistant_HPRD) || 0,
    Contract_Percentage: parseFloat(row.Contract_Percentage) || 0,
  };
}

function parseFacilityRow(row: any): FacilityLiteRow {
  // Parse numeric fields - handle both string and number types
  // Use more defensive parsing to catch CSV misalignment issues
  const totalHPRD = parseFloat(String(row.Total_Nurse_HPRD || row['Total_Nurse_HPRD'] || 0)) || 0;
  const directCareHPRD = parseFloat(String(row.Nurse_Care_HPRD || row['Nurse_Care_HPRD'] || 0)) || 0;
  const rnHPRD = parseFloat(String(row.Total_RN_HPRD || row['Total_RN_HPRD'] || 0)) || 0;
  
  // Log potential misalignment during parsing (only for specific problematic CCNs for debugging)
  const provNum = String(row.PROVNUM || row['PROVNUM'] || '').trim();
  if (provNum && ['265379', '675595', '195454', '205077', '355031', '305051'].includes(provNum)) {
    if (totalHPRD === 0 && (directCareHPRD > 0.5 || rnHPRD > 0.5)) {
      console.warn(`[Parse Warning] CCN=${provNum} may have shifted columns during CSV parsing:`, {
        Total_Nurse_HPRD: row.Total_Nurse_HPRD,
        Nurse_Care_HPRD: row.Nurse_Care_HPRD,
        Total_RN_HPRD: row.Total_RN_HPRD,
        parsed: { totalHPRD, directCareHPRD, rnHPRD }
      });
    }
  }
  
  return {
    ...row,
    Total_Nurse_HPRD: totalHPRD,
    Nurse_Care_HPRD: directCareHPRD,
    Total_RN_HPRD: rnHPRD,
    Direct_Care_RN_HPRD: parseFloat(String(row.Direct_Care_RN_HPRD || row['Direct_Care_RN_HPRD'] || 0)) || 0,
    Contract_Percentage: parseFloat(String(row.Contract_Percentage || row['Contract_Percentage'] || 0)) || 0,
    Census: parseFloat(String(row.Census || row['Census'] || 0)) || 0,
  };
}

function parseProviderInfoRow(row: any): ProviderInfoRow {
  // Map lowercase CSV column names to uppercase interface names
  // Quarter is already in format '2025Q2', just normalize it
  let quarter = (row.quarter || row.CY_Qtr || '').trim().toUpperCase();
  quarter = quarter.replace(/\s+/g, ''); // Remove spaces
  
  // Ensure it's in the format we expect (2025Q1, 2025Q2, etc.)
  if (quarter && !quarter.match(/^\d{4}Q[1-4]$/)) {
    // If it's not in the right format, try to fix it
    quarter = quarter.replace(/Q([1-4])/i, 'Q$1');
  }
  
  return {
    PROVNUM: (row.ccn || row.PROVNUM || '').toString().trim(),
    PROVNAME: (row.provider_name || row.PROVNAME || '').trim(),
    STATE: (row.state || row.STATE || '').trim().toUpperCase(),
    CITY: (row.city || row.CITY || '').trim() || undefined,
    COUNTY_NAME: (row.county || row.COUNTY_NAME || '').trim(),
    CY_Qtr: quarter,
    ownership_type: (row.ownership_type || '').trim() || undefined,
    sff_status: (row.sff_status || '').trim() || undefined,
    overall_rating: (row.overall_rating || '').trim() || undefined,
    staffing_rating: (row.staffing_rating || '').trim() || undefined,
    case_mix_total_nurse_hrs_per_resident_per_day: row.case_mix_total_nurse_hrs_per_resident_per_day
      ? parseFloat(row.case_mix_total_nurse_hrs_per_resident_per_day)
      : undefined,
    case_mix_rn_hrs_per_resident_per_day: row.case_mix_rn_hrs_per_resident_per_day
      ? parseFloat(row.case_mix_rn_hrs_per_resident_per_day)
      : undefined,
    avg_residents_per_day: row.avg_residents_per_day
      ? parseFloat(row.avg_residents_per_day)
      : undefined,
  };
}

/**
 * Load data files optimized by scope (only loads what's needed)
 */
export async function loadAllData(basePath: string = '/data', scope?: 'usa' | 'state' | 'region', identifier?: string): Promise<LoadedData> {
  try {
    // Try to load pre-processed JSON files first (much faster)
    const jsonBasePath = `${basePath}/json`;
    const [
      stateQ1Json,
      stateQ2Json,
      regionQ1Json,
      regionQ2Json,
      nationalQ1Json,
      nationalQ2Json,
      facilityQ1Json,
      facilityQ2Json,
      providerQ1Json,
      providerQ2Json,
      regionMappingJson,
    ] = await Promise.all([
      loadJSON<StateQuarterlyRow[]>(`${jsonBasePath}/state_q1.json`),
      loadJSON<StateQuarterlyRow[]>(`${jsonBasePath}/state_q2.json`),
      loadJSON<RegionQuarterlyRow[]>(`${jsonBasePath}/region_q1.json`),
      loadJSON<RegionQuarterlyRow[]>(`${jsonBasePath}/region_q2.json`),
      loadJSON<NationalQuarterlyRow>(`${jsonBasePath}/national_q1.json`),
      loadJSON<NationalQuarterlyRow>(`${jsonBasePath}/national_q2.json`),
      loadJSON<FacilityLiteRow[]>(`${jsonBasePath}/facility_q1.json`),
      loadJSON<FacilityLiteRow[]>(`${jsonBasePath}/facility_q2.json`),
      loadJSON<ProviderInfoRow[]>(`${jsonBasePath}/provider_q1.json`),
      loadJSON<ProviderInfoRow[]>(`${jsonBasePath}/provider_q2.json`),
      loadJSON<Record<number, string[]>>(`${jsonBasePath}/region_state_mapping.json`),
    ]);
    
    // Load state standards for state and USA scope (needed for USA takeaway about states with min >= 2.00 HPRD)
    // File is generated by preprocess-data.js from macpac_state_standards_clean.csv
    // Use silent=true to avoid 404 console errors if file doesn't exist
    const stateStandardsJson = (scope === 'state' || scope === 'usa')
      ? await loadJSON<Record<string, StateStandardRow>>(`${jsonBasePath}/state_standards.json`, true)
      : null;
    
    // Load SFF data separately to avoid redeclaration
    // Use absolute path /wrapped/sff-facilities.json since file is in dist/ and served by /wrapped/<path:path> route
    // SFF data is optional - don't fail if it's missing
    const sffDataJson = await loadJSON<SFFData>('/wrapped/sff-facilities.json').catch(() => {
      console.warn('[SFF Data] sff-facilities.json not found - SFF features will be disabled');
      return null;
    });

    // If we got JSON data, use it (much faster!)
    // Check if we have the essential JSON files
    // Note: Empty arrays are still valid JSON, so check for null/undefined, not just truthiness
    // Match old behavior: hasJsonData only checks state/region/national files
    // Facility/provider JSON is loaded but not required for hasJsonData check
    // They'll default to empty arrays if missing (old behavior)
    const hasJsonData = stateQ1Json !== null && stateQ1Json !== undefined && 
                        stateQ2Json !== null && stateQ2Json !== undefined &&
                        regionQ1Json !== null && regionQ1Json !== undefined &&
                        regionQ2Json !== null && regionQ2Json !== undefined &&
                        nationalQ1Json !== null && nationalQ1Json !== undefined &&
                        nationalQ2Json !== null && nationalQ2Json !== undefined;
    
    // Log Q1 data status with detailed debugging
    console.log('Q1 Data Status:', {
      stateQ1: stateQ1Json ? `${stateQ1Json.length} rows` : 'missing',
      regionQ1: regionQ1Json ? `${regionQ1Json.length} rows` : 'missing',
      nationalQ1: nationalQ1Json ? 'found' : 'missing',
    });
    
    // Detailed Q1 debugging
    if (stateQ1Json && stateQ1Json.length > 0) {
      const sampleStates = [...new Set(stateQ1Json.slice(0, 10).map(s => s.STATE))];
      console.log(`Q1 State data sample: ${sampleStates.join(', ')}`);
      const nyQ1 = stateQ1Json.find(s => s.STATE === 'NY');
      if (nyQ1) {
        console.log(`✅ NY Q1 found in JSON: Total HPRD = ${nyQ1.Total_Nurse_HPRD}`);
      } else {
        console.warn(`❌ NY Q1 NOT found in JSON file!`);
      }
    } else if (stateQ1Json && stateQ1Json.length === 0) {
      console.error('❌ CRITICAL: state_q1.json exists but is EMPTY! Preprocessing did not find Q1 data. Regenerate JSON files.');
    } else {
      console.error('❌ CRITICAL: state_q1.json is missing! Run preprocessing.');
    }
    
    if (hasJsonData) {
      const regionStateMapping = new Map<number, Set<string>>();
      if (regionMappingJson) {
        for (const [regionNum, stateCodes] of Object.entries(regionMappingJson)) {
          regionStateMapping.set(parseInt(regionNum, 10), new Set(stateCodes));
        }
      }

      // Optimize: Try to load pre-filtered data first (much smaller files!)
      let facilityQ1 = facilityQ1Json || [];
      let facilityQ2 = facilityQ2Json || [];
      let providerQ1 = providerQ1Json || [];
      let providerQ2 = providerQ2Json || [];
      let usingFilteredData = false;

      // For state scope, try to load pre-filtered data first
      if (scope === 'state' && identifier) {
        const stateCode = identifier.toUpperCase();
        // Ensure identifier is a valid 2-letter state code, not a region
        if (stateCode.length === 2 && !stateCode.startsWith('REGION')) {
          const [stateFacilityQ1, stateFacilityQ2, stateProviderQ1, stateProviderQ2] = await Promise.all([
            loadJSON<FacilityLiteRow[]>(`${jsonBasePath}/facility_${stateCode}_q1.json`),
            loadJSON<FacilityLiteRow[]>(`${jsonBasePath}/facility_${stateCode}_q2.json`),
            loadJSON<ProviderInfoRow[]>(`${jsonBasePath}/provider_${stateCode}_q1.json`),
            loadJSON<ProviderInfoRow[]>(`${jsonBasePath}/provider_${stateCode}_q2.json`),
          ]);
          
          if (stateFacilityQ1 && stateFacilityQ2 && stateProviderQ1 && stateProviderQ2) {
            console.log(`✅ Using pre-filtered state data for ${stateCode} (${stateFacilityQ2.length} facilities vs ${facilityQ2.length} total)`);
            console.log(`Provider info for ${stateCode} - Q1: ${stateProviderQ1.length}, Q2: ${stateProviderQ2.length}`);
            if (stateProviderQ2.length > 0) {
              console.log(`Sample pre-filtered Q2: CCN=${stateProviderQ2[0].PROVNUM}, Ownership=${stateProviderQ2[0].ownership_type}, SFF=${stateProviderQ2[0].sff_status}`);
            }
            facilityQ1 = stateFacilityQ1;
            facilityQ2 = stateFacilityQ2;
            providerQ1 = stateProviderQ1;
            providerQ2 = stateProviderQ2;
            usingFilteredData = true;
          }
        }
      }

      // For region scope, try to load pre-filtered data first
      // Only check if scope is explicitly 'region' and we haven't already loaded filtered data
      // Double-check that identifier actually looks like a region (starts with "region" or is just a number)
      if (scope === 'region' && identifier && !usingFilteredData) {
        const identifierLower = identifier.toLowerCase();
        // Only proceed if identifier is clearly a region (starts with "region" or is just digits)
        if (identifierLower.startsWith('region') || /^\d+$/.test(identifierLower)) {
          // Extract region number - handle both "region1" and "1" formats
          const regionNum = identifierLower.replace(/^region/, '');
          if (regionNum && /^\d+$/.test(regionNum)) {
            const [regionFacilityQ1, regionFacilityQ2, regionProviderQ1, regionProviderQ2] = await Promise.all([
              loadJSON<FacilityLiteRow[]>(`${jsonBasePath}/facility_region${regionNum}_q1.json`),
              loadJSON<FacilityLiteRow[]>(`${jsonBasePath}/facility_region${regionNum}_q2.json`),
              loadJSON<ProviderInfoRow[]>(`${jsonBasePath}/provider_region${regionNum}_q1.json`),
              loadJSON<ProviderInfoRow[]>(`${jsonBasePath}/provider_region${regionNum}_q2.json`),
            ]);
            
            if (regionFacilityQ1 && regionFacilityQ2 && regionProviderQ1 && regionProviderQ2) {
              console.log(`✅ Using pre-filtered region data for region ${regionNum} (${regionFacilityQ2.length} facilities vs ${facilityQ2.length} total)`);
              facilityQ1 = regionFacilityQ1;
              facilityQ2 = regionFacilityQ2;
              providerQ1 = regionProviderQ1;
              providerQ2 = regionProviderQ2;
              usingFilteredData = true;
            }
          }
        }
      }

      if (!usingFilteredData) {
        console.log('✅ Using pre-processed JSON files (fast mode)');
      }
      
      // Debug provider info from JSON
      console.log(`Provider info from JSON - Q1: ${providerQ1.length}, Q2: ${providerQ2.length}`);
      if (providerQ2.length > 0) {
        console.log(`Sample JSON Q2 row: CCN=${providerQ2[0].PROVNUM}, State=${providerQ2[0].STATE}, Ownership=${providerQ2[0].ownership_type}, SFF=${providerQ2[0].sff_status}`);
      }

      // Log Q1 data status for debugging
      console.log('Q1 Data Status:', {
        stateQ1: Array.isArray(stateQ1Json) ? `${stateQ1Json.length} rows` : (stateQ1Json ? 'found' : 'missing'),
        regionQ1: Array.isArray(regionQ1Json) ? `${regionQ1Json.length} rows` : (regionQ1Json ? 'found' : 'missing'),
        nationalQ1: nationalQ1Json ? 'found' : 'missing',
      });
      
      // Check if Q1 data is empty (common issue)
      if (Array.isArray(stateQ1Json) && stateQ1Json.length === 0) {
        console.warn('⚠️ WARNING: state_q1.json is empty! Q1 trends will show 0.00. Regenerate JSON files with Q1 data.');
      }
      // Only warn about empty region Q1 if we're actually using region scope (suppress warning - data simply doesn't exist)
      // if (scope === 'region' && Array.isArray(regionQ1Json) && regionQ1Json.length === 0) {
      //   console.warn('⚠️ WARNING: region_q1.json is empty! Q1 trends will show 0.00. Regenerate JSON files with Q1 data.');
      // }

      // Load state standards from JSON if available (CSV fallback removed to avoid 404 errors)
      let stateStandardsMap = new Map<string, StateStandardRow>();
      if (stateStandardsJson) {
        for (const [key, value] of Object.entries(stateStandardsJson)) {
          stateStandardsMap.set(key, value as StateStandardRow);
        }
        console.log(`✅ Loaded ${stateStandardsMap.size} state standards from JSON`);
      }
      // If JSON not found, stateStandardsMap remains empty - state pages work fine without it

      return {
        stateData: { q1: stateQ1Json || [], q2: stateQ2Json || [] },
        regionData: { q1: regionQ1Json || [], q2: regionQ2Json || [] },
        nationalData: { q1: nationalQ1Json, q2: nationalQ2Json },
        facilityData: { q1: facilityQ1, q2: facilityQ2 },
        providerInfo: { q1: providerQ1, q2: providerQ2 },
        regionStateMapping,
        stateStandards: stateStandardsMap,
        sffData: sffDataJson,
      };
    }

    // Fall back to CSV parsing (slower but works if JSON not available)
    console.log('⚠️ JSON files not found, falling back to CSV parsing (this will be slower)...');
    console.log('💡 Tip: Run "preprocess-data.bat" to create JSON files for faster loading');
    
    // Load all CSV files in parallel (excluding optional state standards CSV to avoid 404 errors)
    const [
      stateCsv,
      regionCsv,
      nationalCsv,
      facilityCsv,
      providerInfoCsv,
      regionMappingCsv,
    ] = await Promise.all([
      loadCSV(`${basePath}/state_quarterly_metrics.csv`).catch(() => 
        loadCSV('../state_quarterly_metrics.csv')
      ),
      loadCSV(`${basePath}/cms_region_quarterly_metrics.csv`).catch(() => 
        loadCSV('../cms_region_quarterly_metrics.csv')
      ),
      loadCSV(`${basePath}/national_quarterly_metrics.csv`).catch(() => 
        loadCSV('../national_quarterly_metrics.csv')
      ),
      loadCSV(`${basePath}/facility_lite_metrics.csv`).catch(() => 
        loadCSV('../facility_lite_metrics.csv')
      ),
      loadCSV(`${basePath}/provider_info_combined.csv`).catch(() => 
        loadCSV('../provider_info_combined.csv')
      ),
      loadCSV(`${basePath}/cms_region_state_mapping.csv`).catch(() => 
        loadCSV('../cms_region_state_mapping.csv').catch(() => '')
      ),
    ]);

    // Parse all CSVs
    const [
      stateRows,
      regionRows,
      nationalRows,
      facilityRows,
      providerInfoRows,
      regionMappingRows,
    ] = await Promise.all([
      parseCSV<any>(stateCsv).then(rows => rows.map(parseStateRow)),
      parseCSV<any>(regionCsv).then(rows => rows.map(parseRegionRow)),
      parseCSV<any>(nationalCsv).then(rows => rows.map(parseNationalRow)),
      parseCSV<any>(facilityCsv).then(rows => rows.map(parseFacilityRow)),
      parseCSV<any>(providerInfoCsv).then(rows => rows.map(parseProviderInfoRow)),
      regionMappingCsv ? parseCSV<any>(regionMappingCsv) : Promise.resolve([]),
    ]);

    // State standards CSV loading removed to avoid 404 errors
    // State pages work fine without state standards data (it's optional)
    const stateStandardsMap = new Map<string, StateStandardRow>();

    // Build region-state mapping
    const regionStateMapping = new Map<number, Set<string>>();
    if (regionMappingRows && regionMappingRows.length > 0) {
      for (const row of regionMappingRows) {
        const regionNum = parseInt(row.CMS_Region_Number, 10);
        const stateCode = row.State_Code?.trim();
        if (regionNum && stateCode) {
          if (!regionStateMapping.has(regionNum)) {
            regionStateMapping.set(regionNum, new Set());
          }
          regionStateMapping.get(regionNum)!.add(stateCode);
        }
      }
    }

    // Filter by quarters
    const stateQ1 = filterByQuarter(stateRows, ['2025Q1']);
    const stateQ2 = filterByQuarter(stateRows, ['2025Q2']);
    
    const regionQ1 = filterByQuarter(regionRows, ['2025Q1']);
    const regionQ2 = filterByQuarter(regionRows, ['2025Q2']);
    
    const nationalQ1 = filterByQuarter(nationalRows, ['2025Q1'])[0] || null;
    const nationalQ2 = filterByQuarter(nationalRows, ['2025Q2'])[0] || null;
    
    const facilityQ1 = filterByQuarter(facilityRows, ['2025Q1']);
    const facilityQ2 = filterByQuarter(facilityRows, ['2025Q2']);
    
    // Filter provider info by quarter - always filter (quarter data exists in format 2025Q1, 2025Q2)
    const providerInfoQ1 = filterByQuarter(providerInfoRows, ['2025Q1']);
    const providerInfoQ2 = filterByQuarter(providerInfoRows, ['2025Q2']);
    
    console.log(`Provider info Q1 count: ${providerInfoQ1.length}, Q2 count: ${providerInfoQ2.length}`);
    if (providerInfoQ1.length > 0) {
      console.log(`Sample Q1 row: CCN=${providerInfoQ1[0].PROVNUM}, State=${providerInfoQ1[0].STATE}, Ownership=${providerInfoQ1[0].ownership_type}, SFF=${providerInfoQ1[0].sff_status}`);
    }
    if (providerInfoQ2.length > 0) {
      console.log(`Sample Q2 row: CCN=${providerInfoQ2[0].PROVNUM}, State=${providerInfoQ2[0].STATE}, Ownership=${providerInfoQ2[0].ownership_type}, SFF=${providerInfoQ2[0].sff_status}`);
    }

    // Load SFF data from sff-facilities.json (CSV fallback path)
    // Use absolute path /wrapped/sff-facilities.json since file is in dist/ and served by /wrapped/<path:path> route
    // SFF data is optional - don't fail if it's missing
    const sffDataJsonCsv = await loadJSON<SFFData>('/wrapped/sff-facilities.json').catch(() => {
      console.warn('[SFF Data] sff-facilities.json not found - SFF features will be disabled');
      return null;
    });

    return {
      stateData: {
        q1: stateQ1,
        q2: stateQ2,
      },
      regionData: {
        q1: regionQ1,
        q2: regionQ2,
      },
      nationalData: {
        q1: nationalQ1,
        q2: nationalQ2,
      },
      facilityData: {
        q1: facilityQ1,
        q2: facilityQ2,
      },
      providerInfo: {
        q1: providerInfoQ1,
        q2: providerInfoQ2,
      },
      regionStateMapping,
      stateStandards: stateStandardsMap,
      sffData: sffDataJsonCsv,
    };
  } catch (error) {
    console.error('Error loading data:', error);
    throw new Error(`Failed to load data: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Create lookup map for provider info by PROVNUM and quarter
 */
export function createProviderInfoLookup(
  providerInfo: ProviderInfoRow[]
): Map<string, ProviderInfoRow> {
  const lookup = new Map<string, ProviderInfoRow>();
  for (const row of providerInfo) {
    lookup.set(row.PROVNUM, row);
  }
  return lookup;
}

