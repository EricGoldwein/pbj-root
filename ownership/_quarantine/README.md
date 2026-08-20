# Quarantine — do not ingest

Files here failed download validation or are otherwise unsafe as CMS ownership inputs.

## `SNF_Owners_ADP_Association_2026.07.31.csv`

- **Why quarantined:** HTTP/error body only (`Page not found`, ~14 bytes) — not a real ADP association extract.
- **Rule:** never feed this path into builders, SQLite loads, release validation as “present ADP data,” or ownership pipelines.
- **Policy note:** `ownership_release_policy.json` may still name the expected ADP filename for the July-31 release; treat that as a desired upstream artifact, not proof this quarantine copy is valid.
