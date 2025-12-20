# Wrapped Experience Template

## Overview

This template provides a complete, reusable structure for creating "wrapped" year-in-review experiences similar to Spotify Wrapped. The template is designed to be easily customizable for different datasets, audiences, and branding.

## What is a "Wrapped" Experience?

A wrapped experience is an interactive, story-driven presentation that:
- Shows personalized statistics and achievements
- Uses an auto-advancing slide format (Instagram/TikTok story style)
- Includes touch/swipe navigation
- Supports background music
- Is optimized for mobile devices
- Creates shareable, engaging content

## Template Structure

```
wrapped-template/
├── TEMPLATE_README.md              # This file
├── TEMPLATE_CUSTOMIZATION.md       # Detailed customization guide
├── EXAMPLE_CUSTOMIZATION.md        # Real-world example (WINGO)
├── wrapped.config.template.json    # Main configuration file
├── data-schema.template.json       # Data structure schema
├── open-wrapped.bat.template       # Windows launcher script
├── open-wrapped.ps1.template       # PowerShell launcher script
├── .cursorrules.template           # Cursor AI instructions
└── src/                            # Source code templates
    ├── pages/
    │   └── wrapped.template.tsx
    ├── components/
    │   └── wrapped/
    │       ├── WrappedCard.template.tsx
    │       ├── WrappedContext.template.tsx
    │       ├── WrappedScreenWrapper.template.tsx
    │       └── cards/
    │           ├── TitleCard.template.tsx
    │           ├── StatsCard.template.tsx
    │           └── ... (more card templates)
    └── lib/
        └── wrapped/
            ├── buildWrappedStats.template.ts
            ├── wrappedTypes.template.ts
            └── wrappedCopy.template.ts
```

## Quick Start

1. **Copy template files** to your project directory
2. **Replace placeholders** using the customization guide
3. **Configure your data** in `wrapped.config.template.json`
4. **Customize styling** and branding
5. **Add your data** (CSV files)
6. **Test and deploy**

## Key Placeholders

All placeholders use the format `{{PLACEHOLDER_NAME}}`. Common placeholders include:

### Project-Level
- `{{PROJECT_NAME}}` - Main project identifier
- `{{BRAND_NAME}}` - Full branding name (e.g., "WINGO World Wrapped")
- `{{SHORT_NAME}}` - Short project name (e.g., "WINGO")
- `{{YEAR}}` - Year for the wrapped experience

### Data Fields
- `{{USERNAME_FIELD}}` - Username column name in CSV
- `{{METRIC_1}}`, `{{METRIC_2}}` - Custom metric names
- `{{ACHIEVEMENT_1}}`, `{{ACHIEVEMENT_2}}` - Achievement types
- `{{DATE_FIELD}}` - Date column name
- `{{AMOUNT_FIELD}}` - Amount/value column name

### Styling
- `{{PRIMARY_COLOR}}` - Main brand color (hex code)
- `{{ACCENT_COLOR}}` - Accent color (hex code)
- `{{FONT_FAMILY}}` - Primary font family
- `{{BRAND_LOGO}}` - Logo path/URL

### Routing
- `{{ROUTE_PATH}}` - Main wrapped route (e.g., "/wrapped")
- `{{BASE_URL}}` - Base application URL
- `{{DEV_PORT}}` - Development server port

## Data Requirements

The template expects CSV data files with the following structure:

### Ledger CSV
Contains user summary data:
- Username
- Total metrics (points, balance, distance, etc.)
- Achievement flags
- Rankings

### Log CSV
Contains transaction/activity history:
- Username
- Date
- Category (Mining, Wager, Achievement, etc.)
- Amount/value changes
- Activity metadata

See `data-schema.template.json` for detailed field mappings.

## Features

- ✅ Auto-advancing slides with configurable durations
- ✅ Touch/swipe navigation
- ✅ Progress bar indicator
- ✅ Background music support
- ✅ Mobile-optimized full-screen experience
- ✅ Configurable card types and order
- ✅ Theme customization
- ✅ Type-safe TypeScript implementation
- ✅ Responsive design

## Customization Checklist

- [ ] Replace all `{{PROJECT_NAME}}` placeholders
- [ ] Replace all `{{BRAND_NAME}}` placeholders
- [ ] Update `wrapped.config.template.json` with your settings
- [ ] Map CSV columns in `data-schema.template.json`
- [ ] Customize colors and fonts
- [ ] Update card components for your metrics
- [ ] Add/remove card types as needed
- [ ] Update copy/text content
- [ ] Configure routing paths
- [ ] Test with your data

## Next Steps

1. Read `TEMPLATE_CUSTOMIZATION.md` for detailed instructions
2. Review `EXAMPLE_CUSTOMIZATION.md` to see a real implementation
3. Start with configuration files, then move to components
4. Test incrementally as you customize

## Support

For questions or issues:
1. Check the customization guide
2. Review the example implementation
3. Refer to the original WINGO implementation for reference

