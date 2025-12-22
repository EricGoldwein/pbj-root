import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { loadAllData } from '../lib/wrapped/dataLoader';
import { processWrappedData } from '../lib/wrapped/dataProcessor';
import type { PBJWrappedData } from '../lib/wrapped/wrappedTypes';
import { updateSEO } from '../utils/seo';
import { WrappedScreenWrapper, type WrappedNavigationRef } from '../components/wrapped/WrappedScreenWrapper';
import { WrappedProvider } from '../components/wrapped/WrappedContext';
import { HeaderCardNews } from '../components/wrapped/cards/HeaderCardNews';
import { USANationalScaleCardNews } from '../components/wrapped/cards/USANationalScaleCardNews';
import { StaffingIllusionCard } from '../components/wrapped/cards/StaffingIllusionCard';
import { USAStatesExtremesCardNews } from '../components/wrapped/cards/USAStatesExtremesCardNews';
import { SFFCardNews } from '../components/wrapped/cards/SFFCardNews';
import { KeyTakeawaysCardNews } from '../components/wrapped/cards/KeyTakeawaysCardNews';
import { NavigationCardNews } from '../components/wrapped/cards/NavigationCardNews';
import { getAssetPath } from '../utils/assets';

// Helper to get data path - data is served from /data, not /wrapped/data
function getDataPath(path: string = ''): string {
  const cleanPath = path.startsWith('/') ? path.slice(1) : path;
  return `/data${cleanPath ? `/${cleanPath}` : ''}`.replace(/([^:]\/)\/+/g, '$1');
}

const WrappedNews: React.FC = () => {
  const navigate = useNavigate();
  const navigationRef = useRef<WrappedNavigationRef>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [wrappedData, setWrappedData] = useState<PBJWrappedData | null>(null);
  const [loadingProgress, setLoadingProgress] = useState(0);
  const progressIntervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // Load USA data for news cut
    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);
        setLoadingProgress(0);

        // Simulate progress during loading
        progressIntervalRef.current = setInterval(() => {
          setLoadingProgress(prev => {
            if (prev >= 85) return prev;
            const increment = prev < 30 ? Math.random() * 5 : prev < 60 ? Math.random() * 8 : Math.random() * 12;
            return Math.min(85, prev + increment);
          });
        }, 150);

        // Load USA data
        const baseDataPath = getDataPath();
        let data;
        try {
          setLoadingProgress(25);
          data = await loadAllData(baseDataPath, 'usa', undefined);
        } catch {
          try {
            setLoadingProgress(35);
            data = await loadAllData('/data', 'usa', undefined);
          } catch {
            setLoadingProgress(45);
            data = await loadAllData(baseDataPath, 'usa', undefined);
          }
        }

        if (progressIntervalRef.current) {
          clearInterval(progressIntervalRef.current);
          progressIntervalRef.current = null;
        }
        setLoadingProgress(90);

        // Process USA data
        const processed = processWrappedData('usa', 'usa', data);

        setLoadingProgress(100);
        
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

    return () => {
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = null;
      }
    };
  }, []);

  // Update SEO
  useEffect(() => {
    if (wrappedData) {
      const baseUrl = 'https://pbj320.com';
      updateSEO({
        title: 'PBJ Wrapped News Cut | Q2 2025 Nursing Home Staffing Data',
        description: 'A media-first snapshot of federal nursing home staffing data. What the numbers actually show.',
        keywords: 'nursing home staffing, PBJ, CMS, healthcare data, nursing home quality',
        ogTitle: 'PBJ Wrapped News Cut | Q2 2025 Nursing Home Staffing Data',
        ogDescription: 'A media-first snapshot of federal nursing home staffing data. What the numbers actually show.',
        ogImage: `${baseUrl}/images/phoebe-wrapped-wide.png`,
        ogUrl: `${baseUrl}/usa-news`,
        canonical: `${baseUrl}/usa-news`,
      });
    }
  }, [wrappedData]);

  // Build screens array - exactly 7 slides for news cut
  const { screens, slideDurations } = useMemo(() => {
    if (!wrappedData || wrappedData.scope !== 'usa') {
      return { screens: [], slideDurations: [] };
    }

    const screensArray: React.ReactElement[] = [
      <HeaderCardNews key="header" />,
      <USANationalScaleCardNews key="scale" data={wrappedData} />,
      <StaffingIllusionCard key="illusion" data={wrappedData} />,
      <USAStatesExtremesCardNews key="accountability" data={wrappedData} />,
      <SFFCardNews key="sff" data={wrappedData} />,
      <KeyTakeawaysCardNews key="takeaway" data={wrappedData} />,
      <NavigationCardNews 
        key="navigation" 
        data={wrappedData} 
        onReplay={() => navigationRef.current?.goTo(0)} 
      />,
    ];

    // All slides auto-advance after 5 seconds
    const slideDurationsArray = screensArray.map(() => 5000);

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
          <div className="relative">
            <div className="animate-spin rounded-full h-12 w-12 md:h-16 md:w-16 border-4 border-blue-500/30 border-t-blue-500 mx-auto mb-4"></div>
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-6 h-6 md:w-8 md:w-8 bg-blue-500/20 rounded-full animate-pulse"></div>
            </div>
          </div>
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
    <WrappedProvider scope="usa" name="United States">
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
          scope="usa"
        />
      </div>
    </WrappedProvider>
  );
};

export default WrappedNews;

