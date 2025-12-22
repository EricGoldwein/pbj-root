/**
 * SEO utility functions for dynamically updating meta tags
 */

export interface SEOData {
  title: string;
  description: string;
  keywords?: string;
  ogTitle?: string;
  ogDescription?: string;
  ogImage?: string;
  ogUrl?: string;
  canonical?: string;
}

export function updateSEO(data: SEOData) {
  // Update title
  if (document.title !== data.title) {
    document.title = data.title;
  }

  // Update or create meta tags
  const updateMetaTag = (name: string, content: string, attribute: string = 'name') => {
    let meta = document.querySelector(`meta[${attribute}="${name}"]`) as HTMLMetaElement;
    if (!meta) {
      meta = document.createElement('meta');
      meta.setAttribute(attribute, name);
      document.head.appendChild(meta);
    }
    meta.content = content;
  };

  // Basic meta tags
  updateMetaTag('description', data.description);
  if (data.keywords) {
    updateMetaTag('keywords', data.keywords);
  }

  // Open Graph tags
  updateMetaTag('og:title', data.ogTitle || data.title, 'property');
  updateMetaTag('og:description', data.ogDescription || data.description, 'property');
  updateMetaTag('og:type', 'website', 'property');
  if (data.ogImage) {
    updateMetaTag('og:image', data.ogImage, 'property');
  }
  if (data.ogUrl) {
    updateMetaTag('og:url', data.ogUrl, 'property');
  }
  updateMetaTag('og:site_name', 'PBJ320', 'property');

  // Twitter tags
  updateMetaTag('twitter:card', 'summary_large_image', 'name');
  updateMetaTag('twitter:title', data.ogTitle || data.title, 'name');
  updateMetaTag('twitter:description', data.ogDescription || data.description, 'name');
  if (data.ogImage) {
    updateMetaTag('twitter:image', data.ogImage, 'name');
  }

  // Canonical URL
  if (data.canonical) {
    let canonical = document.querySelector('link[rel="canonical"]') as HTMLLinkElement;
    if (!canonical) {
      canonical = document.createElement('link');
      canonical.rel = 'canonical';
      document.head.appendChild(canonical);
    }
    canonical.href = data.canonical;
  }
}

/**
 * Generate SEO data for Wrapped pages
 */
export function getWrappedSEO(
  scope: 'usa' | 'state' | 'region',
  identifier: string,
  name: string,
  year: string = '2025'
): SEOData {
  const baseUrl = 'https://pbj320.com';
  const path = `/wrapped/${year}/${identifier}`;
  const fullUrl = `${baseUrl}${path}`;
  
  const keywords = [
    'nursing home staffing',
    '2025',
    '320 consulting',
    'pbj320',
    'payroll-based journal',
    'nursing home residents',
    'long-term care',
    'pbj data',
    'CMS PBJ',
    'nursing home quality',
    'staffing levels',
    'HPRD',
    'hours per resident day'
  ].join(', ');

  let title: string;
  let description: string;
  let ogTitle: string;
  let ogDescription: string;

  if (scope === 'usa') {
    title = `PBJ Wrapped Q2 ${year} — United States Nursing Home Staffing Data | PBJ320`;
    description = `Q2 ${year} nursing home staffing data for the United States. Explore national staffing levels, trends, and insights from CMS Payroll-Based Journal (PBJ) data. Comprehensive analysis of 15,000+ nursing homes and long-term care facilities.`;
    ogTitle = `PBJ Wrapped Q2 ${year} — United States Nursing Home Staffing`;
    ogDescription = `National nursing home staffing data and trends for Q2 ${year}. Staffing levels, rankings, and insights from CMS PBJ data.`;
  } else if (scope === 'state') {
    title = `PBJ Wrapped Q2 ${year} — ${name} Nursing Home Staffing Data | PBJ320`;
    description = `Q2 ${year} nursing home staffing data for ${name}. Explore state-level staffing levels, rankings, trends, and insights from CMS Payroll-Based Journal (PBJ) data. Analysis of nursing homes and long-term care facilities in ${name}.`;
    ogTitle = `PBJ Wrapped Q2 ${year} — ${name} Nursing Home Staffing`;
    ogDescription = `${name} nursing home staffing data and trends for Q2 ${year}. Staffing levels, rankings, and insights from CMS PBJ data.`;
  } else {
    // region
    title = `PBJ Wrapped Q2 ${year} — CMS Region ${identifier.replace('region', '')} (${name}) Nursing Home Staffing Data | PBJ320`;
    description = `Q2 ${year} nursing home staffing data for CMS Region ${identifier.replace('region', '')} (${name}). Explore regional staffing levels, rankings, trends, and insights from CMS Payroll-Based Journal (PBJ) data. Analysis of nursing homes and long-term care facilities.`;
    ogTitle = `PBJ Wrapped Q2 ${year} — CMS Region ${identifier.replace('region', '')} Nursing Home Staffing`;
    ogDescription = `CMS Region ${identifier.replace('region', '')} (${name}) nursing home staffing data and trends for Q2 ${year}. Staffing levels, rankings, and insights from CMS PBJ data.`;
  }

  return {
    title,
    description,
    keywords,
    ogTitle,
    ogDescription,
    ogImage: `${baseUrl}/images/phoebe-wrapped-wide.png`,
    ogUrl: fullUrl,
    canonical: fullUrl,
  };
}

