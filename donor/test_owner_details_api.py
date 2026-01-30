"""
Test get_owner_details API for SABER PA HOLDINGS, LLC - verify facilities list is returned.
Run from project root: python donor/test_owner_details_api.py
"""
import sys
from pathlib import Path

# Project root
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "donor"))

def main():
    from owner_donor_dashboard import app, load_data

    print("Loading data...")
    load_data()
    print("Data loaded. Calling GET /api/owner/SABER%20PA%20HOLDINGS%2C%20LLC ...")

    with app.test_client() as client:
        # Same path the main app proxy uses: /api/{api_path} -> /api/owner/SABER%20PA%20HOLDINGS%2C%20LLC
        r = client.get("/api/owner/SABER%20PA%20HOLDINGS%2C%20LLC")
        print(f"Status: {r.status_code}")
        if r.status_code != 200:
            print(f"Response: {r.get_data(as_text=True)[:500]}")
            return 1

        data = r.get_json()
        if not data:
            print("Response JSON is empty")
            return 1
        if data.get("error"):
            print(f"Error: {data['error']}")
            return 1

        facilities = data.get("facilities", [])
        print(f"owner_name: {data.get('owner_name')}")
        print(f"facilities count: {len(facilities)}")
        if facilities:
            print(f"First facility keys: {list(facilities[0].keys())}")
            print(f"First facility name: {facilities[0].get('name') or facilities[0].get('legal_business_name')}")
        else:
            print("facilities list is EMPTY - this is the bug")
            return 1
    print("OK - facilities list is populated")
    return 0

if __name__ == "__main__":
    sys.exit(main())
