import React from 'react';

interface TrendArrowProps {
  change: number;
  size?: number;
}

export const TrendArrow: React.FC<TrendArrowProps> = ({ change, size = 40 }) => {
  const isPositive = change > 0;
  const isNegative = change < 0;
  const isNeutral = change === 0;
  
  const color = isPositive ? '#22c55e' : isNegative ? '#ef4444' : '#9ca3af';
  const arrow = isPositive ? '↑' : isNegative ? '↓' : '→';
  
  return (
    <div 
      className="flex items-center justify-center rounded-full"
      style={{
        width: `${size}px`,
        height: `${size}px`,
        backgroundColor: `${color}20`,
        border: `2px solid ${color}`,
      }}
    >
      <span 
        className="font-bold"
        style={{ 
          fontSize: `${size * 0.5}px`,
          color: color
        }}
      >
        {arrow}
      </span>
    </div>
  );
};

