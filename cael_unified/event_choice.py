"""Experimental event-parser continuity feature; opt-in, no live selection.

This measures grounding, not entailment or physical feasibility. Unknown
syntax is neutral. It leaves the native likelihood scorer untouched.
"""
from dataclasses import asdict
from .event_parser import parse

WEIGHT=.15
ROLES={'actor':3,'patient':1,'recipient':1,'instrument':1,'destination':1}


def features(context,endings):
    if not isinstance(context,str) or len(context)>15000 or not 2<=len(endings)<=12:
        raise ValueError('Unsupported event-choice input')
    if not all(isinstance(e,str) and 0<len(e)<=2000 for e in endings):
        raise ValueError('Unsupported event-choice ending')
    prefix=parse(context)
    left=[e for e in prefix.events if not e.negated and e.modality=='asserted']
    anchored={getattr(e,role) for e in left for role in ROLES if getattr(e,role) is not None}
    actors={e.actor for e in left if e.actor is not None}
    output=[]
    for ending in endings:
        # Fresh document per ending: alternatives never change one another's
        # reference bindings. The common prefix is identical in every arm.
        text=context+' '+ending.lstrip()
        doc=parse(text)
        # A verb can start in the context and receive its object in the
        # continuation. Context anchors must still come ONLY from the prefix,
        # never from arguments supplied by that candidate itself.
        right=[e for e in doc.events if e.end>len(context)]
        numerator=denominator=0
        for event in right:
            if event.negated or event.modality!='asserted':
                continue
            for role,weight in ROLES.items():
                value=getattr(event,role)
                if value is None:
                    continue
                denominator+=weight
                numerator+=weight*int(value in (actors if role=='actor' else anchored))
        continuity=numerator/denominator if denominator and left and not (doc.truncated or prefix.truncated) else 0.
        # Ablation: ignore roles/events, retaining only entity mentions shared
        # across the text boundary. This is descriptive, not a second candidate.
        prior={e.identity for e in doc.entities if any(end<=len(context) for start,end in e.mentions)}
        later={e.identity for e in doc.entities if any(start>=len(context) for start,end in e.mentions)}
        noun_only=len(prior&later)/len(later) if later and not doc.truncated else 0.
        output.append(dict(continuity=continuity,noun_only=noun_only,
            context_events=len(prefix.events),grounded_context_events=len(left),ending_events=len(right),resolved_roles=denominator,
            unresolved_references=sum(len(e.unresolved) for e in right),truncated=doc.truncated,
            events=[asdict(e) for e in right],entities=[asdict(e) for e in doc.entities]))
    return output


def rescore(context,endings,likelihoods):
    if len(likelihoods)!=len(endings):
        raise ValueError('Likelihood count does not match endings')
    details=features(context,endings)
    baseline=[v['sum_lnp']/max(1,v['chars']-1) for v in likelihoods]
    scores=[s+WEIGHT*d['continuity'] for s,d in zip(baseline,details)]
    return dict(prediction=max(range(len(scores)),key=scores.__getitem__),scores=scores,
                baseline=baseline,features=details,weight=WEIGHT)
