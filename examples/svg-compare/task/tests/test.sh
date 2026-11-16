#!/bin/bash
mkdir -p /logs/artifacts && cp /app/scene.svg /logs/verifier/scene.svg 2>/dev/null; cp /app/scene.svg /logs/artifacts/scene.svg 2>/dev/null
python3 - <<'PY'
import os, re, xml.etree.ElementTree as ET
p = "/app/scene.svg"; ok = True; notes = []
if not os.path.exists(p):
    ok = False; notes.append("missing /app/scene.svg")
else:
    size = os.path.getsize(p); notes.append(f"size={size}")
    raw = open(p, encoding="utf-8", errors="replace").read()
    try:
        root = ET.fromstring(raw)
        if not root.tag.endswith("svg"): ok = False; notes.append("root is not <svg>")
    except ET.ParseError as e:
        ok = False; notes.append(f"invalid XML: {e}")
    if size > 5_000_000: ok = False; notes.append("too large")
    if re.search(r"<\s*(script|image)\b", raw, re.I): ok = False; notes.append("has script/image")
    if re.search(r"(href|src)\s*=\s*[\"'](https?:|data:image)", raw, re.I): ok = False; notes.append("external/raster ref")
    notes.append(f"elements={raw.count('<')}")
print("; ".join(notes))
open("/logs/verifier/reward.txt", "w").write("1" if ok else "0")
PY
