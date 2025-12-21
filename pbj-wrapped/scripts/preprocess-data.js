/**
 * Pre-process CSV data to JSON for faster loading
 * Run this once: node scripts/preprocess-data.js
 * 
 * Note: This uses dynamic import for ES modules
 */

import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import Papa from 'papaparse';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Try to find CSV files in parent directory (pbj-root) first, then fall back to public/data
const PARENT_DIR = join(__dirname, '../../');
const DATA_DIR = existsSync(join(PARENT_DIR, 'state_quarterly_metrics.csv')) 
  ? PARENT_DIR 
  : join(__dirname, '../public/data');

console.log(`Using DATA_DIR: ${DATA_DIR}`);
const OUTPUT_DIR = join(__dirname, '../public/data/json');

// Create output directory
if (!existsSync(OUTPUT_DIR)) {
  mkdirSync(OUTPUT_DIR, { recursive: true });
}

const TARGET_QUARTERS = ['2025Q1', '2025Q2'];

function parseCSV(filePath) {
  const csv = readFileSync(filePath, 'utf-8');
  return Papa.parse(csv, {
    header: true,
    skipEmptyLines: true,
    transformHeader: (header) => header.trim(),
    fastMode: true, // Faster parsing for large files
  }).data;
}

function parseCSVStreaming(filePath, callback) {
  // For very large files, use streaming parser
  return new Promise((resolve, reject) => {
    const csv = readFileSync(filePath, 'utf-8');
    const results = [];
    Papa.parse(csv, {
      header: true,
      skipEmptyLines: true,
      transformHeader: (header) => header.trim(),
      fastMode: true,
      step: (result) => {
        results.push(result.data);
        // Process in chunks to avoid memory issues
        if (results.length % 50000 === 0) {
          console.log(`  Processed ${results.length} rows...`);
        }
      },
      complete: () => {
        resolve(results);
      },
      error: (error) => {
        reject(error);
      },
    });
  });
}

function filterByQuarter(rows, quarters) {
  const normalizedQuarters = quarters.map(q => q.toUpperCase().replace(/\s+/g, ''));
  const filtered = rows.filter((row) => {
    // Try multiple possible field names for the quarter column
    const quarterValue = row.CY_Qtr || row.CY_QTR || row.cy_qtr || row['CY_Qtr'] || row['CY_QTR'];
    if (!quarterValue) return false;
    
    // Normalize: convert to string, trim, uppercase, remove spaces
    const q = quarterValue.toString().trim().toUpperCase().replace(/\s+/g, '');
    const matches = q && normalizedQuarters.includes(q);
    return matches;
  });
  
  // Debug: Log filtering results
  if (filtered.length === 0 && rows.length > 0) {
    const sampleQuarters = [...new Set(rows.slice(0, 20).map(r => r.CY_Qtr || r.CY_QTR || r.cy_qtr).filter(Boolean))];
    console.warn(`  ⚠️ No rows matched quarters ${quarters.join(', ')}. Sample quarters in data: ${sampleQuarters.slice(0, 5).join(', ')}`);
    // Show what the first row actually has
    if (rows[0]) {
      const firstRowQ = rows[0].CY_Qtr || rows[0].CY_QTR || rows[0].cy_qtr;
      console.warn(`  First row quarter field: "${firstRowQ || 'MISSING'}" (type: ${typeof firstRowQ})`);
    }
  }
  
  return filtered;
}

function parseNumeric(value) {
  const parsed = parseFloat(value);
  return isNaN(parsed) ? 0 : parsed;
}

