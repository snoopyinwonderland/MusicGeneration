"""Read-only independent MSCX timing audit of an explicit tonal library's works."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from musigen.tonal_reference import read_table
from musigen.mscx_timing import audit


def run(root,library):
    root=Path(root).resolve();results=[]
    for work in library['works']:
        row={'id':work['id'],'previous_status':work['status'],'sources':work['sources']}
        try:
            paths={}
            for name,source in work['sources'].items():
                path=(root/source['path']).resolve()
                if not path.is_relative_to(root) or hashlib.sha256(path.read_bytes()).hexdigest()!=source['sha256']:raise ValueError('source_path_or_hash_changed')
                paths[name]=path
            row.update(audit(paths['score'].read_text(encoding='utf-8'),*[read_table(paths[k]) for k in ('measures','notes','harmonies')]))
        except (ValueError,KeyError,OSError) as exc:row.update(status='unavailable',reason=str(exc))
        results.append(row)
    return {'format':'musicanote-xml-timing-audit','version':1,'works':results,
            'summary':{'works':len(results),'validated':sum(r['status']=='validated' for r in results)},
            'scope':'independent written-time validation; no automatic reclassification of previous library'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--library',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();result=run(a.root,json.loads(a.library.read_text(encoding='utf-8')))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({**result['summary'],'works':[{'id':r['id'],'status':r['status'],'reason':r.get('reason'),'differences':{k:{d:len(v) for d,v in ds.items()} for k,ds in r.get('differences',{}).items()}} for r in result['works']]},ensure_ascii=False))
