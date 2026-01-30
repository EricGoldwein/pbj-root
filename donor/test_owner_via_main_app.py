"""
Test get_owner_details via main app proxy (same URL the browser uses).
Run from project root: python donor/test_owner_via_main_app.py
"""
import sys
import os
from pathlib import Path

# Project root
root = Path(__file__).resolve().parent.parent
os.chdir(root)
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "donor"))

def main():
    # Import main app (this loads owner dashboard and proxy routes)
    import app
    client = app.app.test_client()

    # Same URL the frontend uses: /owners/api/owner/<encoded name>
    url = "/owners/api/owner/SABER%20PA%20HOLDINGS%2C%20LLC"
    print(f"GET {url}")
    r = client.get(url)
    print(f"Status: {r.status_code}")

    if r.status_code != 200:
        print("Response:", r.get_data(as_text=True)[:800])
        return 1

    data = r.get_json()
    if not data:
        print("Response JSON is empty")
        return 1
    if data.get("error"):
        print("Error:", data["error"])
        return 1

    facilities = data.get("facilities", [])
    print(f"owner_name: {data.get('owner_name')}")
    print(f"facilities count: {len(facilities)}")
    if len(facilities) == 0:
        print("FAIL: facilities list is empty when called via main app proxy")
        return 1
    print("OK: Proxy returns facilities correctly")
    return 0

if __name__ == "__main__":
    sys.exit(main())
