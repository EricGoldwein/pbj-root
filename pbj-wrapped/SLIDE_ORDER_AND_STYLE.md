# PBJ Wrapped: Slide Order and Style Guide

This document provides comprehensive details about the slide order, styling, animations, and user interactions for the PBJ Wrapped presentation system.

## Table of Contents
- [Overview](#overview)
- [Slide Order by Scope](#slide-order-by-scope)
- [Visual Design System](#visual-design-system)
- [Animations and Transitions](#animations-and-transitions)
- [Navigation and Interactions](#navigation-and-interactions)
- [Responsive Design](#responsive-design)
- [Special Behaviors](#special-behaviors)

---

## Overview

The PBJ Wrapped presentation system is a full-screen, auto-advancing slide deck that presents nursing home staffing data across four different scopes:
- **USA**: National-level data and comparisons
- **State**: State-specific data and rankings
- **Region**: CMS Region-level data and state comparisons
- **SFF**: Special Focus Facilities dedicated presentation

Each scope has a tailored slide sequence optimized for its data type and audience.

---

## Slide Order by Scope

### USA Scope (15 slides)

| # | Slide Component | Title | Duration | Special Behavior |
|---|----------------|-------|----------|------------------|
| 1 | `HeaderCard` | "Phoebe J's PBJ Wrapped" | 5s | No container, gradient title |
| 2 | `WhatIsPBJCard` | "What is PBJ?" | **∞ (click-to-advance)** | Typing animation, staggered reveals |
| 3 | `WhatIsHPRDCard` | "What is HPRD?" | 5s | Educational content |
| 4 | `USANationalScaleCard` | "US Overview" | 5s | Large animated numbers |
| 5 | `BasicsCard` | "The Basics" | 5s | Key metrics overview |
| 6 | `USAOwnershipCard` | "Ownership Breakdown" | 5s | Distribution chart |
| 7 | `USAOwnershipStaffingCard` | "Staffing by Ownership" | 5s | Median HPRD by type |
| 8 | `USAStatesExtremesCard` | "State Rankings" | 5s | Top 5 / Bottom 5 states |
| 9 | `USARegionsExtremesCard` | "Region Rankings" | 5s | Top 3 / Bottom 3 regions |
| 10 | `SFFCard` | "Special Focus Facilities" | 5s | SFF count and list |
| 11 | `TrendsCard` | "Trends" | 5s | Q1→Q2 changes |
| 12 | `RisersCard` | "Biggest Risers" | 5s | Facilities with largest increases |
| 13 | `DeclinersCard` | "Biggest Decliners" | 5s | Facilities with largest decreases |
| 14 | `KeyTakeawaysCard` | "Phoebe J's Takeaway" | 5s | AI-generated insights |
| 15 | `NavigationCard` | "Explore PBJ320" | 5s | Links and replay button |

**Key Features:**
- Two ownership slides (breakdown + staffing)
- State and region extremes shown separately
- Focus on national comparisons

---

### State Scope (15 slides)

| # | Slide Component | Title | Duration | Special Behavior |
|---|----------------|-------|----------|------------------|
| 1 | `HeaderCard` | "Phoebe J's PBJ Wrapped" | 5s | State outline background |
| 2 | `WhatIsPBJCard` | "What is PBJ?" | **∞ (click-to-advance)** | Typing animation, state-specific context |
| 3 | `WhatIsHPRDCard` | "What is HPRD?" | 5s | Educational content |
| 4 | `StateMinimumCard` | "State Minimum Requirements" | 5s | **Conditional** (only if data available) |
| 5 | `StateOverviewCard` | "[State] at a Glance" | 5s | National rank, average rating |
| 6 | `BasicsCard` | "The Basics" | 5s | Key metrics, rankings |
| 7 | `RankingsCard` | "State Rankings" | 5s | National ranking positions |
| 8 | `LowestStaffingCard` | "Lowest Staffed Facilities" | 5s | Bottom 5 facilities |
| 9 | `HighestStaffingCard` | "Highest Staffed Facilities" | 5s | Top 5 facilities |
| 10 | `SFFCard` | "Special Focus Facilities" | 5s | SFF count and list |
| 11 | `TrendsCard` | "Trends" | 5s | Q1→Q2 changes |
| 12 | `RisersCard` | "Biggest Risers" | 5s | Facilities with largest increases |
| 13 | `DeclinersCard` | "Biggest Decliners" | 5s | Facilities with largest decreases |
| 14 | `KeyTakeawaysCard` | "Phoebe J's Takeaway" | 5s | AI-generated insights (volatility detector) |
| 15 | `NavigationCard` | "Explore PBJ320" | 5s | Links and replay button |

**Key Features:**
- State outline shown as subtle background on all slides
- State minimum requirements slide (if available)
- Facility-level extremes (lowest/highest)
- Volatility detector used for takeaway insights

---

### Region Scope (12 slides)

| # | Slide Component | Title | Duration | Special Behavior |
|---|----------------|-------|----------|------------------|
| 1 | `HeaderCard` | "Phoebe J's PBJ Wrapped" | 5s | No container, gradient title |
| 2 | `WhatIsPBJCard` | "What is PBJ?" | **∞ (click-to-advance)** | Typing animation, region-specific context |
| 3 | `WhatIsHPRDCard` | "What is HPRD?" | 5s | Educational content |
| 4 | `RegionStatesCard` | "States in This Region" | 5s | State list with metrics |
| 5 | `BasicsCard` | "The Basics" | 5s | Key metrics, rankings |
| 6 | `RankingsCard` | "Region Rankings" | 5s | National ranking positions |
| 7 | `SFFCard` | "Special Focus Facilities" | 5s | SFF count and list |
| 8 | `TrendsCard` | "Trends" | 5s | Q1→Q2 changes |
| 9 | `RisersCard` | "Biggest Risers" | 5s | States with largest increases |
| 10 | `DeclinersCard` | "Biggest Decliners" | 5s | States with largest decreases |
| 11 | `KeyTakeawaysCard` | "Phoebe J's Takeaway" | 5s | AI-generated insights |
| 12 | `NavigationCard` | "Explore PBJ320" | 5s | Links and replay button |

**Key Features:**
- **No facility extremes** (focus on state-level data)
- Early state overview slide
- Region name format: "CMS Region X (Region Name)"

---

### SFF Scope (8 slides)

| # | Slide Component | Title | Duration | Special Behavior |
|---|----------------|-------|----------|------------------|
| 1 | `HeaderCard` | "PBJ Wrapped — Q2 2025" | 5s | Custom subtitle: "Special Focus Facilities" |
| 2 | `WhatIsSFFCard` | "What is SFF?" | 5s | Educational content |
| 3 | `WhatIsPBJCard` | "What is PBJ?" | 5s | Standard PBJ explanation |
| 4 | `OverviewCard` | "Overview" | 5s | SFF count / Candidate count |
| 5 | `StaffingOverviewCard` | "Staffing Overview" | 5s | Median HPRD for SFFs and Candidates |
| 6 | `SFFsCard` | "Special Focus Facilities (X)" | 5s | **Conditional** (only if SFFs exist) |
| 7 | `CandidatesCard` | "SFF Candidates (X)" | 5s | **Conditional** (only if candidates exist) |
| 8 | `NavigationCard` | "Explore More" | 5s | Links to USA wrapped and home |

**Key Features:**
- Dedicated SFF presentation flow
- Conditional slides based on data availability
- Focus on facility listings with staffing data

---

## Visual Design System

### Color Palette

- **Primary Background**: `bg-gradient-to-br from-gray-900 via-blue-900 to-gray-900`
- **Card Background**: `bg-black/70` with `backdrop-blur-md`
- **Card Border**: `border-2 border-blue-500/50` (hover: `border-blue-400/60`)
- **Primary Text**: White gradient (`from-white via-gray-100 to-gray-200`)
- **Secondary Text**: `text-gray-300`, `text-gray-400`
- **Accent Colors**:
  - Blue: `text-blue-300`, `bg-blue-500/20`
  - Red (bottom rankings): `text-red-400`
  - Green (top rankings): `text-green-400`
  - Orange (SFF): `bg-orange-500/10`
  - Yellow (Candidates): `bg-yellow-500/10`

### Typography

- **Title**: `text-3xl md:text-4xl lg:text-5xl font-bold`
  - Gradient text effect (white gradient or blue gradient for noContainer)
  - `drop-shadow-2xl` for depth
  - Line height: `1.15` for tight spacing
  
- **Subtitle**: `text-base md:text-lg lg:text-xl text-gray-300`
  - Medium weight, drop shadow
  
- **Body Text**: `text-xs md:text-sm` (mobile) / `text-base md:text-lg` (desktop)
  - Responsive sizing with breakpoints

### Card Container Styling

```css
/* Standard Card Container */
bg-black/70                    /* Semi-transparent black */
backdrop-blur-md                /* Glassmorphism effect */
rounded-3xl                     /* Rounded corners */
p-4 md:p-5 lg:p-6               /* Responsive padding */
pb-6 md:pb-8 lg:pb-10          /* Extra bottom padding */
border-2 border-blue-500/50    /* Blue border */
shadow-2xl                      /* Deep shadow */
max-h-[75vh] md:max-h-[80vh]   /* Max height with scroll */
overflow-y-auto                /* Scrollable content */
```

**Hover Effects:**
- Border: `hover:border-blue-400/60`
- Shadow: `hover:shadow-blue-500/20`
- Transition: `transition-all duration-300`

### Badge Component

- **Background**: `bg-blue-500/20 backdrop-blur-sm`
- **Border**: `border-2 border-blue-500/50`
- **Text**: `text-blue-300 font-bold tracking-wide`
- **Shape**: `rounded-full`
- **Padding**: `px-4 py-2`

### State Outline Background (State Scope Only)

- **Position**: Absolute, full screen, `z-0`
- **Opacity**: `0.15` (subtle)
- **Color**: Inherits from state outline SVG
- **Size**: `max-width: 90vw, max-height: 90vh`
- **Min Size**: `600px × 600px` (prevents too-small rendering)

---

## Animations and Transitions

### Slide Transitions

**Entry Animation:**
```css
animation: slideFadeIn 0.5s cubic-bezier(0.4, 0, 0.2, 1)
```

**Keyframe:**
```css
@keyframes slideFadeIn {
  from {
    opacity: 0;
    transform: translateY(15px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
```

### Typing Animation (WhatIsPBJCard)

- **Speed**: 30ms per character
- **Initial Delay**: 300ms
- **Cursor**: Pulsing blue bar (`animate-pulse`)
- **Text Container**: Blue-tinted box with left border accent

### Staggered Reveals (WhatIsPBJCard)

- **"Why it matters"**: Appears 1200ms after typing completes
- **"Note"**: Appears 2200ms after typing completes
- **Animation**: `animate-fade-in-up` (0.6s ease-out)

**Fade-in-up Keyframe:**
```css
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
```

### Number Animations

- **Hook**: `useAnimatedNumber(target, duration, decimals)`
- **Default Duration**: 1000ms
- **Easing**: Smooth interpolation from 0 to target
- **Used For**: Facility counts, resident counts, HPRD values

### Navigation Hint

- **Visibility**: Fades out after 5 seconds
- **Position**: Top-right corner
- **Style**: `bg-black/60 backdrop-blur-sm border border-blue-500/30`
- **Transition**: `transition-opacity duration-1000`

---

## Navigation and Interactions

### Auto-Advance

- **Default Duration**: 5000ms (5 seconds) per slide
- **Exception**: "What is PBJ?" slide uses `Infinity` (click-to-advance only)
- **Pause Behavior**: Auto-advance pauses when user manually navigates
- **Resume**: Auto-advance resumes on next slide

### Keyboard Navigation

- **Right Arrow / Space**: Advance to next slide
- **Left Arrow**: Go to previous slide
- **Escape**: Pause/resume auto-advance
- **Smart Ignore**: Keyboard events ignored when focus is on input/select/textarea

### Touch/Swipe Navigation

- **Swipe Right**: Previous slide (minimum 50px swipe)
- **Swipe Left**: Next slide (minimum 50px swipe)
- **Tap Anywhere (Mobile)**: Advance to next slide (if not last slide)
- **Tap Anywhere (Desktop)**: No action (except on click-to-advance slides)

### Click-to-Advance Slides

- **"What is PBJ?" Slide**: Requires user interaction to advance
- **Visual Indicator**: "Click or tap anywhere to continue" text below card
- **Cursor**: `cursor-pointer` on desktop
- **Mobile**: Full-screen tap area

### Navigation Controls

**Desktop:**
- Previous/Next arrow buttons (bottom-center)
- Progress bar (bottom)
- Slide counter (e.g., "3 / 15")

**Mobile:**
- Swipe gestures
- Tap-to-advance
- Progress bar (bottom)
- Slide counter (bottom)

**Progress Bar:**
- **Color**: Blue gradient (`from-blue-500 to-blue-400`)
- **Height**: `h-1.5`
- **Position**: Bottom of screen
- **Animation**: Smooth width transition

---

## Responsive Design

### Breakpoints

- **Mobile**: Default (< 768px)
- **Tablet/Desktop**: `md:` prefix (≥ 768px)
- **Large Desktop**: `lg:` prefix (≥ 1024px)

### Typography Scaling

| Element | Mobile | Desktop | Large Desktop |
|---------|--------|---------|---------------|
| Title | `text-3xl` | `text-4xl` | `text-5xl` |
| Subtitle | `text-base` | `text-lg` | `text-xl` |
| Body | `text-xs` | `text-sm` | `text-base` |
| Large Numbers | `text-4xl` | `text-5xl` | `text-6xl` |

### Spacing Scaling

- **Padding**: `p-4` → `md:p-5` → `lg:p-6`
- **Bottom Padding**: `pb-6` → `md:pb-8` → `lg:pb-10`
- **Gaps**: `gap-2` → `md:gap-3` → `lg:gap-4`
- **Margins**: `mb-2` → `md:mb-3` → `lg:mb-4`

### Card Container

- **Max Width**: `max-w-full` (mobile) → `md:max-w-[480px]` (desktop)
- **Max Height**: `max-h-[75vh]` (mobile) → `md:max-h-[80vh]` (desktop)
- **Padding**: Responsive as above

### Image Sizing

- **Header Image (State)**: `max-height: 140px`
- **Header Image (USA/Region)**: `max-height: 280px`
- **Responsive**: `max-width: 100%`, `height: auto`

### Touch Targets

- **Minimum Size**: 44px × 44px (iOS/Android guidelines)
- **Touch Action**: `touch-action: manipulation` (prevents double-tap zoom)
- **Tap Highlight**: `-webkit-tap-highlight-color: transparent`

---

## Special Behaviors

### Conditional Slides

**State Minimum Card:**
- Only appears if `wrappedData.stateMinimum` exists
- Shows state-specific minimum staffing requirements

**SFF Slides:**
- SFFs card only appears if `sffData.sffs.length > 0`
- Candidates card only appears if `sffData.candidates.length > 0`

### Data Formatting

**Numbers:**
- **Large Numbers**: `toLocaleString()` with commas (e.g., "1,234,567")
- **HPRD Values**: 2 decimal places (e.g., "3.78")
- **Percentages**: 2 decimal places with % symbol (e.g., "12.34%")
- **Residents (≥ 1M)**: Formatted as "X.X million" (e.g., "1.2 million")

**State Names:**
- Full state names used (e.g., "Puerto Rico" not "Pr")
- Abbreviations converted via `STATE_ABBR_TO_NAME` mapping

**Region Names:**
- Format: "CMS Region X (Region Name)"
- Example: "CMS Region 2 (New York)"

### Source Attribution

**First Mention:**
- "Source: CMS Payroll-Based Journal, Q2 2025"

**Subsequent Mentions:**
- "Source: CMS PBJ Q2 2025"

**Placement:**
- Bottom of card, small gray text
- Border-top separator above source text

### Link Generation

**State Links:**
- Format: `https://pbjdashboard.com/?state=XX`
- Example: `https://pbjdashboard.com/?state=OR`

**Region Links:**
- Top/Bottom Regions: `https://pbj320.com/report`
- Movers: `https://pbjdashboard.com/?region=X`

**Facility Links:**
- Format: `https://pbjdashboard.com/?facility=XXXXX`

**Internal Routes:**
- SFF Wrapped: `/sff` (resolves to `/pbj-wrapped/sff` with basename)

### Color Coding

**Rankings:**
- **Bottom Rankings**: `text-red-400` (red-ish)
- **Top Rankings**: `text-green-400` (green-ish)

**Ownership Types:**
- **For-Profit**: Blue indicator (`bg-blue-400`)
- **Non-Profit**: Green indicator (`bg-green-400`)
- **Government**: Purple indicator (`bg-purple-400`)

**SFF Status:**
- **SFFs**: Orange background (`bg-orange-500/10`)
- **Candidates**: Yellow background (`bg-yellow-500/10`)

### Text Redundancy Removal

- **HPRD Labels**: Hidden when title already indicates "By total HPRD"
- **"Staffing" Word**: Removed from titles where context is clear (e.g., "State Rankings" not "State Staffing Rankings")
- **RN Staffing**: Changed to "RN staff" (not "RN staffing")

### Volatility Detector (State Takeaway)

- Identifies most volatile state metric for takeaway
- Prioritizes `totalHPRDChange` or `rnHPRDChange` over static counts
- Excludes SFF count (constant across states)

---

## Performance Considerations

### Scrollbar Styling

- **Width**: 6px (thin)
- **Thumb Color**: `rgba(59, 130, 246, 0.5)` (blue, semi-transparent)
- **Track**: Transparent
- **Platform**: Custom styling for webkit browsers

### Image Loading

- **Lazy Loading**: Images load on demand
- **Asset Path**: Uses `getAssetPath()` utility for correct base URL
- **Format**: PNG with transparency support

### Animation Performance

- **GPU Acceleration**: Transform and opacity animations
- **Will-Change**: Not explicitly set (browser optimization)
- **Easing**: `cubic-bezier` for smooth transitions

### Data Processing

- **Memoization**: `useMemo` for screen array generation
- **Lazy Evaluation**: Conditional slides only render when needed
- **Data Caching**: Loaded data cached in component state

---

## Accessibility

### Keyboard Navigation
- Full keyboard support (arrows, space, escape)
- Focus management for interactive elements

### Screen Readers
- Semantic HTML structure
- Alt text for images
- ARIA labels where appropriate

### Color Contrast
- WCAG AA compliant text colors
- High contrast for readability

### Touch Targets
- Minimum 44px × 44px for mobile
- Adequate spacing between interactive elements

---

## Future Enhancements

Potential improvements for consideration:
- Slide transition customization options
- Custom duration per slide type
- Pause on hover (desktop)
- Slide preview thumbnails
- Export/share functionality
- Full-screen mode toggle
- Audio narration support

---

*Last Updated: Q2 2025*
*Documentation Version: 1.0*

