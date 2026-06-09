import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { loadMapLibraries } from '../../lib/mapScripts';

interface USMapProps {
  className?: string;
}

// State abbreviation mapping
const STATE_ABBR_MAP: Record<string, string> = {
  'Alabama': 'al', 'Alaska': 'ak', 'Arizona': 'az', 'Arkansas': 'ar',
  'California': 'ca', 'Colorado': 'co', 'Connecticut': 'ct', 'Delaware': 'de',
  'Florida': 'fl', 'Georgia': 'ga', 'Hawaii': 'hi', 'Idaho': 'id',
  'Illinois': 'il', 'Indiana': 'in', 'Iowa': 'ia', 'Kansas': 'ks',
  'Kentucky': 'ky', 'Louisiana': 'la', 'Maine': 'me', 'Maryland': 'md',
  'Massachusetts': 'ma', 'Michigan': 'mi', 'Minnesota': 'mn', 'Mississippi': 'ms',
  'Missouri': 'mo', 'Montana': 'mt', 'Nebraska': 'ne', 'Nevada': 'nv',
  'New Hampshire': 'nh', 'New Jersey': 'nj', 'New Mexico': 'nm', 'New York': 'ny',
  'North Carolina': 'nc', 'North Dakota': 'nd', 'Ohio': 'oh', 'Oklahoma': 'ok',
  'Oregon': 'or', 'Pennsylvania': 'pa', 'Rhode Island': 'ri', 'South Carolina': 'sc',
  'South Dakota': 'sd', 'Tennessee': 'tn', 'Texas': 'tx', 'Utah': 'ut',
  'Vermont': 'vt', 'Virginia': 'va', 'Washington': 'wa', 'West Virginia': 'wv',
  'Wisconsin': 'wi', 'Wyoming': 'wy', 'District of Columbia': 'dc',
};

export const USMap: React.FC<USMapProps> = ({ className = '' }) => {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const [hoveredState, setHoveredState] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (!svgRef.current || !containerRef.current) return;

    const drawMap = async () => {
      try {
        setIsLoading(true);
        const { d3, topojson } = await loadMapLibraries();
        if (!d3 || !topojson) {
          setIsLoading(false);
          return;
        }
        const d3lib = d3 as any;

        const svg = d3lib.select(svgRef.current);
        svg.selectAll('*').remove();

        const container = containerRef.current;
        const width = container?.offsetWidth || 800;
        const height = Math.min(width * 0.55, 450);

        svg.attr('width', width).attr('height', height).attr('viewBox', `0 0 ${width} ${height}`);

        // Load US map data
        const us = await d3lib.json('https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json');
        const states = topojson.feature(us, (us as { objects: { states: unknown } }).objects.states) as { features: unknown[] };

        // Create projection
        const projection = d3lib.geoAlbersUsa().fitSize([width - 20, height - 20], states);
        const path = d3lib.geoPath().projection(projection);

        // Draw states
        svg.selectAll('.state')
          .data(states.features)
          .enter()
          .append('path')
          .attr('class', 'state')
          .attr('d', path)
          .attr('data-state', (d: any) => d.properties.name)
          .style('fill', (_d: any, i: number) => {
            // Subtle color variation
            return `rgba(59, 130, 246, ${0.3 + (i % 3) * 0.1})`;
          })
          .style('stroke', '#ffffff')
          .style('stroke-width', '1.5px')
          .style('cursor', 'pointer')
          .on('mouseover', function(this: SVGPathElement, _event: MouseEvent, d: any) {
            const stateName = d.properties.name;
            setHoveredState(stateName);
            d3lib.select(this)
              .transition()
              .duration(200)
              .style('fill', 'rgba(59, 130, 246, 0.7)')
              .style('stroke-width', '2.5px');
          })
          .on('mouseout', function(this: SVGPathElement, _event: MouseEvent, _d: any) {
            setHoveredState(null);
            d3lib.select(this)
              .transition()
              .duration(200)
              .style('fill', (_d: any, i: number) => `rgba(59, 130, 246, ${0.3 + (i % 3) * 0.1})`)
              .style('stroke-width', '1.5px');
          })
          .on('click', function(_event: MouseEvent, d: any) {
            const stateName = d.properties.name;
            const stateAbbr = STATE_ABBR_MAP[stateName];
            if (stateAbbr) {
              // Force absolute path navigation - ensure /wrapped prefix is preserved
              const targetPath = `/wrapped/${stateAbbr.toLowerCase()}`;
              navigate(targetPath, { replace: false });
            }
          });

        setIsLoading(false);
      } catch {
        setIsLoading(false);
      }
    };

    drawMap();

    // Handle resize
    const handleResize = () => {
      if (svgRef.current && containerRef.current) {
        drawMap();
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [navigate]);

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-900/50 rounded-lg">
          <div className="text-blue-300 text-sm">Loading map...</div>
        </div>
      )}
      <svg
        ref={svgRef}
        className="w-full h-auto"
        style={{ minHeight: '220px' }}
      />
      {hoveredState && (
        <div className="absolute top-2 left-1/2 -translate-x-1/2 bg-black/80 text-white px-4 py-2 rounded-lg text-sm font-medium pointer-events-none z-10">
          {hoveredState} Wrapped
        </div>
      )}
    </div>
  );
};

