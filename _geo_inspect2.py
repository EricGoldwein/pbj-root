import re, urllib.request
h = urllib.request.urlopen("http://127.0.0.1:5055/geo/connecticut").read().decode()
idx = h.lower().find("regional comparison")
print(h[idx:idx+6000])
