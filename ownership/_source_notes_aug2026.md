# Ownership / CHOW source notes — Aug 2026 RC

Inventory and ingest notes for the `pbj-root-rc-owners-aug2026` owners release candidate. Do not treat this as a CMS release announcement; it records what was found on disk.

## CHOW archive inventory (2026-08-20)

### This RC (`pbj-root-rc-owners-aug2026`)

| Path | Size | Notes |
|------|------|--------|
| `chow_index.json` (repo root) | ~5.6 MB | Built index consumed by `/chow` and `ownership/chow_lookup.py` |
| `ownership/Skilled Nursing Facility Change of Ownership.zip` | 828,673 B | Copied into RC on 2026-08-20 from PBJapp Q2 staging (see below). Gitignored via `ownership/*.zip`. |
| `data/chow/` | empty (`.gitkeep` only) | Optional CSV drop dir for `scripts/build_chow_index.py` |

Before this pass the RC had **no** CHOW zip on disk; the index already matched Q2 row counts but meta still said Q1.

### Sibling: `pbj-root`

| Path | Size | mtime | Notes |
|------|------|-------|--------|
| `ownership/Skilled Nursing Facility Change of Ownership.zip` | 828,673 B | 2026-07-29 | SHA256 `92e1cd6b…b4d80d` — **byte-identical to PBJapp 2026-Q2 zip** |
| `chow_index.json` | ~5.6 MB | 2026-08-20 | Same 5,227 / `date_max=2026-02-01` coverage; meta still labeled Q1 until corrected in this RC |

### Sibling: `PBJapp` (source of truth for CMS CHOW drops)

| Path | Size | mtime | Q indicator | Coverage (raw CSV) |
|------|------|-------|-------------|--------------------|
| `ownership/_sources/cms_chow/2026-Q1/Skilled Nursing Facility Change of Ownership.zip` | 914,328 B | 2026-06-24 | Folder `2026-Q1/`, member `SNF_CHOW_2026.04.01.csv` | 5,141 rows; `date_max=2025-11-01` |
| `ownership/_sources/cms_chow/2026-Q1/SNF_CHOW_2026.04.01.csv` | 1,818,952 B | 2026-06-24 | Filename `2026.04.01` | Same as Q1 zip |
| `ownership/_sources/cms_chow/2026-Q2/Skilled Nursing Facility Change of Ownership.zip` | 828,673 B | 2026-07-29 | Member `SNF_CHOW_Q2_2026.csv` | **5,227 rows; `date_min=2016-01-01`, `date_max=2026-02-01`** |
| `ownership/_sources/cms_chow/2026-Q2/SNF_CHOW_Q2_2026.zip` | 473,414 B | 2026-07-29 | CSV-only Q2 package | Same 5,227 / same date span |
| `ownership/Skilled Nursing Facility Change of Ownership - Owner Information.zip` | ~44 MB | 2026-04-10 | Owner-information package (not the SNF CHOW event file used by `build_chow_index.py`) | Not used for `chow_index.json` |

**Q2 available:** yes — under `PBJapp/ownership/_sources/cms_chow/2026-Q2/`. No newer-than-Q2 CHOW zip was found in this RC, `pbj-root`, or `PBJapp`.

## Build path

- Builder: `scripts/build_chow_index.py`
- Default source: `ownership/Skilled Nursing Facility Change of Ownership.zip`
- Runtime reader: `ownership/chow_lookup.py` → `chow_index.json`
- Buyer/seller columns and associate-id namespaces are preserved by the builder (`ASSOCIATE ID - BUYER/SELLER`, `buyer_*` / `seller_*` fields, `associate_id_namespace` helpers)

## This pass (2026-08-20)

1. Confirmed Q2 CMS SNF CHOW zip exists and is newer than Q1 (more rows; extends through 2026-02-01 vs Q1 `date_max` 2025-11-01).
2. Copied Q2 zip into RC `ownership/Skilled Nursing Facility Change of Ownership.zip` (SHA256 `92e1cd6b5fa72dc5686ea312ee80ec8ac24ea5f72e4a8f867af5ed44afb4d80d`).
3. Rebuilt `chow_index.json` via `python scripts/build_chow_index.py`.
4. Updated builder `infer_meta` so meta records `cms_release`, coverage min/max, event count, and per-source SHA256 (no longer hardcodes Q1).

### Post-rebuild index (verified)

Verified from: `chow_index.json` meta after `python scripts/build_chow_index.py` (generated_at `2026-08-20T19:41:44Z`).

- **Source used:** `ownership/Skilled Nursing Facility Change of Ownership.zip` (CMS **Q2 2026**, member `SNF_CHOW_Q2_2026.csv`)
- **source_sha256:** `92e1cd6b5fa72dc5686ea312ee80ec8ac24ea5f72e4a8f867af5ed44afb4d80d`
- **Events:** 5,227
- **date_min / date_max:** 2016-01-01 / 2026-02-01
- **Q2 available:** yes (ingested)
- Buyer/seller fields and associate-id namespaces retained (sample namespaces: enrollment_pac / owner_control_pac / both / unknown)
