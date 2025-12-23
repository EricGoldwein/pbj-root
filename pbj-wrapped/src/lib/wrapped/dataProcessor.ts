/**
 * Data processing and aggregation for PBJ Wrapped
 */

import type {
  PBJWrappedData,
  Facility,
  FacilityChange,
  StateChange,
  Scope,
  StateQuarterlyRow,
  RegionQuarterlyRow,
  NationalQuarterlyRow,
  FacilityLiteRow,
  ProviderInfoRow,
  OwnershipBreakdown,
  StateMinimum,
} from './wrappedTypes';
import type { LoadedData, SFFData, StateStandardRow } from './dataLoader';
import { createProviderInfoLookup } from './dataLoader';

/**
 * Calculate percentile rank
 * @deprecated Not currently used, but kept for potential future use
 */
// function calculatePercentile(rank: number, total: number): number {
//   if (total === 0) return 0;
//   return Math.round(((total - rank + 1) / total) * 100);
// }

/**
 * Normalize provider number to 6 digits with leading zeros
 */
function normalizeProviderNumber(providerNumber: string | number | null | undefined): string {
  if (!providerNumber) return '';
  const str = providerNumber.toString().trim().replace(/[^0-9]/g, ''); // Remove non-digits
  if (!str) return '';
  return str.padStart(6, '0');
}

/**
 * Parse ownership type from string
 */
function parseOwnershipType(ownershipType?: string): 'forProfit' | 'nonProfit' | 'government' | null {
  if (!ownershipType) return null;
  const lower = ownershipType.toLowerCase();
  // Handle various for-profit formats
  if (lower.includes('for profit') || lower.includes('for-profit') || lower.includes('forprofit')) {
    return 'forProfit';
  }
  // Handle various non-profit formats
  if (lower.includes('non profit') || lower.includes('non-profit') || lower.includes('nonprofit') || lower.includes('not for profit')) {
    return 'nonProfit';
  }
  // Handle government formats
  if (lower.includes('government') || lower.includes('govt') || lower.includes('state') || lower.includes('county') || lower.includes('city') || lower.includes('federal')) {
    return 'government';
  }
  return null;
}

/**
 * Simplify ownership type to exactly one of: "Nonprofit", "For-profit", or "Government"
 * Removes all suffixes like "- Individual", "- Corporation", etc.
 */
function simplifyOwnershipType(ownershipType: string | undefined): string | undefined {
  if (!ownershipType) return undefined;
  const lowerType = ownershipType.toLowerCase();
  if (lowerType.includes('for profit') || lowerType.includes('for-profit') || lowerType.includes('forprofit')) {
    return 'For-profit';
  }
  if (lowerType.includes('non profit') || lowerType.includes('non-profit') || lowerType.includes('nonprofit') || lowerType.includes('not for profit')) {
    return 'Nonprofit';
  }
  if (lowerType.includes('government') || lowerType.includes('govt') || lowerType.includes('state') || lowerType.includes('county') || lowerType.includes('city') || lowerType.includes('federal')) {
    return 'Government';
  }
  return undefined; // Don't return unknown types
}

/**
 * Calculate median value from array
 */
function calculateMedian(values: number[]): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0
    ? (sorted[mid - 1] + sorted[mid]) / 2
    : sorted[mid];
}

/**
 * Calculate ownership breakdown from provider info
 */
function calculateOwnershipBreakdown(providerInfo: ProviderInfoRow[]): OwnershipBreakdown {
  let forProfit = 0;
  let nonProfit = 0;
  let government = 0;
  
  for (const provider of providerInfo) {
    const type = parseOwnershipType(provider.ownership_type);
    if (type === 'forProfit') {
      forProfit++;
    } else if (type === 'nonProfit') {
      nonProfit++;
    } else if (type === 'government') {
      government++;
    }
  }
  
  const total = forProfit + nonProfit + government;
  const percentage = (count: number) => total > 0 ? Math.round((count / total) * 100) : 0;
  
  return {
    forProfit: {
      count: forProfit,
      percentage: percentage(forProfit),
    },
    nonProfit: {
      count: nonProfit,
      percentage: percentage(nonProfit),
    },
    government: {
      count: government,
      percentage: percentage(government),
    },
  };
}

/**
 * Calculate ownership breakdown with median HPRD from provider info and facilities
 */
function calculateOwnershipBreakdownWithStaffing(
  providerInfo: ProviderInfoRow[],
  facilities: FacilityLiteRow[]
): OwnershipBreakdown {
  const baseBreakdown = calculateOwnershipBreakdown(providerInfo);
  
  // Create lookup for facilities by PROVNUM
  const facilityMap = new Map(facilities.map(f => [f.PROVNUM, f]));
  
  // Group facilities by ownership type and collect HPRD values
  const forProfitHPRDs: number[] = [];
  const nonProfitHPRDs: number[] = [];
  const governmentHPRDs: number[] = [];
  
  for (const provider of providerInfo) {
    const facility = facilityMap.get(provider.PROVNUM);
    if (!facility || facility.Total_Nurse_HPRD <= 0) continue;
    
    const type = parseOwnershipType(provider.ownership_type);
    if (type === 'forProfit') {
      forProfitHPRDs.push(facility.Total_Nurse_HPRD);
    } else if (type === 'nonProfit') {
      nonProfitHPRDs.push(facility.Total_Nurse_HPRD);
    } else if (type === 'government') {
      governmentHPRDs.push(facility.Total_Nurse_HPRD);
    }
  }
  
  return {
    forProfit: {
      ...baseBreakdown.forProfit,
      medianHPRD: forProfitHPRDs.length > 0 ? calculateMedian(forProfitHPRDs) : undefined,
    },
    nonProfit: {
      ...baseBreakdown.nonProfit,
      medianHPRD: nonProfitHPRDs.length > 0 ? calculateMedian(nonProfitHPRDs) : undefined,
    },
    government: {
      ...baseBreakdown.government,
      medianHPRD: governmentHPRDs.length > 0 ? calculateMedian(governmentHPRDs) : undefined,
    },
  };
}

/**
 * Shorten long provider names for display
 */
export function shortenProviderName(name: string, maxLength: number = 40): string {
  if (!name || name.length <= maxLength) return name;
  
  // Common abbreviations - preserve capitalization context
  const abbreviations: Record<string, string> = {
    'rehabilitation': 'Rehab',
    'Rehabilitation': 'Rehab',
    'rehabilitative': 'Rehabilitative',
    'Rehabilitative': 'Rehabilitative',
    'rehabilitation center': 'Rehab Center',
    'Rehabilitation Center': 'Rehab Center',
    'rehabilitation facility': 'Rehab Facility',
    'Rehabilitation Facility': 'Rehab Facility',
    'skilled nursing': 'SNF',
    'Skilled Nursing': 'SNF',
    'skilled nursing facility': 'SNF',
    'Skilled Nursing Facility': 'SNF',
    'nursing home': 'NH',
    'Nursing Home': 'NH',
    'nursing center': 'NC',
    'Nursing Center': 'NC',
    'healthcare': 'Health',
    'Healthcare': 'Health',
    'health care': 'Health',
    'Health Care': 'Health',
    'assisted living': 'AL',
    'Assisted Living': 'AL',
    'extended care': 'EC',
    'Extended Care': 'EC',
    'long term care': 'LTC',
    'Long Term Care': 'LTC',
  };
  
  let shortened = name;
  
  // Try to replace common phrases with abbreviations
  for (const [full, abbrev] of Object.entries(abbreviations)) {
    if (shortened.includes(full)) {
      shortened = shortened.replace(new RegExp(full.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi'), (match) => {
        // Preserve capitalization
        if (match[0] === match[0].toUpperCase()) {
          return abbrev.charAt(0).toUpperCase() + abbrev.slice(1);
        }
        return abbrev.toLowerCase();
      });
    }
  }
  
  // If still too long, truncate with ellipsis
  if (shortened.length > maxLength) {
    shortened = shortened.substring(0, maxLength - 3) + '...';
  }
  
  return shortened;
}

export function toTitleCase(name: string): string {
  if (!name) return name;
  
  // First, normalize to lowercase for consistent processing
  const lowerName = name.toLowerCase();
  
  return lowerName
    .split(' ')
    .map((word, index) => {
      // Handle hyphenated words - capitalize both parts (e.g., "Post-Acute")
      if (word.includes('-')) {
        return word
          .split('-')
          .map((part) => {
            // Capitalize each part of hyphenated words
            return part.charAt(0).toUpperCase() + part.slice(1);
          })
          .join('-');
      }
      
      // Always capitalize first word, or if word is not in small words list
      if (index === 0 || !smallWords.has(word)) {
        return word.charAt(0).toUpperCase() + word.slice(1);
      }
      return word;
    })
    .join(' ');
}

