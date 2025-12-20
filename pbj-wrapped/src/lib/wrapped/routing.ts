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

// Valid region identifiers
const VALID_REGIONS = new Set(['region1', 'region2', 'region3', 'region4', 'region5', 'region6', 'region7', 'region8', 'region9', 'region10']);

/**
 * Normalize URL identifier to lowercase
 */
export function normalizeIdentifier(identifier: string): string {
  return identifier.toLowerCase().trim();
}

/**
 * Convert state full name to abbreviation
 */
export function stateNameToAbbr(stateName: string): string | null {
  const normalized = normalizeIdentifier(stateName);
  return STATE_NAME_TO_ABBR[normalized] || null;
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
  return VALID_REGIONS.has(normalized);
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
export function parseRouteParams(year: string, identifier: string): {
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

