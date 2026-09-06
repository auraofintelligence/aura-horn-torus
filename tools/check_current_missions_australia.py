#!/usr/bin/env python3
"""Release checks for the current DFAT mission directory."""
import json, math, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    data=json.loads((ROOT/'data/missions-australia.json').read_text(encoding='utf-8'))
    rows=data['records']; assert len(rows)==521 and len({r['id'] for r in rows})==521
    assert data['counts']=={'sourceRecords':521,'mapped':438,'held':83,'missionsIndexEntries':164,'consulatesIndexEntries':106}
    for r in rows:
        assert r['sourceUrl'].startswith('https://protocol.dfat.gov.au/Public/')
        assert r['status'] in {'mapped','held'}
        if r['status']=='mapped':
            assert r['address'] and math.isfinite(r['latitude']) and math.isfinite(r['longitude'])
            assert 'approximate state-capital position' in r['coordinateBasis']
        else:
            assert r['latitude'] is None and r['longitude'] is None
    layer=json.loads((ROOT/'data/layers/foreign-missions-australia.js').read_text(encoding='utf-8').split('=',1)[1].rstrip(' ;\n'))
    assert len(layer)==438 and len({p[8]['id'] for p in layer})==438
    assert {p[8]['id'] for p in layer}=={r['id'] for r in rows if r['status']=='mapped'}
    print(json.dumps({'status':'ok','records':len(rows),'mapped':len(layer),'held':83}))
if __name__=='__main__': main()