function parseStateRow(row) {
  // CRITICAL: Get CY_Qtr FIRST before doing anything else
  // Papa Parse with transformHeader should give us 'CY_Qtr' exactly as in CSV
  const quarterValue = row.CY_Qtr || row['CY_Qtr'] || row.CY_QTR || row['CY_QTR'] || row.cy_qtr;
  
  // Build parsed row - preserve CY_Qtr explicitly
  const parsed = {
    STATE: (row.STATE || row.state || '').toString().trim().toUpperCase(),
    CY_Qtr: quarterValue, // CRITICAL: Preserve the quarter value AS-IS
    facility_count: parseNumeric(row.facility_count),
    avg_days_reported: parseNumeric(row.avg_days_reported),
    total_resident_days: parseNumeric(row.total_resident_days),
    avg_daily_census: parseNumeric(row.avg_daily_census),
    MDScensus: parseNumeric(row.MDScensus),
    Total_Nurse_Hours: parseNumeric(row.Total_Nurse_Hours),
    Total_RN_Hours: parseNumeric(row.Total_RN_Hours),
    Total_Nurse_Care_Hours: parseNumeric(row.Total_Nurse_Care_Hours),
    Total_RN_Care_Hours: parseNumeric(row.Total_RN_Care_Hours),
    Total_Nurse_Assistant_Hours: parseNumeric(row.Total_Nurse_Assistant_Hours),
    Total_Contract_Hours: parseNumeric(row.Total_Contract_Hours),
    Total_Nurse_HPRD: parseNumeric(row.Total_Nurse_HPRD),
    RN_HPRD: parseNumeric(row.RN_HPRD),
    Nurse_Care_HPRD: parseNumeric(row.Nurse_Care_HPRD),
    RN_Care_HPRD: parseNumeric(row.RN_Care_HPRD),
    Nurse_Assistant_HPRD: parseNumeric(row.Nurse_Assistant_HPRD),
    Contract_Percentage: parseNumeric(row.Contract_Percentage),
    Direct_Care_Percentage: parseNumeric(row.Direct_Care_Percentage),
    Total_RN_Percentage: parseNumeric(row.Total_RN_Percentage),
    Nurse_Aide_Percentage: parseNumeric(row.Nurse_Aide_Percentage),
  };
  
  // Copy any remaining fields from original row
  for (const key in row) {
    if (!(key in parsed)) {
      parsed[key] = row[key];
    }
  }
  
  return parsed;
}

function parseRegionRow(row) {
  return {
    ...row,
    REGION_NUMBER: parseInt(row.REGION_NUMBER, 10) || 0,
    facility_count: parseNumeric(row.facility_count),
    avg_days_reported: parseNumeric(row.avg_days_reported),
    total_resident_days: parseNumeric(row.total_resident_days),
    avg_daily_census: parseNumeric(row.avg_daily_census),
    MDScensus: parseNumeric(row.MDScensus),
    Total_Nurse_Hours: parseNumeric(row.Total_Nurse_Hours),
    Total_RN_Hours: parseNumeric(row.Total_RN_Hours),
    Total_Nurse_Care_Hours: parseNumeric(row.Total_Nurse_Care_Hours),
    Total_RN_Care_Hours: parseNumeric(row.Total_RN_Care_Hours),
    Total_Nurse_Assistant_Hours: parseNumeric(row.Total_Nurse_Assistant_Hours),
    Total_Contract_Hours: parseNumeric(row.Total_Contract_Hours),
    Total_Nurse_HPRD: parseNumeric(row.Total_Nurse_HPRD),
    RN_HPRD: parseNumeric(row.RN_HPRD),
    Nurse_Care_HPRD: parseNumeric(row.Nurse_Care_HPRD),
    RN_Care_HPRD: parseNumeric(row.RN_Care_HPRD),
    Nurse_Assistant_HPRD: parseNumeric(row.Nurse_Assistant_HPRD),
    Contract_Percentage: parseNumeric(row.Contract_Percentage),
    Direct_Care_Percentage: parseNumeric(row.Direct_Care_Percentage),
    Total_RN_Percentage: parseNumeric(row.Total_RN_Percentage),
    Nurse_Aide_Percentage: parseNumeric(row.Nurse_Aide_Percentage),
  };
}

