# v6.7 = v6.6 + rule-based semantic parser over a Wikidata integer-ID graph + SymPy maths solver.
import os,sys,re,json
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import cael_v66 as B6, skills66 as S, ret65 as R, gate65 as G65, addons64 as A64
import kg67 as KG, math67 as M
# keep the fresh check-set NQ questions out of the QA store
_n=lambda s:re.sub(r'\W+',' ',s.lower()).strip()
CHK={_n(json.loads(l)['q']) for l in open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'check67.jsonl')) if json.loads(l)['kind']=='nq'}
for r in R.QA:
    if _n(r['q']) in CHK: r['k']='excluded'
G65.TH['qa_f']['excluded']=10**9
class V6(B6.V6):
    def respond(s,messages):
        text=messages[-1]['content']
        r=S.safety(text)
        if r: return dict(response=r[0],route=r[1])
        if len(messages)==1:
            typ=B6.B.V4M.route(messages)[0]        # integer CA router decides which engine may run
            if typ not in('smalltalk','greet','write'):
                r=M.solve(text)
                if r: return dict(response=r[0],route='math67:'+r[1],ca_type=typ)
            if typ not in('smalltalk','greet','write','code') and not A64.dated(text):
                r=KG.answer(text)
                if r: return dict(response=r[0],route='kg67:'+r[1],ca_type=typ)
        return super().respond(messages)
