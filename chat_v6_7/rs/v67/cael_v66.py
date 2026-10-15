# v6.6 = v6.5 + safety/distress + task skills + no small-talk templates on requests.
import os,sys,re
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import cael_v65 as B, skills66 as S, gate65 as G65
class V6(B.V6):
    def respond(s,messages):
        text=messages[-1]['content']
        r=S.safety(text)
        if r: return dict(response=r[0],route=r[1])
        typ=B.V4M.route(messages)[0]          # integer CA router
        if typ not in('smalltalk','greet') or len(messages)==1:
            r=S.task(messages,typ)
            if r: return dict(response=r[0],route='skill:'+r[1],ca_type=typ)
        out=super().respond(messages)
        if out['route'].startswith('smalltalk') and len(messages)==1 and S.is_request(text):
            x=G65.answer(text,'other')
            if x: return dict(response=x[0],route='req+'+x[1])
            return dict(response=B.safe_task('other',text),route='req+safe',was=out['route'])
        return out
