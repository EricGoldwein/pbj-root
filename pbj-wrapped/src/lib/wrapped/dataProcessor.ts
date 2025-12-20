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
import type { LoadedData, StateStandardRow } from './dataLoader';
import { createProviderInfoLookup } from './dataLoader';

/**
 * Calculate percentile rank
 */
function calculatePercentile(rank: number, total: number): number {
  if (total === 0) return 0;
  return Math.round(((total - rank + 1) / total) * 100);
}

/**
 * Parse ownership type from provider info
 * Categories: "For profit - Corporation", "Non profit - Corporation", "Government - State", etc.
 */
function parseOwnershipType(ownershipType?: string): 'forProfit' | 'nonProfit' | 'government' | null {
  if (!ownershipType) return null;
  const lower = ownershipType.toLowerCase().trim();
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
 * Convert facility name to proper title case
 * Capitalizes first letter of each word, except for common words like "and", "of", "at", etc.
 */
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
    'subacute': 'Sub-Acute',
    'Subacute': 'Sub-Acute',
    'sub-acute': 'Sub-Acute',
    'Sub-Acute': 'Sub-Acute',
    'post acute': 'Post-Acute',
    'Post Acute': 'Post-Acute',
    'post-acute': 'Post-Acute',
    'Post-Acute': 'Post-Acute',
    'continuing care': 'CC',
    'Continuing Care': 'CC',
    'retirement community': 'Retirement',
    'Retirement Community': 'Retirement',
    'retirement home': 'Retirement',
    'Retirement Home': 'Retirement',
    'community': 'Comm',
    'Community': 'Comm',
    'center': 'Ctr',
    'Center': 'Ctr',
    'facility': 'Fac',
    'Facility': 'Fac',
    'facilities': 'Fac',
    'Facilities': 'Fac',
  };
  
  let shortened = name;
  
  // Apply abbreviations (case-sensitive first, then case-insensitive fallback)
  for (const [full, abbrev] of Object.entries(abbreviations)) {
    // Try exact match first
    if (shortened.includes(full)) {
      shortened = shortened.replace(new RegExp(`\\b${full.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'g'), abbrev);
    } else {
      // Fallback to case-insensitive
      const regex = new RegExp(`\\b${full}\\b`, 'gi');
      shortened = shortened.replace(regex, (match) => {
        // Preserve the capitalization pattern of the match
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
  
  const smallWords = new Set(['and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'the', 'a', 'an']);
  
  return name
    .toLowerCase()
    .split(/\s+/)
    .map((word, index) => {
      // Handle hyphenated words (e.g., "post-acute" -> "Post-Acute")
      if (word.includes('-')) {
        return word
          .split('-')
          .map((part, partIndex) => {
            if (partIndex === 0 || !smallWords.has(part)) {
              return part.charAt(0).toUpperCase() + part.slice(1);
            }
            return part;
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

/**
 * Capitalize city names: first letter only, but if two words (like "Carson City"), both are capitalized
 */
export function capitalizeCity(city: string | undefined): string | undefined {
  if (!city) return city;
  
  return city
    .toLowerCase()
    .split(/\s+/)
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/**
 * Create facility link
 */
function createFacilityLink(provnum: string): string {
  return `https://pbjdashboard.com/?facility=${provnum}`;
}

/**
 * Create state link
 */
function createStateLink(stateCode: string): string {
  return `https://pbjdashboard.com/?state=${stateCode}`;
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
  providerInfoQ1: ProviderInfoRow[],
  stateDataQ2: StateQuarterlyRow[],
  stateDataQ1: StateQuarterlyRow[],
  regionDataQ2: RegionQuarterlyRow[],
  regionDataQ1: RegionQuarterlyRow[]
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
  
  // Calculate median HPRD from facilities
  const allHPRDs = facilityQ2.map(f => f.Total_Nurse_HPRD).sort((a, b) => a - b);
  const medianHPRD = allHPRDs.length > 0 
    ? allHPRDs[Math.floor(allHPRDs.length / 2)]
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
  const topStatesByHPRD: Facility[] = sortedStatesByHPRD.slice(0, 3).map(s => ({
    provnum: s.STATE,
    name: getStateFullName(s.STATE),
    state: s.STATE,
    value: s.Total_Nurse_HPRD,
    link: `/${s.STATE.toLowerCase()}`,
  }));
  const bottomStatesByHPRD: Facility[] = sortedStatesByHPRD.slice(-3).reverse().map(s => ({
    provnum: s.STATE,
    name: getStateFullName(s.STATE),
    state: s.STATE,
    value: s.Total_Nurse_HPRD,
    link: `/${s.STATE.toLowerCase()}`,
  }));

  // Top/Bottom States by Direct Care HPRD (excluding PR)
  const sortedStatesByDirectCare = [...statesQ2ExcludingPR].sort((a, b) => b.Nurse_Care_HPRD - a.Nurse_Care_HPRD);
  const topStatesByDirectCare: Facility[] = sortedStatesByDirectCare.slice(0, 3).map(s => ({
    provnum: s.STATE,
    name: getStateFullName(s.STATE),
    state: s.STATE,
    value: s.Nurse_Care_HPRD,
    link: `/${s.STATE.toLowerCase()}`,
  }));
  const bottomStatesByDirectCare: Facility[] = sortedStatesByDirectCare.slice(-3).reverse().map(s => ({
    provnum: s.STATE,
    name: getStateFullName(s.STATE),
    state: s.STATE,
    value: s.Nurse_Care_HPRD,
    link: `/${s.STATE.toLowerCase()}`,
  }));

  // Top/Bottom Regions by Total HPRD
  const sortedRegionsByHPRD = [...regionDataQ2].sort((a, b) => b.Total_Nurse_HPRD - a.Total_Nurse_HPRD);
  const topRegionsByHPRD: Facility[] = sortedRegionsByHPRD.slice(0, 3).map(r => ({
    provnum: `region${r.REGION_NUMBER}`,
    name: r.REGION_NAME || `Region ${r.REGION_NUMBER}`,
    state: `Region ${r.REGION_NUMBER}`,
    value: r.Total_Nurse_HPRD,
    link: `https://pbjdashboard.com/?region=${r.REGION_NUMBER}`,
  }));
  const bottomRegionsByHPRD: Facility[] = sortedRegionsByHPRD.slice(-3).reverse().map(r => ({
    provnum: `region${r.REGION_NUMBER}`,
    name: r.REGION_NAME || `Region ${r.REGION_NUMBER}`,
    state: `Region ${r.REGION_NUMBER}`,
    value: r.Total_Nurse_HPRD,
    link: `https://pbjdashboard.com/?region=${r.REGION_NUMBER}`,
  }));

  // Top/Bottom Regions by Direct Care HPRD
  const sortedRegionsByDirectCare = [...regionDataQ2].sort((a, b) => b.Nurse_Care_HPRD - a.Nurse_Care_HPRD);
  const topRegionsByDirectCare: Facility[] = sortedRegionsByDirectCare.slice(0, 3).map(r => ({
    provnum: `region${r.REGION_NUMBER}`,
    name: r.REGION_NAME || `Region ${r.REGION_NUMBER}`,
    state: `Region ${r.REGION_NUMBER}`,
    value: r.Nurse_Care_HPRD,
    link: `https://pbjdashboard.com/?region=${r.REGION_NUMBER}`,
  }));
  const bottomRegionsByDirectCare: Facility[] = sortedRegionsByDirectCare.slice(-3).reverse().map(r => ({
    provnum: `region${r.REGION_NUMBER}`,
    name: r.REGION_NAME || `Region ${r.REGION_NUMBER}`,
    state: `Region ${r.REGION_NUMBER}`,
    value: r.Nurse_Care_HPRD,
    link: `https://pbjdashboard.com/?region=${r.REGION_NUMBER}`,
  }));

  // Also include facility extremes
  const facilitiesWithInfoQ2 = facilityQ2.map(f => {
    const info = providerInfoLookupQ2.get(f.PROVNUM);
    return { facility: f, info };
  }).filter(f => f.info);

  const sortedByHPRD = [...facilitiesWithInfoQ2].sort((a, b) => 
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

  // Section 5: SFF - check for various SFF status formats
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
  
  const sffQ1Set = new Set(providerInfoQ1.filter(p => {
    if (!p.sff_status) return false;
    const status = p.sff_status.trim().toUpperCase();
    return status === 'SFF' || status === 'SPECIAL FOCUS FACILITY' || status.includes('SFF');
  }).map(p => p.PROVNUM));
  const newSFF = sffQ2.filter(p => !sffQ1Set.has(p.PROVNUM));

  // Shuffle new SFF facilities for random order (not alphabetical)
  const shuffledNewSFF = [...newSFF].sort(() => Math.random() - 0.5);
  const newSFFFacilities: Facility[] = shuffledNewSFF.map(p => {
    const facility = facilityQ2.find(f => f.PROVNUM === p.PROVNUM);
    return {
      provnum: p.PROVNUM,
      name: toTitleCase(p.PROVNAME),
      state: p.STATE,
      value: facility?.Total_Nurse_HPRD || 0,
      link: createFacilityLink(p.PROVNUM),
    };
  });

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
        link: `/${stateQ2.STATE.toLowerCase()}`,
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
        link: `https://pbjdashboard.com/?region=${regionQ2.REGION_NUMBER}`,
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

  // Ownership breakdown for USA - use all provider info Q2
  const ownershipData = providerInfoQ2.filter(p => p.ownership_type && p.ownership_type.trim().length > 0);
  const ownership = calculateOwnershipBreakdown(ownershipData);

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
      currentSFFs: sffQ2.length,
      candidates: candidatesQ2.length,
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
  };
}

/**
 * Process data for State scope
 */
function processStateData(
  stateAbbr: string,
  stateQ2: StateQuarterlyRow | null,
  stateQ1: StateQuarterlyRow | null,
  facilityQ2: FacilityLiteRow[],
  facilityQ1: FacilityLiteRow[],
  providerInfoQ2: ProviderInfoRow[],
  providerInfoQ1: ProviderInfoRow[],
  allStatesQ2: StateQuarterlyRow[],
  stateStandards?: Map<string, StateStandardRow>
): PBJWrappedData {
  if (!stateQ2) {
    throw new Error(`State ${stateAbbr} Q2 data not available`);
  }

  // State codes in CSV are uppercase, ensure we match correctly
  const stateCodeUpper = stateAbbr.toUpperCase();
  const stateFacilitiesQ2 = facilityQ2.filter(f => f.STATE.toUpperCase() === stateCodeUpper);
  const stateFacilitiesQ1 = facilityQ1.filter(f => f.STATE.toUpperCase() === stateCodeUpper);
  const stateProviderInfoQ2 = providerInfoQ2.filter(p => p.STATE.toUpperCase() === stateCodeUpper);
  const stateProviderInfoQ1 = providerInfoQ1.filter(p => p.STATE.toUpperCase() === stateCodeUpper);
  
  // Debug logging
  console.log(`[State ${stateAbbr}] Provider info Q2 total: ${providerInfoQ2.length}, filtered for state: ${stateProviderInfoQ2.length}`);
  if (stateProviderInfoQ2.length > 0) {
    console.log(`[State ${stateAbbr}] Sample provider info: CCN=${stateProviderInfoQ2[0].PROVNUM}, State=${stateProviderInfoQ2[0].STATE}, Ownership=${stateProviderInfoQ2[0].ownership_type}, SFF=${stateProviderInfoQ2[0].sff_status}`);
  } else {
    console.warn(`[State ${stateAbbr}] WARNING: No provider info found for this state!`);
    console.log(`[State ${stateAbbr}] Available states in provider info:`, [...new Set(providerInfoQ2.map(p => p.STATE))].slice(0, 10));
  }

  const providerInfoLookupQ2 = createProviderInfoLookup(stateProviderInfoQ2);

  // Section 2: Basics
  const facilityCount = stateQ2.facility_count;
  // Calculate average daily residents: total_resident_days / avg_days_reported
  // This gives us the average number of residents across all facilities on any given day
  const avgDailyResidents = stateQ2.avg_days_reported > 0
    ? stateQ2.total_resident_days / stateQ2.avg_days_reported
    : stateQ2.avg_daily_census; // Fallback to avg_daily_census if calculation not possible
  const totalHPRD = stateQ2.Total_Nurse_HPRD;
  const directCareHPRD = stateQ2.Nurse_Care_HPRD;
  const rnHPRD = stateQ2.RN_HPRD;
  const rnDirectCareHPRD = stateQ2.RN_Care_HPRD;

  // Section 3: Rankings (excluding PR)
  const allStatesQ2ExcludingPR = allStatesQ2.filter(s => s.STATE !== 'PR');
  const sortedByTotalHPRD = [...allStatesQ2ExcludingPR].sort((a, b) => b.Total_Nurse_HPRD - a.Total_Nurse_HPRD);
  const sortedByDirectCare = [...allStatesQ2ExcludingPR].sort((a, b) => b.Nurse_Care_HPRD - a.Nurse_Care_HPRD);
  const sortedByRN = [...allStatesQ2ExcludingPR].sort((a, b) => b.RN_HPRD - a.RN_HPRD);

  // stateCodeUpper already declared above, reuse it
  const totalHPRDRank = sortedByTotalHPRD.findIndex(s => s.STATE.toUpperCase() === stateCodeUpper) + 1;
  const directCareHPRDRank = sortedByDirectCare.findIndex(s => s.STATE.toUpperCase() === stateCodeUpper) + 1;
  const rnHPRDRank = sortedByRN.findIndex(s => s.STATE.toUpperCase() === stateCodeUpper) + 1;

  const rankings = {
    totalHPRDRank,
    totalHPRDPercentile: calculatePercentile(totalHPRDRank, allStatesQ2ExcludingPR.length),
    directCareHPRDRank,
    directCareHPRDPercentile: calculatePercentile(directCareHPRDRank, allStatesQ2ExcludingPR.length),
    rnHPRDRank,
    rnHPRDPercentile: calculatePercentile(rnHPRDRank, allStatesQ2ExcludingPR.length),
  };

  // Section 4: Extremes - include all facilities, not just those with provider info
  // Filter out facilities with census < 25
  const facilitiesWithInfoQ2 = stateFacilitiesQ2
    .map(f => {
      const info = providerInfoLookupQ2.get(f.PROVNUM);
      return { facility: f, info };
    })
    .filter(({ facility, info }) => {
      const census = info?.avg_residents_per_day || facility.Census || 0;
      return census >= 25;
    });

  const sortedByHPRD = [...facilitiesWithInfoQ2].sort((a, b) => 
    a.facility.Total_Nurse_HPRD - b.facility.Total_Nurse_HPRD
  );

  const lowestByHPRD: Facility[] = sortedByHPRD.slice(0, 5).map(({ facility, info }) => ({
    provnum: facility.PROVNUM,
    name: toTitleCase(facility.PROVNAME),
    city: capitalizeCity(info?.CITY || info?.COUNTY_NAME),
    state: facility.STATE,
    value: facility.Total_Nurse_HPRD,
    link: createFacilityLink(facility.PROVNUM),
  }));

  const highestByHPRD: Facility[] = sortedByHPRD.slice(-5).reverse().map(({ facility, info }) => ({
    provnum: facility.PROVNUM,
    name: toTitleCase(facility.PROVNAME),
    city: capitalizeCity(info?.CITY || info?.COUNTY_NAME),
    state: facility.STATE,
    value: facility.Total_Nurse_HPRD,
    link: createFacilityLink(facility.PROVNUM),
  }));

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

  const lowestByPercentExpected: Facility[] = sortedByPercent.slice(0, 5).map(({ facility, info, percentExpected }) => ({
    provnum: facility.PROVNUM,
    name: toTitleCase(facility.PROVNAME),
    city: capitalizeCity(info?.CITY || info?.COUNTY_NAME),
    state: facility.STATE,
    value: percentExpected,
    link: createFacilityLink(facility.PROVNUM),
  }));

  const highestByPercentExpected: Facility[] = sortedByPercent.slice(-5).reverse().map(({ facility, info, percentExpected }) => ({
    provnum: facility.PROVNUM,
    name: toTitleCase(facility.PROVNAME),
    city: capitalizeCity(info?.CITY || info?.COUNTY_NAME),
    state: facility.STATE,
    value: percentExpected,
    link: createFacilityLink(facility.PROVNUM),
  }));

  // Section 5: SFF - check for various SFF status formats
  // Check all possible SFF status values
  const allSFFStatuses = [...new Set(stateProviderInfoQ2.map(p => p.sff_status).filter(Boolean))];
  console.log(`[State ${stateAbbr}] Unique SFF statuses found:`, allSFFStatuses.slice(0, 10));
  
  const sffQ2 = stateProviderInfoQ2.filter(p => {
    if (!p.sff_status) return false;
    const status = p.sff_status.trim().toUpperCase();
    // Check for various formats: 'SFF', 'SPECIAL FOCUS FACILITY', 'Y', 'YES', etc.
    return status === 'SFF' || 
           status === 'SPECIAL FOCUS FACILITY' || 
           status === 'Y' ||
           status === 'YES' ||
           status.includes('SFF') ||
           status.includes('SPECIAL FOCUS');
  });
  const candidatesQ2 = stateProviderInfoQ2.filter(p => {
    if (!p.sff_status) return false;
    const status = p.sff_status.trim().toUpperCase();
    return status === 'SFF CANDIDATE' || 
           status === 'CANDIDATE' || 
           status === 'C' ||
           (status.includes('CANDIDATE') && !status.includes('SFF'));
  });
  
  console.log(`[State ${stateAbbr}] SFF count: ${sffQ2.length}, Candidates: ${candidatesQ2.length}`);
  
  const sffQ1Set = new Set(stateProviderInfoQ1.filter(p => {
    const status = p.sff_status?.trim().toUpperCase();
    return status === 'SFF' || status === 'SPECIAL FOCUS FACILITY';
  }).map(p => p.PROVNUM));
  const newSFF = sffQ2.filter(p => !sffQ1Set.has(p.PROVNUM));

  const newSFFFacilities: Facility[] = newSFF.map(p => {
    const facility = stateFacilitiesQ2.find(f => f.PROVNUM === p.PROVNUM);
    return {
      provnum: p.PROVNUM,
      name: toTitleCase(p.PROVNAME),
      city: capitalizeCity(p.CITY || p.COUNTY_NAME),
      state: p.STATE,
      value: facility?.Total_Nurse_HPRD || 0,
      link: createFacilityLink(p.PROVNUM),
    };
  });

  // Section 6: Trends - only calculate if Q1 exists and has valid data
  console.log(`[State ${stateAbbr}] Q1 data exists: ${!!stateQ1}, Q2 Total HPRD: ${stateQ2.Total_Nurse_HPRD}`);
  if (stateQ1) {
    console.log(`[State ${stateAbbr}] Q1 Total HPRD: ${stateQ1.Total_Nurse_HPRD}`);
  }
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
    contractPercentChange: (stateQ1 && stateQ1.Contract_Percentage !== undefined)
      ? stateQ2.Contract_Percentage - stateQ1.Contract_Percentage
      : 0,
  };
  console.log(`[State ${stateAbbr}] Trends:`, trends);

  // Section 7: Movers
  const facilityMapQ1 = new Map(stateFacilitiesQ1.map(f => [f.PROVNUM, f]));

  const movers: FacilityChange[] = [];
  for (const f2 of stateFacilitiesQ2) {
    const f1 = facilityMapQ1.get(f2.PROVNUM);
    if (f1) {
      const change = f2.Total_Nurse_HPRD - f1.Total_Nurse_HPRD;
      const directCareChange = f2.Nurse_Care_HPRD - f1.Nurse_Care_HPRD;
      const rnHPRDChange = f2.Total_RN_HPRD - f1.Total_RN_HPRD;
      const info = providerInfoLookupQ2.get(f2.PROVNUM);
      
      movers.push({
        provnum: f2.PROVNUM,
        name: toTitleCase(f2.PROVNAME),
        city: capitalizeCity(info?.CITY || info?.COUNTY_NAME),
        state: f2.STATE,
        value: f2.Total_Nurse_HPRD,
        link: createFacilityLink(f2.PROVNUM),
        change,
        q1Value: f1.Total_Nurse_HPRD,
        q2Value: f2.Total_Nurse_HPRD,
        directCareChange,
        q1DirectCare: f1.Nurse_Care_HPRD,
        q2DirectCare: f2.Nurse_Care_HPRD,
        rnHPRDChange,
        q1RNHPRD: f1.Total_RN_HPRD,
        q2RNHPRD: f2.Total_RN_HPRD,
      } as any);
    }
  }

  const risersByHPRD = [...movers]
    .sort((a, b) => b.change - a.change)
    .slice(0, 5);
  
  const declinersByHPRD = [...movers]
    .sort((a, b) => a.change - b.change)
    .slice(0, 5);

  const risersByDirectCare = [...movers]
    .sort((a, b) => (b as any).directCareChange - (a as any).directCareChange)
    .slice(0, 5);

  const declinersByDirectCare = [...movers]
    .sort((a, b) => (a as any).directCareChange - (b as any).directCareChange)
    .slice(0, 5);

  const risersByRNHPRD = [...movers]
    .sort((a, b) => ((b as any).rnHPRDChange || 0) - ((a as any).rnHPRDChange || 0))
    .slice(0, 5);

  const declinersByRNHPRD = [...movers]
    .sort((a, b) => ((a as any).rnHPRDChange || 0) - ((b as any).rnHPRDChange || 0))
    .slice(0, 5);

  // Ownership breakdown - use all provider info for the state
  // Make sure we're using Q2 data and that ownership_type exists
  const ownershipData = stateProviderInfoQ2.filter(p => p.ownership_type && p.ownership_type.trim().length > 0);
  const allOwnershipTypes = [...new Set(stateProviderInfoQ2.map(p => p.ownership_type).filter(Boolean))];
  console.log(`[State ${stateAbbr}] Ownership data count: ${ownershipData.length}`);
  console.log(`[State ${stateAbbr}] Unique ownership types:`, allOwnershipTypes.slice(0, 10));
  const ownership = calculateOwnershipBreakdown(ownershipData);
  console.log(`[State ${stateAbbr}] Ownership breakdown:`, ownership);

  // Get state minimum staffing requirement
  let stateMinimum: StateMinimum | undefined;
  if (stateStandards) {
    const lookupKey = stateAbbr.toLowerCase();
    console.log(`[State ${stateAbbr}] Looking up state minimum with key: "${lookupKey}"`);
    console.log(`[State ${stateAbbr}] StateStandards map size: ${stateStandards.size}`);
    console.log(`[State ${stateAbbr}] StateStandards map has "${lookupKey}": ${stateStandards.has(lookupKey)}`);
    if (stateStandards.has(lookupKey)) {
      const standard = stateStandards.get(lookupKey)!;
      console.log(`[State ${stateAbbr}] Found standard: ${standard.State}, Min: ${standard.Min_Staffing}`);
    }
    const standard = stateStandards.get(lookupKey);
    if (standard && standard.Min_Staffing >= 1.0) {
      console.log(`[State ${stateAbbr}] Found state minimum: ${standard.Min_Staffing} HPRD`);
      const isRange = standard.Value_Type === 'range' && standard.Max_Staffing > standard.Min_Staffing;
      stateMinimum = {
        minHPRD: standard.Min_Staffing,
        maxHPRD: isRange ? standard.Max_Staffing : undefined,
        isRange,
        displayText: isRange 
          ? `${standard.Min_Staffing.toFixed(2)}-${standard.Max_Staffing.toFixed(2)} minimum`
          : `${standard.Min_Staffing.toFixed(2)} minimum`,
      };
    } else {
      console.warn(`[State ${stateAbbr}] No state minimum found. Standard: ${standard ? 'exists but Min < 1.0' : 'not found'}`);
    }
  } else {
    console.warn(`[State ${stateAbbr}] stateStandards map is undefined or null`);
  }

  return {
    scope: 'state',
    identifier: stateAbbr,
    name: stateAbbr.toUpperCase(),
    stateMinimum,
    facilityCount,
    avgDailyResidents,
    totalHPRD,
    directCareHPRD,
    rnHPRD,
    rnDirectCareHPRD,
    rankings,
    extremes: {
      lowestByHPRD,
      lowestByPercentExpected,
      highestByHPRD,
      highestByPercentExpected,
    },
    sff: {
      currentSFFs: sffQ2.length,
      candidates: candidatesQ2.length,
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
    ownership,
  };
}

/**
 * Process data for Region scope
 */
function processRegionData(
  regionNumber: number,
  regionQ2: RegionQuarterlyRow | null,
  regionQ1: RegionQuarterlyRow | null,
  facilityQ2: FacilityLiteRow[],
  _facilityQ1: FacilityLiteRow[],
  providerInfoQ2: ProviderInfoRow[],
  providerInfoQ1: ProviderInfoRow[],
  allRegionsQ2: RegionQuarterlyRow[],
  regionStateMapping: Map<number, Set<string>>,
  stateDataQ2: StateQuarterlyRow[],
  stateDataQ1: StateQuarterlyRow[],
  stateStandards?: Map<string, StateStandardRow>
): PBJWrappedData {
  if (!regionQ2) {
    throw new Error(`Region ${regionNumber} Q2 data not available`);
  }

  // Get states in this region
  const regionStates = regionStateMapping.get(regionNumber) || new Set<string>();
  
  // Filter facilities and provider info by region states
  const regionFacilitiesQ2 = facilityQ2.filter(f => regionStates.has(f.STATE));
  const regionProviderInfoQ2 = providerInfoQ2.filter(p => regionStates.has(p.STATE));
  const regionProviderInfoQ1 = providerInfoQ1.filter(p => regionStates.has(p.STATE));

  const providerInfoLookupQ2 = createProviderInfoLookup(regionProviderInfoQ2);

  // Section 2: Basics
  const facilityCount = regionQ2.facility_count;
  const avgDailyResidents = regionQ2.avg_daily_census;
  const totalHPRD = regionQ2.Total_Nurse_HPRD;
  const directCareHPRD = regionQ2.Nurse_Care_HPRD;
  const rnHPRD = regionQ2.RN_HPRD;
  const rnDirectCareHPRD = regionQ2.RN_Care_HPRD;

  // Section 3: Rankings
  const sortedByTotalHPRD = [...allRegionsQ2].sort((a, b) => b.Total_Nurse_HPRD - a.Total_Nurse_HPRD);
  const sortedByDirectCare = [...allRegionsQ2].sort((a, b) => b.Nurse_Care_HPRD - a.Nurse_Care_HPRD);
  const sortedByRN = [...allRegionsQ2].sort((a, b) => b.RN_HPRD - a.RN_HPRD);

  const totalHPRDRank = sortedByTotalHPRD.findIndex(r => r.REGION_NUMBER === regionNumber) + 1;
  const directCareHPRDRank = sortedByDirectCare.findIndex(r => r.REGION_NUMBER === regionNumber) + 1;
  const rnHPRDRank = sortedByRN.findIndex(r => r.REGION_NUMBER === regionNumber) + 1;

  // Regions are always out of 10
  const totalRegions = 10;
  const rankings = {
    totalHPRDRank,
    totalHPRDPercentile: calculatePercentile(totalHPRDRank, totalRegions),
    directCareHPRDRank,
    directCareHPRDPercentile: calculatePercentile(directCareHPRDRank, totalRegions),
    rnHPRDRank,
    rnHPRDPercentile: calculatePercentile(rnHPRDRank, totalRegions),
  };

  // Section 4: Extremes (similar to state but show state instead of city)
  // Filter out facilities with census < 25
  const facilitiesWithInfoQ2 = regionFacilitiesQ2
    .map(f => {
      const info = providerInfoLookupQ2.get(f.PROVNUM);
      return { facility: f, info };
    })
    .filter(({ facility, info }) => {
      const census = info?.avg_residents_per_day || facility.Census || 0;
      return census >= 25;
    });

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

  const withPercentExpected = facilitiesWithInfoQ2
    .map(({ facility, info }) => {
      const caseMix = info?.case_mix_total_nurse_hrs_per_resident_per_day;
      if (!caseMix || caseMix === 0) return null;
      const percentExpected = (facility.Total_Nurse_HPRD / caseMix) * 100;
      return { facility, info, percentExpected };
    })
    .filter((f): f is NonNullable<typeof f> => {
      if (!f) return false;
      // Filter out facilities with census < 25
      const census = f.info?.avg_residents_per_day || f.facility.Census || 0;
      return census >= 25;
    });

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

  // Section 5: SFF - check for various SFF status formats
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
  
  const sffQ1Set = new Set(regionProviderInfoQ1.filter(p => {
    const status = p.sff_status?.trim().toUpperCase();
    return status === 'SFF' || status === 'SPECIAL FOCUS FACILITY';
  }).map(p => p.PROVNUM));
  const newSFF = sffQ2.filter(p => !sffQ1Set.has(p.PROVNUM));

  // Shuffle new SFF facilities for random order (not alphabetical)
  const shuffledNewSFF = [...newSFF].sort(() => Math.random() - 0.5);
  const newSFFFacilities: Facility[] = shuffledNewSFF.map(p => {
    const facility = regionFacilitiesQ2.find(f => f.PROVNUM === p.PROVNUM);
    return {
      provnum: p.PROVNUM,
      name: toTitleCase(p.PROVNAME),
      state: p.STATE,
      value: facility?.Total_Nurse_HPRD || 0,
      link: createFacilityLink(p.PROVNUM),
    };
  });

  // Section 6: Trends - calculate changes from Q1 to Q2
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
  
  console.log(`[Region ${regionNumber}] Trends calculated:`, trends);

  // Section 7: Movers - Use state-level data for regions
  // regionStates already declared above, reuse it
  const regionStatesQ2 = stateDataQ2.filter((s: StateQuarterlyRow) => regionStates.has(s.STATE));
  const stateMapQ1 = new Map(stateDataQ1.map((s: StateQuarterlyRow) => [s.STATE, s]));
  
  const stateMovers: StateChange[] = [];
  for (const stateQ2 of regionStatesQ2) {
    const sq2 = stateQ2 as StateQuarterlyRow;
    const stateQ1 = stateMapQ1.get(sq2.STATE);
    if (stateQ1 && 'Total_Nurse_HPRD' in stateQ1 && 'Nurse_Care_HPRD' in stateQ1) {
      const sq1 = stateQ1 as StateQuarterlyRow;
      const change = sq2.Total_Nurse_HPRD - sq1.Total_Nurse_HPRD;
      const directCareChange = sq2.Nurse_Care_HPRD - sq1.Nurse_Care_HPRD;
      const rnHPRDChange = sq2.RN_HPRD - sq1.RN_HPRD;
      
      stateMovers.push({
        state: sq2.STATE,
        change,
        q1Value: sq1.Total_Nurse_HPRD,
        q2Value: sq2.Total_Nurse_HPRD,
        directCareChange,
        q1DirectCare: sq1.Nurse_Care_HPRD,
        q2DirectCare: sq2.Nurse_Care_HPRD,
        rnHPRDChange,
        q1RNHPRD: sq1.RN_HPRD,
        q2RNHPRD: sq2.RN_HPRD,
        link: createStateLink(sq2.STATE),
      });
    }
  }

  const risersByHPRD = [...stateMovers]
    .sort((a, b) => b.change - a.change)
    .slice(0, 5);
  
  const declinersByHPRD = [...stateMovers]
    .sort((a, b) => a.change - b.change)
    .slice(0, 5);

  const risersByDirectCare = [...stateMovers]
    .sort((a, b) => (b.directCareChange || 0) - (a.directCareChange || 0))
    .slice(0, 5);

  const declinersByDirectCare = [...stateMovers]
    .sort((a, b) => (a.directCareChange || 0) - (b.directCareChange || 0))
    .slice(0, 5);

  const risersByRNHPRD = [...stateMovers]
    .sort((a, b) => (b.rnHPRDChange || 0) - (a.rnHPRDChange || 0))
    .slice(0, 5);

  const declinersByRNHPRD = [...stateMovers]
    .sort((a, b) => (a.rnHPRDChange || 0) - (b.rnHPRDChange || 0))
    .slice(0, 5);

  // Ownership breakdown - use all provider info for the region with ownership_type
  const ownership = calculateOwnershipBreakdown(
    regionProviderInfoQ2.filter(p => p.ownership_type && p.ownership_type.trim().length > 0)
  );

  // Build region states info with state minimums
  const getStateFullName = (abbr: string): string => {
    const stateNames: Record<string, string> = {
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
    return stateNames[abbr.toUpperCase()] || abbr;
  };

  const regionStatesInfo = Array.from(regionStates).map(stateCode => {
    const stateQ2 = stateDataQ2.find(s => s.STATE.toUpperCase() === stateCode.toUpperCase());
    let stateMinimum: StateMinimum | undefined;
    
    if (stateStandards) {
      const lookupKey = stateCode.toLowerCase();
      const standard = stateStandards.get(lookupKey);
      if (standard && standard.Min_Staffing >= 1.0) {
        const isRange = standard.Value_Type === 'range' && standard.Max_Staffing > standard.Min_Staffing;
        stateMinimum = {
          minHPRD: standard.Min_Staffing,
          maxHPRD: isRange ? standard.Max_Staffing : undefined,
          isRange,
          displayText: isRange 
            ? `${standard.Min_Staffing.toFixed(2)}-${standard.Max_Staffing.toFixed(2)} minimum`
            : `${standard.Min_Staffing.toFixed(2)} minimum`,
        };
      }
    }
    
    return {
      state: stateCode,
      stateName: getStateFullName(stateCode),
      totalHPRD: stateQ2?.Total_Nurse_HPRD || 0,
      stateMinimum,
    };
  });

  return {
    scope: 'region',
    identifier: `region${regionNumber}`,
    name: regionQ2.REGION_NAME || `Region ${regionNumber}`,
    facilityCount,
    avgDailyResidents,
    totalHPRD,
    directCareHPRD,
    rnHPRD,
    rnDirectCareHPRD,
    rankings,
    extremes: {
      lowestByHPRD,
      lowestByPercentExpected,
      highestByHPRD,
      highestByPercentExpected,
    },
    sff: {
      currentSFFs: sffQ2.length,
      candidates: candidatesQ2.length,
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
    ownership,
    regionStates: regionStatesInfo,
  };
}

/**
 * Main function to process data based on scope
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
      data.facilityData.q2,
      data.facilityData.q1,
      data.providerInfo.q2,
      data.providerInfo.q1,
      data.stateData.q2,
      data.stateData.q1,
      data.regionData.q2,
      data.regionData.q1
    );
  } else if (scope === 'state') {
    // State codes in CSV are uppercase, identifier is lowercase - convert to uppercase for matching
    const stateCodeUpper = identifier.toUpperCase();
    const stateQ2 = data.stateData.q2.find(s => s.STATE.toUpperCase() === stateCodeUpper);
    const stateQ1 = data.stateData.q1.find(s => s.STATE.toUpperCase() === stateCodeUpper);
    
    // Debug: Log what states are available in Q1
    console.log(`[State ${stateCodeUpper}] Looking for Q1 data. Q1 array length: ${data.stateData.q1.length}, Q2 array length: ${data.stateData.q2.length}`);
    if (stateQ2) {
      console.log(`[State ${stateCodeUpper}] Q2 found: Total HPRD = ${stateQ2.Total_Nurse_HPRD}`);
    } else {
      console.warn(`[State ${stateCodeUpper}] Q2 data NOT FOUND!`);
    }
    if (stateQ1) {
      console.log(`[State ${stateCodeUpper}] Q1 found: Total HPRD = ${stateQ1.Total_Nurse_HPRD}`);
    } else {
      console.warn(`[State ${stateCodeUpper}] Q1 data NOT FOUND!`);
      if (data.stateData.q1.length > 0) {
        const availableStates = [...new Set(data.stateData.q1.map(s => s.STATE))].slice(0, 10);
        console.warn(`  Available states in Q1: ${availableStates.join(', ')}`);
      } else {
        console.warn(`  Q1 data array is empty! state_q1.json likely has no data. Regenerate JSON files.`);
      }
    }
    
    return processStateData(
      stateCodeUpper, // Use uppercase for matching with CSV data
      stateQ2 || null,
      stateQ1 || null,
      data.facilityData.q2,
      data.facilityData.q1,
      data.providerInfo.q2,
      data.providerInfo.q1,
      data.stateData.q2,
      data.stateStandards
    );
  } else if (scope === 'region') {
    const regionNumber = parseInt(identifier.replace('region', ''), 10);
    const regionQ2 = data.regionData.q2.find(r => r.REGION_NUMBER === regionNumber);
    const regionQ1 = data.regionData.q1.find(r => r.REGION_NUMBER === regionNumber);
    
    return processRegionData(
      regionNumber,
      regionQ2 || null,
      regionQ1 || null,
      data.facilityData.q2,
      data.facilityData.q1,
      data.providerInfo.q2,
      data.providerInfo.q1,
      data.regionData.q2,
      data.regionStateMapping,
      data.stateData.q2,
      data.stateData.q1,
      data.stateStandards
    );
  } else {
    throw new Error(`Unknown scope: ${scope}`);
  }
}

