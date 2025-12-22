import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

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

    const loadScript = (src: string): Promise<void> => {
      return new Promise((resolve, reject) => {
        if ((window as any).d3 && src.includes('d3')) {
          resolve();
          return;
        }
        if ((window as any).topojson && src.includes('topojson')) {
          resolve();
          return;
        }
        const script = document.createElement('script');
        script.src = src;
        script.onload = () => resolve();
        script.onerror = () => reject(new Error(`Failed to load ${src}`));
        document.head.appendChild(script);
      });
    };

    const drawMap = async () => {
      try {
        setIsLoading(true);
        await Promise.all([
          loadScript('https://d3js.org/d3.v7.min.js'),
          loadScript('https://cdn.jsdelivr.net/npm/topojson-client@3'),
        ]);

        await new Promise(resolve => setTimeout(resolve, 100));

        const d3 = (window as any).d3;
        const topojson = (window as any).topojson;

        if (!d3 || !topojson) {
          console.error('D3 or TopoJSON not loaded');
          setIsLoading(false);
          return;
        }

        const svg = d3.select(svgRef.current);
        svg.selectAll('*').remove();

        const container = containerRef.current;
        const width = container?.offsetWidth || 800;
        const height = Math.min(width * 0.55, 450);

        svg.attr('width', width).attr('height', height).attr('viewBox', `0 0 ${width} ${height}`);

        // Load US map data
        const us = await d3.json('https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json');
        const states = topojson.feature(us, us.objects.states);

        // Create projection
        const projection = d3.geoAlbersUsa().fitSize([width - 20, height - 20], states);
        const path = d3.geoPath().projection(projection);

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
            d3.select(this)
              .transition()
              .duration(200)
              .style('fill', 'rgba(59, 130, 246, 0.7)')
              .style('stroke-width', '2.5px');
          })
          .on('mouseout', function(this: SVGPathElement, _event: MouseEvent, _d: any) {
            setHoveredState(null);
            d3.select(this)
              .transition()
              .duration(200)
              .style('fill', (_d: any, i: number) => `rgba(59, 130, 246, ${0.3 + (i % 3) * 0.1})`)
              .style('stroke-width', '1.5px');
          })
          .on('click', function(_event: MouseEvent, d: any) {
            const stateName = d.properties.name;
            const stateAbbr = STATE_ABBR_MAP[stateName];
            if (stateAbbr) {
              navigate(`/wrapped/${stateAbbr}`);
            }
          });

        setIsLoading(false);
      } catch (error) {
        console.error('Error drawing map:', error);
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
        style={{ minHeight: '300px' }}
      />
      {hoveredState && (
        <div className="absolute top-2 left-1/2 -translate-x-1/2 bg-black/80 text-white px-4 py-2 rounded-lg text-sm font-medium pointer-events-none z-10">
          {hoveredState} — Click to explore
        </div>
      )}
    </div>
  );
};

