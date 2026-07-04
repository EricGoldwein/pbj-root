import re, urllib.request
h = urllib.request.urlopen("http://127.0.0.1:5055/geo/connecticut").read().decode()
for m in re.finditer(r".{0,40}map.{0,40}", h, re.I):
    print(m.group(0).replace("\n"," "))
# facilities by region section
idx = h.lower().find("facilities by region")
chunk = h[idx:idx+5000]
tables = re.findall(r"<table.*?</table>", chunk, re.I|re.S)
print("tables_in_facilities_by_region", len(tables))
if tables:
    print("tr", len(re.findall(r"<tr", tables[0], re.I)))
