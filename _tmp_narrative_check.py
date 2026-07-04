import re, urllib.request
for path in ("/state/fl", "/state/usa"):
    html = urllib.request.urlopen("http://127.0.0.1:10000" + path, timeout=90).read().decode("utf-8", "replace")
    m = re.search(r'class="pbj-takeaway-narrative"[^>]*>(.*?)</p>', html, re.S)
    if m:
        text = re.sub(r"<[^>]+>", "", m.group(1))
        text = " ".join(text.split())
        print(path + ":", text[:320])
    else:
        print(path + ": narrative not found")
