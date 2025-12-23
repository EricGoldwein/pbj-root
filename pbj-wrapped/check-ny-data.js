const fs = require('fs');
const Papa = require('papaparse');

const data = fs.readFileSync('../provider_info_combined.csv', 'utf8');

Papa.parse(data, {
  header: true,
  skipEmptyLines: true,
  complete: function(results) {
    const nyQ2 = results.data.filter(r => 
      (r.STATE === 'NY' || r.STATE === 'New York') && r.CY_Qtr === '2025Q2'
    );
    
    const sff = nyQ2.filter(r => {
      const s = (r.sff_status || '').trim().toUpperCase();
      return s === 'SFF' || s === 'SPECIAL FOCUS FACILITY';
    });
    
    const candidates = nyQ2.filter(r => {
      const s = (r.sff_status || '').trim().toUpperCase();
      return s === 'SFF CANDIDATE' || s === 'CANDIDATE';
    });
    
    const withOwnership = nyQ2.filter(r => 
      r.ownership_type && r.ownership_type.trim().length > 0
    );
    
    const forProfit = withOwnership.filter(r => {
      const o = r.ownership_type.toLowerCase();
      return o.includes('for profit') || o.includes('for-profit') || o.includes('forprofit');
    });
    
    const nonProfit = withOwnership.filter(r => {
      const o = r.ownership_type.toLowerCase();
      return o.includes('non profit') || o.includes('non-profit') || o.includes('nonprofit') || o.includes('not for profit');
    });
    
    const government = withOwnership.filter(r => {
      const o = r.ownership_type.toLowerCase();
      return o.includes('government') || o.includes('govt') || o.includes('state') || o.includes('county') || o.includes('city') || o.includes('federal');
    });
    
    console.log('NY Q2 2025 Analysis:');
    console.log('===================');
    console.log('Total facilities:', nyQ2.length);
    console.log('\nSpecial Focus Facilities:');
    console.log('  SFF:', sff.length);
    console.log('  SFF Candidates:', candidates.length);
    console.log('\nSFF Facilities:');
    sff.forEach(f => console.log('  -', f.PROVNAME, '(' + f.COUNTY_NAME + ')'));
    console.log('\nSFF Candidates:');
    candidates.forEach(f => console.log('  -', f.PROVNAME, '(' + f.COUNTY_NAME + ')'));
    console.log('\nOwnership Breakdown:');
    console.log('  Facilities with ownership data:', withOwnership.length);
    console.log('  For-profit:', forProfit.length, '(' + Math.round(forProfit.length / withOwnership.length * 100) + '%)');
    console.log('  Non-profit:', nonProfit.length, '(' + Math.round(nonProfit.length / withOwnership.length * 100) + '%)');
    console.log('  Government:', government.length, '(' + Math.round(government.length / withOwnership.length * 100) + '%)');
  }
});












