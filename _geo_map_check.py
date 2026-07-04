import re, urllib.request
h = urllib.request.urlopen("http://127.0.0.1:5055/geo/connecticut").read().decode()
for kw in ["map", "choropleth", "topojson", "d3", "geojson", "canvas", "svg"]:
    print(kw, len(re.findall(kw, h, re.I)))
for m in re.finditer(r'id="([^"]*map[^"]*)"', h, re.I):
    print("id", m.group(1))
