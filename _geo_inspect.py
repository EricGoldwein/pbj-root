import re, urllib.request
h = urllib.request.urlopen("http://127.0.0.1:5055/geo/connecticut").read().decode()
for pat in ["geo-region", "planning-region", "region-row", "pbj-geo"]:
    print(pat, h.lower().count(pat))
# tables with caption or heading
for m in re.finditer(r"<h2[^>]*>([^<]+)</h2>", h, re.I):
    print("H2:", m.group(1).strip())
for m in re.finditer(r"<table[^>]*id=\"([^\"]+)\"", h, re.I):
    tid = m.group(1)
    start = m.start()
    chunk = h[start:start+8000]
    tr = len(re.findall(r"<tr\b", chunk)) - 1
    print("TABLE", tid, "approx_data_rows", max(0, tr))
