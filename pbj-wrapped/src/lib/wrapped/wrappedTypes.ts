/**
 * Type definitions for PBJ Wrapped feature
 */

export type Scope = 'usa' | 'state' | 'region';

export interface Facility {
  provnum: string; // CCN
  name: string;
  city?: string;
  state: string;
  value: number; // HPRD or percentage
  link: string; // pbjdashboard.com link
  overallRating?: string; // CMS overall rating (1-5)
  staffingRating?: string; // CMS staffing rating (1-5)
}

export interface FacilityChange extends Facility {
  change: number; // Q2 - Q1
  q1Value: number;
  q2Value: number;
  directCareChange?: number; // Q2 - Q1 for direct care
  q1DirectCare?: number;
  q2DirectCare?: number;
  rnHPRDChange?: number; // Q2 - Q1 for RN HPRD
  q1RNHPRD?: number;
  q2RNHPRD?: number;
}

export interface StateChange {
  state: string;
  stateName?: string;
  change: number; // Q2 - Q1
  q1Value: number;
  q2Value: number;
  directCareChange?: number;
  q1DirectCare?: number;
  q2DirectCare?: number;
  rnHPRDChange?: number; // Q2 - Q1 for RN HPRD
  q1RNHPRD?: number;
  q2RNHPRD?: number;
  link: string; // pbjdashboard.com link
}

export interface StateMinimum {
  minHPRD: number;
  maxHPRD?: number; // For ranges
  isRange: boolean;
  displayText: string;
}

export interface PBJWrappedData {
  scope: Scope;
  identifier: string; // state code, 'usa', or 'region1-10'
  name: string; // Display name
  
  // State minimum staffing requirement (for state scope only)
  stateMinimum?: StateMinimum;
  
  // Section 2: Basics
  facilityCount: number;
  avgDailyResidents: number;
  totalHPRD: number;
  directCareHPRD: number;
  rnHPRD: number;
  rnDirectCareHPRD: number;
  nurseAideHPRD?: number; // For USA only
  medianHPRD?: number; // For USA only
  
  // Section 3: Rankings
  rankings: {
    totalHPRDRank: number;
    totalHPRDPercentile: number;
    directCareHPRDRank: number;
    directCareHPRDPercentile: number;
    rnHPRDRank: number;
    rnHPRDPercentile: number;
  };
  
  // Section 4: Extremes
  extremes: {
    lowestByHPRD: Facility[];
    lowestByPercentExpected: Facility[];
    highestByHPRD: Facility[];
    highestByPercentExpected: Facility[];
    topStatesByHPRD?: Facility[]; // For USA only
    bottomStatesByHPRD?: Facility[]; // For USA only
    topStatesByDirectCare?: Facility[]; // For USA only
    bottomStatesByDirectCare?: Facility[]; // For USA only
    topRegionsByHPRD?: Facility[]; // For USA only
    bottomRegionsByHPRD?: Facility[]; // For USA only
    topRegionsByDirectCare?: Facility[]; // For USA only
    bottomRegionsByDirectCare?: Facility[]; // For USA only
  };
  
  // Section 5: SFF
  sff: {
    currentSFFs: number;
    candidates: number;
    newThisQuarter: Facility[];
  };
  
  // Section 6: Trends
  trends: {
    totalHPRDChange: number;
    directCareHPRDChange: number;
    rnHPRDChange: number;
    nurseAideHPRDChange?: number; // For USA only
    contractPercentChange: number;
  };
  
  // Section 7: Movers
  // For state scope: FacilityChange[]
  // For usa/region scope: StateChange[]
  movers: {
    risersByHPRD: (FacilityChange | StateChange)[];
    risersByDirectCare: (FacilityChange | StateChange)[];
    risersByRNHPRD?: (FacilityChange | StateChange)[];
    declinersByHPRD: (FacilityChange | StateChange)[];
    declinersByDirectCare: (FacilityChange | StateChange)[];
    declinersByRNHPRD?: (FacilityChange | StateChange)[];
  };
  
  // Ownership breakdown (for state and region only)
  ownership?: OwnershipBreakdown;
  
  // Region states info (for region scope only)
  regionStates?: Array<{
    state: string;
    stateName: string;
    totalHPRD: number;
    stateMinimum?: StateMinimum;
  }>;
  
