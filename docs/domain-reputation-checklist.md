# PBJ320 domain reputation checklist

Use this when a corporate web filter blocks `pbj320.com` with “Access Denied,” `policy_denied`, or “uncategorized” errors. The site is often reachable on other networks; the issue is usually URL categorization or allowlisting, not an application outage.

## Standard site description (for vendor categorization)

**Name:** PBJ320  
**Operator:** 320 Consulting LLC  
**URL:** https://pbj320.com (also https://www.pbj320.com)  
**Description:** PBJ320 is a public nursing-home staffing data and analytics platform. It displays and summarizes U.S. Centers for Medicare & Medicaid Services (CMS) Payroll-Based Journal (PBJ) staffing data and CMS Provider Information for research, journalism, advocacy, and professional review. It is not a government site, law firm, social network, or file-sharing service.  
**Suggested categories:** Business, Health, Data Analytics, Reference (optional: Legal Services for attorney-facing marketing pages only)

## Public trust pages (for reviewers)

| Page | URL |
|------|-----|
| Home | https://pbj320.com/ |
| Rankings report | https://pbj320.com/report |
| About | https://pbj320.com/about |
| Data sources | https://pbj320.com/data-sources |
| Contact | https://pbj320.com/contact |
| Privacy | https://pbj320.com/privacy |
| Terms | https://pbj320.com/terms |
| Premium (marketing) | https://pbj320.com/premium |
| robots.txt | https://pbj320.com/robots.txt |
| sitemap.xml | https://pbj320.com/sitemap.xml |

## Vendors to submit or check

Submit or review the domain on each service your organization or client uses:

1. [Google Safe Browsing](https://transparencyreport.google.com/safe-browsing/search)
2. [Microsoft Defender SmartScreen](https://www.microsoft.com/en-us/wdsi/support/report-unsafe-site)
3. [Cisco Talos Intelligence](https://talosintelligence.com/reputation)
4. Palo Alto URL Filtering (via your PAN admin / BrightCloud if applicable)
5. [FortiGuard Web Filter Lookup](https://www.fortiguard.com/webfilter)
6. Zscaler (via your Zscaler admin portal — URL categorization request)
7. [Trend Micro Site Safety Center](https://global.sitesafety.trendmicro.com/)
8. [Broadcom/Symantec Site Review](https://sitereview.broadcom.com/)
9. [Cloudflare Radar](https://radar.cloudflare.com/domains/pbj320.com)
10. [VirusTotal](https://www.virustotal.com/gui/domain/pbj320.com)
11. [URLVoid](https://www.urlvoid.com/scan/pbj320.com/)
12. [Sucuri SiteCheck](https://sitecheck.sucuri.net/)

## Law-firm IT allowlisting (canned message)

> PBJ320 is a nursing-home staffing data and analytics platform operated by 320 Consulting LLC. It uses public CMS Payroll-Based Journal staffing data and CMS Provider Information. Please allowlist **pbj320.com** and **www.pbj320.com** (HTTPS, port 443). Public pages include /, /report, /about, /data-sources, /contact, /privacy, and /terms.

## Internal verification

After deploy, run:

```bash
python scripts/site_health_check.py
```

Review `reports/site_health_latest.csv` for HTTP 200 on public URLs, short redirect chains, HTTPS sitemap `<loc>` values, and presence of baseline security headers.

## Notes

- Do not request allowlisting of private Premium dashboard paths or `/api/*` unless a specific integration requires it.
- Apex (`pbj320.com`) may 301 to `www.pbj320.com` depending on DNS/CDN; allowlist both hostnames.
- If only `/report` is blocked, ask IT whether “uncategorized” or “new domain” rules apply to deep paths separately from the homepage.
