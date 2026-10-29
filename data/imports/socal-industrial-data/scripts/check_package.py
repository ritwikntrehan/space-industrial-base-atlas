#!/usr/bin/env python3
import csv,json,sys
from pathlib import Path
from collections import Counter
R=Path(__file__).resolve().parents[1]

def load(name):
    with (R/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
orgs=load('organizations.csv'); loc=load('locations.csv'); fac=load('facilities.csv'); cap=load('capabilities.csv')
rels=json.loads((R/'relationships.json').read_text()); manifest=json.loads((R/'source_manifest.json').read_text()); js=json.loads((R/'website/candidate_organizations.json').read_text()); audit=json.loads((R/'qa/summary.json').read_text())
assert len(orgs)==audit['total_unique_organizations']
ids={x['organization_id'] for x in orgs}; assert len(ids)==len(orgs)
assert len({x['facility_id'] for x in fac})==len(fac)
assert len({x['location_id'] for x in loc})==len(loc)
assert all(x['organization_id'] in ids for x in loc+fac+cap)
assert all(x['county'] for x in orgs)
assert all(x['location_precision']=='city_only' and x['facility_assertion']=='false' for x in loc)
assert all(x['source_url'].startswith('https://') for x in fac)
assert all(x['verification_status'] for x in orgs)
assert not any(o['space_participation']=='historical_2019_nasa_supplier' for o in orgs if o['publication_status']!='research_only')
assert not any(o['industry_role']=='out-of-scope-seed' for o in js)
assert all('historical-nasa-supplier-lead' not in o['industry_role'] for o in js)
assert len(manifest['sources'])>=15
assert all('source_id' in x and x['url'].startswith('https://') for x in manifest['sources'])
assert len(rels)==audit['relationships']
assert all(x['not_a_contract'] for x in rels)
assert sum(x['relation_type']=='historically_listed_on_nasa_supplier_map_2019' for x in rels)==111
assert sum(x['claim_type']=='official_facility_description' for x in cap)>=10
assert sum(x['verification_status'].startswith('official_') for x in fac)>=12
assert len({x['county'] for x in orgs})==7
print('PASS | organizations',len(orgs),'locations',len(loc),'facilities',len(fac),'capability_claims',len(cap),'links',len(rels),'website_candidates',len(js),'sources',len(manifest['sources']))

# Second-pass release validation
shortlist=json.loads((R/'website/demo_250_organizations.json').read_text(encoding='utf8'))
assert len(shortlist)==250
assert len({r['id'] for r in shortlist})==250
assert len({r['county'] for r in shortlist})==7
assert not any(r['industry_role'] in ('historical-nasa-supplier-lead','out-of-scope-seed') for r in shortlist)
assert all(r['source_urls'] and r['publication_review_required'] for r in shortlist)
assert all(r['is_active_supplier_verified'] is False and r['production_capacity_verified'] is False for r in shortlist)
assert all(r['evidence_status']!='historical_primary_source_not_current' for r in shortlist)
assert len(fac)>=20
assert len(manifest['sources'])>=22
assert (R/'source/second_pass_manufacturers_2026.psv').exists()
print('PASS | 250 evidence-labeled launch candidates, all seven counties, no historical-only records')
