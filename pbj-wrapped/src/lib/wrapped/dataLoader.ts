/**
 * Data loading and parsing for PBJ Wrapped.
 * No CSV fetches: uses /api/dates for quarter discovery and only requests JSON for those quarters.
 */

import type {
  StateQuarterlyRow,
  RegionQuarterlyRow,
  NationalQuarterlyRow,
  FacilityLiteRow,
  ProviderInfoRow,
} from './wrappedTypes';

const DEV = typeof import.meta !== 'undefined' && import.meta.env?.DEV;

/** Get origin for API calls (same origin in browser) */
function getApiBase(): string {
  if (typeof window !== 'undefined' && window.location?.origin) return window.location.origin;
  return 'https://www.pbj320.com';
}

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
 * Load JSON file from path. Returns null on 404 or non-JSON (no CSV fallback).
 */
async function loadJSON<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(path);
    if (!response.ok || response.status === 404) return null;
    const contentType = response.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) return null;
    const text = await response.text();
    if (text.trim().startsWith('<')) return null;
    return JSON.parse(text) as T;
  } catch {
    return null;
  }
}

/** Load JSON and return data + byte count (for dev payload logging). */
async function loadJSONWithSize<T>(path: string): Promise<{ data: T | null; bytes: number }> {
  try {
    const response = await fetch(path);
    const text = await response.text();
    const bytes = new Blob([text]).size;
    if (!response.ok || response.status === 404) return { data: null, bytes };
    const contentType = response.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) return { data: null, bytes };
    if (text.trim().startsWith('<')) return { data: null, bytes };
    return { data: JSON.parse(text) as T, bytes };
  } catch {
    return { data: null, bytes: 0 };
  }
}

/**
 * Filter rows by quarter (used in CSV fallback path). Exported to satisfy TS noUnusedLocals.
 */
