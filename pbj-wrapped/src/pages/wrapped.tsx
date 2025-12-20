import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { loadAllData } from '../lib/wrapped/dataLoader';
import { processWrappedData } from '../lib/wrapped/dataProcessor';
import { parseRouteParams } from '../lib/wrapped/routing';
import type { PBJWrappedData } from '../lib/wrapped/wrappedTypes';
import { updateSEO, getWrappedSEO } from '../utils/seo';
import { WrappedScreenWrapper, type WrappedNavigationRef } from '../components/wrapped/WrappedScreenWrapper';
import { WrappedProvider } from '../components/wrapped/WrappedContext';
import { HeaderCard } from '../components/wrapped/cards/HeaderCard';
import { BasicsCard } from '../components/wrapped/cards/BasicsCard';
import { RankingsCard } from '../components/wrapped/cards/RankingsCard';
import { LowestStaffingCard } from '../components/wrapped/cards/LowestStaffingCard';
import { HighestStaffingCard } from '../components/wrapped/cards/HighestStaffingCard';
import { USAStatesExtremesCard } from '../components/wrapped/cards/USAStatesExtremesCard';
import { USARegionsExtremesCard } from '../components/wrapped/cards/USARegionsExtremesCard';
import { SFFCard } from '../components/wrapped/cards/SFFCard';
import { TrendsCard } from '../components/wrapped/cards/TrendsCard';
import { RisersCard } from '../components/wrapped/cards/RisersCard';
import { DeclinersCard } from '../components/wrapped/cards/DeclinersCard';
import { KeyTakeawaysCard } from '../components/wrapped/cards/KeyTakeawaysCard';
import { NavigationCard } from '../components/wrapped/cards/NavigationCard';
import { WhatIsPBJCard } from '../components/wrapped/cards/WhatIsPBJCard';
import { WhatIsHPRDCard } from '../components/wrapped/cards/WhatIsHPRDCard';
import { USAOwnershipCard } from '../components/wrapped/cards/USAOwnershipCard';
import { StateOverviewCard } from '../components/wrapped/cards/StateOverviewCard';
import { USANationalScaleCard } from '../components/wrapped/cards/USANationalScaleCard';
import { StateMinimumCard } from '../components/wrapped/cards/StateMinimumCard';
import { RegionStatesCard } from '../components/wrapped/cards/RegionStatesCard';
import { getAssetPath } from '../utils/assets';

// Helper to get data path with base URL
function getDataPath(path: string = ''): string {
  const baseUrl = import.meta.env.BASE_URL;
  const cleanPath = path.startsWith('/') ? path.slice(1) : path;
  return `${baseUrl}data${cleanPath ? `/${cleanPath}` : ''}`.replace(/([^:]\/)\/+/g, '$1');
}

