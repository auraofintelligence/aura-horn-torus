#!/usr/bin/env python3
"""Second-pass address-only search for current DFAT offices not yet matched."""
import json,re,time,urllib.parse,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; WORK=ROOT/'work/missions-australia'
def main():
    data=json.loads((ROOT/'data/missions-australia.json').read_text(encoding='utf8'))
    prior={r['address'].lower():r.get('location') for r in json.loads((WORK/'current-geocodes.json').read_text(encoding='utf8'))['records']}
    out=[]; done=set()
    for r in data['records']:
        if r['status']!='mapped' or not r['address'] or prior.get(r['address'].lower()) or r['address'].lower() in done: continue
        done.add(r['address'].lower()); q=f"{r['address']}, Australia"
        params=urllib.parse.urlencode({'q':q,'format':'jsonv2','addressdetails':'1','limit':'5'})
        req=urllib.request.Request('https://nominatim.openstreetmap.org/search?'+params,headers={'User-Agent':'AuraEarth mission directory research contact: auraofintelligence.github.io'})
        try:
            with urllib.request.urlopen(req,timeout=20) as h: results=json.load(h)
        except Exception: results=[]
        number=re.search(r'\b(\d+[A-Za-z]?)\b',r['address']); postcode=re.search(r'\b(\d{4})\b',r['address']); match=None
        for item in results:
            display=item.get('display_name','')
            if number and not re.search(r'(^|\D)'+re.escape(number.group(1))+r'(\D|$)',display): continue
            if postcode and postcode.group(1) not in display: continue
            match={'latitude':float(item['lat']),'longitude':float(item['lon']),'sourceUrl':'https://www.openstreetmap.org/'+item.get('osm_type','').lower()+'/'+str(item.get('osm_id','')),'precision':'address-matched building/property point, not an entrance','checkedAt':'2026-09-07','method':'current-dfat-address+nominatim-address-only','matchedAddress':display,'licence':'ODbL 1.0'}; break
        out.append({'address':r['address'],'location':match}); time.sleep(1.05)
        if len(out)%25==0: print(f'processed {len(out)} unmatched addresses',flush=True)
    (WORK/'current-geocodes-second-pass.json').write_text(json.dumps({'checkedAt':'2026-09-07','records':out},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'searched':len(out),'matched':sum(bool(x['location']) for x in out)}))
if __name__=='__main__': main()
