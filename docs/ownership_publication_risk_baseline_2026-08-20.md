# Ownership publication-risk baseline (pre-remediation)

**Record date:** 2026-08-20  
**Status:** Read-only forensic baseline captured before the contained integrity remediation pass.  
**Production gate at capture:** CT + FL + NJ + NY  
**Active SNF All Owners:** `SNF_All_Owners_2026.07.17.csv` (July 2026)

This document freezes the pre-fix findings. Do not treat local WIP nationwide gate artifacts as production evidence.

## CRITICAL (LIVE)

1. ~2,500 sitemap pages titled “Unknown party Nursing Home Ownership” (e.g. `/owners/6800306788`). Suppress matched `Unknown` but not `Unknown party`.
2. ~6,814 thin single-facility pages indexed solely via `network` context (any related associate / co-enrollee / CHOW counterparty).

## HIGH (LIVE)

3. Titles/OG/JSON-LD say “Ownership” for enrollment and non-equity control roles.
4. Most CMS rows are not ownership interest; blank `%` common (ADP 100% blank).
5. “Since {date}” treats association start as ongoing ownership period.
6. “Associated Owners” / network overclaim feeds indexing.
7. CHOW buyer PACs often enrollment IDs, not SNF owner PACs.
8. Enrollment PAC vs owner PAC vs `/entity/{id}` namespace confusion.
9. July ownership release still used May enrollment CCN bridge pairing.
10. Provider-info May/July skew (`NH_ProviderInfo_Latest` May-aligned vs July Norm) affecting joins/metrics.

## MEDIUM / LOW

Portfolio count semantics (name vs CCN), fuzzy name matches, geography address vs facility state, FEC name-only matching, hub meta omitting NJ, role code fallthrough, multi-% display ambiguity, association-date sentinels.

## Scope note for remediation

Objective pipeline/data defects (enrollment pairing, provider-info precedence, placeholder suppress, network indexability, temporal attribution, CHOW identity namespaces) are in scope for the next remediation pass. Global terminology / title / OG / JSON-LD / FEC UI / geography wording changes are deferred.
