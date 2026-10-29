#!/usr/bin/env python3
"""Build evidence-separated SoCal industrial discovery tables from packaged source extracts.

No network calls; deterministic, stdlib-only. Do not treat candidate or archived
NASA supplier locations as active facilities. Site publication requires review.
"""
import csv, json, re, hashlib
from pathlib import Path
from collections import Counter, defaultdict
from datetime import date

ROOT=Path(__file__).resolve().parents[1]
AS_OF='2026-10-29'
NASA_URL='https://www3.nasa.gov/specials/ESDSuppliersMap/'
SCHT_URL='https://github.com/ritwikntrehan/oc-hard-tech-landscape/blob/main/data/companies.min.json'
DATA_URL='https://raw.githubusercontent.com/ritwikntrehan/oc-hard-tech-landscape/main/data/companies.min.json'

COUNTIES={
'Los Angeles':{'Los Angeles','El Segundo','Long Beach','Hawthorne','Torrance','Redondo Beach','Gardena','Industry','Huntington Park','Monrovia','North Hollywood','Pasadena','Palmdale','Santa Clarita','Santa Fe Springs','South El Monte','South Gate','Sylmar','Valencia','Westchester','Westlake Village','Woodland Hills','Glendale','La Cañada Flintridge','Burbank','Bell Gardens','Cudahy','Canoga Park','San Fernando','Downey','Inglewood'},
'Orange':{'Orange','Irvine','Huntington Beach','Garden Grove','Santa Ana','Los Alamitos','Seal Beach','Lake Forest','Newport Beach','Laguna Hills','Laguna Niguel','Foothill Ranch','Brea','Costa Mesa','Aliso Viejo','Cypress','Tustin','Anaheim','Fountain Valley','Fullerton','Buena Park'},
'San Diego':{'San Diego','El Cajon'},
'Ventura':{'Camarillo','Simi Valley','Thousand Oaks'},
'Riverside':{'Murrieta','Corona'},
'San Bernardino':{'Ontario','Upland','Fontana'},
'Santa Barbara':{'Santa Barbara','Vandenberg SFB'},
}


def county_of(city):
    for county,cities in COUNTIES.items():
        if city in cities:return county
    return ''

def norm(n):
    n=n.casefold().replace('&','and')
    n=re.sub(r'\b(incorporated|inc|corporation|corp|llc|ltd|company|co)\b','',n)
    return re.sub('[^a-z0-9]','',n)

def slug(s):
    return re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-')

def read_psv(path,n):
    lines=[]
    for i,line in enumerate(path.read_text(encoding='utf8').splitlines(),1):
        if not line.strip():continue
        cells=line.split('|')
        if len(cells)!=n:raise ValueError(f'{path.name}:{i}: {len(cells)} fields expected {n}')
        lines.append((i,cells))
    return lines

ORGS={}; LOCATIONS=[]; RELS=[]; provenance=defaultdict(list); duplicates=[]


def add_org(name,city,county,website,tier,sector,capabilities,source_id,source_url,record_status,verification,extract_ref,prior_id='',include_default=False):
    key=norm(name)
    if not key:raise ValueError('empty name')
    if county and county not in COUNTIES:raise ValueError(f'unknown county {county}')
    if not county and city: county=county_of(city)
    if not county and city:raise ValueError(f'missing county for {name} ({city})')
    if key in ORGS:
        org=ORGS[key]; duplicates.append({'incoming':name,'existing':org['name'],'source_id':source_id,'type':'name-normalized'})
        # multiple locations are preserved below; never merge facilities
        if (org['publication_status']=='research_only' and include_default) or verification=='official_current':
            org.update({k:v for k,v in dict(website=website,ecosystem_tier=tier,sector=sector,capability_summary=capabilities,verification_status=verification,publication_status='candidate_for_publication',space_participation=record_status).items() if v})
        if verification=='official_current' and city:
            org['city']=city
            org['county']=county
        org['source_ids']=sorted(set(org['source_ids']+[source_id]))
        org['source_urls']=sorted(set(org['source_urls']+[source_url]))
        org['source_extract_refs'].append(extract_ref)
    else:
        oid=prior_id if prior_id else 'SOCAL-'+slug(name)
        org=dict(organization_id=oid,name=name,city=city,county=county,state='CA',website=website,ecosystem_tier=tier,sector=sector,capability_summary=capabilities,space_participation=record_status,verification_status=verification,publication_status=('candidate_for_publication' if include_default else 'research_only'),location_precision='city_only',source_ids=[source_id],source_urls=[source_url],source_extract_refs=[extract_ref],research_date=AS_OF,last_source_review=AS_OF,actual_capacity='',qualification='',supplier_customer_links='',notes='')
        ORGS[key]=org
    org=ORGS[key]
    if record_status=='historical_2019_nasa_supplier':
        org['notes']='NASA exploration program supplier location listed in 2019; current operations, identity, city and space program status require re-verification.' if not org['notes'] else org['notes']
    if city and not any(x['organization_id']==org['organization_id'] and x['city']==city for x in LOCATIONS):
        lid=f"{org['organization_id']}:{slug(city)}"
        LOCATIONS.append(dict(location_id=lid,organization_id=org['organization_id'],city=city,county=county,location_precision='city_only',facility_assertion='false',latitude='',longitude='',source_id=source_id,source_url=source_url,location_evidence_status=('historical_2019_city' if record_status.startswith('historical') else 'reported_city'),as_of=('2019-01' if record_status.startswith('historical') else AS_OF)))
    provenance[org['organization_id']].append({'source_id':source_id,'source_url':source_url,'extract_ref':extract_ref,'location':city})
    return org