  // Compliance metrics (for state scope only)
  compliance?: {
    facilitiesBelowTotalMinimum: number;
    facilitiesBelowTotalMinimumPercent: number;
    facilitiesBelowDirectCareMinimum?: number; // If state has direct care minimum
    facilitiesBelowDirectCareMinimumPercent?: number;
  };
  
  // Average ratings (for state and region only, not USA)
  averageOverallRating?: number; // Average CMS overall rating (1-5)
}

// CSV row types
export interface StateQuarterlyRow {
  STATE: string;
  CY_Qtr: string;
  facility_count: number;
  avg_days_reported: number;
  total_resident_days: number;
  avg_daily_census: number;
  MDScensus: number;
  Total_Nurse_Hours: number;
  Total_RN_Hours: number;
  Total_Nurse_Care_Hours: number;
  Total_RN_Care_Hours: number;
  Total_Nurse_Assistant_Hours: number;
  Total_Contract_Hours: number;
  Total_Nurse_HPRD: number;
  RN_HPRD: number;
  Nurse_Care_HPRD: number;
  RN_Care_HPRD: number;
  Nurse_Assistant_HPRD: number;
  Contract_Percentage: number;
  Direct_Care_Percentage: number;
  Total_RN_Percentage: number;
  Nurse_Aide_Percentage: number;
}

export interface RegionQuarterlyRow {
  REGION: string;
  REGION_NUMBER: number;
  REGION_NAME: string;
  CY_Qtr: string;
  facility_count: number;
  avg_days_reported: number;
  total_resident_days: number;
  avg_daily_census: number;
  MDScensus: number;
  Total_Nurse_Hours: number;
  Total_RN_Hours: number;
  Total_Nurse_Care_Hours: number;
  Total_RN_Care_Hours: number;
  Total_Nurse_Assistant_Hours: number;
  Total_Contract_Hours: number;
  Total_Nurse_HPRD: number;
  RN_HPRD: number;
  Nurse_Care_HPRD: number;
  RN_Care_HPRD: number;
  Nurse_Assistant_HPRD: number;
  Contract_Percentage: number;
  Direct_Care_Percentage: number;
  Total_RN_Percentage: number;
  Nurse_Aide_Percentage: number;
}

export interface NationalQuarterlyRow {
  STATE: string; // "NATIONAL"
  CY_Qtr: string;
  facility_count: number;
  avg_days_reported: number;
  total_resident_days: number;
  avg_daily_census: number;
  MDScensus: number;
  Total_Nurse_Hours: number;
  Total_RN_Hours: number;
  Total_Nurse_Care_Hours: number;
  Total_RN_Care_Hours: number;
  Total_Nurse_Assistant_Hours: number;
  Total_Contract_Hours: number;
  Total_Nurse_HPRD: number;
  RN_HPRD: number;
  Nurse_Care_HPRD: number;
  RN_Care_HPRD: number;
  Nurse_Assistant_HPRD: number;
  Contract_Percentage: number;
}

export interface FacilityLiteRow {
  CY_Qtr: string;
  PROVNUM: string;
  PROVNAME: string;
  STATE: string;
  COUNTY_NAME: string;
  Total_Nurse_HPRD: number;
  Nurse_Care_HPRD: number;
  Total_RN_HPRD: number;
  Direct_Care_RN_HPRD: number;
  Contract_Percentage: number;
  Census: number;
}

export interface ProviderInfoRow {
  PROVNUM: string;
  PROVNAME: string;
  STATE: string;
  CITY?: string;
  COUNTY_NAME: string;
  CY_Qtr: string;
  ownership_type?: string;
  sff_status?: string;
  overall_rating?: string;
  staffing_rating?: string; // CMS staffing rating (1-5)
  case_mix_total_nurse_hrs_per_resident_per_day?: number;
  case_mix_rn_hrs_per_resident_per_day?: number;
  avg_residents_per_day?: number;
}

export interface OwnershipBreakdown {
  forProfit: {
    count: number;
    percentage: number;
    medianHPRD?: number; // Median total HPRD for this ownership type (USA only)
  };
  nonProfit: {
    count: number;
    percentage: number;
    medianHPRD?: number; // Median total HPRD for this ownership type (USA only)
  };
  government: {
    count: number;
    percentage: number;
    medianHPRD?: number; // Median total HPRD for this ownership type (USA only)
  };
}

