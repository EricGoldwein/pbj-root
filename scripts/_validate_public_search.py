#!/usr/bin/env python3
"""Quick smoke validation for global header search wiring."""
from app import app

client = app.test_client()
checks = [
    ('/', 'homepage'),
    ('/provider/015009', 'provider'),
    ('/state/new-york', 'state'),
    ('/entity/237', 'entity'),
    ('/owners/ny', 'ownership'),
    ('/public-search.js', 'js'),
]
for path, kind in checks:
    resp = client.get(path)
    data = resp.data
    ok_ctx = b'pbj-route-context' in data if kind != 'js' else True
    ok_js = b'PBJ320_initPublicSearch' in data if kind == 'js' else True
    ok_nav = b'nav-menu' in data or b'nav-links' in data if kind != 'js' else True
    ok_sticky = b'.navbar { position: relative; }' not in data if kind != 'js' else True
    ok_scroll = b'scroll-margin-top: 5rem' in data if kind in ('provider', 'state', 'entity', 'ownership') else True
    print(
        path,
        resp.status_code,
        'ctx' if ok_ctx else 'NO_CTX',
        'nav' if ok_nav else 'NO_NAV',
        'sticky' if ok_sticky else 'STICKY_BAD',
        'scroll' if ok_scroll else 'NO_SCROLL',
        'js' if ok_js else 'NO_JS',
    )