# SCHTMap 100: preserve whole hard-tech seed, but non-space entries are not published as space suppliers.
for lineno, (eid,name,city,web,group,caps) in read_psv(ROOT/'source/schtmap_100_extract.psv',6):
    if group=='Aerospace & Space': tier='direct-or-aerospace'
    elif group in ('Advanced Manufacturing','Materials & Composites','Semiconductors & Electronics','Defense','Industrial Systems'):tier='adjacent-industrial-candidate'
    else:tier='out-of-scope-seed'
    include=(tier!='out-of-scope-seed')
    add_org(name,city,'Orange',web,tier,group,caps,'schtmap_2026',SCHT_URL,'source_curated_industry_classification','curated_2026_source_snapshot',f'source/schtmap_100_extract.psv:{lineno}',eid,include)

# NASA 2019: supplier name+city are historical program evidence, NOT an active space supplier credential.
for lineno,(name,city) in read_psv(ROOT/'source/nasa_2019_supplier_leads.psv',2):
    add_org(name,city,'','','historical-nasa-supplier-lead','2019 NASA Exploration supplier map','', 'nasa_esd_2019',NASA_URL,'historical_2019_nasa_supplier','historical_primary_source_not_current',f'source/nasa_2019_supplier_leads.psv:{lineno}',include_default=False)

# Current secondary index facts; capability tags are short analyst paraphrases, not independent official qualification.
for lineno,(name,city,county,tier,caps,url,sourceid) in read_psv(ROOT/'source/current_discovery.psv',7):
    add_org(name,city,county,'',tier,'2026 regional industry index',caps,sourceid,url,'third_party_recent_index','secondary_index_requires_primary_verification',f'source/current_discovery.psv:{lineno}',include_default=True)

# Second-pass 2026 aerospace manufacturing directories, independently described in structured facts.
# These are DIRECTORY-REPORTED aerospace suppliers, NOT confirmed space suppliers.
# We only use concise names, cities and process tags, not copyrighted profile descriptions.
for filename,sourceid in [('second_pass_manufacturers_2026.psv','noramark_aerospace_oct2026'),('second_pass_sector_2026.psv','regional_sector_secondpass_oct2026')]:
    for lineno,(name,city,county,tier,caps,url) in read_psv(ROOT/'source'/filename,6):
        org=add_org(name,city,county,'',tier,'2026 public industrial directory or regional sector list',caps,sourceid,url,
                    'directory_reported_aerospace_or_space_relevance','secondary_index_requires_primary_verification',
                    f'source/{filename}:{lineno}',include_default=True)
        if sourceid=='noramark_aerospace_oct2026':
            org['notes']=(org['notes']+' | ' if org['notes'] else '')+'Noramark classifies this business in aerospace; space hardware participation, current facility and acceptance criteria are NOT verified.'

# Official company and location pages supplement secondary-directory discovery leads.
for lineno,(name,city,county,tier,caps,website,src) in read_psv(ROOT/'source/official_current_2026.psv',7):
    add_org(name,city,county,website,tier,'Official space/industrial company site',caps,'official_company_2026',src,'official_company_site','official_current',f'source/official_current_2026.psv:{lineno}',include_default=True)

