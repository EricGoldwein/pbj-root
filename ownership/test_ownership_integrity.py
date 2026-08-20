"""Ownership publication integrity remediation tests (P2-P7)."""
from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from ownership.owner_indexability import (  # noqa: E402
    classify_owner_profile,
    is_suppress_owner_name,
    meaningful_context_flags,
    public_owner_associate_ids_for_sitemap,
)
from ownership.owner_portfolio_metrics import (  # noqa: E402
    _merge_provider_lookup_row,
    ownership_provider_info_paths,
    provider_info_source_sort_key,
)
from ownership.ownership_release_policy import (  # noqa: E402
    OwnershipReleaseEntry,
    OwnershipReleasePolicyError,
    validate_enrollment_bridge_pairing,
)
from ownership.relationship_period import (  # noqa: E402
    parse_pbj_quarter_bounds,
    relationship_supported_for_period,
)
from ownership.role_classification import (  # noqa: E402
    CATEGORY_ADMIN,
    CATEGORY_OWNERSHIP,
    PCT_COL,
    ROLE_CODE_COL,
    ROLE_TEXT_COL,
    classify_owner_record,
    facility_stake_column_label,
    parse_ownership_pct,
)


def _fac(**kwargs):
    base = {"ccn": "123456", "state": "NY", "pbj_matched": True}
    base.update(kwargs)
    return base


class ReleasePolicyIntegrityTests(unittest.TestCase):
    def test_july_rejects_may_enrollment_without_override(self) -> None:
        entry = OwnershipReleaseEntry(
            release_date="2026-07-17",
            ownership_source_filename="SNF_All_Owners_2026.07.17.csv",
            bridge_lookup_filename="release_2026-07-17_lookup.json",
            bridge_pairing_status="exact_release_date_match",
            status="active",
            ownership_source_sha256="abc",
            enrollment_release_date="2026-05-01",
            allow_enrollment_date_mismatch=False,
        )
        with self.assertRaises(OwnershipReleasePolicyError) as ctx:
            validate_enrollment_bridge_pairing(
                entry, {"enrollment_release_date": "2026-05-01"}
            )
        self.assertIn("mismatch", str(ctx.exception).lower())

    def test_july_allows_documented_enrollment_mismatch(self) -> None:
        entry = OwnershipReleaseEntry(
            release_date="2026-07-17",
            ownership_source_filename="SNF_All_Owners_2026.07.17.csv",
            bridge_lookup_filename="release_2026-07-17_lookup.json",
            bridge_pairing_status="exact_release_date_match",
            status="active",
            ownership_source_sha256="abc",
            enrollment_release_date="2026-05-01",
            allow_enrollment_date_mismatch=True,
        )
        validate_enrollment_bridge_pairing(
            entry, {"enrollment_release_date": "2026-05-01"}
        )


class ProviderInfoPrecedenceTests(unittest.TestCase):
    def test_norm_sorts_above_combined_latest(self) -> None:
        norm = Path("provider_info/ProviderInfoNorm_2026_07.csv")
        combined = Path("provider_info_combined_latest.csv")
        self.assertGreater(
            provider_info_source_sort_key(norm),
            provider_info_source_sort_key(combined),
        )

    def test_historical_combined_not_on_hot_path(self) -> None:
        paths = ownership_provider_info_paths()
        self.assertTrue(all(p.name.lower() != "provider_info_combined.csv" for p in paths))

    def test_older_snapshot_cannot_override_newer_norm_values(self) -> None:
        newer = {"hprd": "3.5", "overall_rating": "4", "provider_name": "July Name"}
        older = {"hprd": "2.0", "overall_rating": "1", "provider_name": "May Name", "beds": "100"}
        merged = _merge_provider_lookup_row(newer, older)
        self.assertEqual(merged["hprd"], "3.5")
        self.assertEqual(merged["overall_rating"], "4")
        self.assertEqual(merged["provider_name"], "July Name")
        self.assertEqual(merged["beds"], "100")  # blank-fill only