/**
 * Generate SEO data for SFF Wrapped page
 */
export function getSFFWrappedSEO(year: string = '2025'): SEOData {
  const baseUrl = 'https://pbj320.com';
  const path = `/wrapped/${year}/sff`;
  const fullUrl = `${baseUrl}${path}`;
  
  const keywords = [
    'special focus facilities',
    'SFF',
    'nursing home staffing',
    '2025',
    '320 consulting',
    'pbj320',
    'payroll-based journal',
    'nursing home residents',
    'long-term care',
    'pbj data',
    'CMS PBJ',
    'nursing home quality',
    'poor performing nursing homes'
  ].join(', ');

  return {
    title: `PBJ Wrapped Q2 ${year} — Special Focus Facilities (SFF) | PBJ320`,
    description: `Q2 ${year} Special Focus Facilities (SFF) nursing home staffing data. Explore staffing levels, quality ratings, and locations of SFF and SFF candidate facilities from CMS Payroll-Based Journal (PBJ) data.`,
    keywords,
    ogTitle: `PBJ Wrapped Q2 ${year} — Special Focus Facilities`,
    ogDescription: `Special Focus Facilities (SFF) nursing home staffing data for Q2 ${year}. Staffing levels, quality ratings, and locations from CMS PBJ data.`,
    ogImage: `${baseUrl}/images/phoebe-wrapped-wide.png`,
    ogUrl: fullUrl,
    canonical: fullUrl,
  };
}

/**
 * Generate SEO data for Wrapped landing page
 */
export function getWrappedLandingSEO(year: string = '2025'): SEOData {
  const baseUrl = 'https://pbj320.com';
  const path = '/';
  const fullUrl = `${baseUrl}${path}`;
  
  const keywords = [
    'nursing home staffing',
    '2025',
    '320 consulting',
    'pbj320',
    'payroll-based journal',
    'nursing home residents',
    'long-term care',
    'pbj data',
    'CMS PBJ',
    'nursing home quality',
    'staffing levels',
    'HPRD',
    'hours per resident day',
    'PBJ Wrapped'
  ].join(', ');

  return {
    title: `PBJ Wrapped Q2 ${year} — Nursing Home Staffing Data by State and Region | PBJ320`,
    description: `Explore Q2 ${year} nursing home staffing data across all 50 states, CMS regions, and the United States. Interactive staffing insights from CMS Payroll-Based Journal (PBJ) data. Comprehensive analysis of 15,000+ nursing homes and long-term care facilities.`,
    keywords,
    ogTitle: `PBJ Wrapped Q2 ${year} — Nursing Home Staffing Data`,
    ogDescription: `Interactive nursing home staffing data for Q2 ${year}. Explore staffing levels, trends, and insights by state, region, and nationally from CMS PBJ data.`,
    ogImage: `${baseUrl}/images/phoebe-wrapped-wide.png`,
    ogUrl: fullUrl,
    canonical: fullUrl,
  };
}