# Individually checked company-operated sites and current product descriptions.
for lineno,(name,city,county,tier,caps,website,src) in read_psv(ROOT/'source/second_pass_official_companies_2026.psv',7):
    add_org(name,city,county,website,tier,'Official 2026 industrial site and product descriptions',caps,
            'official_primary_secondpass_2026',src,'official_company_site','official_current',
            f'source/second_pass_official_companies_2026.psv:{lineno}',include_default=True)

# Specific source-backed infrastructure already used in the live Atlas.
FACILITIES=[
 dict(facility_id='jpl-25ft',organization_name='Jet Propulsion Laboratory',name='NASA JPL 25-Foot Space Simulator',city='La Cañada Flintridge',county='Los Angeles',latitude='34.2014',longitude='-118.1718',location_precision='campus_approximate_not_test_chamber',facility_type='environmental-test',capabilities='Thermal-vacuum testing; Environmental qualification facilities',verification_status='official_facility_description',customer_access_status='not_verified',capacity_status='unknown',source_url='https://www.jpl.nasa.gov/images/pia26708-voyager-technologies-griffin-1-completes-environmental-testing-at-nasa-jpl/',date_verified='2026-10-29'),
 dict(facility_id='jpl-ep-lab',organization_name='Jet Propulsion Laboratory',name='NASA JPL Electric Propulsion Laboratory',city='La Cañada Flintridge',county='Los Angeles',latitude='34.2014',longitude='-118.1718',location_precision='campus_approximate_not_lab_building',facility_type='propulsion-test',capabilities='Electric propulsion testing; Vacuum testing',verification_status='official_facility_description',customer_access_status='not_verified',capacity_status='unknown',source_url='https://www.jpl.nasa.gov/go/epl/capabilities/facilities/',date_verified='2026-10-29'),
 dict(facility_id='vandenberg-sld30',organization_name='U.S. Space Force / Space Launch Delta 30',name='Vandenberg Space Force Base / Space Launch Delta 30',city='Vandenberg SFB',county='Santa Barbara',latitude='34.742',longitude='-120.572',location_precision='base_centroid_not_launch_pad',facility_type='launch-infrastructure',capabilities='Launch range; Launch-site operations',verification_status='official_installation_description',customer_access_status='not_verified',capacity_status='unknown',source_url='https://www.ssc.spaceforce.mil/Program-Offices/SPACE-ACCESS',date_verified='2026-10-29')
]
for lineno,(fid,oname,name,city,county,address,precision,caps,src,reviewed) in read_psv(ROOT/'source/official_facilities_2026.psv',10):
    status=('official_announced_facility_operations_unconfirmed' if fid=='trueanomaly-long-beach' else 'official_company_facility_description')
    FACILITIES.append(dict(facility_id=fid,organization_name=oname,name=name,city=city,county=county,latitude='',longitude='',street_address=address,location_precision=precision,facility_type='industrial-site',capabilities=caps,verification_status=status,customer_access_status='not_verified',capacity_status='unknown',source_url=src,date_verified=reviewed))

add_org('U.S. Space Force / Space Launch Delta 30','Vandenberg SFB','Santa Barbara','','ecosystem','Launch infrastructure','Launch range; Launch site operations','spaceforce_sld30_2026',FACILITIES[-1]['source_url'],'official_public_site','official_current', 'source official referenced',include_default=True)

# Historical listing links do not establish a continuing contract or active supplier status.
for org in ORGS.values():
    if 'nasa_esd_2019' in org['source_ids']:
        RELS.append(dict(relation_id=f"historical-nasa-{org['organization_id']}",from_id=org['organization_id'],to_id='NASA-2019-Exploration-Systems-Supplier-Map',relation_type='historically_listed_on_nasa_supplier_map_2019',evidence_status='historical_as_of_2019_only',source_url=NASA_URL,valid_as_of='2019-01',not_a_contract=True))

# Long-form capability claims. Source semantics retained.
CAPS=[]
for org in ORGS.values():
    for cap in dict.fromkeys(x.strip() for x in org['capability_summary'].split(';') if x.strip()):
        capid='cap-'+slug(cap)
        related=dict(organization_id=org['organization_id'],capability_id=capid,capability_label=cap,claim_type=('official_company_description' if org['verification_status']=='official_current' else 'third_party_index_analyst_tag' if org['verification_status'].startswith('secondary') else 'curated_company_description'),evidence_status=org['verification_status'],source_url=next((p['source_url'] for p in reversed(provenance[org['organization_id']]) if p['source_id'] in ('official_primary_secondpass_2026','official_company_2026')),org['source_urls'][0] if org['source_urls'] else ''),data_as_of=AS_OF,space_qualification='unknown',facility_specific='no')
        CAPS.append(related)
        RELS.append(dict(relation_id=f"rel-{org['organization_id']}-{capid}",from_id=org['organization_id'],to_id=capid,relation_type='organization_has_reported_capability',evidence_status=related['claim_type'],source_url=related['source_url'],valid_as_of=AS_OF,not_a_contract=True))