class UnknownPartySuppressTests(unittest.TestCase):
    def test_suppress_variants(self) -> None:
        for name in (
            "",
            "Unknown",
            "unknown party",
            "Unknown Party",
            "N/A",
            "None",
            "null",
            "  unknown parties  ",
        ):
            self.assertTrue(is_suppress_owner_name(name), msg=repr(name))

    def test_real_name_not_suppressed(self) -> None:
        self.assertFalse(is_suppress_owner_name("Benjamin Landa"))

    def test_sitemap_excludes_suppress_even_if_cache_stale(self) -> None:
        stale = {
            "6800306788": {
                "classification": "index",
                "owner_name": "Unknown party",
            },
            "1234567890": {
                "classification": "index",
                "owner_name": "Acme Holdings LLC",
            },
        }
        with patch(
            "ownership.owner_indexability.load_owner_indexability_cache",
            return_value=stale,
        ):
            pacs = public_owner_associate_ids_for_sitemap(cache_only=True)
        self.assertNotIn("6800306788", pacs)
        self.assertIn("1234567890", pacs)

    def test_write_before_after_scratch(self) -> None:
        audit = _ROOT / "ownership" / "owner_indexability_audit.csv"
        out = _ROOT / "_scratch" / "unknown_party_before_after.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        before = {"unknown": 0, "unknown_party": 0, "other_suppress_candidates": 0, "rows": 0}
        after = {"would_suppress": 0, "rows": 0}
        if audit.is_file():
            with audit.open(encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    before["rows"] += 1
                    after["rows"] += 1
                    name = (row.get("owner_name") or "").strip()
                    low = name.casefold()
                    if low == "unknown":
                        before["unknown"] += 1
                    if "unknown party" in low:
                        before["unknown_party"] += 1
                    if is_suppress_owner_name(name):
                        after["would_suppress"] += 1
        payload = {
            "source": str(audit) if audit.is_file() else None,
            "before_name_counts": before,
            "after_reclassify_suppress_name_count": after["would_suppress"],
            "note": "before counts are name-token tallies; after applies is_suppress_owner_name",
        }
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.assertTrue(out.is_file())
        if audit.is_file():
            self.assertGreater(before["unknown_party"], 0)


class NullPctNotInferredEquityTests(unittest.TestCase):
    def test_blank_pct_does_not_infer_ownership_interest(self) -> None:
        info = classify_owner_record(
            {
                ROLE_CODE_COL: "72",
                ROLE_TEXT_COL: "ADP OF THE SNF",
                PCT_COL: "",
            }
        )
        self.assertEqual(info["role_category"], CATEGORY_ADMIN)
        self.assertFalse(info["is_ownership_interest"])
        self.assertIsNone(info["ownership_pct"])
        self.assertIsNone(parse_ownership_pct(""))
        self.assertIsNone(parse_ownership_pct(None))
        short, _long = facility_stake_column_label(
            role_raw="ADP OF THE SNF", role_code="72", pct_raw=""
        )
        self.assertNotRegex(short, r"^\d")
        self.assertNotIn("ownership interest", short.lower())


class TemporalAttributionTests(unittest.TestCase):
    def test_metric_before_assoc_excluded(self) -> None:
        bounds = parse_pbj_quarter_bounds("Q1 2026")
        assert bounds is not None
        start, end = bounds
        self.assertEqual(start, date(2026, 1, 1))
        self.assertEqual(end, date(2026, 3, 31))
        self.assertEqual(
            relationship_supported_for_period("04/15/2026", start, end),
            "exclude",
        )
        self.assertEqual(
            relationship_supported_for_period("01/01/2025", start, end),
            "supported",
        )
        self.assertEqual(
            relationship_supported_for_period("", start, end),
            "uncertain",
        )


class ChowNamespaceTests(unittest.TestCase):
    def test_namespace_not_silently_converted(self) -> None:
        from ownership.owner_profile import associate_id_namespace

        with patch(
            "ownership.owner_profile.classify_associate_id",
            return_value="enrollment",
        ):
            self.assertEqual(associate_id_namespace("1234567890"), "enrollment_pac")
        with patch(
            "ownership.owner_profile.classify_associate_id",
            return_value="owner_control",
        ):
            self.assertEqual(associate_id_namespace("1234567890"), "owner_control_pac")
        with patch(
            "ownership.owner_profile.classify_associate_id",
            return_value="both",
        ):
            self.assertEqual(associate_id_namespace("1234567890"), "both")
        with patch(
            "ownership.owner_profile.classify_associate_id",
            return_value="none",
        ):
            self.assertEqual(associate_id_namespace("1234567890"), "unknown")


class NetworkIndexabilityTests(unittest.TestCase):
    def test_coenrollment_alone_does_not_index_thin_profile(self) -> None:
        profile = {
            "associate_id": "1234567890",
            "display_name": "Acme Holdings LLC",
            "states": ["CT"],
            "facilities": [_fac()],
            "related_associates": [
                {
                    "associate_id": "0987654321",
                    "name": "Co Enrollee",
                    "snf_shared": 1,
                    "chow_count": 0,
                    "shared_ownership_interest": False,
                    "sources": ["snf"],
                }
            ],
        }
        flags = meaningful_context_flags(profile)
        self.assertNotIn("network", flags)
        self.assertNotIn("shared_ownership_interest", flags)
        cl, reason, _meta = classify_owner_profile(profile)
        self.assertEqual(cl, "noindex_follow")
        self.assertEqual(reason, "single_facility_no_context")

    def test_shared_ownership_interest_indexes(self) -> None:
        profile = {
            "associate_id": "1234567890",
            "display_name": "Acme Holdings LLC",
            "states": ["CT"],
            "facilities": [_fac()],
            "related_associates": [
                {
                    "associate_id": "0987654321",
                    "name": "Equity Partner",
                    "shared_ownership_interest": True,
                    "sources": ["snf"],
                }
            ],
        }
        flags = meaningful_context_flags(profile)
        self.assertIn("shared_ownership_interest", flags)
        cl, reason, _meta = classify_owner_profile(profile)
        self.assertEqual(cl, "index")
        self.assertIn("shared_ownership_interest", reason)

    def test_flag_breakdown_categories_documented(self) -> None:
        """Document single-facility indexability breakdown categories."""
        categories = {
            "coenrollment_only_related_associates": "noindex_follow (no network flag)",
            "shared_ownership_interest": "index",
            "abuse_sff_enforcement": "index",
            "recent_chow_on_profile": "index (separate from counterparty network)",
            "affiliated_control_parties": "index",
            "operator_grouping_enrollment": "index",
            "portfolio_or_multi_state": "index",
        }
        out = _ROOT / "_scratch" / "indexability_flag_breakdown.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        audit = _ROOT / "ownership" / "owner_indexability_audit.csv"
        counts = {
            "index_network_only_legacy": 0,
            "index_total": 0,
            "rows": 0,
        }
        if audit.is_file():
            with audit.open(encoding="utf-8", newline="") as f:
                for row in csv.DictReader(f):
                    counts["rows"] += 1
                    if row.get("classification") == "index":
                        counts["index_total"] += 1
                        if (row.get("flags") or "") == "network":
                            counts["index_network_only_legacy"] += 1
        payload = {"categories": categories, "legacy_audit_counts": counts}
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.assertIn("coenrollment_only_related_associates", categories)
        self.assertTrue(out.is_file())


if __name__ == "__main__":
    unittest.main()
