import json,sys,os,collections
os.environ['WIKI_OFFLINE']='1'
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from cael_v67 import V6
S=V6();P=[json.loads(l) for l in open(sys.argv[1])];out={}
for r in P:
    try: out[r['id']]=S.respond(r['messages'])
    except Exception as e: out[r['id']]=dict(response='ERR '+repr(e),route='err')
json.dump(out,open(sys.argv[2],'w'),indent=0)
print(collections.Counter(v['route'] for v in out.values()).most_common())
