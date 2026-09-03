# PBJ320 vNext — Implementation Decisions

## Product

- Familiar renovation, not reinvention.
- Preserve routes, calculations, terminology, data relationships, and proven UX.
- Core discovery is Provider -> Chain -> State.
- Owner/control party belongs to the same connected data system.
- Rankings, SFF, and other comparative surfaces are views of that system, not separate products.

## Visual system

- Warm paper / light analytical canvas.
- Near-black primary text.
- Restrained PBJ purple for brand, frame, focus, and actions.
- Brand owns the frame; semantics own the data.
- White analytical surfaces only where separation helps.
- Low chrome, minimal shadows, restrained radii.
- DM Sans: primary UI, body, headings, tables.
- Vollkorn: selective editorial accent.
- DM Mono: IDs, quarters, vintages, methodology, technical metadata.

## Navigation

Current global navigation baseline:

- About
- Report
- Insights
- Owners
- Premium
- PBJ Explained is currently a mobile-only navigation item.

Provider, Chain, and State are homepage search modes, not global navigation destinations.

Generated mockups do not define PBJ320 information architecture.

Do not change global navigation IA during proof phases without a separate deliberate decision.

## Phoebe

- Use canonical Phoebe J artwork only.
- Primary recurring role: PBJ Takeaway / explanation.
- Use as a small circular avatar beside the Takeaway heading.
- Do not reserve large illustration space for Phoebe.
- No speech bubbles or "Phoebe says."
- Bricky and Mr. Cells are not PBJ320 characters.
- PBJ favicon remains the product mark.

## Provider proof

- Provider is the first dense analytical proof surface.
- Preserve existing analytical hierarchy and data logic.
- Metrics use a flat typographic grammar rather than SaaS cards.
- PBJ Takeaway is the principal branded analytical object.
- Major page sections may use anchor-style navigation.

Trends use one primary analytical surface with:

1. Total staffing
2. By role
3. Census

- Total staffing is the default.
- By-role trends remain available but do not permanently consume a second chart.
- Census trend is important context because HPRD depends on resident census.
- Historical census must use existing supported data; never fabricate it.

## Charts

- Primary observed series: strongest solid treatment.
- Secondary/direct series: quieter or dashed.
- Benchmark/reference: neutral dashed.
- RN/LPN/aide receive categorical distinction when displayed together.
- Census receives its own simple observed-series treatment.
- Do not create a permanent rainbow where every metric has a mandatory brand color.

## Homepage

- Utility first, not a marketing landing page.
- Visual direction comes from the approved PBJ/Figma direction.
- Current production is the behavioral/content baseline.
- Provider / Chain / State search remains dominant above the fold.
- Preserve the working USA/state filter in Provider mode.
- Useful current discovery content remains below search.
- Email capture comes after the primary search utility.
- Premium remains downstream and restrained.
- No testimonials, generic SaaS feature rows, or invented marketing claims.
- Phoebe is supporting, not hero-sized.

## Audience / email

- Existing audience infrastructure is canonical.
- Facility, State, National, and PBJ320 Insights subscription concepts already exist.
- The 320 / Substack remains a separate editorial relationship.
- Do not rebuild audience infrastructure during vNext UI work.
- Chain-scoped sending remains intentionally disabled pending send-workflow support.
- Production persistence and delivery configuration are later ops verification, not a vNext blocker.

## Provenance

- Preserve and consolidate existing source/vintage helpers.
- Progressive disclosure: scan -> inspect -> reproduce.
- Keep source information rigorous without repeating bulky provenance blocks everywhere.

## Sequence

1. Phase 0A dead-interface cleanup
2. Provider proof
3. Homepage proof
4. State / Entity extension
5. Tables / overlays / charts / provenance consolidation
6. Ownership
7. Premium alignment
8. SFF / Report integration separately

## Deferred

- Chain/owner subscription sending
- Entity -> Owner / Owner -> State connection work
- broader global navigation IA reconsideration
- State benchmark/anomaly parity
- PBJPedia integration timing
- SFF/Report rewrite decisions
