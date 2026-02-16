"""
Internal check: replicate exactly what the live site does for MAGA Inc. committee search.

Calls the same HTTP endpoint the browser calls on Render:
  GET /api/search/committee?q=C00892471  (or q=MAGA Inc.)

Asserts:
  a) Request does NOT time out (completes within 115s; gunicorn timeout is 120s).
  b) Response is 200 and Landa (Benjamin Landa, $5M) appears in the returned data.

Run from repo root:
  python -m donor.test_maga_committee_integration

Requires FEC_API_KEY. Uses real FEC API (no mocks) so behavior matches production.
"""
import concurrent.futures
import json
import sys
import time
from pathlib import Path

# Run from repo root; donor dir on path for imports
donor_dir = Path(__file__).resolve().parent
repo_root = donor_dir.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))
if str(donor_dir) not in sys.path:
    sys.path.insert(0, str(donor_dir))

# Gunicorn on Render uses timeout=120; fail if our request would exceed 115s
REQUEST_TIMEOUT_SEC = 115


def _find_landa_in_response(data):
    """Return (found, details). Check owners, raw_contributions, all_contributions for LANDA and $5M."""
    def has_landa_5m(rec):
        name = (rec.get("donor_name") or rec.get("contributor_name_fec") or rec.get("owner_name") or "").strip()
        if not name or "landa" not in name.lower():
            return False
        amt = rec.get("amount") or rec.get("total_contributed") or rec.get("contribution_receipt_amount") or 0
        try:
            return float(amt) >= 4_999_000  # 5M
        except (TypeError, ValueError):
            return False

    owners = data.get("owners") or []
    for o in owners:
        if has_landa_5m(o):
            return True, f"owners: {o.get('owner_name')} / {o.get('contributor_name_fec')} ${o.get('total_contributed')}"
    raw = data.get("raw_contributions") or []
    for r in raw:
        if has_landa_5m(r):
            return True, f"raw_contributions: {r.get('donor_name')} ${r.get('amount')}"
    all_c = data.get("all_contributions") or []
    for c in all_c:
        if has_landa_5m(c):
            return True, f"all_contributions: {c.get('donor_name')} ${c.get('amount')}"
    return False, None


def run_integration_test():
    from fec_api_client import FEC_API_KEY

    if not FEC_API_KEY or FEC_API_KEY == "YOUR_API_KEY_HERE":
        print("ERROR: Set FEC_API_KEY in donor/.env or environment.")
        return False, "FEC_API_KEY missing"

    # Import app after path setup so BASE_DIR and data paths resolve correctly
    from owner_donor_dashboard import app as owner_app

    client = owner_app.test_client()
    url = "/api/search/committee?q=C00892471"  # same as live when user selects "MAGA Inc." from autocomplete

    print("Internal check: MAGA Inc. committee search (same as live site)")
    print("  Endpoint: GET " + url)
    print("  Timeout: request must complete within {}s (gunicorn=120s)".format(REQUEST_TIMEOUT_SEC))
    print()

    start = time.perf_counter()
    response = None
    timeout_occurred = False

    def do_request():
        return client.get(url)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(do_request)
            try:
                response = future.result(timeout=REQUEST_TIMEOUT_SEC)
            except concurrent.futures.TimeoutError:
                return False, "REQUEST_TIMED_OUT"
    except Exception as e:
        return False, "request_failed: " + str(e)

    elapsed = time.perf_counter() - start
    print("  Elapsed: {:.1f}s".format(elapsed))

    if response.status_code != 200:
        try:
            body = response.get_json() or {}
            err = body.get("error") or response.get_data(as_text=True)
        except Exception:
            err = response.get_data(as_text=True)
        return False, "status {}: {}".format(response.status_code, err)

    try:
        data = response.get_json()
    except Exception as e:
        return False, "invalid_json: " + str(e)

    if not data:
        return False, "empty_response"

    committee = data.get("committee") or {}
    cid = (committee.get("id") or "").strip().upper()
    if cid != "C00892471":
        return False, "committee_id_mismatch: got {}".format(cid)

    found, details = _find_landa_in_response(data)
    if not found:
        return False, "Landa not in response (owners/raw_contributions/all_contributions)"

    print("  Committee: {} ({})".format(committee.get("name"), cid))
    print("  Landa: YES — {}".format(details))
    print("  OK: no timeout, 200, Landa included.")
    return True, None


def main():
    ok, err = run_integration_test()
    if ok:
        print()
        print("PASS: MAGA Inc. committee search would succeed on live site (no timeout, Landa returned).")
        return 0
    print()
    print("FAIL: " + (err or "unknown"))
    return 1


if __name__ == "__main__":
    sys.exit(main())
