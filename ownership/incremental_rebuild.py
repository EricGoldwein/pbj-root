"""Incremental monthly ownership rebuild strategy (Phase 11).

After a clean nationwide RC baseline:

1. Ingest new monthly SNF_All_Owners into a release-scoped raw table (or sidecar DB).
2. Diff current_relationships vs prior release on (pac, ccn, role_category, ownership_pct, association_date).
3. Collect changed PAC set, CCN set, and touched states.
4. Rebuild only:
   - pac_to_ccns / ccn_to_pacs / ownership_interest_current rows for changed PACs/CCNs
   - pac_publication_taxonomy + pac_indexability for changed PACs
   - owner_search_lite rows for changed PACs
   - state_owner_index lists for touched states only
5. Regenerate global artifacts once from the normalized current store:
   - national OI rankings
   - sitemap PAC list (from pac_indexability where classification=index)
   - national hub counts

Do not re-run load_owner_profile_resolved across ~100k PACs when a few percent of
relationships change. Full profile construction remains a request-time / cache-warming
concern, not a monthly index build prerequisite.
"""
