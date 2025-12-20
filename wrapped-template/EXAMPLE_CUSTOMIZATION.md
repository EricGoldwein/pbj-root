# Example Customization: WINGO World Wrapped

This document shows how the WINGO World Wrapped implementation was created from the template, serving as a real-world example of template customization.

## Overview

WINGO World Wrapped is a year-in-review experience for the 320 Track Club, showing personalized statistics from WINGO mining activities. This example demonstrates how the generic template was adapted for a specific use case.

## Placeholder Replacements

### Project-Level

| Placeholder | WINGO Value |
|------------|-------------|
| `{{PROJECT_NAME}}` | `WINGO` |
| `{{BRAND_NAME}}` | `WINGO World Wrapped` |
| `{{SHORT_NAME}}` | `WINGO` |
| `{{YEAR}}` | `2025` |

### Data Fields

| Placeholder | WINGO Value |
|------------|-------------|
| `{{USERNAME_FIELD}}` | `Username` |
| `{{TOTAL_METRIC_FIELD}}` | `Total Mined` |
| `{{METRIC_NAME}}` | `Wingo` |
| `{{METRIC_NAME_LOWERCASE}}` | `wingo` |
| `{{DISTANCE_FIELD}}` | `Distance (KM)` |
| `{{RANK_FIELD}}` | `Rank` |
| `{{DATE_FIELD}}` | `Date` |
| `{{AMOUNT_FIELD}}` | `WINGO +/-` |
| `{{CATEGORY_FIELD}}` | `Category` |
| `{{CATEGORY_1}}` | `Mining` |
| `{{CATEGORY_2}}` | `Wager` |
| `{{ACTIVITY_TYPE_1}}` | `Wager` |
| `{{ACHIEVEMENT_1}}` | `OBWIPrize` |
| `{{ACHIEVEMENT_2}}` | `Yellowstone` |
| `{{ACHIEVEMENT_3}}` | `DancingDaisy` |
| `{{ACHIEVEMENT_4}}` | `GateUnlock` |

### Styling

| Placeholder | WINGO Value |
|------------|-------------|
| `{{PRIMARY_COLOR}}` | `blue` (used in some contexts) |
| `{{ACCENT_COLOR}}` | `yellow` (primary accent) |
| `{{FONT_FAMILY}}` | Default system fonts |

### Routing

| Placeholder | WINGO Value |
|------------|-------------|
| `{{ROUTE_PATH}}` | `/wapped` |
| `{{DEV_PORT}}` | `5173` |

## File Structure Comparison

### Template Structure
```
wrapped-template/
├── src/
│   ├── pages/
│   │   └── wrapped.template.tsx
│   ├── components/
│   │   └── wrapped/
│   │       └── cards/
│   │           └── TotalMinedCard.template.tsx
│   └── lib/
│       └── wrapped/
│           ├── buildWrappedStats.template.ts
│           └── wrappedTypes.template.ts
```

### WINGO Implementation
```
wingo-bets/
├── src/
│   ├── pages/
│   │   └── wapped.tsx
│   ├── components/
│   │   └── wrapped/
│   │       └── cards/
│   │           ├── TotalMinedCard.tsx
│   │           ├── TitleCard.tsx
│   │           ├── InitiationCard.tsx
│   │           └── ... (18+ card types)
│   └── lib/
│       └── wrapped/
│           ├── buildWrappedStats.ts
│           ├── wrappedTypes.ts
│           └── wrappedCopy.ts
```

## Key Customizations

### 1. Data Processing (`buildWrappedStats.ts`)

**Template:**
```typescript
function group{{CATEGORY_1}}Sessions(logRows: LogRow[]): {{CATEGORY_1}}Session[] {
  // Generic session grouping
}
```

**WINGO Implementation:**
```typescript
function groupMiningSessions(logRows: LogRow[]): MiningSession[] {
  // Groups by date and activity link
  // Handles WINGO-specific session logic
}
```

**Changes:**
- Renamed to `groupMiningSessions`
- Customized for WINGO mining activities
- Added activity link grouping logic

### 2. Type Definitions (`wrappedTypes.ts`)

**Template:**
```typescript
export interface LedgerRow {
  {{USERNAME_FIELD}}: string;
  {{TOTAL_METRIC_FIELD}}: number;
}
```

**WINGO Implementation:**
```typescript
export interface LedgerRow {
  Username: string;
  'Total Mined': number;
  'Distance (KM)': number;
  Rank: number;
  'OBWI Prize': number;
  // ... more fields
}
```

**Changes:**
- Used exact CSV column names (with spaces)
- Added WINGO-specific fields
- Included achievement fields

### 3. Card Components

**Template TotalMinedCard:**
```typescript
interface TotalMinedCardProps {
  total{{METRIC_NAME}}Mined: number;
  {{DISTANCE_FIELD}}?: number;
}
```

**WINGO TotalMinedCard:**
```typescript
interface TotalMinedCardProps {
  totalWingoMined: number;
  distanceKM?: number;
}
```

