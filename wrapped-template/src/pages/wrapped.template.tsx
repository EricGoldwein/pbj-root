import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import Papa from 'papaparse';
import { usePageTitle } from '../hooks/usePageTitle';
import { buildWrappedStatsForUser } from '../lib/wrapped/buildWrappedStats';
import type { LedgerRow, LogRow } from '../lib/wrapped/wrappedTypes';
import { WrappedScreenWrapper, type WrappedNavigationRef } from '../components/wrapped/WrappedScreenWrapper';
import { TitleCard } from '../components/wrapped/cards/TitleCard';
import { InitiationCard } from '../components/wrapped/cards/InitiationCard';
import { TotalMetricCard } from '../components/wrapped/cards/TotalMetricCard';
// Import other card components as needed
import { getAvatarForUser } from '../lib/wrapped/avatarUtils';
import { WrappedProvider } from '../components/wrapped/WrappedContext';

/**
 * Convert username to URL-friendly format
 * - Lowercase
 * - Replace spaces, underscores, and special chars with dashes
 * - Remove multiple consecutive dashes
 * - Trim dashes from start/end
 */
export function usernameToUrlFormat(username: string): string {
  return username
    .toLowerCase()
    .replace(/[\s_]+/g, '-') // Replace spaces and underscores with dashes
    .replace(/[^a-z0-9-]/g, '-') // Replace other special chars with dashes
    .replace(/-+/g, '-') // Replace multiple dashes with single dash
    .replace(/^-|-$/g, ''); // Remove leading/trailing dashes
}

/**
 * Decode username from URL format back to original format
 * This is a best-effort conversion - we'll match against actual usernames in the ledger
 */
function urlFormatToUsername(urlFormat: string): string {
  // Replace dashes with spaces for matching
  // We'll use this to search the ledger for the actual username
  return urlFormat.replace(/-/g, ' ');
}

