import React, { useEffect, useRef } from 'react';
import { loadMapLibraries } from '../../lib/mapScripts';

interface StateOutlineProps {
  stateCode: string;
  className?: string;
}

/**
 * State outline SVG component using D3 and US Atlas
 * This provides accurate state outlines
 */
export const StateOutline: React.FC<StateOutlineProps> = ({ stateCode, className = '' }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!svgRef.current || !containerRef.current) return;

    const stateAbbr = stateCode.toUpperCase();
    
    // State name mapping
    const stateNameMap: Record<string, string> = {
      'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
      'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
      'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
      'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
      'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
      'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
      'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
      'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
      'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
      'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
      'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
      'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
      'WI': 'Wisconsin', 'WY': 'Wyoming', 'DC': 'District of Columbia',
    };

    const stateName = stateNameMap[stateAbbr];
    if (!stateName) return;

    const showFallback = () => {
      if (!svgRef.current) return;
      // Fallback: show state code as text
      svgRef.current.innerHTML = `
        <text x="200" y="200" text-anchor="middle" dominant-baseline="middle" 
              font-size="72" font-weight="bold" fill="currentColor" 
              class="text-blue-400 opacity-30">${stateAbbr}</text>
      `;
      svgRef.current.setAttribute('viewBox', '0 0 400 400');
    };

    const drawState = async () => {
      try {
        const { d3, topojson } = await loadMapLibraries();
        if (!d3 || !topojson) {
          showFallback();
          return;
        }

        const d3lib = d3 as any;
        const svg = d3lib.select(svgRef.current);
        svg.selectAll('*').remove();

        const width = 400;
        const height = 400;
        svg.attr('width', width).attr('height', height).attr('viewBox', `0 0 ${width} ${height}`);

        // Load US map data
        const us = await d3lib.json('https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json');
        const states = topojson.feature(us, (us as { objects: { states: unknown } }).objects.states) as { features: Array<{ properties: { name?: string; abbrev?: string } }> };

        // Find the specific state - try both name and abbreviation
        let stateFeature = states.features.find((f: any) => f.properties.name === stateName);
        if (!stateFeature) {
          // Try abbreviation as fallback
          stateFeature = states.features.find((f: any) => f.properties.abbrev === stateAbbr);
        }
        if (!stateFeature) {
          showFallback();
          return;
        }

        // Create projection to fit the state
        const projection = d3lib.geoAlbersUsa()
          .fitSize([width - 40, height - 40], { type: 'FeatureCollection', features: [stateFeature] });

        const path = d3lib.geoPath().projection(projection);

        // Draw the state
        svg.append('g')
          .append('path')
          .datum(stateFeature)
          .attr('d', path)
          .attr('fill', 'none')
          .attr('stroke', 'currentColor')
          .attr('stroke-width', '2')
          .attr('class', 'text-blue-400')
          .attr('stroke-linecap', 'round')
          .attr('stroke-linejoin', 'round');


      } catch {
        showFallback();
      }
    };

    drawState();
  }, [stateCode]);

  return (
    <div ref={containerRef} className={`flex items-center justify-center ${className}`} style={{ width: '100%', height: '100%' }}>
      <svg
        ref={svgRef}
        className="w-full h-full"
        style={{ width: '100%', height: '100%', maxWidth: '400px', maxHeight: '400px' }}
        viewBox="0 0 400 400"
        preserveAspectRatio="xMidYMid meet"
      />
    </div>
  );
};
