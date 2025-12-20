# Template Files Index

This document provides a quick reference to all template files and their purposes.

## Documentation Files

- **TEMPLATE_README.md** - Main template guide and overview
- **TEMPLATE_CUSTOMIZATION.md** - Detailed step-by-step customization instructions
- **EXAMPLE_CUSTOMIZATION.md** - Real-world example showing WINGO implementation
- **TEMPLATE_INDEX.md** - This file (quick reference)

## Configuration Files

- **wrapped.config.template.json** - Main configuration file (project settings, routing, data sources, styling, slides)
- **data-schema.template.json** - CSV data structure schema and field definitions
- **.cursorrules.template** - Cursor AI instructions for template usage

## Script Templates

- **open-wrapped.bat.template** - Windows batch launcher script
- **open-wrapped.ps1.template** - PowerShell launcher script (better error handling)

## Source Code Templates

### Main Page
- **src/pages/wrapped.template.tsx** - Main wrapped experience page component

### Core Components
- **src/components/wrapped/WrappedCard.template.tsx** - Base card wrapper component
- **src/components/wrapped/WrappedContext.template.tsx** - React context for wrapped data
- **src/components/wrapped/WrappedImage.template.tsx** - Image component with loading/error handling

### Card Components
- **src/components/wrapped/cards/TitleCard.template.tsx** - Welcome/title card
- **src/components/wrapped/cards/TotalMetricCard.template.tsx** - Total metric display card

### Data Processing
- **src/lib/wrapped/buildWrappedStats.template.ts** - Main data processing logic
- **src/lib/wrapped/wrappedTypes.template.ts** - TypeScript type definitions
- **src/lib/wrapped/wrappedCopy.template.ts** - Centralized text/copy content
- **src/lib/wrapped/avatarUtils.template.ts** - Avatar/image utility functions

## Quick Start Checklist

1. [ ] Read `TEMPLATE_README.md` for overview
2. [ ] Copy template files to your project
3. [ ] Remove `.template` extensions from files
4. [ ] Replace placeholders starting with project-level ones
5. [ ] Configure `wrapped.config.json`
6. [ ] Update `data-schema.json` for your CSV structure
7. [ ] Customize data processing in `buildWrappedStats.ts`
8. [ ] Update type definitions in `wrappedTypes.ts`
9. [ ] Customize card components
10. [ ] Update copy/text in `wrappedCopy.ts`
11. [ ] Test with your data
12. [ ] Deploy

## File Customization Priority

### High Priority (Start Here)
1. `wrapped.config.template.json` → `wrapped.config.json`
2. `data-schema.template.json` → `data-schema.json`
3. `src/lib/wrapped/wrappedTypes.template.ts` → `wrappedTypes.ts`
4. `src/lib/wrapped/wrappedCopy.template.ts` → `wrappedCopy.ts`

### Medium Priority
5. `src/lib/wrapped/buildWrappedStats.template.ts` → `buildWrappedStats.ts`
6. `src/pages/wrapped.template.tsx` → `wrapped.tsx`
7. Card components in `src/components/wrapped/cards/`

### Low Priority (Usually Work As-Is)
8. `src/components/wrapped/WrappedCard.template.tsx`
9. `src/components/wrapped/WrappedContext.template.tsx`
10. `src/components/wrapped/WrappedImage.template.tsx`
11. Script files (`.bat`, `.ps1`)

## Notes

- **WrappedScreenWrapper**: This component is not templated as it's core infrastructure that typically works as-is. It handles navigation, audio, progress bars, etc. Customize only if needed.

- **Additional Cards**: The template includes example cards. You'll likely need to create additional cards specific to your use case. Use existing cards as templates.

- **Styling**: If using Tailwind CSS, you may need to update `tailwind.config.js` to include your color scheme. The template uses placeholder color names.

## Getting Help

1. Check `TEMPLATE_CUSTOMIZATION.md` for detailed instructions
2. Review `EXAMPLE_CUSTOMIZATION.md` for WINGO example
3. Refer to original WINGO implementation in `wingo-bets/src/`
4. Check `.cursorrules.template` for AI assistant guidelines

