#!/usr/bin/env python3
"""Resolve current DFAT office addresses through the public Nominatim service."""
import json, re, time, urllib.parse, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'work/missions-australia/current-geocodes.json'
def main():
    source=json.loads((ROOT/'data/missions-australia.json').read_text(encoding='utf-8'))
    old=json.loads((ROOT/'work/missions-australia/address-matches.json').read_text(encoding='utf-8'))
    by_query={x.get('query','').lower():x.get('location') for x in old.get('records',[]) if x.get('location')}
    rows=[]; seen=set()
    for r in source['records']:
        if r['status']!='mapped' or not r['address']: continue
        q=f"{r['address']}, Australia"; key=q.lower()
        if key in seen: continue
        seen.add(key)
        loc=by_query.get(key)
        if not loc:
            params=urllib.parse.urlencode({'q':f"{r['officialName']}, {r['address']}, Australia",'format':'jsonv2','addressdetails':'1','limit':'3'})
            req=urllib.request.Request('https://nominatim.openstreetmap.org/search?'+params,headers={'User-Agent':'AuraEarth mission directory research contact: auraofintelligence.github.io'})
            try:
                with urllib.request.urlopen(req,timeout=20) as response: results=json.load(response)
            except Exception as exc: results=[]
            number=re.search(r'\b(\d+[A-Za-z]?)\b',r['address']); postcode=re.search(r'\b(\d{4})\b',r['address'])
            candidates=[]
            for item in results:
                display=item.get('display_name',''); addr=item.get('address',{}); ok=True
                if number and not re.search(r'(^|\D)'+re.escape(number.group(1))+r'(\D|$)',display): ok=False
                if postcode and postcode.group(1) not in display: ok=False
                if ok: candidates.append(item)
            if candidates:
                item=candidates[0]; loc={'latitude':float(item['lat']),'longitude':float(item['lon']),'sourceUrl':'https://www.openstreetmap.org/'+item.get('osm_type','').lower()+'/'+str(item.get('osm_id','')),'precision':'address-matched building/property point, not an entrance','checkedAt':'2026-09-07','method':'current-dfat-address+nominatim','matchedAddress':item.get('display_name',''),'licence':'ODbL 1.0'}
            time.sleep(1.05)
        rows.append({'address':r['address'],'location':loc})
        if len(rows)%25==0: print(f'processed {len(rows)} addresses',flush=True)
    OUT.write_text(json.dumps({'checkedAt':'2026-09-07','records':rows},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'addresses':len(rows),'matched':sum(bool(x['location']) for x in rows)}))
if __name__=='__main__': main()