**Changes:**
- Renamed props to WINGO terminology
- Added WINGO-specific styling
- Customized display format

### 4. Copy/Text Content (`wrappedCopy.ts`)

**Template:**
```typescript
export const wrappedCopy = {
  title: {
    main: '{{BRAND_NAME}}',
    subtitle: '{{SUBTITLE_TEXT}}',
  },
};
```

**WINGO Implementation:**
```typescript
export const wrappedCopy = {
  title: {
    main: 'WINGO World Wapped',
    subtitle: 'A 320 Track Club Experience',
  },
  cards: {
    totalMined: {
      title: 'WINGO Mined (2025)',
      distance: 'That\'s {km} km of Wingos',
    },
    // ... more cards
  },
};
```

**Changes:**
- Added WINGO-specific copy
- Included all card text content
- Added WINGO terminology and tone

### 5. Main Page (`wapped.tsx`)

**Template:**
```typescript
const screensArray: React.ReactElement[] = [
  <TitleCard key="title" ... />,
  <TotalMinedCard key="totalMined" ... />,
  // Generic cards
];
```

**WINGO Implementation:**
```typescript
const screensArray: React.ReactElement[] = [
  <TitleCard key="title" ... />,
  <InitiationCard key="initiation" ... />,
  <WingateSatelliteCard key="wingateSatellite" ... />,
  <TotalMinedCard key="totalMined" ... />,
  <HighestSessionCard key="highestSession" ... />,
  // ... 18+ cards total
];
```

**Changes:**
- Added WINGO-specific cards
- Customized card order
- Added conditional cards (OBWI Prize, etc.)
- Configured custom durations for video/ad cards

## Custom Cards Added

WINGO added many custom cards beyond the template:

1. **InitiationCard** - Shows user's initiation date
2. **WingateSatelliteCard** - Satellite view of the track
3. **HighestSessionCard** - Best single mining session
4. **WingoPerSessionCard** - Average WINGO per session
5. **MinedWithDaisyCard** - Special recognition card
6. **DaisyCategoryCard** - DAISY's personal designation
7. **WagersCard** - Wager statistics
8. **SpecialUnlocksCard** - Achievement unlocks
9. **DaisyTrustCard** - Trust score
10. **OBWIVideoCard** - Special video for prize winners
11. **OBWIPrizeCard** - Prize recognition
12. **TenPlusOneCard** - Membership completion
13. **OldBalanceCard** - Advertisement card
14. **WingonomicsCard** - Advertisement card
15. **WingipediaCard** - Link card
16. **NextYearCard** - Future goals
17. **SaveTheDateCard** - Event information
18. **ShareCard** - Final summary

## Styling Customizations

### Colors
- Primary accent: Yellow/Amber (`yellow-400`, `yellow-500`)
- Background: Dark/Black with gradients
- Text: White with yellow accents

### Typography
- Large, bold numbers for metrics
- Gradient text effects
- Responsive sizing (mobile/desktop)

### Layout
- Full-screen mobile experience
- Centered cards with max-width
- Progress bar at top
- Audio controls

## Data Processing Customizations

### Session Grouping
- Groups by date and activity link
- Handles multiple activities per day
- Tracks source types

### Scoring Algorithms
- DAISY Trust Score: Custom algorithm based on:
  - Initiation status
  - Session count
  - Average WINGO per session
  - Membership completion
  - Wager behavior
- DVOT Score: Deterministic random number based on username

### Achievement Detection
- OBWI Prize: Checks ledger and log
- Yellowstone: Completion flag
- Dancing Daisy: Achievement flag
- Gate Unlock: Special unlock status

## Lessons Learned

### What Worked Well

1. **Template Structure**: The modular card system made it easy to add new cards
2. **Type Safety**: TypeScript interfaces caught many errors early
3. **Configuration**: Having a config file would have helped (added later)
4. **Copy Centralization**: `wrappedCopy.ts` made text updates easy

### Challenges

1. **CSV Column Names**: Spaces in column names required careful handling
2. **Date Parsing**: Multiple date formats needed robust parsing
3. **Username Matching**: Case-insensitive matching with accents was complex
4. **Session Grouping**: Logic needed refinement for WINGO's use case

### Recommendations

1. **Start Simple**: Begin with basic cards, add complexity later
2. **Test Early**: Test with real data as soon as possible
3. **Document Assumptions**: Note any data format assumptions
4. **Plan for Edge Cases**: Handle missing/null data gracefully

## Migration Path

If starting from template today:

1. **Week 1**: Replace placeholders, set up basic structure
2. **Week 2**: Customize data processing, test with sample data
3. **Week 3**: Create core cards (Title, Stats, Achievements)
4. **Week 4**: Add advanced cards, polish styling
5. **Week 5**: Testing, bug fixes, deployment

## Conclusion

The template provided a solid foundation that saved significant development time. The main work was:
- Customizing data processing logic
- Creating WINGO-specific cards
- Adapting styling to brand
- Handling WINGO-specific business logic

The template's structure and patterns made these customizations straightforward and maintainable.