function parseNationalRow(row) {
  return {
    ...row,
    facility_count: parseNumeric(row.facility_count),
    avg_days_reported: parseNumeric(row.avg_days_reported),
    total_resident_days: parseNumeric(row.total_resident_days),
    avg_daily_census: parseNumeric(row.avg_daily_census),
    MDScensus: parseNumeric(row.MDScensus),
    Total_Nurse_Hours: parseNumeric(row.Total_Nurse_Hours),
    Total_RN_Hours: parseNumeric(row.Total_RN_Hours),
    Total_Nurse_Care_Hours: parseNumeric(row.Total_Nurse_Care_Hours),
    Total_RN_Care_Hours: parseNumeric(row.Total_RN_Care_Hours),
    Total_Nurse_Assistant_Hours: parseNumeric(row.Total_Nurse_Assistant_Hours),
    Total_Contract_Hours: parseNumeric(row.Total_Contract_Hours),
    Total_Nurse_HPRD: parseNumeric(row.Total_Nurse_HPRD),
    RN_HPRD: parseNumeric(row.RN_HPRD),
    Nurse_Care_HPRD: parseNumeric(row.Nurse_Care_HPRD),
    RN_Care_HPRD: parseNumeric(row.RN_Care_HPRD),
    Nurse_Assistant_HPRD: parseNumeric(row.Nurse_Assistant_HPRD),
    Contract_Percentage: parseNumeric(row.Contract_Percentage),
  };
}

function parseFacilityRow(row) {
  return {
    ...row,
    Total_Nurse_HPRD: parseNumeric(row.Total_Nurse_HPRD),
    Nurse_Care_HPRD: parseNumeric(row.Nurse_Care_HPRD),
    Total_RN_HPRD: parseNumeric(row.Total_RN_HPRD),
    Direct_Care_RN_HPRD: parseNumeric(row.Direct_Care_RN_HPRD),
    Contract_Percentage: parseNumeric(row.Contract_Percentage),
    Census: parseNumeric(row.Census),
  };
}

function parseProviderInfoRow(row) {
  // Map lowercase CSV column names to our interface names
  const quarter = (row.quarter || row.CY_Qtr || '').trim().toUpperCase().replace(/\s+/g, '');
  
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
      ? parseNumeric(row.case_mix_total_nurse_hrs_per_resident_per_day)
      : undefined,
    case_mix_rn_hrs_per_resident_per_day: row.case_mix_rn_hrs_per_resident_per_day
      ? parseNumeric(row.case_mix_rn_hrs_per_resident_per_day)
      : undefined,
    avg_residents_per_day: row.avg_residents_per_day
      ? parseNumeric(row.avg_residents_per_day)
      : undefined,
  };
}

// Process provider info using streaming to avoid memory issues
function processProviderInfo() {
  return new Promise((resolve, reject) => {
    console.log('Processing provider info (this may take a while - large file)...');
    console.log('  Loading and filtering data in streaming mode...');
    
    const providerQ1 = [];
    const providerQ2 = [];
    
    const csv = readFileSync(join(DATA_DIR, 'provider_info_combined.csv'), 'utf-8');
    let processedRows = 0;
    
    Papa.parse(csv, {
      header: true,
      skipEmptyLines: true,
      transformHeader: (header) => header.trim(),
      fastMode: true,
      step: (result) => {
        const row = parseProviderInfoRow(result.data);
        processedRows++;
        
        // Only keep rows for Q1 and Q2
        // Use the parseProviderInfoRow function which handles column mapping
        const parsedRow = parseProviderInfoRow(result.data);
        
        // Only keep rows for Q1 and Q2
        if (parsedRow.CY_Qtr === '2025Q1' || parsedRow.CY_Qtr === '2025Q2') {
          if (parsedRow.CY_Qtr === '2025Q1') {
            providerQ1.push(parsedRow);
          } else if (parsedRow.CY_Qtr === '2025Q2') {
            providerQ2.push(parsedRow);
          }
        }
        
        // Progress indicator
        if (processedRows % 100000 === 0) {
          console.log(`  Processed ${processedRows.toLocaleString()} rows... (Q1: ${providerQ1.length}, Q2: ${providerQ2.length})`);
        }
      },
      complete: () => {
        console.log(`  Total processed: ${processedRows.toLocaleString()} rows`);
        writeFileSync(join(OUTPUT_DIR, 'provider_q1.json'), JSON.stringify(providerQ1));
        writeFileSync(join(OUTPUT_DIR, 'provider_q2.json'), JSON.stringify(providerQ2));
        console.log(`  Q1: ${providerQ1.length} rows, Q2: ${providerQ2.length} rows`);
        resolve({ providerQ1, providerQ2 });
      },
      error: (error) => {
        console.error('Error parsing provider info:', error);
        reject(error);
      },
    });
  });
}

