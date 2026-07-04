import re
p = r"c:\Users\egold\PycharmProjects\pbj-root\_geo_acceptance_probe.py"
t = open(p, encoding="utf-8").read()
i = t.find("def selected_quarter")
j = t.find("def count_region_rows")
fix = """def selected_quarter(html):
    m = re.search(r'<option[^>]*selected[^>]*value=\"([^\"]+)\"', html, re.I)
    if m:
        return m.group(1)
    m = re.search(r'<option[^>]*value=\"([^\"]+)\"[^>]*selected', html, re.I)
    if m:
        return m.group(1)
    return None

"""
open(p, "w", encoding="utf-8").write(t[:i] + fix + t[j:])
