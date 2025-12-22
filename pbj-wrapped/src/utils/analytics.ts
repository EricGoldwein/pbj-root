/**
 * Google Analytics utility functions
 */

// Declare gtag function for TypeScript
declare global {
  interface Window {
    gtag: (...args: any[]) => void;
    dataLayer: any[];
  }
}

/**
 * Track a page view
 */
export function trackPageView(path: string, title?: string): void {
  if (typeof window !== 'undefined' && window.gtag) {
    window.gtag('config', 'G-NDPVY6TWBK', {
      page_path: path,
      page_title: title,
    });
  }
}

/**
 * Track an event
 */
export function trackEvent(
  action: string,
  category: string,
  label?: string,
  value?: number
): void {
  if (typeof window !== 'undefined' && window.gtag) {
    window.gtag('event', action, {
      event_category: category,
      event_label: label,
      value: value,
    });
  }
}

/**
 * Track a click on a facility dashboard link
 */
export function trackFacilityLinkClick(provnum: string, facilityName?: string, context?: string): void {
  trackEvent('click', 'facility_dashboard_link', `${provnum}${facilityName ? ` - ${facilityName}` : ''}${context ? ` (${context})` : ''}`);
}

/**
 * Track a click on a state dashboard link
 */
export function trackStateLinkClick(stateCode: string, stateName?: string, context?: string): void {
  trackEvent('click', 'state_dashboard_link', `${stateCode}${stateName ? ` - ${stateName}` : ''}${context ? ` (${context})` : ''}`);
}

/**
 * Track a click on a general dashboard link
 */
export function trackDashboardLinkClick(linkType: string, context?: string): void {
  trackEvent('click', 'dashboard_link', `${linkType}${context ? ` (${context})` : ''}`);
}

