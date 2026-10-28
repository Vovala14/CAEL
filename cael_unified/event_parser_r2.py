"""Opt-in syntax-count-assisted event parser; existing CA kernels unchanged."""
from functools import lru_cache
from pathlib import Path

from .count_syntax import CountSyntax
from .event_parser import Parser as OriginalParser
from .event_parser import VERBS, PHRASES, ASPECT, PAST_PARTICIPLES, PREPS, CONNECT, BREAK, PRONOUNS, DET, OBJECTS

MODEL=Path(__file__).resolve().parents[1]/'models/cael-count-syntax-r2d-20261022/model.json'
MODEL_SHA='d8b703feeff3a60d030c6246496ef2899aa78cd92e08e0a49d9cecdde83c4df0'


@lru_cache(maxsize=1)
def trained_syntax():
    model=CountSyntax(MODEL)
    if model.sha256!=MODEL_SHA:raise ValueError('Experimental syntax checkpoint changed')
    return model


class Parser(OriginalParser):
    def __init__(self,tagger=None):
        chosen=tagger or getattr(self,'tagger',None) or trained_syntax()
        super().__init__()
        self.tagger=chosen
        self.tags=[]
        self.collectives={}

    def actions(self):
        self.tags=self.tagger.tag(tuple(t[0] for t in self.tokens))
        out=[]
        for i,(word,tag) in enumerate(zip(self.lower,self.tags)):
            if i and self.lower[i-1] in DET:continue
            action=self.tagger.lemma(word,tag if tag.startswith('VB') else 'VBZ')
            pronoun_object=i+1<len(self.lower) and self.lower[i+1] in {'it','him','her','them'}
            coordinated=i and self.lower[i-1] in {'and','then','but'}
            subject=i and self.tags[i-1]=='PRP' or i>=2 and self.tags[i-1]=='NN' and self.lower[i-2] in {'a','an'}
            morphology=word.endswith('s') and action in self.tagger.verb_lemmas and (subject or coordinated and pronoun_object)
            if not tag.startswith('VB') and not morphology:continue
            if action in {'be','have','do'}:continue
            later=range(i+1,min(len(self.tokens),i+4))
            if action in ASPECT|{'see'} and any(self.tags[j].startswith('VB') for j in later) and not any(self.lower[j] in BREAK for j in later):
                if action!='see' or word=='seen':continue
            # A prenominal participle modifies an NP; it is not an assertion
            # of an action by the preceding adjective/determiner.
            if tag in {'VBG','VBN'} and i:
                first=next((j for j in later if self.tags[j].startswith('NN') or self.lower[j] in PREPS|BREAK),None)
                if first is not None and self.tags[first].startswith('NN'):
                    prefix=self.lower[max(0,i-3):i]
                    if any(w in DET for w in prefix) and not any(w in {'is','are','was','were','been','being','has','have','had'} for w in prefix):
                        continue
            end=i+1
            if end<len(self.lower) and (action,self.lower[end]) in PHRASES:
                action=PHRASES[action,self.lower[end]];end+=1
            out.append((i,end,action))
            if len(out)>=100:
                self.doc.truncated=True
                break
        return out

    def ref(self,ids,unresolved,exclude=None):
        ids=list(ids)
        if not ids:return None
        if len(ids)>48:
            unresolved.append(dict(reference='overlong noun phrase',start=self.tokens[ids[0]].start(),candidates=[]))
            return None
        words=[self.lower[j] for j in ids]
        if words[0] in PRONOUNS and (len(words)==1 or words[1] in {'is','are','was','were','has','have','had'}):
            return super().ref(ids,unresolved,exclude)
        if 'and' in words:return super().ref(ids,unresolved,exclude)
        if 'or' in words:
            unresolved.append(dict(reference='alternative noun phrases',start=self.tokens[ids[0]].start(),candidates=[]))
            return None
        # Generic collective phrases, rather than a target-specific actor
        # vocabulary: plural members carry the reference used by "they".
        collective={'group','crowd','team','pair','couple','flock','herd','band'}
        of=words.index('of') if 'of' in words else None
        if of is not None and any(w in collective for w in words[:of]):
            ref=self.ref(ids[of+1:],unresolved,exclude)
            label=next(w for w in words[:of] if w in collective)
            if ref:self.collectives.setdefault(label,set()).add(ref)
            return ref
        head_word=next((w for w in words if w in collective),None)
        if head_word and words[0] in {'the','this','that'}:
            candidates=self.collectives.get(head_word,set())
            if len(candidates)==1:return next(iter(candidates))
        # Stop at actual finite predicates, not arbitrary last words. Keep
        # nominal compounds/adjectives and their source spans intact.
        end=len(ids)
        for k,j in enumerate(ids):
            nominal_after_determiner=k and self.lower[ids[k-1]] in DET and self.lower[j] in self.tagger.noun_lemmas
            if k and (self.lower[j] in PREPS|CONNECT|BREAK|{'who','which','that'} or self.tags[j] in {'VB','VBD','VBP','VBZ'} and not nominal_after_determiner):
                end=k;break
        ids=ids[:end]
        def adverbial(j):
            return self.lower[j].endswith('ly') and self.lower[j] not in self.tagger.noun_lemmas and not self.tokens[j][0][:1].isupper()
        nominal=[j for k,j in enumerate(ids) if not adverbial(j) and (self.tags[j].startswith('NN') or self.tags[j] in {'PRP','WP'} or k and self.lower[ids[k-1]] in DET and self.lower[j] in self.tagger.noun_lemmas)]
        if not nominal:
            # Auxiliaries/adverbs alone are ordinary shared-subject clauses;
            # do not manufacture a malformed entity from them.
            return None
        head=nominal[-1]
        ids=[j for j in ids if j<=head and self.tags[j] not in {'RB','RBR','RBS'}]
        if not ids:return None
        ref=super().ref(ids,unresolved,exclude)
        if ref:
            entity=next(e for e in self.doc.entities if e.identity==ref)
            if not ref.startswith('group:'):
                proper=self.tags[head] in {'NNP','NNPS'} and self.tokens[head][0][:1].isupper() and entity.head not in OBJECTS
                entity.kind='person' if entity.head in self.tagger.human_nouns or proper else 'object'
        return ref

    def parse(self,text):
        doc=super().parse(text)
        positions={token.start():i for i,token in enumerate(self.tokens)}
        for event in doc.events:
            i=positions[event.action_start]
            if self.tags[i]!='VBN' or event.voice=='passive':continue
            sentence=max((j+1 for j in range(i) if self.lower[j] in {'.',';','!','?',':'}),default=0)
            local=self.lower[sentence:i]
            has_be=any(w in {'is','are','was','were','been','being','be'} for w in local[-5:])
            has_have=any(w in {'has','have','had'} for w in local[-3:])
            reduced=i>0 and self.tags[i-1].startswith('NN') and not has_have
            if has_be or reduced:
                patient=event.actor
                if reduced:
                    candidates=[e for e in doc.entities if any(end<=event.action_start for start,end in e.mentions)]
                    if candidates:patient=max(candidates,key=lambda e:max(end for start,end in e.mentions if end<=event.action_start)).identity
                by=any(self.lower[j]=='by' for j in range(i+1,len(self.tokens)) if self.tokens[j].start()<event.end)
                event.patient=patient
                event.actor=event.location if by else None
                if by:event.location=None
                event.voice='passive'
        return doc


def parse(text):
    return Parser().parse(text)
