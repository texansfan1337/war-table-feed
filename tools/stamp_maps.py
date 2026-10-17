#!/usr/bin/env python3
"""Stamp each map in index.html's MAPS list with a content hash (?v=...) so browsers
and the GitHub Pages cache always fetch the current map. Run after changing any file in maps/."""
import hashlib, pathlib, re
root = pathlib.Path(__file__).resolve().parent.parent
idx = root / "index.html"; s = idx.read_text(encoding="utf-8")
def stamp(m):
    path = m.group(1)
    h = hashlib.sha256((root / path).read_bytes()).hexdigest()[:10]
    return f'path: "{path}?v={h}"'
s2 = re.sub(r'path: "(maps/[^"?]+)(?:\?v=[0-9a-f]+)?"', stamp, s)
idx.write_text(s2, encoding="utf-8"); print("stamped" if s2 != s else "unchanged")