for lineno,(fid,oname,name,city,county,address,precision,caps,src,reviewed) in read_psv(ROOT/'source/second_pass_official_facilities_2026.psv',10):
    FACILITIES.append(dict(facility_id=fid,organization_name=oname,name=name,city=city,county=county,
         latitude='',longitude='',street_address=address,location_precision=precision,facility_type='industrial-site',
         capabilities=caps,verification_status='official_company_facility_description',customer_access_status='not_verified',
         capacity_status='unknown',source_url=src,date_verified=reviewed))

for f in FACILITIES:
    o=ORGS.get(norm(f['organization_name']))
    if not o:
        o=add_org(f['organization_name'],f['city'],f['county'],'','ecosystem','Space infrastructure','','facility_baseline',f['source_url'],'official_public_site','official_current','facility source',include_default=True)
    f['organization_id']=o['organization_id']
    RELS.append(dict(relation_id=f"operates-{f['facility_id']}",from_id=o['organization_id'],to_id=f['facility_id'],relation_type='organization_operates_or_controls_facility',evidence_status='official_facility_description',source_url=f['source_url'],valid_as_of=AS_OF,not_a_contract=True))
    for cap in f['capabilities'].split(';'):
        cap=cap.strip(); rel=dict(relation_id=f"facility-{f['facility_id']}-cap-{slug(cap)}",from_id=f['facility_id'],to_id='cap-'+slug(cap),relation_type='facility_has_documented_capability',evidence_status='official_facility_description',source_url=f['source_url'],valid_as_of=AS_OF,not_a_contract=True)
        RELS.append(rel)
        CAPS.append(dict(organization_id=o['organization_id'],capability_id='cap-'+slug(cap),capability_label=cap,claim_type='official_facility_description',evidence_status='official_facility_description',source_url=f['source_url'],data_as_of=AS_OF,space_qualification='unknown',facility_specific='yes'))

# CSV and JSON, reproducible and deterministic.
def write_csv(path,records,fields=None):
    path.parent.mkdir(parents=True,exist_ok=True)
    fields=fields or list(dict.fromkeys(k for record in records for k in record))
    with path.open('w',newline='',encoding='utf-8-sig') as io:
        writer=csv.DictWriter(io,fieldnames=fields,extrasaction='ignore');writer.writeheader()
        for r in records:
            rr={k:(' | '.join(v) if isinstance(v,list) else v) for k,v in r.items()}
            writer.writerow(rr)

