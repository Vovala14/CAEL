"""Discrete count/HMM syntax model. Integer Viterbi, no neural components."""
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re

SCALE=1024


def shape(word):
    if any(c.isdigit() for c in word):return 'digit'
    if word.isupper() and word.isalpha():return 'upper'
    if word[:1].isupper():return 'title'
    if re.fullmatch(r'[^\w\s]+',word):return 'punct'
    return 'lower'


class CountSyntax:
    def __init__(self,path):
        path=Path(path)
        self.model=json.loads(path.read_text(encoding='utf-8'))
        if self.model.get('format')!='cael-count-syntax-v1':
            raise ValueError('Unsupported count syntax model')
        self.sha256=hashlib.sha256(path.read_bytes()).hexdigest()
        self.tags=self.model['tags']
        self.counts=self.model['tag_counts']
        self.words=self.model['words']
        self.alpha=self.model['smoothing']
        self.vocabulary=len(self.words)
        self.transitions={}
        # Quantization is done once on loading; inference adds/compares ints.
        for prev in ['<s>']+self.tags:
            row=self.model['transitions'].get(prev,{})
            total=sum(row.values())+self.alpha*len(self.tags)
            self.transitions[prev]={tag:round(SCALE*math.log((row.get(tag,0)+self.alpha)/total)) for tag in self.tags}
        self.human_nouns=set(self.model.get('human_nouns',[]))
        self.verb_lemmas=set(self.model.get('verb_lemmas',[]))
        self.noun_lemmas=set(self.model.get('noun_lemmas',[]))

    @lru_cache(maxsize=8192)
    def emissions(self,word):
        lower=word.lower()
        if lower.endswith("n't"):
            base={"can't":'can',"won't":'will',"shan't":'shall'}.get(lower,lower[:-3])
            if base in self.words:return self.emissions(base)
        if lower.endswith("'s") and lower[:-2] in self.words:
            nominal={tag:value for tag,value in self.emissions(lower[:-2]).items() if tag.startswith('NN')}
            if nominal:return nominal
        counts=self.words.get(lower)
        if counts:
            # All observed tags remain candidates, including genuine lexical
            # ambiguity. No tag is inferred from a benchmark vocabulary list.
            candidates=dict(counts)
            if sum(counts.values())<=3:
                stems=[]
                if lower.endswith('s'):stems=[lower[:-1],lower[:-2],lower[:-3]+'y']
                if any(stem in self.verb_lemmas for stem in stems):candidates.setdefault('VBZ',.2)
                if lower in self.verb_lemmas:
                    candidates.setdefault('VB',.2);candidates.setdefault('VBP',.2)
                if lower.endswith('ing') and self.lemma(lower,'VBG') in self.verb_lemmas:candidates.setdefault('VBG',.2)
                if lower.endswith('ed') and self.lemma(lower,'VBD') in self.verb_lemmas:
                    candidates.setdefault('VBD',.2);candidates.setdefault('VBN',.2)
            return {tag:round(SCALE*math.log((count+self.alpha)/(self.counts[tag]+self.alpha*self.vocabulary)))
                    for tag,count in candidates.items() if tag in self.counts}
        suffix=None
        for n in (4,3,2,1):
            row=self.model['suffixes'].get(lower[-n:]) if len(lower)>=n else None
            if row and sum(row.values())>=3:
                suffix=row
                break
        suffix=suffix or self.counts
        form=self.model['shapes'].get(shape(word),self.counts)
        # Rare-word suffix and orthographic shape evidence, de-biased by tag
        # frequency. Keep eight candidates to bound dynamic-programming work.
        scores={tag:round(SCALE*(math.log((suffix.get(tag,0)+.2)/(sum(suffix.values())+.2*len(self.tags)))
                   +.5*math.log((form.get(tag,0)+.2)/(sum(form.values())+.2*len(self.tags)))
                   -math.log(self.counts[tag]/sum(self.counts.values())))) for tag in self.tags}
        keep=set(tag for tag,_ in sorted(scores.items(),key=lambda p:(-p[1],p[0]))[:8])
        keep.update(tag for tag in ('NN','NNS','NNP','JJ','VB','VBP','VBZ','VBD','VBN','VBG','RB') if tag in scores)
        noun=lower in self.noun_lemmas
        verb=self.lemma(lower,'VB') in self.verb_lemmas or any(self.lemma(lower,t) in self.verb_lemmas for t in ('VBZ','VBD','VBG'))
        if noun and not verb:
            keep={t for t in keep if not t.startswith('VB')}
        return {tag:scores[tag] for tag in sorted(keep)}

    @lru_cache(maxsize=4096)
    def segment(self,words):
        if not words:return ()
        prev={'<s>':0}
        history=[]
        for word in words:
            current={};back={}
            for tag,emission in self.emissions(word).items():
                best=max(prev,key=lambda p:prev[p]+self.transitions[p][tag])
                current[tag]=prev[best]+self.transitions[best][tag]+emission
                back[tag]=best
            history.append(back)
            prev=current
        tag=max(prev,key=prev.get)
        out=[]
        for back in reversed(history):
            out.append(tag)
            tag=back[tag]
        return tuple(reversed(out))

    def tag(self,words):
        if len(words)>3000:raise ValueError('At most 3000 syntax tokens')
        out=[];segment=[]
        for word in words:
            segment.append(word)
            if word in {'.','!','?',':',';'} or len(segment)>=100:
                out.extend(self.segment(tuple(segment)))
                segment=[]
        out.extend(self.segment(tuple(segment)))
        return list(out)

    def lemma(self,word,tag):
        lower=word.lower()
        if lower.endswith("n't"):
            base={"can't":'can',"won't":'will',"shan't":'shall'}.get(lower,lower[:-3])
            return self.lemma(base,tag)
        value=self.model.get('lemmas',{}).get(lower+'|'+tag)
        if value:return value
        candidates=[lower]
        if tag=='VBZ':candidates += [lower[:-1],lower[:-2],lower[:-3]+'y']
        if tag in {'VBD','VBN'}:candidates += [lower[:-1],lower[:-2],lower[:-3]+'y']
        if tag=='VBG':
            stem=lower[:-3]
            candidates += [stem,stem+'e',stem[:-1] if len(stem)>1 and stem[-1]==stem[-2] else stem]
        return next((w for w in candidates if w in self.verb_lemmas),lower)
