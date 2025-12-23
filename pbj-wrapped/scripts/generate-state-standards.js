/**
 * Generate state_standards.json from macpac_state_standards_clean.csv
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import Papa from 'papaparse';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const DATA_DIR = join(__dirname, '../public/data');
const OUTPUT_DIR = join(__dirname, '../dist/data/json');

// Create output directory
if (!existsSync(OUTPUT_DIR)) {
  mkdirSync(OUTPUT_DIR, { recursive: true });
}

const stateStandardsFilePath = join(DATA_DIR, 'macpac_state_standards_clean.csv');
const outputPath = join(OUTPUT_DIR, 'state_standards.json');

if (!existsSync(stateStandardsFilePath)) {
  console.error(`ERROR: State standards CSV file not found at ${stateStandardsFilePath}`);
  process.exit(1);
}

console.log(`Reading from: ${stateStandardsFilePath}`);
const csv = readFileSync(stateStandardsFilePath, 'utf-8');
const stateStandardsRows = Papa.parse(csv, {
  header: true,
  skipEmptyLines: true,
  transformHeader: (header) => header.trim(),
}).data;

console.log(`Loaded ${stateStandardsRows.length} state standard rows`);

// State name to abbreviation mapping
const STATE_NAME_TO_ABBR = {
  'alabama': 'al', 'alaska': 'ak', 'arizona': 'az', 'arkansas': 'ar',
  'california': 'ca', 'colorado': 'co', 'connecticut': 'ct', 'delaware': 'de',
  'florida': 'fl', 'georgia': 'ga', 'hawaii': 'hi', 'idaho': 'id',
  'illinois': 'il', 'indiana': 'in', 'iowa': 'ia', 'kansas': 'ks',
  'kentucky': 'ky', 'louisiana': 'la', 'maine': 'me', 'maryland': 'md',
  'massachusetts': 'ma', 'michigan': 'mi', 'minnesota': 'mn', 'mississippi': 'ms',
  'missouri': 'mo', 'montana': 'mt', 'nebraska': 'ne', 'nevada': 'nv',
  'new hampshire': 'nh', 'new jersey': 'nj', 'new mexico': 'nm', 'new york': 'ny',
  'north carolina': 'nc', 'north dakota': 'nd', 'ohio': 'oh', 'oklahoma': 'ok',
  'oregon': 'or', 'pennsylvania': 'pa', 'rhode island': 'ri', 'south carolina': 'sc',
  'south dakota': 'sd', 'tennessee': 'tn', 'texas': 'tx', 'utah': 'ut',
  'vermont': 'vt', 'virginia': 'va', 'washington': 'wa', 'west virginia': 'wv',
  'wisconsin': 'wi', 'wyoming': 'wy', 'district of columbia': 'dc', 'washington dc': 'dc', 'dc': 'dc',
};

function stateNameToAbbr(stateName) {
  const normalized = (stateName || '').trim().toLowerCase();
  return STATE_NAME_TO_ABBR[normalized] || null;
}

function parseNumeric(val) {
  const num = parseFloat(val);
  return isNaN(num) ? 0 : num;
}

const stateStandardsMap = {};

for (const row of stateStandardsRows) {
  const minStaffing = parseNumeric(row.Min_Staffing);
  // Only include states with requirements >= 1.00
  if (minStaffing >= 1.0) {
    const stateName = row.State?.trim();
    if (stateName) {
      const stateCode = stateNameToAbbr(stateName);
      if (stateCode) {
        const key = stateCode.toLowerCase();
        stateStandardsMap[key] = {
          State: stateName,
          Total_Estimated_Staffing_Requirements: row.Total_Estimated_Staffing_Requirements || '',
          Min_Staffing: minStaffing,
          Max_Staffing: parseNumeric(row.Max_Staffing) || minStaffing,
          Value_Type: row.Value_Type || 'single',
          Is_Federal_Minimum: row.Is_Federal_Minimum || 'False',
          Display_Text: row.Display_Text || '',
        };
      }
    }
  }
}

writeFileSync(outputPath, JSON.stringify(stateStandardsMap, null, 2));
console.log(`✅ Generated state_standards.json with ${Object.keys(stateStandardsMap).length} states`);
console.log(`Output: ${outputPath}`);