orgs=sorted(ORGS.values(),key=lambda x:x['name'].casefold())
write_csv(ROOT/'organizations.csv',orgs)
write_csv(ROOT/'locations.csv',sorted(LOCATIONS,key=lambda x:x['organization_id']))
write_csv(ROOT/'facilities.csv',FACILITIES)
write_csv(ROOT/'capabilities.csv',sorted(CAPS,key=lambda x:(x['organization_id'],x['capability_id'])))
(ROOT/'relationships.json').write_text(json.dumps(RELS,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
(ROOT/'canonical/organizations.json').write_text(json.dumps(orgs,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
(ROOT/'canonical/evidence_index.json').write_text(json.dumps(dict(provenance),indent=2,ensure_ascii=False)+'\n',encoding='utf8')

# For website use only reviewed/recent, relevant candidates. Historic NASA records excluded.
website_orgs=[{'id':r['organization_id'],'name':r['name'],'city':r['city'],'county':r['county'],'industry_role':r['ecosystem_tier'],'capabilities':[x.strip() for x in r['capability_summary'].split(';') if x.strip()],'website':r['website'],'source_urls':r['source_urls'],'evidence_status':r['verification_status'],'location_precision':'city_only'} for r in orgs if r['publication_status']=='candidate_for_publication' and r['ecosystem_tier']!='out-of-scope-seed']
(ROOT/'website/candidate_organizations.json').write_text(json.dumps(website_orgs,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf8')
(ROOT/'website/verified_facilities.json').write_text(json.dumps(FACILITIES,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf8')
# Curated release shortlist: exactly 250 relevant records, not 250 verified space vendors.
# Exclude generic adjacent technologies for the first demo; retain all 305 in the
# candidate export and all historic/out-of-scope records in research tables.
core_tiers={'direct-space','direct-or-aerospace','industrial-supply-base','ecosystem'}
# Broad hard-tech capabilities are only included with a meaningful space/aerospace
# or build-chain relevance: an electronics/composites/precision supplier can
# matter even when it has no published flight heritage.
strategic_adjacent={
 'ADDMAN Polymer','Airtech International','Anduril Industries','Great Western Grinding',
 'Ibis Industries','Intellian Technologies','Layup Parts','RAVE Manufacturing',
 'Regal Technology Partners','TTM Technologies','Mercury Systems','Menlo Micro',
 'AONDevices','Mobix Labs','InPlay Technologies','Litrinium','Movandi',
 'Lantronix','Scientific Applications & Research Associates (SARA)',
 'Syndicus USA / Syndicus Aerospace','Aevex Aerospace','General Atomics',
 'Dart Aerospace','AhnTech','Syntiant','Mach Industries','Airborne Systems North America of CA',
 'Design West Technologies','FieldAI','Acceliot','indie Semiconductor',
 'Neon Aero','Auron Solutions','Newlight Technologies','Solid Energies',
 'Applied Composites','GKN Aerospace','ABB Space Division'
}
core=[x for x in website_orgs if x['industry_role'] in core_tiers or x['name'] in strategic_adjacent]
assert len(core)>=250, f'not enough currently sourced candidates: {len(core)}'
priority_words={'machining','aerospace','satellite','spacecraft','launch','composite','testing','calibration','qualif','fabrication','welding','grinding','plating','anodizing','inspection','electronics','pcb','rf','avionics','propulsion','rocket','valves','connectors','harness','gears','casting','material','heat treating','laser','metal','manufacturing','vibration','precision','cryogenic','power','sensor','wire','additive'}
def relevance(o):
    caps=' '.join(o['capabilities']).lower()
    role=o['industry_role']
    base={'direct-space':120,'direct-or-aerospace':112,'ecosystem':104,'industrial-supply-base':70,'adjacent-industrial-candidate':98,'adjacent-industrial':94}[role]
    src=20 if o['evidence_status']=='official_current' else 10 if o['evidence_status']=='curated_2026_source_snapshot' else 0
    terms=sum(1 for w in priority_words if w in caps)
    # Preserve broad manufacturing and geographically underserved regions when comparable.
    county=8 if o['county'] in ('San Diego','Ventura','Riverside','San Bernardino','Santa Barbara') else 0
    return base+src+min(terms,8)*3+county
shortlist=sorted(core,key=lambda o:(-relevance(o),o['name'].casefold()))[:250]
for o in shortlist:
    o['atlas_display_tier']=('documented_space_activity_or_aerospace_directory' if o['industry_role'] in ('direct-space','direct-or-aerospace') else
                             'regional_infrastructure_or_ecosystem' if o['industry_role']=='ecosystem' else 'adjacent_capability_candidate' if o['industry_role'] in ('adjacent-industrial','adjacent-industrial-candidate') else 'directory_reported_industrial_candidate')
    o['is_active_supplier_verified']=False
    o['production_capacity_verified']=False
    o['spacetech_qualification_verified']=False
    o['publication_review_required']=True
(ROOT/'website/demo_250_organizations.json').write_text(json.dumps(shortlist,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf8')
write_csv(ROOT/'website/demo_250_organizations.csv',shortlist)


COUNTS=Counter(r['ecosystem_tier'] for r in orgs)
SOURCES=Counter(s for org in orgs for s in org['source_ids'])
COUNTY_CT=Counter(r['county'] for r in orgs)
summary={'as_of':AS_OF,'total_unique_organizations':len(orgs),'locations_city_labels':len(LOCATIONS),'individually_evidenced_facilities':len(FACILITIES),'capability_claims':len(CAPS),'relationships':len(RELS),'by_tier':dict(COUNTS),'by_county':dict(COUNTY_CT),'by_source':dict(SOURCES),'ready_as_candidates_for_website':len(website_orgs),'demo_shortlist_250':len(shortlist),'source_record_count_second_pass':len(read_psv(ROOT/'source/second_pass_manufacturers_2026.psv',6))+len(read_psv(ROOT/'source/second_pass_sector_2026.psv',6)),'research_only':sum(r['publication_status']=='research_only' for r in orgs),'duplicate_name_merges':len(duplicates),'duplicate_examples':duplicates,'no_active_supplier_status_inferred_from_2019_nasa_map':True}
(ROOT/'qa/summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
print(json.dumps(summary,indent=2))