const Wrapped: React.FC = () => {
  usePageTitle('{{BRAND_NAME}}');
  const { username: usernameParam } = useParams<{ username?: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const navigationRef = useRef<WrappedNavigationRef>(null);

  // Support both new path format ({{ROUTE_PATH}}/username) and old query format (?username=...)
  // Prefer path parameter, fallback to query parameter for backwards compatibility
  const usernameFromPath = usernameParam ? urlFormatToUsername(usernameParam) : '';
  const usernameFromQuery = searchParams.get('username') || '';
  const usernameFromUrl = usernameFromPath || usernameFromQuery;
  
  // Redirect old query format to new path format
  useEffect(() => {
    if (usernameFromQuery && !usernameFromPath) {
      const urlFormat = usernameToUrlFormat(usernameFromQuery);
      navigate(`{{ROUTE_PATH}}/${urlFormat}`, { replace: true });
    }
  }, [usernameFromQuery, usernameFromPath, navigate]);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<any>(null);
  const [ledgerRows, setLedgerRows] = useState<LedgerRow[]>([]);
  const [logRows, setLogRows] = useState<LogRow[]>([]);
  const [actualUsername, setActualUsername] = useState<string>('');

  // Normalize string for comparison (lowercase, remove accents, normalize spaces/dashes)
  const normalizeForMatching = (str: string): string => {
    return str
      .toLowerCase()
      .normalize('NFD') // Decompose accented characters (é -> e + ´)
      .replace(/[\u0300-\u036f]/g, '') // Remove diacritical marks
      .replace(/[\s_-]+/g, ' ') // Normalize spaces, dashes, underscores to spaces
      .trim();
  };

  // Find actual username from ledger (case-insensitive, handles spaces/dashes, accents)
  const findUsernameInLedger = (searchTerm: string, ledger: LedgerRow[]): string | null => {
    if (!searchTerm) return null;
    
    const normalizedSearch = normalizeForMatching(searchTerm);
    
    for (const row of ledger) {
      const normalizedRow = normalizeForMatching(row.{{USERNAME_FIELD}});
      if (normalizedRow === normalizedSearch) {
        return row.{{USERNAME_FIELD}}; // Return with original capitalization and accents
      }
    }
    
    return null;
  };

  useEffect(() => {
    if (!usernameFromUrl) {
      setError('Please provide a username in the URL: {{ROUTE_PATH}}/username (e.g., {{ROUTE_PATH}}/{{EXAMPLE_USERNAME_1}})');
      setLoading(false);
      return;
    }

    // Load and parse CSV data
    const loadData = async () => {
      try {
        setLoading(true);
        setError(null);

        // Load CSV files - try multiple paths
        // Customize paths based on your configuration
        let ledgerCsv = '';
        let logCsv = '';
        
        const paths = [
          { ledger: '/data/{{LEDGER_CSV_FILENAME}}', log: '/data/{{LOG_CSV_FILENAME}}' },
          { ledger: '/src/data/{{LEDGER_CSV_FILENAME}}', log: '/src/data/{{LOG_CSV_FILENAME}}' },
        ];
        
        for (const pathSet of paths) {
          try {
            const [ledgerRes, logRes] = await Promise.all([
              fetch(pathSet.ledger),
              fetch(pathSet.log),
            ]);
            
            if (ledgerRes.ok && logRes.ok) {
              ledgerCsv = await ledgerRes.text();
              logCsv = await logRes.text();
              break;
            }
          } catch (e) {
            // Try next path set
            continue;
          }
        }
        
        if (!ledgerCsv || !logCsv) {
          throw new Error('Failed to load CSV data. Please ensure the CSV files are in /public/data/ or /src/data/');
        }

        // Parse CSVs
        // Customize field parsing based on your data structure
        Papa.parse<LedgerRow>(ledgerCsv, {
          header: true,
          skipEmptyLines: true,
          complete: (results) => {
            const parsedLedger = results.data.map((row) => ({
              ...row,
              {{TOTAL_METRIC_FIELD}}: parseFloat(String(row.{{TOTAL_METRIC_FIELD}})) || 0,
              {{DISTANCE_FIELD}}: parseFloat(String(row.{{DISTANCE_FIELD}})) || 0,
              {{RANK_FIELD}}: parseFloat(String(row.{{RANK_FIELD}})) || 0,
              // Add more field parsing as needed
            }));

            setLedgerRows(parsedLedger);

            Papa.parse<LogRow>(logCsv, {
              header: true,
              skipEmptyLines: true,
              complete: (logResults) => {
                const parsedLog = logResults.data.map((row) => ({
                  ...row,
                  ID: parseFloat(String(row.ID)) || 0,
                  {{AMOUNT_FIELD}}: parseFloat(String(row.{{AMOUNT_FIELD}})) || 0,
                  {{DISTANCE_FIELD}}: row.{{DISTANCE_FIELD}}
                    ? parseFloat(String(row.{{DISTANCE_FIELD}}))
                    : null,
                  // Add more field parsing as needed
                }));

                setLogRows(parsedLog);

                // Find actual username from ledger (handles case-insensitive matching, spaces/dashes)
                const foundUsername = findUsernameInLedger(usernameFromUrl, parsedLedger);
                
                if (!foundUsername) {
                  setError(`User "${usernameFromUrl}" not found in ledger. Please check the username and try again.`);
                  setLoading(false);
                  return;
                }
                
                setActualUsername(foundUsername);

                // Build stats - function will use correct capitalization from ledger row
                try {
                  const userStats = buildWrappedStatsForUser(
                    foundUsername,
                    parsedLedger,
                    parsedLog
                  );
                  setStats(userStats);
                } catch (err) {
                  setError(`Failed to build stats: ${err instanceof Error ? err.message : 'Unknown error'}`);
                }

                setLoading(false);
              },
              error: (err) => {
                setError(`Failed to parse Log CSV: ${err.message}`);
                setLoading(false);
              },
            });
          },
          error: (err) => {
            setError(`Failed to parse Ledger CSV: ${err.message}`);
            setLoading(false);
          },
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load data');
        setLoading(false);
      }
    };

    loadData();
  }, [usernameFromUrl]);

  const avatarUrl = getAvatarForUser(actualUsername || usernameFromUrl);

  // Build screens array with useMemo for performance
  // Customize this based on your card types and order
  const { screens, slideDurations } = useMemo(() => {
    if (!stats) {
      return { screens: [], slideDurations: [] };
    }
    
    const screensArray: React.ReactElement[] = [
      // Customize card order and types based on your needs
      <TitleCard key="title" username={stats.username} avatarUrl={avatarUrl} />,
      <InitiationCard key="initiation" initiationDate={stats.initiationDate} avatarUrl={avatarUrl} username={stats.username} />,
      <TotalMetricCard
        key="totalMetric"
        total{{METRIC_NAME}}={stats.total{{METRIC_NAME}}}
        {{DISTANCE_FIELD}}={stats.{{DISTANCE_FIELD}}}
        avatarUrl={avatarUrl}
        username={stats.username}
      />,
      // Add more cards as needed
    ];
    
    // Create slide durations array
    // Customize durations based on card types (video, ad, standard)
    const slideDurationsArray: number[] = screensArray.map((screen, index) => {
      if (React.isValidElement(screen) && screen.key === 'videoCard') {
        return 15000; // 15 seconds for video
      }
      if (React.isValidElement(screen) && screen.key === 'adCard') {
        return 8000; // 8 seconds for forced ad countdown
      }
      return 4000; // Default 4 seconds
    });
    
    return { screens: screensArray, slideDurations: slideDurationsArray };
  }, [stats, avatarUrl, navigationRef]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-{{PRIMARY_COLOR}}-50 to-{{ACCENT_COLOR}}-100">
        <div className="text-center">
          <div className="text-2xl font-bold text-{{PRIMARY_COLOR}}-600 mb-4">Loading your {{BRAND_NAME}}...</div>
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-{{PRIMARY_COLOR}}-600 mx-auto"></div>
        </div>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-{{PRIMARY_COLOR}}-50 to-{{ACCENT_COLOR}}-100">
        <div className="text-center max-w-md mx-auto px-6">
          <div className="text-2xl font-bold text-red-600 mb-4">Error</div>
          <p className="text-gray-700 mb-4">{error || 'Failed to load wrapped data'}</p>
          <button
            onClick={() => navigate('/')}
            className="px-6 py-2 bg-{{PRIMARY_COLOR}}-600 text-white rounded-lg hover:bg-{{PRIMARY_COLOR}}-700"
          >
            Go Home
          </button>
        </div>
      </div>
    );
  }

  return (
    <WrappedProvider username={stats.username} avatarUrl={avatarUrl}>
      <div 
        className="fixed inset-0 w-full overflow-hidden"
        style={{ 
          height: '100dvh', // Dynamic viewport height accounts for browser chrome
          maxHeight: '100dvh'
        }}
      >
        <WrappedScreenWrapper ref={navigationRef} screens={screens} slideDurations={slideDurations} />
      </div>
    </WrappedProvider>
  );
};

export default Wrapped;

