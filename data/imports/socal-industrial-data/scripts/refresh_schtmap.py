#!/usr/bin/env python3
"""Optional fetch of complete user-owned SCHTMap source JSON; no secrets needed.

Not required to rebuild included compact snapshot. Check upstream status and diff
before integrating new fields. Deliberately does NOT overwrite the curated tables.
"""
import json, urllib.request, hashlib
from pathlib import Path
URL='https://raw.githubusercontent.com/ritwikntrehan/oc-hard-tech-landscape/main/data/companies.min.json'
BASE=Path(__file__).resolve().parents[1]
DEST=BASE/'source/schtmap_full_external.json'
request=urllib.request.Request(URL,headers={'User-Agent':'SoCalIndustrialAtlasDataResearch/1.0'})
with urllib.request.urlopen(request,timeout=25) as resp: raw=resp.read()
parsed=json.loads(raw)
assert isinstance(parsed,list) and len(parsed)>=100, 'Unexpected upstream SCHTMap payload'
assert all('name' in x and 'id' in x for x in parsed)
DEST.write_bytes(raw)
print('Saved',DEST,'records',len(parsed),'sha256',hashlib.sha256(raw).hexdigest())
print('Review provenance/licenses before importing fields or adding to Git.')