const smallWords = new Set(['a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'if', 'in', 'of', 'on', 'or', 'the', 'to']);

/**
 * Capitalize city names properly
 */
export function capitalizeCity(city: string | undefined): string | undefined {
  if (!city) return city;
  
  // First normalize to lowercase to handle all-caps input like "MEMPHIS"
  const normalized = city.trim().toLowerCase();
  
  const specialCases: Record<string, string> = {
    'st.': 'St.',
    'st': 'St.',
    'ft.': 'Ft.',
    'ft': 'Ft.',
    'mt.': 'Mt.',
    'mt': 'Mt.',
  };
  
  if (specialCases[normalized]) {
    return specialCases[normalized];
  }
  
  // Standard title case: capitalize first letter of each word
  return normalized
    .split(' ')
    .map(word => {
      if (!word) return word;
      // Handle "Mc" prefix
      if (word.startsWith('mc') && word.length > 2) {
        return 'Mc' + word.charAt(2).toUpperCase() + word.slice(3);
      }
      // Handle "O'" prefix
      if (word.startsWith("o'") && word.length > 2) {
        return "O'" + word.charAt(2).toUpperCase() + word.slice(3);
      }
      // Handle special cases within words
      if (word === 'st' || word === 'st.') {
        return 'St.';
      }
      // Capitalize first letter, lowercase the rest
      return word.charAt(0).toUpperCase() + word.slice(1);
    })
    .join(' ');
}

/**
 * Create link to facility dashboard
 */
function createFacilityLink(provnum: string): string {
  return `https://pbjdashboard.com/?facility=${provnum}`;
}

/**
 * Create link to state wrapped page
 */
function createStateLink(stateCode: string): string {
  // Return wrapped page link instead of dashboard link
  return `/wrapped/${stateCode.toLowerCase()}`;
}

/**
 * Process data for USA scope
 */
function processUSAData(
  nationalQ2: NationalQuarterlyRow | null,
  nationalQ1: NationalQuarterlyRow | null,
  facilityQ2: FacilityLiteRow[],
  _facilityQ1: FacilityLiteRow[],
  providerInfoQ2: ProviderInfoRow[],
  _providerInfoQ1: ProviderInfoRow[],
  stateDataQ2: StateQuarterlyRow[],
  stateDataQ1: StateQuarterlyRow[],
  regionDataQ2: RegionQuarterlyRow[],
  regionDataQ1: RegionQuarterlyRow[],
  sffData?: SFFData | null,
  stateStandards?: Map<string, StateStandardRow>
): PBJWrappedData {
  if (!nationalQ2) {
    throw new Error('National Q2 data not available');
  }

  console.log('[USA] Q1 data check:', {
    nationalQ1: !!nationalQ1,
    nationalQ1TotalHPRD: nationalQ1?.Total_Nurse_HPRD,
    nationalQ2TotalHPRD: nationalQ2.Total_Nurse_HPRD,
  });

  const providerInfoLookupQ2 = createProviderInfoLookup(providerInfoQ2);

  // Section 2: Basics
  const facilityCount = nationalQ2.facility_count;
  // Calculate average daily residents: total_resident_days / avg_days_reported
  // This gives us the average number of residents across all facilities on any given day
  const avgDailyResidents = nationalQ2.avg_days_reported > 0
    ? nationalQ2.total_resident_days / nationalQ2.avg_days_reported
    : nationalQ2.avg_daily_census * facilityCount; // Fallback: avg per facility * facility count
  const totalHPRD = nationalQ2.Total_Nurse_HPRD;
  const directCareHPRD = nationalQ2.Nurse_Care_HPRD;
  const rnHPRD = nationalQ2.RN_HPRD;
  const rnDirectCareHPRD = nationalQ2.RN_Care_HPRD;
  const nurseAideHPRD = nationalQ2.Nurse_Assistant_HPRD;
  
  // Calculate median HPRD from facilities - use more efficient approach
  // Only sort a copy if we need it, and reuse for other calculations
  const allHPRDs = facilityQ2.map(f => f.Total_Nurse_HPRD);
  const sortedHPRDs = [...allHPRDs].sort((a, b) => a - b);
  const medianHPRD = sortedHPRDs.length > 0 
    ? sortedHPRDs[Math.floor(sortedHPRDs.length / 2)]
    : 0;

  // Section 3: Rankings (USA is always rank 1 of 1, 100th percentile)
  const rankings = {
    totalHPRDRank: 1,
    totalHPRDPercentile: 100,
    directCareHPRDRank: 1,
    directCareHPRDPercentile: 100,
    rnHPRDRank: 1,
    rnHPRDPercentile: 100,
  };

  // Section 4: Extremes - Top/Bottom States and Regions
  // Filter out Puerto Rico (PR) from state data
  const statesQ2ExcludingPR = stateDataQ2.filter(s => s.STATE !== 'PR');
  
  // State abbreviation to full name mapping
  const STATE_ABBR_TO_NAME: Record<string, string> = {
    'al': 'Alabama', 'ak': 'Alaska', 'az': 'Arizona', 'ar': 'Arkansas', 'ca': 'California',
    'co': 'Colorado', 'ct': 'Connecticut', 'de': 'Delaware', 'fl': 'Florida', 'ga': 'Georgia',
    'hi': 'Hawaii', 'id': 'Idaho', 'il': 'Illinois', 'in': 'Indiana', 'ia': 'Iowa',
    'ks': 'Kansas', 'ky': 'Kentucky', 'la': 'Louisiana', 'me': 'Maine', 'md': 'Maryland',
    'ma': 'Massachusetts', 'mi': 'Michigan', 'mn': 'Minnesota', 'ms': 'Mississippi', 'mo': 'Missouri',
    'mt': 'Montana', 'ne': 'Nebraska', 'nv': 'Nevada', 'nh': 'New Hampshire', 'nj': 'New Jersey',
    'nm': 'New Mexico', 'ny': 'New York', 'nc': 'North Carolina', 'nd': 'North Dakota', 'oh': 'Ohio',
    'ok': 'Oklahoma', 'or': 'Oregon', 'pa': 'Pennsylvania', 'ri': 'Rhode Island', 'sc': 'South Carolina',
    'sd': 'South Dakota', 'tn': 'Tennessee', 'tx': 'Texas', 'ut': 'Utah', 'vt': 'Vermont',
    'va': 'Virginia', 'wa': 'Washington', 'wv': 'West Virginia', 'wi': 'Wisconsin', 'wy': 'Wyoming',
    'dc': 'District of Columbia'
  };
  
  function getStateFullName(abbr: string): string {
    return STATE_ABBR_TO_NAME[abbr.toLowerCase()] || abbr.toUpperCase();
  }

  // Top/Bottom States by Total HPRD (excluding PR)
  const sortedStatesByHPRD = [...statesQ2ExcludingPR].sort((a, b) => b.Total_Nurse_HPRD - a.Total_Nurse_HPRD);
  const topStatesByHPRD: Facility[] = sortedStatesByHPRD.slice(0, 5).map(s => ({
    provnum: s.STATE,
    name: getStateFullName(s.STATE),
    state: s.STATE,
    value: s.Total_Nurse_HPRD,
    link: createStateLink(s.STATE),
  }));
  const bottomStatesByHPRD: Facility[] = sortedStatesByHPRD.slice(-5).reverse().map(s => ({
    provnum: s.STATE,
    name: getStateFullName(s.STATE),
    state: s.STATE,
    value: s.Total_Nurse_HPRD,
    link: createStateLink(s.STATE),
  }));

  // Top/Bottom States by Direct Care HPRD (excluding PR)
  const sortedStatesByDirectCare = [...statesQ2ExcludingPR].sort((a, b) => b.Nurse_Care_HPRD - a.Nurse_Care_HPRD);
  const topStatesByDirectCare: Facility[] = sortedStatesByDirectCare.slice(0, 3).map(s => ({
    provnum: s.STATE,
    name: getStateFullName(s.STATE),
    state: s.STATE,
    value: s.Nurse_Care_HPRD,
    link: createStateLink(s.STATE),
  }));
  const bottomStatesByDirectCare: Facility[] = sortedStatesByDirectCare.slice(-3).reverse().map(s => ({
    provnum: s.STATE,
    name: getStateFullName(s.STATE),
    state: s.STATE,
    value: s.Nurse_Care_HPRD,
    link: createStateLink(s.STATE),
  }));

  // Top/Bottom Regions by Total HPRD
  const sortedRegionsByHPRD = [...regionDataQ2].sort((a, b) => b.Total_Nurse_HPRD - a.Total_Nurse_HPRD);
  const topRegionsByHPRD: Facility[] = sortedRegionsByHPRD.slice(0, 3).map(r => ({
    provnum: `region${r.REGION_NUMBER}`,
    name: r.REGION_NAME || `Region ${r.REGION_NUMBER}`,
    state: `Region ${r.REGION_NUMBER}`,
    value: r.Total_Nurse_HPRD,
    link: `/wrapped/region${r.REGION_NUMBER}`,
  }));
  const bottomRegionsByHPRD: Facility[] = sortedRegionsByHPRD.slice(-3).reverse().map(r => ({
    provnum: `region${r.REGION_NUMBER}`,
    name: r.REGION_NAME || `Region ${r.REGION_NUMBER}`,
    state: `Region ${r.REGION_NUMBER}`,
    value: r.Total_Nurse_HPRD,
    link: `/wrapped/region${r.REGION_NUMBER}`,
  }));

  // Top/Bottom Regions by Direct Care HPRD
  const sortedRegionsByDirectCare = [...regionDataQ2].sort((a, b) => b.Nurse_Care_HPRD - a.Nurse_Care_HPRD);
  const topRegionsByDirectCare: Facility[] = sortedRegionsByDirectCare.slice(0, 3).map(r => ({
    provnum: `region${r.REGION_NUMBER}`,
    name: r.REGION_NAME || `Region ${r.REGION_NUMBER}`,
    state: `Region ${r.REGION_NUMBER}`,
    value: r.Nurse_Care_HPRD,
    link: `/wrapped/region${r.REGION_NUMBER}`,
  }));
  const bottomRegionsByDirectCare: Facility[] = sortedRegionsByDirectCare.slice(-3).reverse().map(r => ({
    provnum: `region${r.REGION_NUMBER}`,
    name: r.REGION_NAME || `Region ${r.REGION_NUMBER}`,
    state: `Region ${r.REGION_NUMBER}`,
    value: r.Nurse_Care_HPRD,
    link: `/wrapped/region${r.REGION_NUMBER}`,
  }));

  // Also include facility extremes - combine mapping and filtering in one pass
  // Pre-allocate array size for better performance
  const facilitiesWithInfoQ2: Array<{ facility: FacilityLiteRow; info: ProviderInfoRow }> = [];
  for (const f of facilityQ2) {
    const info = providerInfoLookupQ2.get(f.PROVNUM);
    if (info) {
      facilitiesWithInfoQ2.push({ facility: f, info });
    }
  }

  // Sort once and reuse
  const sortedByHPRD = facilitiesWithInfoQ2.sort((a, b) => 
    a.facility.Total_Nurse_HPRD - b.facility.Total_Nurse_HPRD
  );
  
  const lowestByHPRD: Facility[] = sortedByHPRD.slice(0, 3).map(({ facility }) => ({
    provnum: facility.PROVNUM,
    name: toTitleCase(facility.PROVNAME),
    state: facility.STATE,
    value: facility.Total_Nurse_HPRD,
    link: createFacilityLink(facility.PROVNUM),
  }));

  const highestByHPRD: Facility[] = sortedByHPRD.slice(-3).reverse().map(({ facility }) => ({
    provnum: facility.PROVNUM,
    name: toTitleCase(facility.PROVNAME),
    state: facility.STATE,
    value: facility.Total_Nurse_HPRD,
    link: createFacilityLink(facility.PROVNUM),
  }));

  // Lowest/Highest by % of expected (case-mix adjusted)
  const withPercentExpected = facilitiesWithInfoQ2
    .map(({ facility, info }) => {
      const caseMix = info?.case_mix_total_nurse_hrs_per_resident_per_day;
      if (!caseMix || caseMix === 0) return null;
      const percentExpected = (facility.Total_Nurse_HPRD / caseMix) * 100;
      return { facility, info, percentExpected };
    })
    .filter((f): f is NonNullable<typeof f> => f !== null);

  const sortedByPercent = [...withPercentExpected].sort((a, b) => 
    a.percentExpected - b.percentExpected
  );

  const lowestByPercentExpected: Facility[] = sortedByPercent.slice(0, 5).map(({ facility, percentExpected }) => ({
    provnum: facility.PROVNUM,
    name: toTitleCase(facility.PROVNAME),
    state: facility.STATE,
    value: percentExpected,
    link: createFacilityLink(facility.PROVNUM),
  }));

  const highestByPercentExpected: Facility[] = sortedByPercent.slice(-5).reverse().map(({ facility, percentExpected }) => ({
    provnum: facility.PROVNUM,
    name: toTitleCase(facility.PROVNAME),
    state: facility.STATE,
    value: percentExpected,
    link: createFacilityLink(facility.PROVNUM),
  }));

  // Section 5: SFF - use sff-facilities.json if available, otherwise fall back to providerInfo
  let sffCount = 0;
  let candidatesCount = 0;
  let graduatesCount = 0;
  let inactiveCount = 0;
  let newSFFFacilities: Facility[] = [];
  
  if (sffData && sffData.facilities) {
    // Use data from sff-facilities.json
    const sffFacilities = sffData.facilities.filter(f => f.category === 'SFF');
    const candidateFacilities = sffData.facilities.filter(f => f.category === 'Candidate');
    const graduateFacilities = sffData.facilities.filter(f => f.category === 'Graduate');
    const inactiveFacilities = sffData.facilities.filter(f => f.category === 'Terminated');
    sffCount = sffFacilities.length;
    candidatesCount = candidateFacilities.length;
    graduatesCount = graduateFacilities.length;
    inactiveCount = inactiveFacilities.length;
    
    // Get new SFF facilities based on months_as_sff (facilities with <= 3 months are considered new)
    const newSFF = sffFacilities.filter(f => 
      f.months_as_sff !== null && 
      f.months_as_sff !== undefined && 
      f.months_as_sff <= 3
    );
    const shuffledNewSFF = [...newSFF].sort(() => Math.random() - 0.5);
    // Create a map for efficient lookup
    const facilityMapQ2 = new Map(facilityQ2.map(f => [normalizeProviderNumber(f.PROVNUM), f]));
    newSFFFacilities = shuffledNewSFF.slice(0, 5).map(f => {
      const normalizedProviderNum = normalizeProviderNumber(f.provider_number);
      const facility = facilityMapQ2.get(normalizedProviderNum);
      return {
        provnum: normalizedProviderNum,
        name: toTitleCase(f.facility_name || ''),
        state: f.state || '',
        value: facility?.Total_Nurse_HPRD || 0,
        link: createFacilityLink(normalizedProviderNum),
      };
    });
  } else {
    // Fall back to providerInfo data (no Q1/Q2 comparison, just use Q2 data)
    const sffQ2 = providerInfoQ2.filter(p => {
      if (!p.sff_status) return false;
      const status = p.sff_status.trim().toUpperCase();
      return status === 'SFF' || status === 'SPECIAL FOCUS FACILITY' || status.includes('SFF');
    });
    const candidatesQ2 = providerInfoQ2.filter(p => {
      if (!p.sff_status) return false;
      const status = p.sff_status.trim().toUpperCase();
      return status === 'SFF CANDIDATE' || status === 'CANDIDATE' || (status.includes('CANDIDATE') && !status.includes('SFF'));
    });
    
    sffCount = sffQ2.length;
    candidatesCount = candidatesQ2.length;
  
    // No new SFF determination available without sffData, so use empty array
    newSFFFacilities = [];
  }

  // Section 6: Trends - calculate changes from Q1 to Q2
  const trends = {
    totalHPRDChange: nationalQ1 
      ? nationalQ2.Total_Nurse_HPRD - nationalQ1.Total_Nurse_HPRD 
      : 0,
    directCareHPRDChange: nationalQ1
      ? nationalQ2.Nurse_Care_HPRD - nationalQ1.Nurse_Care_HPRD
      : 0,
    rnHPRDChange: nationalQ1
      ? nationalQ2.RN_HPRD - nationalQ1.RN_HPRD
      : 0,
    nurseAideHPRDChange: nationalQ1
      ? nationalQ2.Nurse_Assistant_HPRD - nationalQ1.Nurse_Assistant_HPRD
      : 0,
    contractPercentChange: (nationalQ1 && nationalQ1.Contract_Percentage !== undefined && nationalQ2.Contract_Percentage !== undefined)
      ? nationalQ2.Contract_Percentage - nationalQ1.Contract_Percentage
      : 0,
  };
  
  console.log('[USA] Trends calculated:', trends);

  // Section 7: Movers - State and Region movers Q1 to Q2 (excluding PR)
  // statesQ2ExcludingPR already declared above, reuse it
  const statesQ1ExcludingPR = stateDataQ1.filter(s => s.STATE !== 'PR');
  const stateMapQ1 = new Map(statesQ1ExcludingPR.map(s => [s.STATE, s]));
  
  const stateMovers: StateChange[] = [];
  for (const stateQ2 of statesQ2ExcludingPR) {
    const stateQ1 = stateMapQ1.get(stateQ2.STATE);
    if (stateQ1) {
      const change = stateQ2.Total_Nurse_HPRD - stateQ1.Total_Nurse_HPRD;
      const directCareChange = stateQ2.Nurse_Care_HPRD - stateQ1.Nurse_Care_HPRD;
      const rnHPRDChange = stateQ2.RN_HPRD - stateQ1.RN_HPRD;
      
      stateMovers.push({
        state: stateQ2.STATE,
        stateName: getStateFullName(stateQ2.STATE),
        change,
        q1Value: stateQ1.Total_Nurse_HPRD,
        q2Value: stateQ2.Total_Nurse_HPRD,
        directCareChange,
        q1DirectCare: stateQ1.Nurse_Care_HPRD,
        q2DirectCare: stateQ2.Nurse_Care_HPRD,
        rnHPRDChange,
        q1RNHPRD: stateQ1.RN_HPRD,
        q2RNHPRD: stateQ2.RN_HPRD,
        link: createStateLink(stateQ2.STATE),
      });
    }
  }

  // Region movers
  const regionMapQ1 = new Map(regionDataQ1.map(r => [r.REGION_NUMBER, r]));
  const regionMovers: StateChange[] = [];
  for (const regionQ2 of regionDataQ2) {
    const regionQ1 = regionMapQ1.get(regionQ2.REGION_NUMBER);
    if (regionQ1) {
      const change = regionQ2.Total_Nurse_HPRD - regionQ1.Total_Nurse_HPRD;
      const directCareChange = regionQ2.Nurse_Care_HPRD - regionQ1.Nurse_Care_HPRD;
      const rnHPRDChange = regionQ2.RN_HPRD - regionQ1.RN_HPRD;
      
      regionMovers.push({
        state: regionQ2.REGION_NAME || `Region ${regionQ2.REGION_NUMBER}`,
        change,
        q1Value: regionQ1.Total_Nurse_HPRD,
        q2Value: regionQ2.Total_Nurse_HPRD,
        directCareChange,
        q1DirectCare: regionQ1.Nurse_Care_HPRD,
        q2DirectCare: regionQ2.Nurse_Care_HPRD,
        rnHPRDChange,
        q1RNHPRD: regionQ1.RN_HPRD,
        q2RNHPRD: regionQ2.RN_HPRD,
        link: `/wrapped/region${regionQ2.REGION_NUMBER}`,
      });
    }
  }

  // Combine state and region movers
  const allMovers = [...stateMovers, ...regionMovers];

  const risersByHPRD = [...allMovers]
    .sort((a, b) => b.change - a.change)
    .slice(0, 5);
  
  const declinersByHPRD = [...allMovers]
    .sort((a, b) => a.change - b.change)
    .slice(0, 5);

  const risersByDirectCare = [...allMovers]
    .sort((a, b) => (b.directCareChange || 0) - (a.directCareChange || 0))
    .slice(0, 5);

  const declinersByDirectCare = [...allMovers]
    .sort((a, b) => (a.directCareChange || 0) - (b.directCareChange || 0))
    .slice(0, 5);

  const risersByRNHPRD = [...allMovers]
    .sort((a, b) => (b.rnHPRDChange || 0) - (a.rnHPRDChange || 0))
    .slice(0, 5);

  const declinersByRNHPRD = [...allMovers]
    .sort((a, b) => (a.rnHPRDChange || 0) - (b.rnHPRDChange || 0))
    .slice(0, 5);

  // Ownership breakdown for USA - use all provider info Q2 with median HPRD
  const ownershipData = providerInfoQ2.filter(p => p.ownership_type && p.ownership_type.trim().length > 0);
  const ownership = calculateOwnershipBreakdownWithStaffing(ownershipData, facilityQ2);

  // Calculate count of states with minimum >= 2.00 HPRD (including ranges where max >= 2.00)
  let statesWithMinAbove2HPRD = 0;
  if (stateStandards) {
    for (const standard of stateStandards.values()) {
      // Include states where min >= 2.00 OR max >= 2.00 (for ranges like Kansas 1.91-2.06)
      if (standard.Min_Staffing >= 2.0 || (standard.Max_Staffing && standard.Max_Staffing >= 2.0)) {
        statesWithMinAbove2HPRD++;
      }
    }
  }

  return {
    scope: 'usa',
    identifier: 'usa',
    name: 'United States',
    facilityCount,
    avgDailyResidents,
    totalHPRD,
    directCareHPRD,
    rnHPRD,
    rnDirectCareHPRD,
    nurseAideHPRD,
    medianHPRD,
    rankings,
    ownership, // Add ownership for USA
    extremes: {
      lowestByHPRD,
      lowestByPercentExpected,
      highestByHPRD,
      highestByPercentExpected,
      topStatesByHPRD,
      bottomStatesByHPRD,
      topStatesByDirectCare,
      bottomStatesByDirectCare,
      topRegionsByHPRD,
      bottomRegionsByHPRD,
      topRegionsByDirectCare,
      bottomRegionsByDirectCare,
    },
    sff: {
      currentSFFs: sffCount,
      candidates: candidatesCount,
      graduates: graduatesCount || 0,
      inactive: inactiveCount || 0,
      newThisQuarter: newSFFFacilities,
    },
    trends,
    movers: {
      risersByHPRD,
      risersByDirectCare,
      risersByRNHPRD,
      declinersByHPRD,
      declinersByDirectCare,
      declinersByRNHPRD,
    },
    statesWithMinAbove2HPRD,
  };
}

/**
 * Process data for State scope
 */
function processStateData(
  stateQ2: StateQuarterlyRow | null,
  stateQ1: StateQuarterlyRow | null,
  facilityQ2: FacilityLiteRow[],
  facilityQ1: FacilityLiteRow[],
  providerInfoQ2: ProviderInfoRow[],
  _providerInfoQ1: ProviderInfoRow[],
  stateDataQ2: StateQuarterlyRow[],
  _stateDataQ1: StateQuarterlyRow[],
  _regionDataQ2: RegionQuarterlyRow[],
  _regionDataQ1: RegionQuarterlyRow[],
  stateCode: string,
  stateMinimum?: StateMinimum,
  sffData?: SFFData | null
): PBJWrappedData {
  if (!stateQ2) {
    throw new Error(`State Q2 data not available for ${stateCode}`);
  }

  // State abbreviation to full name mapping
  const STATE_ABBR_TO_NAME: Record<string, string> = {
    'al': 'Alabama', 'ak': 'Alaska', 'az': 'Arizona', 'ar': 'Arkansas', 'ca': 'California',
    'co': 'Colorado', 'ct': 'Connecticut', 'de': 'Delaware', 'fl': 'Florida', 'ga': 'Georgia',
    'hi': 'Hawaii', 'id': 'Idaho', 'il': 'Illinois', 'in': 'Indiana', 'ia': 'Iowa',
    'ks': 'Kansas', 'ky': 'Kentucky', 'la': 'Louisiana', 'me': 'Maine', 'md': 'Maryland',
    'ma': 'Massachusetts', 'mi': 'Michigan', 'mn': 'Minnesota', 'ms': 'Mississippi', 'mo': 'Missouri',
    'mt': 'Montana', 'ne': 'Nebraska', 'nv': 'Nevada', 'nh': 'New Hampshire', 'nj': 'New Jersey',
    'nm': 'New Mexico', 'ny': 'New York', 'nc': 'North Carolina', 'nd': 'North Dakota', 'oh': 'Ohio',
    'ok': 'Oklahoma', 'or': 'Oregon', 'pa': 'Pennsylvania', 'ri': 'Rhode Island', 'sc': 'South Carolina',
    'sd': 'South Dakota', 'tn': 'Tennessee', 'tx': 'Texas', 'ut': 'Utah', 'vt': 'Vermont',
    'va': 'Virginia', 'wa': 'Washington', 'wv': 'West Virginia', 'wi': 'Wisconsin', 'wy': 'Wyoming',
    'dc': 'District of Columbia'
  };

  function getStateFullName(abbr: string): string {
    return STATE_ABBR_TO_NAME[abbr.toLowerCase()] || abbr.toUpperCase();
  }

  const stateName = getStateFullName(stateCode);
  const providerInfoLookupQ2 = createProviderInfoLookup(providerInfoQ2);

  // Filter facilities by state
  const stateFacilitiesQ2 = facilityQ2.filter(f => f.STATE === stateCode);
  const stateFacilitiesQ1 = facilityQ1.filter(f => f.STATE === stateCode);
  const stateProviderInfoQ2 = providerInfoQ2.filter(p => p.STATE === stateCode);

  // Section 2: Basics
  const facilityCount = stateQ2.facility_count;
  const avgDailyResidents = stateQ2.avg_days_reported > 0
    ? stateQ2.total_resident_days / stateQ2.avg_days_reported
    : stateQ2.avg_daily_census * facilityCount;
  const totalHPRD = stateQ2.Total_Nurse_HPRD;
  const directCareHPRD = stateQ2.Nurse_Care_HPRD;
  const rnHPRD = stateQ2.RN_HPRD;
  const rnDirectCareHPRD = stateQ2.RN_Care_HPRD;

  // Calculate median HPRD from facilities
  const allHPRDs = stateFacilitiesQ2.map(f => f.Total_Nurse_HPRD).sort((a, b) => a - b);
  const medianHPRD = allHPRDs.length > 0 
    ? allHPRDs[Math.floor(allHPRDs.length / 2)]
    : 0;

  // Section 3: Rankings - rank this state among all states (excluding PR)
  const statesQ2ExcludingPR = stateDataQ2.filter(s => s.STATE !== 'PR');
  const sortedStatesByHPRD = [...statesQ2ExcludingPR].sort((a, b) => b.Total_Nurse_HPRD - a.Total_Nurse_HPRD);
  const stateRankByHPRD = sortedStatesByHPRD.findIndex(s => s.STATE === stateCode) + 1;
  const totalHPRDPercentile = statesQ2ExcludingPR.length > 0
    ? Math.round(((statesQ2ExcludingPR.length - stateRankByHPRD + 1) / statesQ2ExcludingPR.length) * 100)
    : 0;

  const sortedStatesByDirectCare = [...statesQ2ExcludingPR].sort((a, b) => b.Nurse_Care_HPRD - a.Nurse_Care_HPRD);
  const stateRankByDirectCare = sortedStatesByDirectCare.findIndex(s => s.STATE === stateCode) + 1;
  const directCareHPRDPercentile = statesQ2ExcludingPR.length > 0
    ? Math.round(((statesQ2ExcludingPR.length - stateRankByDirectCare + 1) / statesQ2ExcludingPR.length) * 100)
    : 0;

  const sortedStatesByRN = [...statesQ2ExcludingPR].sort((a, b) => b.RN_HPRD - a.RN_HPRD);
  const stateRankByRN = sortedStatesByRN.findIndex(s => s.STATE === stateCode) + 1;
  const rnHPRDPercentile = statesQ2ExcludingPR.length > 0
    ? Math.round(((statesQ2ExcludingPR.length - stateRankByRN + 1) / statesQ2ExcludingPR.length) * 100)
    : 0;

  const rankings = {
    totalHPRDRank: stateRankByHPRD,
    totalHPRDPercentile,
    directCareHPRDRank: stateRankByDirectCare,
    directCareHPRDPercentile,
    rnHPRDRank: stateRankByRN,
    rnHPRDPercentile,
  };

  // Section 4: Extremes - Top/Bottom Facilities in State
  const facilitiesWithInfoQ2 = stateFacilitiesQ2.map(f => {
    const info = providerInfoLookupQ2.get(f.PROVNUM);
    return { facility: f, info };
  }).filter(f => f.info);

  const sortedByHPRD = [...facilitiesWithInfoQ2].sort((a, b) => 
    a.facility.Total_Nurse_HPRD - b.facility.Total_Nurse_HPRD
  );
  
  const lowestByHPRD: Facility[] = sortedByHPRD.slice(0, 5).map(({ facility }) => ({
    provnum: facility.PROVNUM,
    name: toTitleCase(facility.PROVNAME),
    state: facility.STATE,
    value: facility.Total_Nurse_HPRD,
    link: createFacilityLink(facility.PROVNUM),
  }));

  const highestByHPRD: Facility[] = sortedByHPRD.slice(-5).reverse().map(({ facility }) => ({
    provnum: facility.PROVNUM,
    name: toTitleCase(facility.PROVNAME),
    state: facility.STATE,
    value: facility.Total_Nurse_HPRD,
    link: createFacilityLink(facility.PROVNUM),
  }));

  // Lowest/Highest by % of expected (case-mix adjusted)
  const withPercentExpected = facilitiesWithInfoQ2
    .map(({ facility, info }) => {
      const caseMix = info?.case_mix_total_nurse_hrs_per_resident_per_day;
      if (!caseMix || caseMix === 0) return null;
      const percentExpected = (facility.Total_Nurse_HPRD / caseMix) * 100;
      return { facility, info, percentExpected };
    })
    .filter((f): f is NonNullable<typeof f> => f !== null);

  const sortedByPercent = [...withPercentExpected].sort((a, b) => 
    a.percentExpected - b.percentExpected
  );

  const lowestByPercentExpected: Facility[] = sortedByPercent.slice(0, 5).map(({ facility, percentExpected }) => ({
    provnum: facility.PROVNUM,
    name: toTitleCase(facility.PROVNAME),
    state: facility.STATE,
    value: percentExpected,
    link: createFacilityLink(facility.PROVNUM),
  }));

  const highestByPercentExpected: Facility[] = sortedByPercent.slice(-5).reverse().map(({ facility, percentExpected }) => ({
    provnum: facility.PROVNUM,
    name: toTitleCase(facility.PROVNAME),
    state: facility.STATE,
    value: percentExpected,
    link: createFacilityLink(facility.PROVNUM),
  }));

  // Section 5: SFF
  let sffCount = 0;
  let candidatesCount = 0;
  let graduatesCount = 0;
  let inactiveCount = 0;
  let newSFFFacilities: Facility[] = [];
  
  if (sffData && sffData.facilities) {
    // Filter SFF facilities by state code (case-insensitive matching)
    const stateCodeUpper = stateCode.toUpperCase();
    const stateSFFFacilities = sffData.facilities.filter(f => 
      f.state && f.state.toUpperCase() === stateCodeUpper && f.category === 'SFF'
    );
    const stateCandidateFacilities = sffData.facilities.filter(f => 
      f.state && f.state.toUpperCase() === stateCodeUpper && f.category === 'Candidate'
    );
    const stateGraduateFacilities = sffData.facilities.filter(f => 
      f.state && f.state.toUpperCase() === stateCodeUpper && f.category === 'Graduate'
    );
    const stateInactiveFacilities = sffData.facilities.filter(f => 
      f.state && f.state.toUpperCase() === stateCodeUpper && f.category === 'Terminated'
    );
    sffCount = stateSFFFacilities.length;
    candidatesCount = stateCandidateFacilities.length;
    graduatesCount = stateGraduateFacilities.length;
    inactiveCount = stateInactiveFacilities.length;
    
    // Get new SFF facilities based on months_as_sff (facilities with <= 3 months are considered new)
    const newSFF = stateSFFFacilities.filter(f => 
      f.months_as_sff !== null && 
      f.months_as_sff !== undefined && 
      f.months_as_sff <= 3
    );
    const shuffledNewSFF = [...newSFF].sort(() => Math.random() - 0.5);
    // Create a map for efficient lookup
    const stateFacilityMapQ2 = new Map(stateFacilitiesQ2.map(f => [normalizeProviderNumber(f.PROVNUM), f]));
    newSFFFacilities = shuffledNewSFF.slice(0, 5).map(f => {
      const normalizedProviderNum = normalizeProviderNumber(f.provider_number);
      const facility = stateFacilityMapQ2.get(normalizedProviderNum);
      return {
        provnum: normalizedProviderNum,
        name: toTitleCase(f.facility_name || ''),
        state: f.state || stateCode,
        value: facility?.Total_Nurse_HPRD || 0,
        link: createFacilityLink(normalizedProviderNum),
      };
    });
  } else {
    const sffQ2 = stateProviderInfoQ2.filter(p => {
      if (!p.sff_status) return false;
      const status = p.sff_status.trim().toUpperCase();
      return status === 'SFF' || status === 'SPECIAL FOCUS FACILITY' || status.includes('SFF');
    });
    const candidatesQ2 = stateProviderInfoQ2.filter(p => {
      if (!p.sff_status) return false;
      const status = p.sff_status.trim().toUpperCase();
      return status === 'SFF CANDIDATE' || status === 'CANDIDATE' || (status.includes('CANDIDATE') && !status.includes('SFF'));
    });
    
    sffCount = sffQ2.length;
    candidatesCount = candidatesQ2.length;
  
    // No new SFF determination available without sffData, so use empty array
    newSFFFacilities = [];
  }

  // Section 6: Trends
  const trends = {
    totalHPRDChange: stateQ1 
      ? stateQ2.Total_Nurse_HPRD - stateQ1.Total_Nurse_HPRD 
      : 0,
    directCareHPRDChange: stateQ1
      ? stateQ2.Nurse_Care_HPRD - stateQ1.Nurse_Care_HPRD
      : 0,
    rnHPRDChange: stateQ1
      ? stateQ2.RN_HPRD - stateQ1.RN_HPRD
      : 0,
    contractPercentChange: (stateQ1 && stateQ1.Contract_Percentage !== undefined && stateQ2.Contract_Percentage !== undefined)
      ? stateQ2.Contract_Percentage - stateQ1.Contract_Percentage
      : 0,
  };

  // Section 7: Movers - Facility changes Q1 to Q2
  const facilityMapQ1 = new Map(stateFacilitiesQ1.map(f => [f.PROVNUM, f]));
  const facilityMovers: FacilityChange[] = [];
  
  for (const facilityQ2Item of stateFacilitiesQ2) {
    const facilityQ1Item = facilityMapQ1.get(facilityQ2Item.PROVNUM);
    if (facilityQ1Item) {
      const change = facilityQ2Item.Total_Nurse_HPRD - facilityQ1Item.Total_Nurse_HPRD;
      const directCareChange = facilityQ2Item.Nurse_Care_HPRD - facilityQ1Item.Nurse_Care_HPRD;
      const rnHPRDChange = facilityQ2Item.Total_RN_HPRD - facilityQ1Item.Total_RN_HPRD;
      const providerInfo = providerInfoLookupQ2.get(facilityQ2Item.PROVNUM);
      
      facilityMovers.push({
        provnum: facilityQ2Item.PROVNUM,
        name: toTitleCase(facilityQ2Item.PROVNAME),
        city: providerInfo?.CITY ? capitalizeCity(providerInfo.CITY) : undefined,
        state: facilityQ2Item.STATE,
        value: facilityQ2Item.Total_Nurse_HPRD,
        change,
        q1Value: facilityQ1Item.Total_Nurse_HPRD,
        q2Value: facilityQ2Item.Total_Nurse_HPRD,
        directCareChange,
        q1DirectCare: facilityQ1Item.Nurse_Care_HPRD,
        q2DirectCare: facilityQ2Item.Nurse_Care_HPRD,
        rnHPRDChange,
        q1RNHPRD: facilityQ1Item.Total_RN_HPRD,
        q2RNHPRD: facilityQ2Item.Total_RN_HPRD,
        link: createFacilityLink(facilityQ2Item.PROVNUM),
      });
    }
  }

  const risersByHPRD = [...facilityMovers]
    .sort((a, b) => b.change - a.change)
    .slice(0, 5);
  
  const declinersByHPRD = [...facilityMovers]
    .sort((a, b) => a.change - b.change)
    .slice(0, 5);

  const risersByDirectCare = [...facilityMovers]
    .sort((a, b) => (b.directCareChange || 0) - (a.directCareChange || 0))
    .slice(0, 5);

  const declinersByDirectCare = [...facilityMovers]
    .sort((a, b) => (a.directCareChange || 0) - (b.directCareChange || 0))
    .slice(0, 5);

  const risersByRNHPRD = [...facilityMovers]
    .sort((a, b) => (b.rnHPRDChange || 0) - (a.rnHPRDChange || 0))
    .slice(0, 5);

  const declinersByRNHPRD = [...facilityMovers]
    .sort((a, b) => (a.rnHPRDChange || 0) - (b.rnHPRDChange || 0))
    .slice(0, 5);

  // Ownership breakdown
  const ownership = calculateOwnershipBreakdownWithStaffing(stateProviderInfoQ2, stateFacilitiesQ2);

  // Compliance metrics (if stateMinimum is provided)
  let compliance;
  if (stateMinimum) {
    const facilitiesBelowMinimum = stateFacilitiesQ2.filter(f => f.Total_Nurse_HPRD < stateMinimum.minHPRD).length;
    compliance = {
      facilitiesBelowTotalMinimum: facilitiesBelowMinimum,
      facilitiesBelowTotalMinimumPercent: stateFacilitiesQ2.length > 0
        ? Math.round((facilitiesBelowMinimum / stateFacilitiesQ2.length) * 100)
        : 0,
    };
  }

  // Average ratings
  const ratings = stateProviderInfoQ2
    .map(p => {
      const rating = p.overall_rating ? parseFloat(p.overall_rating) : null;
      return rating !== null && !isNaN(rating) ? rating : null;
    })
    .filter((r): r is number => r !== null);
  const averageOverallRating = ratings.length > 0
    ? ratings.reduce((sum, r) => sum + r, 0) / ratings.length
    : undefined;

  // Spotlight facility - find a facility with interesting characteristics
  let spotlightFacility;
  const spotlightCandidates = facilitiesWithInfoQ2
    .map(({ facility, info }) => {
      const caseMix = info?.case_mix_total_nurse_hrs_per_resident_per_day || 0;
      const facilityQ1 = facilityMapQ1.get(facility.PROVNUM);
      const qoqChange = facilityQ1 ? facility.Total_Nurse_HPRD - facilityQ1.Total_Nurse_HPRD : 0;
      const gapVsExpected = caseMix > 0 ? facility.Total_Nurse_HPRD - caseMix : 0;
      
      return {
        facility,
        info,
        gapVsExpected,
        qoqChange,
      };
    })
    .filter(f => {
      if (!f.info || f.facility.Total_Nurse_HPRD <= 0) return false;
      // Filter out facilities with census < 50
      const census = f.facility.Census || f.info.avg_residents_per_day || 0;
      return census >= 50;
    })
    .filter(f => {
      // Only include facilities where staffing decreased (negative qoqChange) or has significant gap
      // This ensures we highlight facilities with problems, not improvements
      return f.qoqChange < 0 || f.gapVsExpected < -0.5;
    })
    .sort((a, b) => {
      // Prefer facilities with significant negative gaps (below expected) and negative changes (declined)
      // Weight negative qoqChange more heavily since we want to highlight declines
      const scoreA = Math.abs(a.gapVsExpected < 0 ? a.gapVsExpected : 0) + (a.qoqChange < 0 ? Math.abs(a.qoqChange) * 2 : 0);
      const scoreB = Math.abs(b.gapVsExpected < 0 ? b.gapVsExpected : 0) + (b.qoqChange < 0 ? Math.abs(b.qoqChange) * 2 : 0);
      return scoreB - scoreA;
    });

  if (spotlightCandidates.length > 0) {
    const candidate = spotlightCandidates[0];
    const facilityQ1Item = facilityMapQ1.get(candidate.facility.PROVNUM);
    const census = candidate.facility.Census || candidate.info?.avg_residents_per_day || 0;
    spotlightFacility = {
      provnum: candidate.facility.PROVNUM,
      name: toTitleCase(candidate.facility.PROVNAME),
      city: capitalizeCity(candidate.info?.CITY),
      state: candidate.facility.STATE,
      totalHPRD: candidate.facility.Total_Nurse_HPRD,
      caseMixExpectedHPRD: candidate.info?.case_mix_total_nurse_hrs_per_resident_per_day || 0,
      gapVsExpected: candidate.gapVsExpected,
      qoqChange: facilityQ1Item ? candidate.facility.Total_Nurse_HPRD - facilityQ1Item.Total_Nurse_HPRD : candidate.qoqChange,
      rnHPRD: candidate.facility.Total_RN_HPRD,
      cnaHPRD: candidate.facility.Total_Nurse_HPRD - candidate.facility.Total_RN_HPRD,
      contractPercent: candidate.facility.Contract_Percentage,
      census: Math.round(census),
      sffStatus: candidate.info?.sff_status,
      ownershipType: simplifyOwnershipType(candidate.info?.ownership_type),
      link: createFacilityLink(candidate.facility.PROVNUM),
    };
  }

  return {
    scope: 'state',
    identifier: stateCode.toLowerCase(),
    name: stateName,
    stateMinimum,
    facilityCount,
    avgDailyResidents,
    totalHPRD,
    directCareHPRD,
    rnHPRD,
    rnDirectCareHPRD,
    medianHPRD,
    rankings,
    ownership,
    extremes: {
      lowestByHPRD,
      lowestByPercentExpected,
      highestByHPRD,
      highestByPercentExpected,
    },
    sff: {
      currentSFFs: sffCount,
      candidates: candidatesCount,
      graduates: graduatesCount || 0,
      inactive: inactiveCount || 0,
      newThisQuarter: newSFFFacilities,
    },
    trends,
    movers: {
      risersByHPRD,
      risersByDirectCare,
      risersByRNHPRD,
      declinersByHPRD,
      declinersByDirectCare,
      declinersByRNHPRD,
    },
    compliance,
    averageOverallRating,
    spotlightFacility,
  };
}

/**
 * Process data for Region scope
 */
function processRegionData(
  regionQ2: RegionQuarterlyRow | null,
  regionQ1: RegionQuarterlyRow | null,
  facilityQ2: FacilityLiteRow[],
  facilityQ1: FacilityLiteRow[],
  providerInfoQ2: ProviderInfoRow[],
  _providerInfoQ1: ProviderInfoRow[],
  stateDataQ2: StateQuarterlyRow[],
  _stateDataQ1: StateQuarterlyRow[],
  regionDataQ2: RegionQuarterlyRow[],
  _regionDataQ1: RegionQuarterlyRow[],
  regionNumber: number,
  sffData?: SFFData | null,
  regionStateMapping?: Map<number, Set<string>>
): PBJWrappedData {
  if (!regionQ2) {
    throw new Error(`Region Q2 data not available for region ${regionNumber}`);
  }

  const regionName = regionQ2.REGION_NAME || `Region ${regionNumber}`;
  const providerInfoLookupQ2 = createProviderInfoLookup(providerInfoQ2);
  
  // State abbreviation to full name mapping
  const STATE_ABBR_TO_NAME: Record<string, string> = {
    'al': 'Alabama', 'ak': 'Alaska', 'az': 'Arizona', 'ar': 'Arkansas', 'ca': 'California',
    'co': 'Colorado', 'ct': 'Connecticut', 'de': 'Delaware', 'fl': 'Florida', 'ga': 'Georgia',
    'hi': 'Hawaii', 'id': 'Idaho', 'il': 'Illinois', 'in': 'Indiana', 'ia': 'Iowa',
    'ks': 'Kansas', 'ky': 'Kentucky', 'la': 'Louisiana', 'me': 'Maine', 'md': 'Maryland',
    'ma': 'Massachusetts', 'mi': 'Michigan', 'mn': 'Minnesota', 'ms': 'Mississippi', 'mo': 'Missouri',
    'mt': 'Montana', 'ne': 'Nebraska', 'nv': 'Nevada', 'nh': 'New Hampshire', 'nj': 'New Jersey',
    'nm': 'New Mexico', 'ny': 'New York', 'nc': 'North Carolina', 'nd': 'North Dakota', 'oh': 'Ohio',
    'ok': 'Oklahoma', 'or': 'Oregon', 'pa': 'Pennsylvania', 'pr': 'Puerto Rico', 'ri': 'Rhode Island', 'sc': 'South Carolina',
    'sd': 'South Dakota', 'tn': 'Tennessee', 'tx': 'Texas', 'ut': 'Utah', 'vt': 'Vermont',
    'va': 'Virginia', 'wa': 'Washington', 'wv': 'West Virginia', 'wi': 'Wisconsin', 'wy': 'Wyoming',
    'dc': 'District of Columbia', 'vi': 'Virgin Islands'
  };
  
  function getStateFullName(abbr: string): string {
    return STATE_ABBR_TO_NAME[abbr.toLowerCase()] || abbr.toUpperCase();
  }

  // Filter facilities by region - need to get state codes for this region
  // We'll filter facilities by checking if their state is in the region
  // For now, we'll use the facility data that was pre-filtered by region in dataLoader
  const regionFacilitiesQ2 = facilityQ2; // Already filtered in dataLoader
  const regionFacilitiesQ1 = facilityQ1; // Already filtered in dataLoader
  const regionProviderInfoQ2 = providerInfoQ2; // Already filtered in dataLoader

  // Section 2: Basics
  const facilityCount = regionQ2.facility_count;
  const avgDailyResidents = regionQ2.avg_days_reported > 0
    ? regionQ2.total_resident_days / regionQ2.avg_days_reported
    : regionQ2.avg_daily_census * facilityCount;
  const totalHPRD = regionQ2.Total_Nurse_HPRD;
  const directCareHPRD = regionQ2.Nurse_Care_HPRD;
  const rnHPRD = regionQ2.RN_HPRD;
  const rnDirectCareHPRD = regionQ2.RN_Care_HPRD;

  // Calculate median HPRD from facilities
  const allHPRDs = regionFacilitiesQ2.map(f => f.Total_Nurse_HPRD).sort((a, b) => a - b);
  const medianHPRD = allHPRDs.length > 0 
    ? allHPRDs[Math.floor(allHPRDs.length / 2)]
    : 0;

  // Section 3: Rankings - rank this region among all regions
  const sortedRegionsByHPRD = [...regionDataQ2].sort((a, b) => b.Total_Nurse_HPRD - a.Total_Nurse_HPRD);
  const regionRankByHPRD = sortedRegionsByHPRD.findIndex(r => r.REGION_NUMBER === regionNumber) + 1;
  const totalHPRDPercentile = regionDataQ2.length > 0
    ? Math.round(((regionDataQ2.length - regionRankByHPRD + 1) / regionDataQ2.length) * 100)
    : 0;

  const sortedRegionsByDirectCare = [...regionDataQ2].sort((a, b) => b.Nurse_Care_HPRD - a.Nurse_Care_HPRD);
  const regionRankByDirectCare = sortedRegionsByDirectCare.findIndex(r => r.REGION_NUMBER === regionNumber) + 1;
  const directCareHPRDPercentile = regionDataQ2.length > 0
    ? Math.round(((regionDataQ2.length - regionRankByDirectCare + 1) / regionDataQ2.length) * 100)
    : 0;

  const sortedRegionsByRN = [...regionDataQ2].sort((a, b) => b.RN_HPRD - a.RN_HPRD);
  const regionRankByRN = sortedRegionsByRN.findIndex(r => r.REGION_NUMBER === regionNumber) + 1;
  const rnHPRDPercentile = regionDataQ2.length > 0
    ? Math.round(((regionDataQ2.length - regionRankByRN + 1) / regionDataQ2.length) * 100)
    : 0;

  const rankings = {
    totalHPRDRank: regionRankByHPRD,
    totalHPRDPercentile,
    directCareHPRDRank: regionRankByDirectCare,
    directCareHPRDPercentile,
    rnHPRDRank: regionRankByRN,
    rnHPRDPercentile,
  };

  // Section 4: Extremes - Top/Bottom Facilities in Region
  const facilitiesWithInfoQ2 = regionFacilitiesQ2.map(f => {
    const info = providerInfoLookupQ2.get(f.PROVNUM);
    return { facility: f, info };
  }).filter(f => f.info);

  const sortedByHPRD = [...facilitiesWithInfoQ2].sort((a, b) => 
    a.facility.Total_Nurse_HPRD - b.facility.Total_Nurse_HPRD
  );
  
  const lowestByHPRD: Facility[] = sortedByHPRD.slice(0, 5).map(({ facility }) => ({
    provnum: facility.PROVNUM,
    name: toTitleCase(facility.PROVNAME),
    state: facility.STATE,
    value: facility.Total_Nurse_HPRD,
    link: createFacilityLink(facility.PROVNUM),
  }));

  const highestByHPRD: Facility[] = sortedByHPRD.slice(-5).reverse().map(({ facility }) => ({
    provnum: facility.PROVNUM,
    name: toTitleCase(facility.PROVNAME),
    state: facility.STATE,
    value: facility.Total_Nurse_HPRD,
    link: createFacilityLink(facility.PROVNUM),
  }));

  // Lowest/Highest by % of expected (case-mix adjusted)
  const withPercentExpected = facilitiesWithInfoQ2
    .map(({ facility, info }) => {
      const caseMix = info?.case_mix_total_nurse_hrs_per_resident_per_day;
      if (!caseMix || caseMix === 0) return null;
      const percentExpected = (facility.Total_Nurse_HPRD / caseMix) * 100;
      return { facility, info, percentExpected };
    })
    .filter((f): f is NonNullable<typeof f> => f !== null);

  const sortedByPercent = [...withPercentExpected].sort((a, b) => 
    a.percentExpected - b.percentExpected
  );

  const lowestByPercentExpected: Facility[] = sortedByPercent.slice(0, 5).map(({ facility, percentExpected }) => ({
    provnum: facility.PROVNUM,
    name: toTitleCase(facility.PROVNAME),
    state: facility.STATE,
    value: percentExpected,
    link: createFacilityLink(facility.PROVNUM),
  }));

  const highestByPercentExpected: Facility[] = sortedByPercent.slice(-5).reverse().map(({ facility, percentExpected }) => ({
    provnum: facility.PROVNUM,
    name: toTitleCase(facility.PROVNAME),
    state: facility.STATE,
    value: percentExpected,
    link: createFacilityLink(facility.PROVNUM),
  }));

  // Section 5: SFF
  let sffCount = 0;
  let candidatesCount = 0;
  let graduatesCount = 0;
  let inactiveCount = 0;
  let newSFFFacilities: Facility[] = [];
  
  if (sffData && sffData.facilities) {
    // Get state codes for this region - use regionStateMapping if available (matches SFF page logic)
    // Otherwise fall back to deriving from facilities
    let regionStateCodes: Set<string>;
    if (regionStateMapping) {
      const regionStates = regionStateMapping.get(regionNumber) || new Set<string>();
      regionStateCodes = new Set(Array.from(regionStates).map(s => s.toUpperCase()));
    } else {
      regionStateCodes = new Set(regionFacilitiesQ2.map(f => f.STATE.toUpperCase()));
    }
    const regionSFFFacilities = sffData.facilities.filter(f => 
      f.state && regionStateCodes.has(f.state.toUpperCase()) && f.category === 'SFF'
    );
    const regionCandidateFacilities = sffData.facilities.filter(f => 
      f.state && regionStateCodes.has(f.state.toUpperCase()) && f.category === 'Candidate'
    );
    const regionGraduateFacilities = sffData.facilities.filter(f => 
      f.state && regionStateCodes.has(f.state.toUpperCase()) && f.category === 'Graduate'
    );
    const regionInactiveFacilities = sffData.facilities.filter(f => 
      f.state && regionStateCodes.has(f.state.toUpperCase()) && f.category === 'Terminated'
    );
    sffCount = regionSFFFacilities.length;
    candidatesCount = regionCandidateFacilities.length;
    graduatesCount = regionGraduateFacilities.length;
    inactiveCount = regionInactiveFacilities.length;
    
    // Get new SFF facilities based on months_as_sff (facilities with <= 3 months are considered new)
    const newSFF = regionSFFFacilities.filter(f => 
      f.months_as_sff !== null && 
      f.months_as_sff !== undefined && 
      f.months_as_sff <= 3
    );
    const shuffledNewSFF = [...newSFF].sort(() => Math.random() - 0.5);
    // Create a map for efficient lookup
    const regionFacilityMapQ2 = new Map(regionFacilitiesQ2.map(f => [normalizeProviderNumber(f.PROVNUM), f]));
    newSFFFacilities = shuffledNewSFF.slice(0, 5).map(f => {
      const normalizedProviderNum = normalizeProviderNumber(f.provider_number);
      const facility = regionFacilityMapQ2.get(normalizedProviderNum);
      return {
        provnum: normalizedProviderNum,
        name: toTitleCase(f.facility_name || ''),
        state: f.state || '',
        value: facility?.Total_Nurse_HPRD || 0,
        link: createFacilityLink(normalizedProviderNum),
      };
    });
  } else {
    const sffQ2 = regionProviderInfoQ2.filter(p => {
      if (!p.sff_status) return false;
      const status = p.sff_status.trim().toUpperCase();
      return status === 'SFF' || status === 'SPECIAL FOCUS FACILITY' || status.includes('SFF');
    });
    const candidatesQ2 = regionProviderInfoQ2.filter(p => {
      if (!p.sff_status) return false;
      const status = p.sff_status.trim().toUpperCase();
      return status === 'SFF CANDIDATE' || status === 'CANDIDATE' || (status.includes('CANDIDATE') && !status.includes('SFF'));
    });
    
    sffCount = sffQ2.length;
    candidatesCount = candidatesQ2.length;
  
    // No new SFF determination available without sffData, so use empty array
    newSFFFacilities = [];
  }

  // Section 6: Trends
  // Debug logging before calculating trends
  if (!regionQ1) {
    console.warn(`[Region ${regionNumber}] Q1 data not found - trends will show 0.00. Looking for REGION_NUMBER: ${regionNumber}`);
  }
  const trends = {
    totalHPRDChange: regionQ1 
      ? regionQ2.Total_Nurse_HPRD - regionQ1.Total_Nurse_HPRD 
      : 0,
    directCareHPRDChange: regionQ1
      ? regionQ2.Nurse_Care_HPRD - regionQ1.Nurse_Care_HPRD
      : 0,
    rnHPRDChange: regionQ1
      ? regionQ2.RN_HPRD - regionQ1.RN_HPRD
      : 0,
    contractPercentChange: (regionQ1 && regionQ1.Contract_Percentage !== undefined && regionQ2.Contract_Percentage !== undefined)
      ? regionQ2.Contract_Percentage - regionQ1.Contract_Percentage
      : 0,
  };
  console.log(`[Region ${regionNumber}] Trends calculated:`, trends);

  // Section 7: Movers - Facility changes Q1 to Q2
  const facilityMapQ1 = new Map(regionFacilitiesQ1.map(f => [f.PROVNUM, f]));
  const facilityMovers: FacilityChange[] = [];
  
  for (const facilityQ2Item of regionFacilitiesQ2) {
    const facilityQ1Item = facilityMapQ1.get(facilityQ2Item.PROVNUM);
    if (facilityQ1Item) {
      const change = facilityQ2Item.Total_Nurse_HPRD - facilityQ1Item.Total_Nurse_HPRD;
      const directCareChange = facilityQ2Item.Nurse_Care_HPRD - facilityQ1Item.Nurse_Care_HPRD;
      const rnHPRDChange = facilityQ2Item.Total_RN_HPRD - facilityQ1Item.Total_RN_HPRD;
      
      facilityMovers.push({
        provnum: facilityQ2Item.PROVNUM,
        name: toTitleCase(facilityQ2Item.PROVNAME),
        state: facilityQ2Item.STATE,
        value: facilityQ2Item.Total_Nurse_HPRD,
        change,
        q1Value: facilityQ1Item.Total_Nurse_HPRD,
        q2Value: facilityQ2Item.Total_Nurse_HPRD,
        directCareChange,
        q1DirectCare: facilityQ1Item.Nurse_Care_HPRD,
        q2DirectCare: facilityQ2Item.Nurse_Care_HPRD,
        rnHPRDChange,
        q1RNHPRD: facilityQ1Item.Total_RN_HPRD,
        q2RNHPRD: facilityQ2Item.Total_RN_HPRD,
        link: createFacilityLink(facilityQ2Item.PROVNUM),
      });
    }
  }

  const risersByHPRD = [...facilityMovers]
    .sort((a, b) => b.change - a.change)
    .slice(0, 5);
  
  const declinersByHPRD = [...facilityMovers]
    .sort((a, b) => a.change - b.change)
    .slice(0, 5);

  const risersByDirectCare = [...facilityMovers]
    .sort((a, b) => (b.directCareChange || 0) - (a.directCareChange || 0))
    .slice(0, 5);

  const declinersByDirectCare = [...facilityMovers]
    .sort((a, b) => (a.directCareChange || 0) - (b.directCareChange || 0))
    .slice(0, 5);

  const risersByRNHPRD = [...facilityMovers]
    .sort((a, b) => (b.rnHPRDChange || 0) - (a.rnHPRDChange || 0))
    .slice(0, 5);

  const declinersByRNHPRD = [...facilityMovers]
    .sort((a, b) => (a.rnHPRDChange || 0) - (b.rnHPRDChange || 0))
    .slice(0, 5);

  // Ownership breakdown
  const ownership = calculateOwnershipBreakdownWithStaffing(regionProviderInfoQ2, regionFacilitiesQ2);

  // Average ratings
  const ratings = regionProviderInfoQ2
    .map(p => {
      const rating = p.overall_rating ? parseFloat(p.overall_rating) : null;
      return rating !== null && !isNaN(rating) ? rating : null;
    })
    .filter((r): r is number => r !== null);
  const averageOverallRating = ratings.length > 0
    ? ratings.reduce((sum, r) => sum + r, 0) / ratings.length
    : undefined;

  // Spotlight facility - find a facility with interesting characteristics
  let spotlightFacility;
  const spotlightCandidates = facilitiesWithInfoQ2
    .map(({ facility, info }) => {
      const caseMix = info?.case_mix_total_nurse_hrs_per_resident_per_day || 0;
      const facilityQ1 = facilityMapQ1.get(facility.PROVNUM);
      const qoqChange = facilityQ1 ? facility.Total_Nurse_HPRD - facilityQ1.Total_Nurse_HPRD : 0;
      const gapVsExpected = caseMix > 0 ? facility.Total_Nurse_HPRD - caseMix : 0;
      
      return {
        facility,
        info,
        gapVsExpected,
        qoqChange,
      };
    })
    .filter(f => {
      if (!f.info || f.facility.Total_Nurse_HPRD <= 0) return false;
      // Filter out facilities with census < 50
      const census = f.facility.Census || f.info.avg_residents_per_day || 0;
      return census >= 50;
    })
    .filter(f => {
      // Only include facilities where staffing decreased (negative qoqChange) or has significant gap
      // This ensures we highlight facilities with problems, not improvements
      return f.qoqChange < 0 || f.gapVsExpected < -0.5;
    })
    .sort((a, b) => {
      // Prefer facilities with significant negative gaps (below expected) and negative changes (declined)
      // Weight negative qoqChange more heavily since we want to highlight declines
      const scoreA = Math.abs(a.gapVsExpected < 0 ? a.gapVsExpected : 0) + (a.qoqChange < 0 ? Math.abs(a.qoqChange) * 2 : 0);
      const scoreB = Math.abs(b.gapVsExpected < 0 ? b.gapVsExpected : 0) + (b.qoqChange < 0 ? Math.abs(b.qoqChange) * 2 : 0);
      return scoreB - scoreA;
    });

  if (spotlightCandidates.length > 0) {
    const candidate = spotlightCandidates[0];
    const facilityQ1Item = facilityMapQ1.get(candidate.facility.PROVNUM);
    const census = candidate.facility.Census || candidate.info?.avg_residents_per_day || 0;
    
    // Simplify ownership type using helper function
    
    spotlightFacility = {
      provnum: candidate.facility.PROVNUM,
      name: toTitleCase(candidate.facility.PROVNAME),
      city: capitalizeCity(candidate.info?.CITY),
      state: candidate.facility.STATE,
      totalHPRD: candidate.facility.Total_Nurse_HPRD,
      caseMixExpectedHPRD: candidate.info?.case_mix_total_nurse_hrs_per_resident_per_day || 0,
      gapVsExpected: candidate.gapVsExpected,
      qoqChange: facilityQ1Item ? candidate.facility.Total_Nurse_HPRD - facilityQ1Item.Total_Nurse_HPRD : candidate.qoqChange,
      rnHPRD: candidate.facility.Total_RN_HPRD,
      cnaHPRD: candidate.facility.Total_Nurse_HPRD - candidate.facility.Total_RN_HPRD,
      contractPercent: candidate.facility.Contract_Percentage,
      census: Math.round(census),
      sffStatus: candidate.info?.sff_status,
      ownershipType: simplifyOwnershipType(candidate.info?.ownership_type),
      link: createFacilityLink(candidate.facility.PROVNUM),
    };
  }

  // Find highest and lowest HPRD states in this region (excluding PR and VI)
  let highestStateInRegion: { state: string; stateName: string; hprd: number } | undefined = undefined;
  let lowestStateInRegion: { state: string; stateName: string; hprd: number } | undefined = undefined;
  
  if (regionStateMapping && stateDataQ2.length > 0) {
    const regionStates = regionStateMapping.get(regionNumber);
    if (regionStates) {
      const regionStateCodes = new Set(Array.from(regionStates).map(s => s.toUpperCase()));
      const regionStatesData = stateDataQ2.filter(s => 
        regionStateCodes.has(s.STATE.toUpperCase()) && 
        s.STATE !== 'PR' && 
        s.STATE !== 'VI'
      );
      
      if (regionStatesData.length > 0) {
        const sortedByHPRD = [...regionStatesData].sort((a, b) => b.Total_Nurse_HPRD - a.Total_Nurse_HPRD);
        const highest = sortedByHPRD[0];
        const lowest = sortedByHPRD[sortedByHPRD.length - 1];
        
        highestStateInRegion = {
          state: highest.STATE,
          stateName: getStateFullName(highest.STATE),
          hprd: highest.Total_Nurse_HPRD,
        };
        
        lowestStateInRegion = {
          state: lowest.STATE,
          stateName: getStateFullName(lowest.STATE),
          hprd: lowest.Total_Nurse_HPRD,
        };
      }
    }
  }

  return {
    scope: 'region',
    identifier: `region${regionNumber}`,
    name: regionName,
    facilityCount,
    avgDailyResidents,
    totalHPRD,
    directCareHPRD,
    rnHPRD,
    rnDirectCareHPRD,
    medianHPRD,
    rankings,
    ownership,
    extremes: {
      lowestByHPRD,
      lowestByPercentExpected,
      highestByHPRD,
      highestByPercentExpected,
    },
    sff: {
      currentSFFs: sffCount,
      candidates: candidatesCount,
      graduates: graduatesCount || 0,
      inactive: inactiveCount || 0,
      newThisQuarter: newSFFFacilities,
    },
    trends,
    movers: {
      risersByHPRD,
      risersByDirectCare,
      risersByRNHPRD,
      declinersByHPRD,
      declinersByDirectCare,
      declinersByRNHPRD,
    },
    averageOverallRating,
    spotlightFacility,
    highestStateInRegion,
    lowestStateInRegion,
  };
}

/**
 * Main function to process wrapped data based on scope
 */
export function processWrappedData(
  scope: Scope,
  identifier: string,
  data: LoadedData
): PBJWrappedData {
  if (scope === 'usa') {
    return processUSAData(
      data.nationalData.q2,
      data.nationalData.q1,
      data.facilityData.q2 || [],
      data.facilityData.q1 || [],
      data.providerInfo.q2 || [],
      data.providerInfo.q1 || [],
      data.stateData.q2 || [],
      data.stateData.q1 || [],
      data.regionData.q2 || [],
      data.regionData.q1 || [],
      data.sffData,
      data.stateStandards
    );
  } else if (scope === 'state') {
    const stateCode = identifier.toUpperCase();
    const stateQ2 = data.stateData.q2?.find(s => s.STATE === stateCode) || null;
    const stateQ1 = data.stateData.q1?.find(s => s.STATE === stateCode) || null;
    
    // Calculate stateMinimum from stateStandards if available
    let stateMinimum: StateMinimum | undefined;
    if (data.stateStandards) {
      const stateStandard = data.stateStandards.get(stateCode.toLowerCase());
      if (stateStandard) {
        const minHPRD = stateStandard.Min_Staffing;
        const maxHPRD = stateStandard.Max_Staffing;
        const isRange = maxHPRD !== undefined && maxHPRD > minHPRD;
        stateMinimum = {
          minHPRD,
          maxHPRD: isRange ? maxHPRD : undefined,
          isRange,
          displayText: stateStandard.Display_Text || (isRange ? `${minHPRD.toFixed(2)}-${maxHPRD!.toFixed(2)} HPRD` : `${minHPRD.toFixed(2)} HPRD`),
        };
      }
    }
    
    return processStateData(
      stateQ2,
      stateQ1,
      data.facilityData.q2 || [],
      data.facilityData.q1 || [],
      data.providerInfo.q2 || [],
      data.providerInfo.q1 || [],
      data.stateData.q2 || [],
      data.stateData.q1 || [],
      data.regionData.q2 || [],
      data.regionData.q1 || [],
      stateCode,
      stateMinimum,
      data.sffData
    );
  } else if (scope === 'region') {
    const regionNumber = parseInt(identifier.replace(/^region/i, '').replace(/^-/, ''), 10);
    const regionQ2 = data.regionData.q2?.find(r => r.REGION_NUMBER === regionNumber) || null;
    const regionQ1 = data.regionData.q1?.find(r => r.REGION_NUMBER === regionNumber) || null;
    
    // Debug logging for region Q1 data
    console.log(`[Region ${regionNumber}] Q1 data check:`, {
      regionQ1Found: !!regionQ1,
      regionQ1TotalHPRD: regionQ1?.Total_Nurse_HPRD,
      regionQ2TotalHPRD: regionQ2?.Total_Nurse_HPRD,
      regionDataQ1Length: data.regionData.q1?.length || 0,
      regionDataQ2Length: data.regionData.q2?.length || 0,
    });
    return processRegionData(
      regionQ2,
      regionQ1,
      data.facilityData.q2 || [],
      data.facilityData.q1 || [],
      data.providerInfo.q2 || [],
      data.providerInfo.q1 || [],
      data.stateData.q2 || [],
      data.stateData.q1 || [],
      data.regionData.q2 || [],
      data.regionData.q1 || [],
      regionNumber,
      data.sffData,
      data.regionStateMapping
    );
  } else {
    throw new Error(`Unknown scope: ${scope}`);
  }
}
