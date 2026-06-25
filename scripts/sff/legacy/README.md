# Legacy SFF extraction scripts

These scripts are **not** used by the current pipeline.

| File | Former role | Replacement |
|------|-------------|-------------|
| `extract_sff_candidates_pypdf2.py` | PyPDF2 text parser writing `sff-candidate-months.json` | `scripts/sff/extract_sff_posting.py` + `build_sff_dataset.py` |
| `extract_sff_candidate_months.py` | Candidate-months-only helper | `publish_sff_artifacts.py` (legacy JSON derived from canonical dataset) |

Current pipeline: see `docs/data_sources/sff.md`.
