/**
 * Routing helpers for PBJ Wrapped
 */

// State name to abbreviation mapping
const STATE_NAME_TO_ABBR: Record<string, string> = {
  'alabama': 'al',
  'alaska': 'ak',
  'arizona': 'az',
  'arkansas': 'ar',
  'california': 'ca',
  'colorado': 'co',
  'connecticut': 'ct',
  'delaware': 'de',
  'florida': 'fl',
  'georgia': 'ga',
  'hawaii': 'hi',
  'idaho': 'id',
  'illinois': 'il',
  'indiana': 'in',
  'iowa': 'ia',
  'kansas': 'ks',
  'kentucky': 'ky',
  'louisiana': 'la',
  'maine': 'me',
  'maryland': 'md',
  'massachusetts': 'ma',
  'michigan': 'mi',
  'minnesota': 'mn',
  'mississippi': 'ms',
  'missouri': 'mo',
  'montana': 'mt',
  'nebraska': 'ne',
  'nevada': 'nv',
  'new hampshire': 'nh',
  'new jersey': 'nj',
  'new mexico': 'nm',
  'new york': 'ny',
  'north carolina': 'nc',
  'north dakota': 'nd',
  'ohio': 'oh',
  'oklahoma': 'ok',
  'oregon': 'or',
  'pennsylvania': 'pa',
  'rhode island': 'ri',
  'south carolina': 'sc',
  'south dakota': 'sd',
  'tennessee': 'tn',
  'texas': 'tx',
  'utah': 'ut',
  'vermont': 'vt',
  'virginia': 'va',
  'washington': 'wa',
  'west virginia': 'wv',
  'wisconsin': 'wi',
  'wyoming': 'wy',
  'district of columbia': 'dc',
  'washington dc': 'dc',
  'dc': 'dc',
};

// Valid state abbreviations
const VALID_STATE_ABBR = new Set(Object.values(STATE_NAME_TO_ABBR));

// Valid region identifiers - support region1, region-1, region_1
const VALID_REGIONS = new Set(['region1', 'region2', 'region3', 'region4', 'region5', 'region6', 'region7', 'region8', 'region9', 'region10']);
const VALID_REGION_VARIANTS = new Set([
  'region1', 'region-1', 'region_1', 'region2', 'region-2', 'region_2',
  'region3', 'region-3', 'region_3', 'region4', 'region-4', 'region_4',
  'region5', 'region-5', 'region_5', 'region6', 'region-6', 'region_6',
  'region7', 'region-7', 'region_7', 'region8', 'region-8', 'region_8',
  'region9', 'region-9', 'region_9', 'region10', 'region-10', 'region_10'
]);

/**
 * Normalize URL identifier to lowercase and handle variations
 */
export function normalizeIdentifier(identifier: string): string {
  let normalized = identifier.toLowerCase().trim();
  
  // Handle state name variations: new-york, newyork, new_york -> new york
  normalized = normalized.replace(/[-_]/g, ' ');
  
  // Handle region variations: region-1, region_1 -> region1
  const regionMatch = normalized.match(/^region[-_]?(\d+)$/);
  if (regionMatch) {
    normalized = `region${regionMatch[1]}`;
  }
  
  return normalized;
}

/**
 * Convert state full name to abbreviation
 * Handles variations: new-york, newyork, new_york, tennessee, tn
 */
export function stateNameToAbbr(stateName: string): string | null {
  const normalized = normalizeIdentifier(stateName);
  // First check direct mapping
  if (STATE_NAME_TO_ABBR[normalized]) {
    return STATE_NAME_TO_ABBR[normalized];
  }
  // Handle variations: new-york, newyork, new_york -> new york
  const withSpaces = normalized.replace(/[-_]/g, ' ');
  if (STATE_NAME_TO_ABBR[withSpaces]) {
    return STATE_NAME_TO_ABBR[withSpaces];
  }
  // If it's already a 2-letter code, return it
  if (VALID_STATE_ABBR.has(normalized)) {
    return normalized;
  }
  return null;
}

/**
 * Check if identifier is a valid state (2-letter or full name)
 */
export function isValidState(identifier: string): boolean {
  const normalized = normalizeIdentifier(identifier);
  
  // Check if it's a 2-letter abbreviation
  if (VALID_STATE_ABBR.has(normalized)) {
    return true;
  }
  
  // Check if it's a full state name
  if (STATE_NAME_TO_ABBR[normalized]) {
    return true;
  }
  
  return false;
}

/**
 * Get state abbreviation from identifier (handles both 2-letter and full names)
 */
export function getStateAbbr(identifier: string): string | null {
  const normalized = normalizeIdentifier(identifier);
  
  // If it's already a 2-letter code
  if (VALID_STATE_ABBR.has(normalized)) {
    return normalized;
  }
  
  // Try to convert from full name
  return stateNameToAbbr(normalized);
}

/**
 * Check if identifier is a valid region
 */
export function isValidRegion(identifier: string): boolean {
  const normalized = normalizeIdentifier(identifier);
  return VALID_REGIONS.has(normalized) || VALID_REGION_VARIANTS.has(identifier.toLowerCase().trim());
}

/**
 * Get region number from identifier (e.g., "region1" -> 1)
 */
export function getRegionNumber(identifier: string): number | null {
  const normalized = normalizeIdentifier(identifier);
  if (!VALID_REGIONS.has(normalized)) {
    return null;
  }
  
  const match = normalized.match(/region(\d+)/);
  return match ? parseInt(match[1], 10) : null;
}

/**
 * Check if identifier is "usa"
 */
export function isUSA(identifier: string): boolean {
  return normalizeIdentifier(identifier) === 'usa';
}

/**
 * Validate and normalize route parameters
 */
export function parseRouteParams(_year: string, identifier: string): {
  scope: 'usa' | 'state' | 'region' | null;
  normalizedIdentifier: string | null;
  displayName: string | null;
} {
  const normalizedId = normalizeIdentifier(identifier);
  
  if (isUSA(normalizedId)) {
    return {
      scope: 'usa',
      normalizedIdentifier: 'usa',
      displayName: 'United States',
    };
  }
  
  if (isValidState(normalizedId)) {
    const abbr = getStateAbbr(normalizedId);
    if (abbr) {
      // Get display name from abbreviation (uppercase for display)
      const displayName = abbr.toUpperCase();
      return {
        scope: 'state',
        normalizedIdentifier: abbr,
        displayName: displayName,
      };
    }
  }
  
  if (isValidRegion(normalizedId)) {
    const regionNum = getRegionNumber(normalizedId);
    if (regionNum) {
      // Region names will be determined from data
      return {
        scope: 'region',
        normalizedIdentifier: normalizedId,
        displayName: `Region ${regionNum}`,
      };
    }
  }
  
  return {
    scope: null,
    normalizedIdentifier: null,
    displayName: null,
  };
}

