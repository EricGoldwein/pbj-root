import React from 'react';

interface RankingsBarChartProps {
  rank: number;
  total: number;
  width?: number;
  height?: number;
}

export const RankingsBarChart: React.FC<RankingsBarChartProps> = ({ 
  rank, 
  total, 
  width = 200,
  height = 8
}) => {
  const percentile = Math.round(((total - rank + 1) / total) * 100);
  const barWidth = (percentile / 100) * width;
  
  // Color based on percentile
  let barColor = '#ef4444'; // red for bottom
  if (percentile >= 75) {
    barColor = '#22c55e'; // green for top 25%
  } else if (percentile >= 50) {
    barColor = '#eab308'; // yellow for middle
  } else if (percentile >= 25) {
    barColor = '#f97316'; // orange for bottom-middle
  }
  
  return (
    <div className="flex items-center gap-2">
      <div className="relative" style={{ width: `${width}px`, height: `${height}px` }}>
        <div 
          className="absolute left-0 top-0 rounded-full"
          style={{ 
            width: `${width}px`, 
            height: `${height}px`,
            backgroundColor: '#374151' // gray background
          }}
        />
        <div 
          className="absolute left-0 top-0 rounded-full transition-all"
          style={{ 
            width: `${barWidth}px`, 
            height: `${height}px`,
            backgroundColor: barColor
          }}
        />
      </div>
      <span className="text-xs text-gray-400">{percentile}th</span>
    </div>
  );
};




