# Wrapped Experience Template

This folder contains a complete, reusable template for creating "wrapped" year-in-review experiences.

## Quick Start

1. **Copy this entire `wrapped-template/` folder** to your new project
2. **Remove `.template` extensions** from all files
3. **Replace placeholders** (see `TEMPLATE_CUSTOMIZATION.md`)
4. **Configure your data** in `wrapped.config.json`
5. **Test and deploy**

## Folder Structure

All template files are organized in this single folder:

```
wrapped-template/
├── README.md                          # This file
├── TEMPLATE_README.md                 # Main template guide
├── TEMPLATE_CUSTOMIZATION.md          # Detailed customization guide
├── EXAMPLE_CUSTOMIZATION.md           # WINGO implementation example
├── TEMPLATE_INDEX.md                  # File index reference
├── wrapped.config.template.json       # Main configuration
├── data-schema.template.json          # Data structure schema
├── .cursorrules.template              # Cursor AI instructions
├── open-wrapped.bat.template          # Windows launcher
├── open-wrapped.ps1.template          # PowerShell launcher
└── src/                               # Source code templates
    ├── pages/
    │   └── wrapped.template.tsx
    ├── components/
    │   └── wrapped/
    │       ├── WrappedCard.template.tsx
    │       ├── WrappedContext.template.tsx
    │       ├── WrappedImage.template.tsx
    │       └── cards/
    │           ├── TitleCard.template.tsx
    │           └── TotalMetricCard.template.tsx
    └── lib/
        └── wrapped/
            ├── buildWrappedStats.template.ts
            ├── wrappedTypes.template.ts
            ├── wrappedCopy.template.ts
            └── avatarUtils.template.ts
```

## Usage

1. **Copy the folder**: Copy this entire `wrapped-template/` directory to your project
2. **Rename files**: Remove `.template` extension from all files
3. **Customize**: Follow `TEMPLATE_CUSTOMIZATION.md` for step-by-step instructions
4. **Configure**: Update `wrapped.config.json` with your project settings
5. **Deploy**: Integrate into your React/TypeScript project

## Documentation

- **TEMPLATE_README.md** - Overview and quick start
- **TEMPLATE_CUSTOMIZATION.md** - Detailed customization guide
- **EXAMPLE_CUSTOMIZATION.md** - Real-world example (WINGO)
- **TEMPLATE_INDEX.md** - Quick file reference

## Features

- ✅ Generic placeholders (no WINGO-specific terms)
- ✅ Config-driven customization
- ✅ Type-safe TypeScript
- ✅ Modular card system
- ✅ Mobile-optimized
- ✅ Auto-advancing slides
- ✅ Touch navigation
- ✅ Background music support

## Requirements

- React 18+
- TypeScript 4.5+
- Modern build tool (Vite, Create React App, etc.)
- CSV data files

## Next Steps

1. Read `TEMPLATE_README.md` for overview
2. Follow `TEMPLATE_CUSTOMIZATION.md` for customization
3. Reference `EXAMPLE_CUSTOMIZATION.md` for examples
4. Start replacing placeholders!

