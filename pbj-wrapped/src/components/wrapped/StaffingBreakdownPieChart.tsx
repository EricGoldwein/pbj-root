import React from 'react';

interface StaffingBreakdown {
  rn: number;
  lpn: number;
  nurseAide: number;
}

interface StaffingBreakdownPieChartProps {
  breakdown: StaffingBreakdown;
  size?: number;
}

export const StaffingBreakdownPieChart: React.FC<StaffingBreakdownPieChartProps> = ({ 
  breakdown, 
  size = 120 
}) => {
  const center = size / 2;
  const radius = size / 2 - 4;
  
  // Calculate total and percentages
  const total = breakdown.rn + breakdown.lpn + breakdown.nurseAide;
  const rnPercent = total > 0 ? (breakdown.rn / total) * 100 : 0;
  const lpnPercent = total > 0 ? (breakdown.lpn / total) * 100 : 0;
  const nurseAidePercent = total > 0 ? (breakdown.nurseAide / total) * 100 : 0;
  
  // Calculate angles for each segment
  const rnAngle = (rnPercent / 100) * 360;
  const lpnAngle = (lpnPercent / 100) * 360;
  const nurseAideAngle = (nurseAidePercent / 100) * 360;
  
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
  const rnPath = createArc(currentAngle, currentAngle + rnAngle);
  currentAngle += rnAngle;
  const lpnPath = createArc(currentAngle, currentAngle + lpnAngle);
  currentAngle += lpnAngle;
  const nurseAidePath = createArc(currentAngle, currentAngle + nurseAideAngle);
  
  return (
    <div className="flex items-center justify-center">
      <svg width={size} height={size} className="flex-shrink-0">
        {/* RN - blue */}
        {rnPercent > 0 && (
          <path
            d={rnPath}
            fill="#60a5fa"
            stroke="#1e293b"
            strokeWidth="1"
          />
        )}
        {/* LPN - green */}
        {lpnPercent > 0 && (
          <path
            d={lpnPath}
            fill="#34d399"
            stroke="#1e293b"
            strokeWidth="1"
          />
        )}
        {/* Nurse Aide - orange */}
        {nurseAidePercent > 0 && (
          <path
            d={nurseAidePath}
            fill="#fb923c"
            stroke="#1e293b"
            strokeWidth="1"
          />
        )}
      </svg>
    </div>
  );
};

