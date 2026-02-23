"""
Replicate Render for MAGA Inc. committee search.

- Uses the SAME app and URL as the site: main app (app.py) + GET /owners/api/search/committee?q=C00892471
  so the request goes through owner_api_proxy and lazy-loads owner_donor_dashboard (same as Render).
- Enforces Render's gunicorn worker timeout: request must finish in 90s (gunicorn_config.py has timeout=120;
  we use 90s so if we pass locally we have margin on slower Render).
- Requires FEC_API_KEY. Uses real FEC API and full owner DB.

Run from repo root:
  python -m donor.test_maga_committee_integration

Pass = 200, completed in <90s, Landa in response.
Fail = timeout (>90s), 500, or Landa missing.
"""
import concurrent.futures
import os
import sys
import time
from pathlib import Path

# Repo root and donor on path so app.py and donor imports resolve
donor_dir = Path(__file__).resolve().parent
repo_root = donor_dir.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))
if str(donor_dir) not in sys.path:
    sys.path.insert(0, str(donor_dir))

# Match Render: read gunicorn timeout from gunicorn_config.py; fail if request exceeds (timeout - 30)s
try:
    import importlib.util
    _spec = importlib.util.spec_from_file_location("gunicorn_config", repo_root / "gunicorn_config.py")
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    GUNICORN_TIMEOUT = int(getattr(_mod, "timeout", 120))
except Exception:
    GUNICORN_TIMEOUT = 120
REQUEST_TIMEOUT_SEC = max(60, GUNICORN_TIMEOUT - 30)
if os.environ.get("MAGA_TEST_TIMEOUT"):
    try:
        REQUEST_TIMEOUT_SEC = int(os.environ["MAGA_TEST_TIMEOUT"])
    except ValueError:
        pass


def _find_landa_in_response(data):
    """Return (found, details). Check owners, raw_contributions, all_contributions for LANDA and $5M."""
    def has_landa_5m(rec):
        name = (rec.get("donor_name") or rec.get("contributor_name_fec") or rec.get("owner_name") or "").strip()
        if not name or "landa" not in name.lower():
            return False
        amt = rec.get("amount") or rec.get("total_contributed") or rec.get("contribution_receipt_amount") or 0
        try:
            return float(amt) >= 4_999_000
        except (TypeError, ValueError):
            return False

    for o in (data.get("owners") or []):
        if has_landa_5m(o):
            return True, "owners: {} / {} ${}".format(o.get("owner_name"), o.get("contributor_name_fec"), o.get("total_contributed"))
    for r in (data.get("raw_contributions") or []):
        if has_landa_5m(r):
            return True, "raw_contributions: {} ${}".format(r.get("donor_name"), r.get("amount"))
    for c in (data.get("all_contributions") or []):
        if has_landa_5m(c):
            return True, "all_contributions: {} ${}".format(c.get("donor_name"), c.get("amount"))
    return False, None


def run_integration_test():
    from fec_api_client import FEC_API_KEY

    if not FEC_API_KEY or FEC_API_KEY == "YOUR_API_KEY_HERE":
        print("ERROR: Set FEC_API_KEY in donor/.env or environment.")
        return False, "FEC_API_KEY missing"

    # Main app (app.py) so request goes through /owners/api/... proxy and lazy-loads owner_donor_dashboard (same as Render)
    from app import app as main_app

    client = main_app.test_client()
    url = "/owners/api/search/committee?q=C00892471"

    print("Replicating Render: MAGA Inc. committee search")
    print("  App: main app (app.py) -> /owners/api/... proxy -> owner_donor_dashboard (same as site)")
    print("  URL: GET {}".format(url))
    print("  Limit: request must finish in {}s (Render gunicorn timeout={}s)".format(REQUEST_TIMEOUT_SEC, GUNICORN_TIMEOUT))
    print()

    start = time.perf_counter()
    response = None

    def do_request():
        return client.get(url)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(do_request)
            try:
                response = future.result(timeout=REQUEST_TIMEOUT_SEC)
            except concurrent.futures.TimeoutError:
                return False, "REQUEST_TIMED_OUT (>{}s - would hit Render worker timeout)".format(REQUEST_TIMEOUT_SEC)
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
    print("  Landa: YES - {}".format(details))
    print("  OK: completed in {:.1f}s (<{}s), 200, Landa included.".format(elapsed, REQUEST_TIMEOUT_SEC))
    return True, None


def main():
    ok, err = run_integration_test()
    if ok:
        print()
        print("PASS: Same request would succeed on Render (under timeout, 200, Landa returned).")
        return 0
    print()
    print("FAIL: " + (err or "unknown"))
    return 1


if __name__ == "__main__":
    sys.exit(main())
