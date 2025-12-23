import React from 'react';
import type { OwnershipBreakdown } from '../../lib/wrapped/wrappedTypes';

interface OwnershipPieChartProps {
  ownership: OwnershipBreakdown;
  size?: number;
}

export const OwnershipPieChart: React.FC<OwnershipPieChartProps> = ({ 
  ownership, 
  size = 120 
}) => {
  const center = size / 2;
  const radius = size / 2 - 4;
  
  // Calculate angles for each segment
  const forProfitAngle = (ownership.forProfit.percentage / 100) * 360;
  const nonProfitAngle = (ownership.nonProfit.percentage / 100) * 360;
  const governmentAngle = (ownership.government.percentage / 100) * 360;
  
  // Convert angles to radians and calculate path coordinates
  const toRadians = (degrees: number) => (degrees * Math.PI) / 180;
  
  const createArc = (startAngle: number, endAngle: number) => {
    const start = {
      x: center + radius * Math.cos(toRadians(startAngle - 90)),
      y: center + radius * Math.sin(toRadians(startAngle - 90)),
    };
    const end = {
      x: center + radius * Math.cos(toRadians(endAngle - 90)),
      y: center + radius * Math.sin(toRadians(endAngle - 90)),
    };
    const largeArc = endAngle - startAngle > 180 ? 1 : 0;
    return `M ${center} ${center} L ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArc} 1 ${end.x} ${end.y} Z`;
  };
  
  let currentAngle = 0;
  const forProfitPath = createArc(currentAngle, currentAngle + forProfitAngle);
  currentAngle += forProfitAngle;
  const nonProfitPath = createArc(currentAngle, currentAngle + nonProfitAngle);
  currentAngle += nonProfitAngle;
  const governmentPath = createArc(currentAngle, currentAngle + governmentAngle);
  
  return (
    <div className="flex items-center justify-center">
      <svg width={size} height={size} className="flex-shrink-0">
        {/* For-profit - blue */}
        {ownership.forProfit.percentage > 0 && (
          <path
            d={forProfitPath}
            fill="#60a5fa"
            stroke="#1e293b"
            strokeWidth="1"
          />
        )}
        {/* Non-profit - green */}
        {ownership.nonProfit.percentage > 0 && (
          <path
            d={nonProfitPath}
            fill="#34d399"
            stroke="#1e293b"
            strokeWidth="1"
          />
        )}
        {/* Government - purple */}
        {ownership.government.percentage > 0 && (
          <path
            d={governmentPath}
            fill="#a78bfa"
            stroke="#1e293b"
            strokeWidth="1"
          />
        )}
      </svg>
    </div>
  );
};










