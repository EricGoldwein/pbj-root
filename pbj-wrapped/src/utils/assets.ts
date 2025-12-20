/**
 * Utility function to get asset paths that work with Vite's base path
 * In dev: base is '/pbj-wrapped/'
 * In production: base is '/pbj-wrapped/'
 * This ensures assets work both locally and on pbj320.com/pbj-wrapped/
 */
export function getAssetPath(path: string): string {
  // Remove leading slash if present, we'll add it properly
  const cleanPath = path.startsWith('/') ? path.slice(1) : path;
  // Get base URL from Vite (includes trailing slash)
  const baseUrl = import.meta.env.BASE_URL;
  // Combine base URL with path, ensuring no double slashes
  return `${baseUrl}${cleanPath}`.replace(/([^:]\/)\/+/g, '$1');
}