export function _filterByQuarter<T extends { CY_Qtr: string }>(
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

/** Parse numeric fields from CSV rows. Exported to satisfy TS noUnusedLocals. */
export function _parseStateRow(row: any): StateQuarterlyRow {
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

export function _parseRegionRow(row: any): RegionQuarterlyRow {
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

export function _parseNationalRow(row: any): NationalQuarterlyRow {
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

export function _parseFacilityRow(row: any): FacilityLiteRow {
  // Parse numeric fields - handle both facility_quarterly_metrics and legacy facility_lite column names
  const totalHPRD = parseFloat(String(row.Total_Nurse_HPRD || row['Total_Nurse_HPRD'] || 0)) || 0;
  const directCareHPRD = parseFloat(String(row.Nurse_Care_HPRD || row['Nurse_Care_HPRD'] || 0)) || 0;
  const rnHPRD = parseFloat(String(row.Total_RN_HPRD || row['Total_RN_HPRD'] || row.RN_HPRD || row['RN_HPRD'] || 0)) || 0;
  
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
    Direct_Care_RN_HPRD: parseFloat(String(row.Direct_Care_RN_HPRD || row['Direct_Care_RN_HPRD'] || row.RN_Care_HPRD || row['RN_Care_HPRD'] || 0)) || 0,
    Contract_Percentage: parseFloat(String(row.Contract_Percentage || row['Contract_Percentage'] || 0)) || 0,
    Census: parseFloat(String(row.Census || row['Census'] || row.avg_daily_census || row['avg_daily_census'] || 0)) || 0,
  };
}

export function _parseProviderInfoRow(row: any): ProviderInfoRow {
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
 * Load data via JSON only. Uses /api/dates to discover quarters; requests only those JSON files.
 * No CSV fetches. State/region scope loads only state/region + mapping (and scope-filtered facility/provider).
 */
export async function loadAllData(basePath: string = '/data', scope?: 'usa' | 'state' | 'region', identifier?: string): Promise<LoadedData> {
  try {
    const apiBase = getApiBase();
    const datesRes = await fetch(`${apiBase}/api/dates`);
    const datesData = (datesRes.ok ? await datesRes.json() : null) as { quarters?: string[] } | null;
    const quarters: string[] = Array.isArray(datesData?.quarters) && datesData.quarters.length > 0
      ? datesData.quarters
      : ['2025Q1', '2025Q2'];

    if (DEV) {
      console.log('[Data] Quarters from API:', quarters, '→ using fixed q1/q2 files (most recent = q2)');
    }

    const q = `${basePath}/json/quarterly`;
    const qNational = `${q}/national`;
    const qState = `${q}/state`;
    const qRegion = `${q}/region`;
    const qFacility = `${q}/facility`;
    const qProvider = `${q}/provider`;

    let totalBytes = 0;
    const r = (path: string) => {
      if (DEV) {
        return loadJSONWithSize<unknown>(path).then(({ data, bytes }) => {
          totalBytes += bytes;
          return data;
        });
      }
      return loadJSON(path);
    };

    const stateBySuffix: Record<string, StateQuarterlyRow[]> = {};
    const regionBySuffix: Record<string, RegionQuarterlyRow[]> = {};
    const nationalBySuffix: Record<string, NationalQuarterlyRow | null> = {};
    const facilityBySuffix: Record<string, FacilityLiteRow[]> = {};
    const providerBySuffix: Record<string, ProviderInfoRow[]> = {};

    const isUSA = scope === 'usa';
    const isState = scope === 'state' && identifier && identifier.length === 2 && !identifier.toLowerCase().startsWith('region');
    const isRegion = scope === 'region' && identifier && /^region?\d*$|^\d+$/.test(identifier.toLowerCase().replace(/-/g, ''));
    const stateCode = isState ? identifier!.toUpperCase() : '';
    const regionNum = isRegion ? identifier!.toLowerCase().replace(/^region-?/, '') : '';

    // Preprocess always writes two quarters: q1 = previous, q2 = most recent. We load only those; "current" = q2 only (no fallbacks). Replicable when preprocess adds next quarter (q1/q2 roll forward).
    const FILE_SUFFIXES = ['q1', 'q2'] as const;
    const REGIONS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

    const statePromises = FILE_SUFFIXES.map((suf) => r(`${qState}/state_${suf}.json`) as Promise<StateQuarterlyRow[] | null>);
    const mappingPromise = r(`${qRegion}/region_state_mapping.json`) as Promise<Record<number, string[]> | null>;
    const standardsPromise = (scope === 'state' || scope === 'usa')
      ? (r(`${qState}/state_standards.json`) as Promise<Record<string, StateStandardRow> | null>)
      : Promise.resolve(null);

    const sffPromise = loadJSON<SFFData>('/wrapped/sff-facilities.json').catch(() => null);

    let regionPromises: Promise<RegionQuarterlyRow[] | null>[] = [];
    let nationalPromises: Promise<NationalQuarterlyRow | null>[] = [];
    let facilityPromises: Promise<FacilityLiteRow[] | null>[] = [];
    let providerPromises: Promise<ProviderInfoRow[] | null>[] = [];

    if (isUSA) {
      regionPromises = FILE_SUFFIXES.map((suf) => r(`${qRegion}/region_${suf}.json`) as Promise<RegionQuarterlyRow[] | null>);
      nationalPromises = FILE_SUFFIXES.map((suf) => r(`${qNational}/national_${suf}.json`) as Promise<NationalQuarterlyRow | null>);
      // USA: load facility/provider by fixed q1/q2 (most recent quarter = q2), same as state/region
      facilityPromises = FILE_SUFFIXES.flatMap((suf) =>
        REGIONS.map((reg) =>
          r(`${qFacility}/facility_region${reg}_${suf}.json`) as Promise<FacilityLiteRow[] | null>
        )
      );
      providerPromises = FILE_SUFFIXES.flatMap((suf) =>
        REGIONS.map((reg) =>
          r(`${qProvider}/provider_region${reg}_${suf}.json`) as Promise<ProviderInfoRow[] | null>
        )
      );
    } else if (isState) {
      facilityPromises = FILE_SUFFIXES.map((suf) => r(`${qFacility}/facility_${stateCode}_${suf}.json`) as Promise<FacilityLiteRow[] | null>);
      providerPromises = FILE_SUFFIXES.map((suf) => r(`${qProvider}/provider_${stateCode}_${suf}.json`) as Promise<ProviderInfoRow[] | null>);
    } else if (isRegion) {
      regionPromises = FILE_SUFFIXES.map((suf) => r(`${qRegion}/region_${suf}.json`) as Promise<RegionQuarterlyRow[] | null>);
      facilityPromises = FILE_SUFFIXES.map((suf) => r(`${qFacility}/facility_region${regionNum}_${suf}.json`) as Promise<FacilityLiteRow[] | null>);
      providerPromises = FILE_SUFFIXES.map((suf) => r(`${qProvider}/provider_region${regionNum}_${suf}.json`) as Promise<ProviderInfoRow[] | null>);
    }

    const all = await Promise.all([
      ...statePromises,
      mappingPromise,
      standardsPromise,
      sffPromise,
      ...regionPromises,
      ...nationalPromises,
      ...facilityPromises,
      ...providerPromises,
    ]);

    const n = statePromises.length;
    statePromises.forEach((_, i) => {
      const val = all[i];
      stateBySuffix[FILE_SUFFIXES[i]] = Array.isArray(val) ? (val as StateQuarterlyRow[]) : [];
    });
    const regionMapping = all[n] as Record<number, string[]> | null;
    const stateStandardsJson = all[n + 1];
    const sffDataJson = all[n + 2] as SFFData | null;
    let off = n + 3;
    regionPromises.forEach((_, i) => {
      const val = all[off + i];
      regionBySuffix[FILE_SUFFIXES[i]] = Array.isArray(val) ? (val as RegionQuarterlyRow[]) : [];
    });
    off += regionPromises.length;
    nationalPromises.forEach((_, i) => {
      nationalBySuffix[FILE_SUFFIXES[i]] = (all[off + i] as NationalQuarterlyRow | null) ?? null;
    });
    off += nationalPromises.length;
    // All scopes use q1/q2 file names. q2 = most recent quarter (e.g. 2025Q3). No fallbacks to prior quarters.
    const regionsPerQuarter = REGIONS.length;
    if (facilityPromises.length === FILE_SUFFIXES.length * regionsPerQuarter) {
      // USA: 20 files = 10 regions × q1, 10 regions × q2
      FILE_SUFFIXES.forEach((suf, sufIdx) => {
        const start = sufIdx * regionsPerQuarter;
        let merged: FacilityLiteRow[] = [];
        for (let i = 0; i < regionsPerQuarter; i++) {
          const val = all[off + start + i];
          const arr = Array.isArray(val) ? (val as FacilityLiteRow[]) : [];
          merged = merged.concat(arr);
        }
        facilityBySuffix[suf] = merged;
      });
    } else if (facilityPromises.length === FILE_SUFFIXES.length) {
      facilityBySuffix['q1'] = Array.isArray(all[off]) ? (all[off] as FacilityLiteRow[]) : [];
      facilityBySuffix['q2'] = Array.isArray(all[off + 1]) ? (all[off + 1] as FacilityLiteRow[]) : [];
    } else {
      facilityPromises.forEach((_, i) => {
        const val = all[off + i];
        facilityBySuffix[FILE_SUFFIXES[i]] = Array.isArray(val) ? (val as FacilityLiteRow[]) : [];
      });
    }
    off += facilityPromises.length;
    if (providerPromises.length === FILE_SUFFIXES.length * regionsPerQuarter) {
      FILE_SUFFIXES.forEach((suf, sufIdx) => {
        const start = sufIdx * regionsPerQuarter;
        let merged: ProviderInfoRow[] = [];
        for (let i = 0; i < regionsPerQuarter; i++) {
          const val = all[off + start + i];
          const arr = Array.isArray(val) ? (val as ProviderInfoRow[]) : [];
          merged = merged.concat(arr);
        }
        providerBySuffix[suf] = merged;
      });
    } else if (providerPromises.length === FILE_SUFFIXES.length) {
      providerBySuffix['q1'] = Array.isArray(all[off]) ? (all[off] as ProviderInfoRow[]) : [];
      providerBySuffix['q2'] = Array.isArray(all[off + 1]) ? (all[off + 1] as ProviderInfoRow[]) : [];
    } else {
      providerPromises.forEach((_, i) => {
        const val = all[off + i];
        providerBySuffix[FILE_SUFFIXES[i]] = Array.isArray(val) ? (val as ProviderInfoRow[]) : [];
      });
    }
    off += providerPromises.length;

    const regionStateMapping = new Map<number, Set<string>>();
    if (regionMapping && typeof regionMapping === 'object') {
      for (const [regionNumStr, stateCodes] of Object.entries(regionMapping)) {
        const num = parseInt(regionNumStr, 10);
        if (Array.isArray(stateCodes)) regionStateMapping.set(num, new Set(stateCodes));
      }
    }

    const stateStandardsMap = new Map<string, StateStandardRow>();
    if (stateStandardsJson && typeof stateStandardsJson === 'object') {
      for (const [k, v] of Object.entries(stateStandardsJson)) {
        stateStandardsMap.set(k, v as StateStandardRow);
      }
    }

    // Only q1/q2; q2 = most recent quarter. No fallbacks.
    const stateQ1 = stateBySuffix['q1'] ?? [];
    const stateQ2 = stateBySuffix['q2'] ?? [];
    const regionQ1 = regionBySuffix['q1'] ?? [];
    const regionQ2 = regionBySuffix['q2'] ?? [];
    const nationalQ1 = nationalBySuffix['q1'] ?? null;
    const nationalQ2 = nationalBySuffix['q2'] ?? null;
    // Current quarter only: q2 = most recent (e.g. 2025Q3). No fallbacks to prior quarters.
    const facilityQ1 = facilityBySuffix['q1'] ?? [];
    const facilityQ2 = facilityBySuffix['q2'] ?? [];
    const providerQ1 = providerBySuffix['q1'] ?? [];
    const providerQ2 = providerBySuffix['q2'] ?? [];

    const hasMinimalData = stateQ1.length > 0 || stateQ2.length > 0;
    if (!hasMinimalData) {
      throw new Error('No state quarterly JSON data available. Run preprocess-data to generate JSON files.');
    }

    if (DEV) {
      console.log('[Data] Total payload size (bytes):', totalBytes);
      if (totalBytes > 500 * 1024) console.warn('[Data] Total payload exceeds 500KB:', (totalBytes / 1024).toFixed(1), 'KB');
    }

    return {
      stateData: { q1: stateQ1, q2: stateQ2 },
      regionData: { q1: regionQ1, q2: regionQ2 },
      nationalData: { q1: nationalQ1, q2: nationalQ2 },
      facilityData: { q1: facilityQ1, q2: facilityQ2 },
      providerInfo: { q1: providerQ1, q2: providerQ2 },
      regionStateMapping,
      stateStandards: stateStandardsMap,
      sffData: sffDataJson ?? null,
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

