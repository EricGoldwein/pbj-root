"""
Unit tests for conduit/earmark attribution (fec_api_client).
Covers: direct donation, conduit_resolved, conduit_unresolved.
"""
import os
import sys

# Avoid loading .env for unit tests
os.environ.setdefault("FEC_API_KEY", "test-key-not-used")

donor_dir = os.path.dirname(os.path.abspath(__file__))
if donor_dir not in sys.path:
    sys.path.insert(0, donor_dir)

from fec_api_client import (
    CONDUIT_COMMITTEE_IDS,
    is_earmarked_transaction,
    add_conduit_attribution,
    compute_conduit_diagnostics,
    normalize_fec_donation,
)


def test_direct_donation():
    """Committee not conduit, no earmark -> donation_attribution_type = 'direct', ultimate = recipient."""
    record = {
        "contributor_name": "Jane Doe",
        "contribution_receipt_amount": 100,
        "contribution_receipt_date": "2024-01-15",
        "committee_id": "C00999999",
        "committee": {"committee_id": "C00999999", "name": "Some PAC"},
        "candidate": {},
        "memo_code": None,
        "memo_text": None,
    }
    norm = normalize_fec_donation(record)
    out = add_conduit_attribution(norm)
    assert out["donation_attribution_type"] == "direct"
    assert out["ultimate_recipient_id"] == "C00999999"
    assert out["ultimate_recipient_name"] == "Some PAC"
    assert out["is_earmarked_transaction"] is False


def test_conduit_resolved():
    """Recipient is ActBlue (conduit) and candidate is present -> conduit_resolved, ultimate = candidate."""
    record = {
        "contributor_name": "Jane Doe",
        "contribution_receipt_amount": 50,
        "contribution_receipt_date": "2024-02-01",
        "committee_id": "C00401224",
        "committee": {"committee_id": "C00401224", "name": "ACTBLUE"},
        "candidate": {"candidate_id": "P80001571", "name": "BIDEN, JOSEPH R JR"},
        "memo_code": "X",
        "memo_text": "Earmarked for Biden",
    }
    norm = normalize_fec_donation(record)
    out = add_conduit_attribution(norm)
    assert out["donation_attribution_type"] == "conduit_resolved"
    assert out["ultimate_recipient_id"] == "P80001571"
    assert out["ultimate_recipient_name"] == "BIDEN, JOSEPH R JR"
    assert out["is_earmarked_transaction"] is True


def test_conduit_unresolved():
    """Recipient is WinRed (conduit) but no candidate -> conduit_unresolved, ultimate empty."""
    record = {
        "contributor_name": "John Smith",
        "contribution_receipt_amount": 25,
        "contribution_receipt_date": "2024-03-01",
        "committee_id": "C00694323",
        "committee": {"committee_id": "C00694323", "name": "WINRED"},
        "candidate": None,
        "memo_code": None,
        "memo_text": None,
    }
    norm = normalize_fec_donation(record)
    out = add_conduit_attribution(norm)
    assert out["donation_attribution_type"] == "conduit_unresolved"
    assert out["ultimate_recipient_id"] == ""
    assert out["ultimate_recipient_name"] == ""
    assert out["is_earmarked_transaction"] is False


def test_earmark_via_memo_text():
    """memo_text contains 'processed by' -> is_earmarked_transaction True; resolve if candidate present."""
    record = {
        "contributor_name": "Donor",
        "contribution_receipt_amount": 10,
        "contribution_receipt_date": "2024-01-01",
        "committee_id": "C00999999",
        "committee": {"committee_id": "C00999999", "name": "Other PAC"},
        "candidate": {"candidate_id": "P00000001", "name": "CANDIDATE"},
        "memo_code": None,
        "memo_text": "Processed by ActBlue",
    }
    norm = normalize_fec_donation(record)
    out = add_conduit_attribution(norm)
    assert out["is_earmarked_transaction"] is True
    assert out["donation_attribution_type"] == "conduit_resolved"
    assert out["ultimate_recipient_id"] == "P00000001"


def test_conduit_diagnostics():
    """compute_conduit_diagnostics returns totals, pct via conduit, resolved/unresolved, top recipients."""
    records = [
        add_conduit_attribution(normalize_fec_donation({
            "contributor_name": "A", "contribution_receipt_amount": 100, "contribution_receipt_date": "2024-01-01",
            "committee_id": "C00999999", "committee": {"committee_id": "C00999999", "name": "PAC"}, "candidate": {},
            "memo_code": None, "memo_text": None,
        })),
        add_conduit_attribution(normalize_fec_donation({
            "contributor_name": "B", "contribution_receipt_amount": 50, "contribution_receipt_date": "2024-01-01",
            "committee_id": "C00401224", "committee": {"committee_id": "C00401224", "name": "ActBlue"},
            "candidate": {"candidate_id": "P1", "name": "Candidate 1"}, "memo_code": "X", "memo_text": "Earmark",
        })),
        add_conduit_attribution(normalize_fec_donation({
            "contributor_name": "C", "contribution_receipt_amount": 25, "contribution_receipt_date": "2024-01-01",
            "committee_id": "C00694323", "committee": {"committee_id": "C00694323", "name": "WinRed"},
            "candidate": None, "memo_code": None, "memo_text": None,
        })),
    ]
    diag = compute_conduit_diagnostics(records)
    assert diag["total_donations"] == 3
    assert diag["total_amount"] == 175
    assert diag["conduit_count"] == 2
    assert diag["conduit_amount"] == 75
    assert diag["pct_via_conduit"] == round(100.0 * 2 / 3, 1)
    assert diag["conduit_resolved_count"] == 1
    assert diag["conduit_unresolved_count"] == 1
    assert len(diag["top_ultimate_recipients"]) <= 10


def test_conduit_committee_ids():
    """ActBlue and WinRed are in CONDUIT_COMMITTEE_IDS."""
    assert "C00401224" in CONDUIT_COMMITTEE_IDS
    assert "C00694323" in CONDUIT_COMMITTEE_IDS


if __name__ == "__main__":
    test_direct_donation()
    test_conduit_resolved()
    test_conduit_unresolved()
    test_earmark_via_memo_text()
    test_conduit_diagnostics()
    test_conduit_committee_ids()
    print("All conduit attribution tests passed.")
