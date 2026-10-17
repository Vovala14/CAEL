"""Non-neural conditional language probabilities from fitted sparse token counts.

The retriever and token memories are statistical tables. No neural inference,
benchmark IDs, topic metadata, alternatives or labels enter next-token scoring.
"""
from collections import OrderedDict
import hashlib
import json
from pathlib import Path
import re

TOKEN = re.compile(r"[a-z]+(?:'[a-z]+)?|[0-9]+|[^\w\s]",re.I)


def tokenize(text):
    return TOKEN.findall(text.lower())


class CountLanguage:
    def __init__(self,path):
        import joblib
        import numpy as np
        from scipy import sparse
        self.np=np
        self.path=Path(path)
        self.manifest=json.loads((self.path/'model.json').read_text())
        if self.manifest.get('format')!='cael-conditional-count-v1':
            raise ValueError('Unsupported count-language checkpoint')
        for name,expected in self.manifest['files'].items():
            file=self.path/name
            if not file.resolve().is_relative_to(self.path.resolve()):
                raise ValueError('Invalid count-language member')
            with file.open('rb') as stream:
                digest=hashlib.file_digest(stream,'sha256').hexdigest()
            if digest!=expected:
                raise ValueError('Count-language checksum mismatch: '+name)
        self.retriever=joblib.load(self.path/'retriever.joblib')
        self.contexts=sparse.load_npz(self.path/'contexts.npz')
        self.answers=sparse.load_npz(self.path/'answers.npz')
        self.prefix=sparse.load_npz(self.path/'prefix.npz')
        self.vocab=json.loads((self.path/'vocab.json').read_text())
        self.index={word:i for i,word in enumerate(self.vocab)}
        self.global_counts=np.load(self.path/'global.npy',allow_pickle=False).astype(np.float64)
        self.global_p=(self.global_counts+.1)/(self.global_counts.sum()+.1*len(self.vocab))
        self.prefix_totals=np.asarray(self.prefix.sum(axis=1)).reshape(-1)
        self.settings=self.manifest['settings']
        self.association=sparse.load_npz(self.path/'association.npz') if 'association.npz' in self.manifest['files'] else None
        self.transfer=sparse.load_npz(self.path/'lexical_transfer.npz').tocsc() if 'lexical_transfer.npz' in self.manifest['files'] else None
        self.output_vocab=json.loads((self.path/'lexical_vocab.json').read_text()) if self.transfer is not None else self.vocab
        self.output_index={word:i for i,word in enumerate(self.output_vocab)}
        self.context_aliases=json.loads((self.path/'context_aliases.json').read_text()) if 'context_aliases.json' in self.manifest['files'] else {}
        self.association_cache=OrderedDict()
        self.cache=OrderedDict()

    def query_features(self,context):
        if self.manifest.get('entity_binding'):
            from .entity_binding import normalize
            context=normalize(context)[0]
        query=self.retriever.transform([context])
        if self.context_aliases:
            aliases=[alias for word in tokenize(context) for alias in self.context_aliases.get(word,[])[:3]]
            if aliases:
                weight=self.settings.get('context_lexical_weight',.15)
                query=(1-weight)*query+weight*self.retriever.transform([' '.join(aliases)])
        return query

    def neighbours(self,context,limit=128):
        np=self.np
        if context in self.cache:
            self.cache.move_to_end(context)
            return self.cache[context]
        query=self.query_features(context)
        # Both stored/query rows are L2 normalized; this is sparse cosine recall.
        from sklearn.preprocessing import normalize
        query=normalize(query,copy=False)
        hits=(query@self.contexts.T).tocsr()
        if hits.nnz:
            take=min(limit,hits.nnz)
            selection=np.argpartition(hits.data,-take)[-take:]
            order=np.lexsort((hits.indices[selection],-hits.data[selection]))
            selection=selection[order]
            result=(hits.indices[selection],hits.data[selection])
        else:
            result=(np.array([],dtype=np.int64),np.array([],dtype=np.float64))
        self.cache[context]=result
        if len(self.cache)>32:
            self.cache.popitem(last=False)
        return result

    def conditional(self,context,settings=None):
        np=self.np
        settings=settings or self.settings
        indices,similarities=self.neighbours(context)
        count=min(len(indices),settings['neighbours'])
        if count:
            weights=similarities[:count].astype(np.float64)**settings['recall_power']
            recalled=np.asarray(weights@self.answers[indices[:count]]).reshape(-1)
            recalled=recalled/recalled.sum() if recalled.sum() else self.global_p
        else:
            recalled=self.global_p
        mix=settings['recall_weight']
        base=(1-mix)*self.global_p+mix*recalled
        strength=settings.get('association_strength',0.)
        if self.association is not None and strength:
            if context not in self.association_cache:
                from sklearn.preprocessing import normalize
                query=normalize(self.query_features(context),copy=False)
                projection=(query@self.association).toarray().reshape(-1)
                self.association_cache[context]=projection
                if len(self.association_cache)>32:
                    self.association_cache.popitem(last=False)
            evidence=self.association_cache[context]
            logits=np.log(base)+strength*evidence
            logits-=logits.max()
            base=np.exp(logits)
            base/=base.sum()
            base=(1-1e-6)*base+1e-6*self.global_p
        return base

    def score_ending(self,context,ending,settings=None,base=None):
        settings=settings or self.settings
        base=self.conditional(context,settings) if base is None else base
        original_chars=len(ending)
        if self.manifest.get('entity_binding'):
            from .entity_binding import normalize
            context,normalized,_=normalize(context,[ending])
            ending=normalized[0]
        tokens=tokenize(ending)
        previous=tokenize(context)[-1:]
        previous=self.index.get(previous[0],0) if previous else 0
        total=0.
        weight=settings['prefix_weight']
        for word in tokens:
            current=self.index.get(word,0)
            # Smoothed conditional prefix distribution is normalized over the
            # entire fitted vocabulary, not over the four supplied endings.
            if self.transfer is None:
                prefix_p=(float(self.prefix[previous,current])+self.global_p[current])/(self.prefix_totals[previous]+1.)
                probability=(1-weight)*base[current]+weight*prefix_p
            else:
                output=self.output_index.get(word,0)
                begin,end=self.transfer.indptr[output:output+2]
                ids=self.transfer.indices[begin:end]
                coefficients=self.transfer.data[begin:end]
                lexical=settings.get('lexical_weight',.1)
                prefix_values=(self.prefix[previous,ids].toarray().reshape(-1)+self.global_p[ids])/(self.prefix_totals[previous]+1.)
                probability=lexical*float(coefficients@((1-weight)*base[ids]+weight*prefix_values))
                original=self.index.get(word,0 if output==0 else None)
                if original is not None:
                    prefix_p=(float(self.prefix[previous,original])+self.global_p[original])/(self.prefix_totals[previous]+1.)
                    probability+=(1-lexical)*((1-weight)*base[original]+weight*prefix_p)
                elif len(ids):
                    current=int(ids[coefficients.argmax()])
            total+=float(self.np.log(probability))
            previous=current
        return dict(sum_lnp=total,tokens=len(tokens),chars=original_chars)

    def score_endings(self,context,endings,settings=None):
        if not isinstance(context,str) or len(context)>20000 or not 2<=len(endings)<=12:
            raise ValueError('Unsupported continuation request')
        if not all(isinstance(text,str) and 0<len(text)<=2000 and tokenize(text) for text in endings):
            raise ValueError('Invalid ending')
        base=self.conditional(context,settings)
        return [self.score_ending(context,ending,settings,base) for ending in endings]
