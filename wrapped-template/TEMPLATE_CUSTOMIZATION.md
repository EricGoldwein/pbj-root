# Template Customization Guide

This guide provides step-by-step instructions for customizing the Wrapped Experience Template for your specific project.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Placeholder Replacement](#placeholder-replacement)
3. [Configuration Files](#configuration-files)
4. [Data Structure Customization](#data-structure-customization)
5. [Component Customization](#component-customization)
6. [Styling and Branding](#styling-and-branding)
7. [Adding Custom Cards](#adding-custom-cards)
8. [Testing](#testing)

## Quick Start

1. **Copy template files** to your project
2. **Rename files** (remove `.template` extension)
3. **Replace placeholders** using find-and-replace
4. **Configure data** in `wrapped.config.json`
5. **Test with your data**

## Placeholder Replacement

### Step 1: Identify All Placeholders

Use your editor's find feature to search for `{{` to find all placeholders. Common placeholders include:

#### Project-Level Placeholders
- `{{PROJECT_NAME}}` → Your project identifier (e.g., "MyProject")
- `{{BRAND_NAME}}` → Full branding name (e.g., "MyProject Year in Review")
- `{{SHORT_NAME}}` → Short name (e.g., "MP")
- `{{YEAR}}` → Year for the wrapped (e.g., "2025")

#### Data Field Placeholders
- `{{USERNAME_FIELD}}` → Username column name (e.g., "Username")
- `{{TOTAL_METRIC_FIELD}}` → Total metric column (e.g., "Total Points")
- `{{METRIC_NAME}}` → Metric name (e.g., "Points")
- `{{METRIC_NAME_LOWERCASE}}` → Lowercase metric (e.g., "points")
- `{{DISTANCE_FIELD}}` → Distance column (e.g., "Distance (KM)")
- `{{RANK_FIELD}}` → Rank column (e.g., "Rank")
- `{{DATE_FIELD}}` → Date column (e.g., "Date")
- `{{AMOUNT_FIELD}}` → Amount column (e.g., "Amount")
- `{{CATEGORY_FIELD}}` → Category column (e.g., "Category")
- `{{CATEGORY_1}}`, `{{CATEGORY_2}}` → Category values (e.g., "Mining", "Wager")
- `{{ACHIEVEMENT_FIELD_1}}`, `{{ACHIEVEMENT_FIELD_2}}` → Achievement columns
- `{{ACHIEVEMENT_1}}`, `{{ACHIEVEMENT_2}}` → Achievement names

#### Styling Placeholders
- `{{PRIMARY_COLOR}}` → Main brand color (e.g., "blue", "#3B82F6")
- `{{ACCENT_COLOR}}` → Accent color (e.g., "yellow", "#FCD34D")
- `{{BACKGROUND_COLOR}}` → Background color
- `{{TEXT_COLOR}}` → Text color
- `{{FONT_FAMILY}}` → Font family (e.g., "Inter, sans-serif")

#### Routing Placeholders
- `{{ROUTE_PATH}}` → Route path (e.g., "/wrapped")
- `{{BASE_URL}}` → Base URL (e.g., "https://example.com")
- `{{DEV_PORT}}` → Dev server port (e.g., "5173")

### Step 2: Replace Placeholders

**Recommended approach:**
1. Start with project-level placeholders (most common)
2. Then data field placeholders
3. Then styling placeholders
4. Finally, routing and content placeholders

**Find and Replace Strategy:**
- Use case-sensitive find and replace
- Replace one placeholder type at a time
- Verify replacements don't break syntax (especially in code files)

## Configuration Files

### wrapped.config.json

This is the main configuration file. Customize:

```json
{
  "project": {
    "name": "YourProject",
    "brandName": "Your Project Wrapped",
    "shortName": "YP",
    "year": "2025"
  },
  "routing": {
    "basePath": "/wrapped",
    "devPort": 5173
  },
  "data": {
    "sources": {
      "ledger": {
        "path": "/data/ledger.csv"
      },
      "log": {
        "path": "/data/log.csv"
      }
    }
  },
  "styling": {
    "theme": {
      "primaryColor": "blue",
      "accentColor": "yellow"
    }
  }
}
```

### data-schema.json

Define your CSV structure:

```json
{
  "ledger": {
    "fields": {
      "Username": {
        "type": "string",
        "description": "User identifier"
      },
      "Total Points": {
        "type": "number",
        "description": "Total points earned"
      }
    }
  }
}
```

## Data Structure Customization

### Step 1: Update Type Definitions

Edit `src/lib/wrapped/wrappedTypes.ts`:

```typescript
export interface LedgerRow {
  Username: string;
  TotalPoints: number;  // Your field
  Rank: number;
  // Add your fields
}
```

### Step 2: Update Data Processing

Edit `src/lib/wrapped/buildWrappedStats.ts`:

1. **Update field references** to match your CSV columns
2. **Customize session grouping** logic if needed
3. **Adjust scoring algorithms** for your metrics
4. **Modify achievement detection** logic

### Step 3: Update CSV Parsing

In `src/pages/wrapped.tsx`, update the Papa.parse calls:

```typescript
const parsedLedger = results.data.map((row) => ({
  ...row,
  TotalPoints: parseFloat(String(row.TotalPoints)) || 0,
  // Add your field parsing
}));
```

## Component Customization

### Card Components

Each card is in `src/components/wrapped/cards/`. To customize:

1. **Update props interface** to match your data
2. **Modify JSX** to display your metrics
3. **Adjust styling** for your brand
4. **Update copy** from `wrappedCopy`

Example - Customizing TotalMetricCard:

```typescript
interface TotalMetricCardProps {
  totalPoints: number;  // Changed from totalMetric
  distanceKM?: number;
  avatarUrl?: string;
  username?: string;
}
```

### Adding New Cards

1. Create new file: `src/components/wrapped/cards/MyNewCard.tsx`
2. Use `WrappedCard` as base wrapper
3. Import and add to `wrapped.tsx` screens array
4. Configure in `wrapped.config.json` if using config-driven approach

### Removing Cards

1. Remove import from `wrapped.tsx`
2. Remove from screens array
3. Delete card file if not needed elsewhere

## Styling and Branding

### Color Scheme

1. **Update Tailwind config** (if using Tailwind):
```javascript
theme: {
  extend: {
    colors: {
      'your-primary': '#YOUR_COLOR',
      'your-accent': '#YOUR_COLOR',
    }
  }
}
```

2. **Replace color placeholders** in components:
   - `{{PRIMARY_COLOR}}` → Your primary color class
   - `{{ACCENT_COLOR}}` → Your accent color class

3. **Update CSS variables** if using CSS:
```css
:root {
  --primary-color: #YOUR_COLOR;
  --accent-color: #YOUR_COLOR;
}
```

### Fonts

1. **Add font** to your project (Google Fonts, local files, etc.)
2. **Update font-family** placeholders
3. **Configure in Tailwind** or CSS

### Branding Elements

- **Logo**: Update `{{BRAND_LOGO}}` placeholder
- **Badge text**: Update in `WrappedCard.tsx`
- **Favicon**: Update in HTML head

## Adding Custom Cards

### Step 1: Create Card Component

```typescript
// src/components/wrapped/cards/CustomCard.tsx
import React from 'react';
import { WrappedCard } from '../WrappedCard';

interface CustomCardProps {
  data: YourDataType;
  username?: string;
}

export const CustomCard: React.FC<CustomCardProps> = ({ data, username }) => {
  return (
    <WrappedCard
      title="Your Title"
      username={username}
    >
      {/* Your content */}
    </WrappedCard>
  );
};
```

### Step 2: Add to Main Page

In `src/pages/wrapped.tsx`:

```typescript
import { CustomCard } from '../components/wrapped/cards/CustomCard';

// In screens array:
<CustomCard
  key="custom"
  data={stats.customData}
  username={stats.username}
/>
```

### Step 3: Configure Duration (if needed)

```typescript
const slideDurationsArray: number[] = screensArray.map((screen, index) => {
  if (React.isValidElement(screen) && screen.key === 'custom') {
    return 6000; // 6 seconds
  }
  return 4000; // Default
});
```

## Testing

### Step 1: Prepare Test Data

1. Create sample CSV files with test data
2. Ensure data matches your schema
3. Test with multiple users

### Step 2: Local Testing

1. Start dev server: `npm run dev`
2. Navigate to `/wrapped/test-username`
3. Verify all cards display correctly
4. Test navigation (swipe, tap, auto-advance)
5. Check mobile responsiveness

### Step 3: Data Validation

1. Test with missing data (null/undefined handling)
2. Test with edge cases (zero values, very large numbers)
3. Test with special characters in usernames
4. Verify date parsing works correctly

### Step 4: Performance Testing

1. Test with large datasets
2. Check image loading performance
3. Verify audio playback
4. Test on mobile devices

## Common Customization Tasks

### Changing Slide Duration

In `wrapped.tsx`, modify `slideDurationsArray`:

```typescript
const slideDurationsArray: number[] = screensArray.map((screen, index) => {
  if (React.isValidElement(screen) && screen.key === 'videoCard') {
    return 15000; // 15 seconds
  }
  return 5000; // Changed from 4000 to 5000
});
```

### Disabling Auto-Advance

In `WrappedScreenWrapper`, set `autoAdvance={false}` or modify config.

### Adding Background Music

1. Add audio file to `/public/` directory
2. Update `wrapped.config.json`:
```json
{
  "audio": {
    "file": "/your-audio.mp3"
  }
}
```

3. Update `WrappedScreenWrapper.tsx` to use your audio file

### Customizing Progress Bar

The progress bar is in `WrappedScreenWrapper.tsx`. Modify styling or behavior there.

## Troubleshooting

### Placeholders Not Replaced

- Use case-sensitive search
- Check for typos in placeholder names
- Verify file extensions are correct

### Data Not Loading

- Check CSV file paths
- Verify CSV column names match your schema
- Check browser console for errors
- Verify CSV format (headers, encoding)

### Styling Issues

- Check Tailwind config if using Tailwind
- Verify color classes exist
- Check CSS variable definitions
- Inspect element to see applied styles

### Component Errors

- Check prop types match data
- Verify imports are correct
- Check for missing dependencies
- Review console errors

## Next Steps

After customization:

1. Review `EXAMPLE_CUSTOMIZATION.md` for reference
2. Test thoroughly with real data
3. Deploy to staging environment
4. Gather user feedback
5. Iterate and improve

## Additional Resources

- React documentation: https://react.dev
- TypeScript documentation: https://www.typescriptlang.org
- Tailwind CSS: https://tailwindcss.com
- PapaParse (CSV parsing): https://www.papaparse.com

