/**
 * PHOEBE J USAGE RULES (Authoritative)
 * ====================================
 * Internal, code-level documentation for Phoebe J placement and framing.
 * Phoebe J is an anthropomorphized PBJ sandwich used for consumer-facing explanation.
 *
 * WHAT PHOEBE J IS:
 * - An OPTIONAL explainer
 * - A translation aid for PBJ concepts
 * - Consumer-facing only
 *
 * WHAT PHOEBE J IS NOT:
 * - A spokesperson
 * - An analyst
 * - An authority
 * - A brand mascot
 * - Appropriate for legal or press credibility contexts
 *
 * HARD EXCLUSIONS (Phoebe J must NEVER appear on):
 * - Press page
 * - Custom Reports / Legal Support (Attorneys) page
 * - Methodology or limitations sections
 * - Anything that could be cited or screenshotted in court or media
 *
 * ALLOWED ZONES (use sparingly):
 * - Homepage (light touch only)
 * - PBJ explainer / educational sections (e.g. About)
 * - Dashboard onboarding or tooltips
 * - "New to PBJ?" moments
 *
 * VISUAL CONSTRAINTS:
 * - max-width: 120-160px desktop, smaller on mobile
 * - Maintain aspect ratio
 * - Responsive, tucked in, not floating
 *
 * TONE OF ACCOMPANYING TEXT:
 * - Explain structure, not conclusions
 * - Plain-English but precise
 * - Avoid: jokes, declarative claims, "what this shows" language
 */

// Allowed pages for Phoebe J visual placement (page identifiers)
const PHOEBE_ALLOWED_PAGES = ['index', 'about', 'insights', 'pbj-sample'];

// Pages where Phoebe J must NEVER appear
const PHOEBE_EXCLUDED_PAGES = ['press', 'attorneys'];

// Max dimensions (px) for Phoebe J image
const PHOEBE_MAX_WIDTH_DESKTOP = 160;
const PHOEBE_MAX_WIDTH_MOBILE = 100;
