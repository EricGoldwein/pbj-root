import re, urllib.request
h = urllib.request.urlopen("http://127.0.0.1:5055/geo/connecticut").read().decode()
idx = h.lower().find("regional comparison")
open(r"c:\Users\egold\PycharmProjects\pbj-root\_geo_snip.html","w",encoding="utf-8").write(h[idx:idx+8000])
# count rows in first table after regional comparison
chunk = h[idx:idx+12000]
m = re.search(r"<table.*?</table>", chunk, re.I|re.S)
if m:
    rows = re.findall(r"<tbody>.*?</tbody>", m.group(0), re.I|re.S)
    if rows:
        tr = len(re.findall(r"<tr", rows[0], re.I))
        print("regional_comparison_tbody_tr", tr)
    else:
        tr = len(re.findall(r"<tr", m.group(0), re.I)) - 1
        print("regional_comparison_tr_no_tbody", tr)
# county table?
idx2 = h.lower().find("county")
print("county_section_offset", idx2)
