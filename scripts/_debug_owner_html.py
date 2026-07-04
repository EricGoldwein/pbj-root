import re
from ownership.owner_profile import load_owner_profile
from ownership.owner_profile_html import render_owner_profile_body

p = load_owner_profile("4284019316")
print("kind", p.get("profile_kind"), "is_chow_only", p.get("is_chow_only"))
print("control_parties", len(p.get("control_parties") or []))
print("facilities", len(p.get("facilities") or []))
print("chow_tx", len(p.get("chow_transactions") or []))
body, *_ = render_owner_profile_body(p)
print("Ownership transactions count", body.count("Ownership transactions"))
print("owner-collapsible--txns count", body.count("owner-collapsible--txns"))
print("in CMS data count", body.count("in CMS data"))
for m in re.finditer(r"<summary[^>]*>([^<]+)", body):
    t = m.group(1)
    if "wnership" in t or "CHOW" in t or "change" in t.lower():
        print("summary:", t[:120])
for m in re.finditer(r'<h2 class="section-header">([^<]+)', body):
    print("h2:", m.group(1)[:120])