const Wrapped: React.FC = () => {
  const { identifier } = useParams<{ identifier?: string }>();
  const navigate = useNavigate();
  const navigationRef = useRef<WrappedNavigationRef>(null);
  const year = '2025'; // Fixed year for Q2 2025

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [wrappedData, setWrappedData] = useState<PBJWrappedData | null>(null);
  const [loadingProgress, setLoadingProgress] = useState(0);
  const progressIntervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // Debug: log the params
    console.log('Route params:', { identifier });
    
    if (!identifier) {
      setError(`Invalid route parameters. Identifier: ${identifier || 'missing'}. Expected format: /{usa|state|region}`);
      setLoading(false);
      return;
    }

    // Parse and validate route parameters (year is fixed to 2025)
    const params = parseRouteParams(year, identifier);
    
    if (!params.scope || !params.normalizedIdentifier) {
      setError(`Invalid route: /${identifier}. Please check the URL and try again.`);
      setLoading(false);
      return;
    }

    // Redirect if needed (e.g., full state name to abbreviation)
    if (params.scope === 'state' && identifier.toLowerCase() !== params.normalizedIdentifier) {
      navigate(`/${params.normalizedIdentifier}`, { replace: true });
      return;
    }

    // Load and process data
    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);
        setLoadingProgress(0);

        // Simulate progress during loading - starts slow, accelerates
        progressIntervalRef.current = setInterval(() => {
          setLoadingProgress(prev => {
            if (prev >= 85) return prev; // Don't go above 85% until done
            // Accelerate progress: slower at start, faster as it goes
            const increment = prev < 30 ? Math.random() * 5 : prev < 60 ? Math.random() * 8 : Math.random() * 12;
            return Math.min(85, prev + increment);
          });
        }, 150);

        // Try multiple data paths, pass scope for optimization
        let data;
        const scope = params.scope || 'usa';
        const normalizedId = params.normalizedIdentifier ?? undefined;
        // Use base path for data files
        const baseDataPath = getDataPath();
        try {
          setLoadingProgress(25);
          data = await loadAllData(baseDataPath, scope, normalizedId);
        } catch {
          // Fallback to absolute path if base path fails
          try {
            setLoadingProgress(35);
            data = await loadAllData('/data', scope, normalizedId);
          } catch {
            setLoadingProgress(45);
            data = await loadAllData(baseDataPath, scope, normalizedId);
          }
        }

        if (progressIntervalRef.current) {
          clearInterval(progressIntervalRef.current);
          progressIntervalRef.current = null;
        }
        setLoadingProgress(90);

        // Process data based on scope
        const processed = processWrappedData(
          scope,
          normalizedId ?? '',
          data
        );

        setLoadingProgress(100);
        
        // Small delay to show 100% before hiding
        setTimeout(() => {
          setWrappedData(processed);
          setLoading(false);
        }, 200);
      } catch (err) {
        if (progressIntervalRef.current) {
          clearInterval(progressIntervalRef.current);
          progressIntervalRef.current = null;
        }
        console.error('Error loading wrapped data:', err);
        setError(err instanceof Error ? err.message : 'Failed to load data');
        setLoading(false);
        setLoadingProgress(0);
      }
    };

    loadData();

    // Cleanup function
    return () => {
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = null;
      }
    };
  }, [identifier, navigate, year]);

  // Update SEO when wrappedData is loaded
  useEffect(() => {
    if (wrappedData && identifier) {
      const params = parseRouteParams(year, identifier);
      if (params.scope && params.normalizedIdentifier) {
        const seoData = getWrappedSEO(
          params.scope,
          params.normalizedIdentifier,
          wrappedData.name,
          year
        );
        updateSEO(seoData);
      }
    }
  }, [wrappedData, identifier, year]);

  // Build screens array
  const { screens, slideDurations } = useMemo(() => {
    if (!wrappedData) {
      return { screens: [], slideDurations: [] };
    }

    const screensArray: React.ReactElement[] = [
      <HeaderCard key="header" name={wrappedData.name} />,
      <WhatIsPBJCard key="what-is-pbj" data={wrappedData} />,
      <WhatIsHPRDCard key="what-is-hprd" data={wrappedData} />,
      // State minimum staffing requirement (if available)
      ...(wrappedData.scope === 'state' && wrappedData.stateMinimum ? [<StateMinimumCard key="state-minimum" data={wrappedData} />] : []),
      // Region states overview (early on for regions)
      ...(wrappedData.scope === 'region' && wrappedData.regionStates ? [<RegionStatesCard key="region-states" data={wrappedData} />] : []),
      // State-specific narrative overview
      ...(wrappedData.scope === 'state' ? [<StateOverviewCard key="state-overview" data={wrappedData} />] : []),
      // USA-specific national scale
      ...(wrappedData.scope === 'usa' ? [<USANationalScaleCard key="national-scale" data={wrappedData} />] : []),
      <BasicsCard key="basics" data={wrappedData} />,
      ...(wrappedData.scope !== 'usa' ? [<RankingsCard key="rankings" data={wrappedData} />] : []),
      // For USA, add ownership slide after basics
      ...(wrappedData.scope === 'usa' && wrappedData.ownership ? [<USAOwnershipCard key="ownership" data={wrappedData} />] : []),
      // For USA, split extremes into two slides
      // For state, split into lowest and highest slides
      // For region, skip facility extremes (focus on state-level trends)
      ...(wrappedData.scope === 'usa' 
        ? [
            <USAStatesExtremesCard key="extremes-states" data={wrappedData} />,
            <USARegionsExtremesCard key="extremes-regions" data={wrappedData} />,
          ]
        : wrappedData.scope === 'state'
        ? [
            <LowestStaffingCard key="lowest-staffing" data={wrappedData} />,
            <HighestStaffingCard key="highest-staffing" data={wrappedData} />,
          ]
        : [] // Regions skip facility extremes
      ),
      <SFFCard key="sff" data={wrappedData} />,
      <TrendsCard key="trends" data={wrappedData} />,
      <RisersCard key="risers" data={wrappedData} />,
      <DeclinersCard key="decliners" data={wrappedData} />,
      <KeyTakeawaysCard key="takeaways" data={wrappedData} />,
      <NavigationCard 
        key="navigation" 
        data={wrappedData} 
        onReplay={() => navigationRef.current?.goTo(0)} 
      />,
    ];

    const slideDurationsArray = screensArray.map((screen) => {
      // Make "What is PBJ" slide longer so typing effect can complete
      // Typing speed is 30ms per char, estimate ~200 chars = 6 seconds typing + 4 seconds for reading
      if (screen.key === 'what-is-pbj') {
        return 10000; // 10 seconds total - typing completes in ~6s, 4s to read
      }
      return 5000; // 5 seconds per slide
    });

    return { screens: screensArray, slideDurations: slideDurationsArray };
  }, [wrappedData]);

  if (loading) {
    return (
      <div 
        className="fixed inset-0 w-full overflow-hidden flex items-center justify-center bg-gradient-to-br from-gray-900 via-blue-900 to-gray-900"
        style={{ height: '100dvh', maxHeight: '100dvh' }}
      >
        <div className="text-center max-w-md px-6">
          <div className="mb-6 flex justify-center">
            <img 
              src={getAssetPath('/images/phoebe-wrapped-wide.png')} 
              alt="PBJ Wrapped" 
              className="max-w-[200px] md:max-w-[250px] h-auto opacity-80"
            />
          </div>
          <div className="text-2xl md:text-3xl font-bold text-blue-300 mb-3">Loading PBJ Wrapped...</div>
          <div className="text-base md:text-lg text-gray-400 mb-6">
            {wrappedData ? 'Processing data...' : 'Loading data files...'}
          </div>
          <div className="relative">
            <div className="animate-spin rounded-full h-12 w-12 md:h-16 md:w-16 border-4 border-blue-500/30 border-t-blue-500 mx-auto mb-4"></div>
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-6 h-6 md:w-8 md:h-8 bg-blue-500/20 rounded-full animate-pulse"></div>
            </div>
          </div>
          {/* Progress bar */}
          <div className="w-full max-w-xs mx-auto h-1.5 bg-gray-700/50 rounded-full overflow-hidden">
            <div 
              className="h-full bg-gradient-to-r from-blue-500 to-blue-400 rounded-full transition-all duration-300 ease-out" 
              style={{ width: `${Math.min(100, Math.max(0, loadingProgress))}%` }}
            ></div>
          </div>
        </div>
      </div>
    );
  }

  if (error || !wrappedData) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-900 via-blue-900 to-gray-900">
        <div className="text-center max-w-md mx-auto px-6">
          <div className="text-2xl font-bold text-red-400 mb-4">Error</div>
          <p className="text-gray-300 mb-4">{error || 'Failed to load wrapped data'}</p>
          <button
            onClick={() => navigate('/')}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Go Home
          </button>
        </div>
      </div>
    );
  }

  return (
    <WrappedProvider scope={wrappedData.scope} name={wrappedData.name}>
      <div
        className="fixed inset-0 w-full overflow-hidden"
        style={{
          height: '100dvh',
          maxHeight: '100dvh',
        }}
      >
        <WrappedScreenWrapper 
          ref={navigationRef} 
          screens={screens} 
          slideDurations={slideDurations}
          scope={wrappedData.scope}
          stateCode={wrappedData.scope === 'state' ? wrappedData.identifier.toUpperCase() : undefined}
        />
      </div>
    </WrappedProvider>
  );
};

export default Wrapped;