async function runPreprocessing() {
  try {
    console.log('Starting data preprocessing...');
    console.log('Using increased memory limit (8GB) for large files...\n');

    // Process state data
    console.log('Processing state data...');
    const stateFilePath = join(DATA_DIR, 'state_quarterly_metrics.csv');
    if (!existsSync(stateFilePath)) {
      console.error(`ERROR: State CSV file not found at ${stateFilePath}`);
      throw new Error(`State CSV file not found at ${stateFilePath}`);
    }
    
    const rawStateRows = parseCSV(stateFilePath);
    console.log(`  Total raw rows loaded: ${rawStateRows.length}`);
    
    // CRITICAL DEBUG: Check CSV headers and first row BEFORE parsing
    if (rawStateRows.length > 0) {
      const firstRow = rawStateRows[0];
      const keys = Object.keys(firstRow);
      console.log(`  First row keys (first 10): ${keys.slice(0, 10).join(', ')}`);
      console.log(`  First row CY_Qtr value: "${firstRow.CY_Qtr}" (raw, before parsing, type: ${typeof firstRow.CY_Qtr})`);
      console.log(`  First row STATE value: "${firstRow.STATE}"`);
      
      // Check if CY_Qtr exists in the raw data
      if (!firstRow.CY_Qtr) {
        console.error(`  ❌ ERROR: CY_Qtr field is MISSING from raw CSV data!`);
        console.error(`  Available fields: ${keys.join(', ')}`);
      }
    }
    
    const stateRows = rawStateRows.map(parseStateRow);
    console.log(`  Total rows after parsing: ${stateRows.length}`);
    
    // CRITICAL: Verify CY_Qtr is preserved after parsing
    if (stateRows.length > 0) {
      const sampleRow = stateRows[0];
      console.log(`  Sample parsed row - STATE: "${sampleRow.STATE}", CY_Qtr: "${sampleRow.CY_Qtr}" (type: ${typeof sampleRow.CY_Qtr})`);
      
      // Check if any rows have 2025Q1 - do this BEFORE filtering
      const q1Test = stateRows.filter(r => {
        const q = (r.CY_Qtr || '').toString().trim().toUpperCase();
        return q === '2025Q1';
      });
      console.log(`  ✅ Rows with exact "2025Q1" match BEFORE filterByQuarter: ${q1Test.length}`);
      
      if (q1Test.length > 0) {
        console.log(`  ✅ Sample Q1 row: STATE=${q1Test[0].STATE}, CY_Qtr="${q1Test[0].CY_Qtr}"`);
      }
    }
    
    // Debug: Check what quarters exist in the data AFTER parsing
    const allQuarters = [...new Set(stateRows.map(r => r.CY_Qtr).filter(Boolean))].sort();
    const quarters2025 = allQuarters.filter(q => {
      const qStr = q.toString().toUpperCase();
      return qStr.includes('2025');
    });
    console.log(`  Found 2025 quarters: ${quarters2025.join(', ')}`);
    console.log(`  All unique quarters (first 20): ${allQuarters.slice(0, 20).join(', ')}`);
    
    // Try filtering with multiple quarter format attempts
    let stateQ1 = filterByQuarter(stateRows, ['2025Q1']);
    let stateQ2 = filterByQuarter(stateRows, ['2025Q2']);
    
    console.log(`  After filterByQuarter - Q1: ${stateQ1.length} rows, Q2: ${stateQ2.length} rows`);
    
    // If Q1 is empty, try DIRECT filtering (bypass filterByQuarter)
    if (stateQ1.length === 0) {
      console.warn(`  ⚠️ No 2025Q1 data found with filterByQuarter. Trying DIRECT filtering...`);
      const sampleQuarters = [...new Set(stateRows.slice(0, 100).map(r => r.CY_Qtr).filter(Boolean))];
      console.warn(`  Sample quarter values from first 100 rows: ${sampleQuarters.slice(0, 10).join(', ')}`);
      
      // DIRECT filter - check every row manually
      stateQ1 = stateRows.filter((row) => {
        const q = (row.CY_Qtr || '').toString().trim().toUpperCase().replace(/\s+/g, '');
        const matches = q === '2025Q1';
        return matches;
      });
      
      stateQ2 = stateRows.filter((row) => {
        const q = (row.CY_Qtr || '').toString().trim().toUpperCase().replace(/\s+/g, '');
        const matches = q === '2025Q2';
        return matches;
      });
      
      console.log(`  After DIRECT filtering - Q1: ${stateQ1.length} rows, Q2: ${stateQ2.length} rows`);
      
      // If STILL empty, try even more flexible matching
      if (stateQ1.length === 0) {
        console.warn(`  ⚠️ Still no Q1 data. Trying flexible matching...`);
        stateQ1 = stateRows.filter((row) => {
          const q = (row.CY_Qtr || '').toString().trim().toUpperCase();
          return q.includes('2025') && q.includes('Q1');
        });
        stateQ2 = stateRows.filter((row) => {
          const q = (row.CY_Qtr || '').toString().trim().toUpperCase();
          return q.includes('2025') && q.includes('Q2');
        });
        console.log(`  After flexible matching - Q1: ${stateQ1.length} rows, Q2: ${stateQ2.length} rows`);
      }
    }
    
    // Debug: Check if NY exists in Q1
    const nyQ1 = stateQ1.find(s => s.STATE === 'NY');
    const nyQ2 = stateQ2.find(s => s.STATE === 'NY');
    console.log(`  NY Q1: ${nyQ1 ? `found (Total HPRD: ${nyQ1.Total_Nurse_HPRD})` : 'NOT FOUND'}`);
    console.log(`  NY Q2: ${nyQ2 ? `found (Total HPRD: ${nyQ2.Total_Nurse_HPRD})` : 'NOT FOUND'}`);
    
    // Final check - if still empty, show detailed debug info
    if (stateQ1.length === 0) {
      console.error(`  ❌ CRITICAL: Still no Q1 data after all attempts!`);
      if (stateRows.length > 0) {
        const firstRow = stateRows[0];
        console.error(`  First row sample: STATE=${firstRow.STATE}, CY_Qtr="${firstRow.CY_Qtr}", type=${typeof firstRow.CY_Qtr}`);
        const allUniqueQuarters = [...new Set(stateRows.map(r => r.CY_Qtr).filter(Boolean))].sort();
        console.error(`  All unique quarters in CSV: ${allUniqueQuarters.slice(0, 20).join(', ')}`);
      }
    }
    
    // Write JSON files
    const q1Path = join(OUTPUT_DIR, 'state_q1.json');
    const q2Path = join(OUTPUT_DIR, 'state_q2.json');
    writeFileSync(q1Path, JSON.stringify(stateQ1));
    writeFileSync(q2Path, JSON.stringify(stateQ2));
    console.log(`  ✅ Q1: ${stateQ1.length} rows written to state_q1.json`);
    console.log(`  ✅ Q2: ${stateQ2.length} rows written to state_q2.json`);
    
    // Verify files were written
    if (stateQ1.length === 0) {
      console.error(`  ❌ ERROR: state_q1.json is EMPTY! Q1 data was not found in CSV.`);
      console.error(`  This means trends will show 0.00. Check the CSV file for 2025Q1 data.`);
    } else {
      console.log(`  ✅ SUCCESS: state_q1.json contains ${stateQ1.length} rows of Q1 data`);
    }

    // Process region data
    console.log('Processing region data...');
    const regionRows = parseCSV(join(DATA_DIR, 'cms_region_quarterly_metrics.csv')).map(parseRegionRow);
    const regionQ1 = filterByQuarter(regionRows, ['2025Q1']);
    const regionQ2 = filterByQuarter(regionRows, ['2025Q2']);
    writeFileSync(join(OUTPUT_DIR, 'region_q1.json'), JSON.stringify(regionQ1));
    writeFileSync(join(OUTPUT_DIR, 'region_q2.json'), JSON.stringify(regionQ2));
    console.log(`  Q1: ${regionQ1.length} rows, Q2: ${regionQ2.length} rows`);

    // Process national data
    console.log('Processing national data...');
    const nationalRows = parseCSV(join(DATA_DIR, 'national_quarterly_metrics.csv')).map(parseNationalRow);
    const nationalQ1 = filterByQuarter(nationalRows, ['2025Q1'])[0] || null;
    const nationalQ2 = filterByQuarter(nationalRows, ['2025Q2'])[0] || null;
    writeFileSync(join(OUTPUT_DIR, 'national_q1.json'), JSON.stringify(nationalQ1));
    writeFileSync(join(OUTPUT_DIR, 'national_q2.json'), JSON.stringify(nationalQ2));
    console.log(`  Q1: ${nationalQ1 ? 'found' : 'not found'}, Q2: ${nationalQ2 ? 'found' : 'not found'}`);

    // Process facility data (only Q1 and Q2)
    console.log('Processing facility data (this may take a while)...');
    const facilityRows = parseCSV(join(DATA_DIR, 'facility_lite_metrics.csv')).map(parseFacilityRow);
    const facilityQ1 = filterByQuarter(facilityRows, ['2025Q1']);
    const facilityQ2 = filterByQuarter(facilityRows, ['2025Q2']);
    writeFileSync(join(OUTPUT_DIR, 'facility_q1.json'), JSON.stringify(facilityQ1));
    writeFileSync(join(OUTPUT_DIR, 'facility_q2.json'), JSON.stringify(facilityQ2));
    console.log(`  Q1: ${facilityQ1.length} rows, Q2: ${facilityQ2.length} rows`);

    // Process provider info using streaming (async)
    const { providerQ1, providerQ2 } = await processProviderInfo();

    // Process region-state mapping
    console.log('Processing region-state mapping...');
    const mappingRows = parseCSV(join(DATA_DIR, 'cms_region_state_mapping.csv'));
    const regionStateMapping = {};
    for (const row of mappingRows) {
      const regionNum = parseInt(row.CMS_Region_Number, 10);
      const stateCode = row.State_Code?.trim();
      if (regionNum && stateCode) {
        if (!regionStateMapping[regionNum]) {
          regionStateMapping[regionNum] = [];
        }
        regionStateMapping[regionNum].push(stateCode);
      }
    }
    writeFileSync(join(OUTPUT_DIR, 'region_state_mapping.json'), JSON.stringify(regionStateMapping));
    console.log(`  Mapped ${Object.keys(regionStateMapping).length} regions`);

    // Process state standards (macpac data)
    console.log('\nProcessing state standards...');
    const stateStandardsFilePath = join(DATA_DIR, 'macpac_state_standards_clean.csv');
    let stateStandardsMap = {};
    if (existsSync(stateStandardsFilePath)) {
      const stateStandardsRows = parseCSV(stateStandardsFilePath);
      console.log(`  Loaded ${stateStandardsRows.length} state standard rows`);
      
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
      writeFileSync(join(OUTPUT_DIR, 'state_standards.json'), JSON.stringify(stateStandardsMap));
      console.log(`  Processed ${Object.keys(stateStandardsMap).length} state standards`);
    } else {
      console.log(`  ⚠️ State standards file not found at ${stateStandardsFilePath}`);
    }

    // Create state-specific facility/provider files for faster loading
    console.log('\nCreating state-specific data files for faster loading...');
    const stateCodes = new Set();
    for (const row of facilityQ2) {
      if (row.STATE) {
        // Sanitize state code - only allow 2-letter uppercase codes
        const sanitized = row.STATE.trim().toUpperCase().replace(/[^A-Z]/g, '');
        if (sanitized.length === 2) {
          stateCodes.add(sanitized);
        }
      }
    }
    
    // Valid US state codes (50 states + DC)
    const validStateCodes = new Set([
      'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
      'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
      'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
      'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
      'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'
    ]);
    
    let stateFilesCreated = 0;
    for (const stateCode of stateCodes) {
      // Only process valid 2-letter state codes
      if (!validStateCodes.has(stateCode)) {
        console.log(`  Skipping invalid state code: ${stateCode}`);
        continue;
      }
      
      const stateFacilitiesQ1 = facilityQ1.filter(f => f.STATE === stateCode);
      const stateFacilitiesQ2 = facilityQ2.filter(f => f.STATE === stateCode);
      const stateProvidersQ1 = providerQ1.filter(p => p.STATE === stateCode);
      const stateProvidersQ2 = providerQ2.filter(p => p.STATE === stateCode);
      
      if (stateFacilitiesQ1.length > 0 || stateFacilitiesQ2.length > 0) {
        writeFileSync(join(OUTPUT_DIR, `facility_${stateCode}_q1.json`), JSON.stringify(stateFacilitiesQ1));
        writeFileSync(join(OUTPUT_DIR, `facility_${stateCode}_q2.json`), JSON.stringify(stateFacilitiesQ2));
        writeFileSync(join(OUTPUT_DIR, `provider_${stateCode}_q1.json`), JSON.stringify(stateProvidersQ1));
        writeFileSync(join(OUTPUT_DIR, `provider_${stateCode}_q2.json`), JSON.stringify(stateProvidersQ2));
        stateFilesCreated++;
      }
    }
    console.log(`  Created ${stateFilesCreated} state-specific file sets`);

    // Create region-specific facility/provider files
    console.log('Creating region-specific data files...');
    let regionFilesCreated = 0;
    for (const [regionNum, stateCodes] of Object.entries(regionStateMapping)) {
      const regionStates = new Set(stateCodes);
      const regionFacilitiesQ1 = facilityQ1.filter(f => regionStates.has(f.STATE));
      const regionFacilitiesQ2 = facilityQ2.filter(f => regionStates.has(f.STATE));
      const regionProvidersQ1 = providerQ1.filter(p => regionStates.has(p.STATE));
      const regionProvidersQ2 = providerQ2.filter(p => regionStates.has(p.STATE));
      
      if (regionFacilitiesQ1.length > 0 || regionFacilitiesQ2.length > 0) {
        writeFileSync(join(OUTPUT_DIR, `facility_region${regionNum}_q1.json`), JSON.stringify(regionFacilitiesQ1));
        writeFileSync(join(OUTPUT_DIR, `facility_region${regionNum}_q2.json`), JSON.stringify(regionFacilitiesQ2));
        writeFileSync(join(OUTPUT_DIR, `provider_region${regionNum}_q1.json`), JSON.stringify(regionProvidersQ1));
        writeFileSync(join(OUTPUT_DIR, `provider_region${regionNum}_q2.json`), JSON.stringify(regionProvidersQ2));
        regionFilesCreated++;
      }
    }
    console.log(`  Created ${regionFilesCreated} region-specific file sets`);

    console.log('\n✅ Data preprocessing complete!');
    console.log(`Output directory: ${OUTPUT_DIR}`);
    console.log(`\n💡 State and region-specific files created for faster loading!`);
  } catch (error) {
    console.error('Error preprocessing data:', error);
    process.exit(1);
  }
}

// Run the async preprocessing
runPreprocessing();

