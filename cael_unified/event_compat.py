"""Experimental count evidence for event/argument compatibility; no neurons."""
from collections import Counter
import json
import math
from pathlib import Path
from .event_parser_r2 import parse


def extract(context,endings,parents):
    prefix=parse(context)
    left=[e for e in prefix.events if not e.negated and e.modality=='asserted']
    ctx={e.identity:e for e in prefix.entities}
    previous=[e.action for e in left[-2:]]
    ctx_objects=[ctx[e.patient].head for e in left[-2:] if e.patient in ctx]
    result=[]
    for ending in endings:
        doc=parse(context+' '+ending.lstrip())
        entities={e.identity:e for e in doc.entities}
        events=[e for e in doc.events if e.end>len(context) and not e.negated and e.modality=='asserted']
        features=set();pairs=[]
        for event in events[:4]:
            action=event.action
            features.add('action|'+action)
            if event.actor in entities:
                entity=entities[event.actor]
                kind='person' if entity.head.startswith('person') else entity.kind
                features.add('agent|'+action+'|'+kind)
            for role in ('patient','instrument','recipient','destination'):
                if getattr(event,role) not in entities:continue
                head=entities[getattr(event,role)].head
                features.add(role+'|'+action+'|'+head)
                for parent in parents.get(head,[])[:2]:features.add(role+'class|'+action+'|'+parent)
            for before in previous:
                features.add('transition|'+before+'|'+action)
                pairs.append((before,action))
            for obj in ctx_objects:
                features.add('context_object|'+obj+'|'+action)
                for parent in parents.get(obj,[])[:2]:features.add('context_class|'+parent+'|'+action)
        for a,b in zip(events,events[1:]):features.add('sequence|'+a.action+'|'+b.action)
        if prefix.truncated or doc.truncated:features=set();pairs=[]
        result.append(dict(features=sorted(features),pairs=pairs,events=len(events)))
    return result


class Compatibility:
    def __init__(self,path):
        self.model=json.loads(Path(path).read_text(encoding='utf-8'))
        if self.model['format']!='cael-event-count-evidence-v1':raise ValueError('Unsupported event evidence')
        self.parents=self.model['parents']

    def score_features(self,value):
        scores=[]
        for feature in value['features']:
            positive,negative=self.model['counts'].get(feature,(0,0))
            if positive+negative<36:continue
            scores.append(math.log((positive+6)/(negative+6)))
        transitions=[]
        for before,after in value['pairs']:
            key=before+'|'+after
            count=self.model['transitions'].get(key,0)
            if count<3:continue
            conditional=(count+1)/(self.model['before'].get(before,0)+len(self.model['after']))
            prior=(self.model['after'].get(after,0)+1)/(self.model['transition_total']+len(self.model['after']))
            transitions.append(max(-3,min(3,math.log(conditional/prior))))
        return (sum(scores)/len(scores) if scores else 0)+.25*(sum(transitions)/len(transitions) if transitions else 0)

    def scores(self,context,endings):
        return [self.score_features(value) for value in extract(context,endings,self.parents)]
