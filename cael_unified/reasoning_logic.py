"""Bounded Horn-rule graph automaton with explicit proof support and open-world answers."""
from dataclasses import dataclass
import re


class Unparsed(ValueError):
    pass


def sentences(text):
    return [re.sub(r'^\s*\d+\s+', '', part).strip(' .\n') for part in re.split(r'[.\n]+', text) if part.strip(' .\n')]


class LogicCA:
    def __init__(self, model):
        self.model = model

    def noun(self, text, plural=False):
        text = re.sub(r'^(?:a|an|the)\s+', '', text.strip().lower())
        if plural:
            pieces = text.split()
            if len(pieces)>1 and pieces[-1] in self.model.get('plural', {}):
                pieces[-1] = self.model['plural'][pieces[-1]]
                return ' '.join(pieces)
            text = self.model.get('plural', {}).get(text, text)
            if text.endswith('uses'):
                text = text[:-2]
            elif text.endswith('ies'):
                text = text[:-3] + 'y'
            elif text.endswith('s') and not text.endswith(('ss', 'us', 'ous', 'is')):
                text = text[:-1]
        return text

    def properties(self, text, plural=False):
        if re.search(r'\b(?:or|either|neither|unless|only if)\b', text, re.I):
            raise Unparsed('Disjunction and exceptions are outside this Horn-rule solver')
        text = re.sub(r',\s*(?:and\s+)?', ' and ', text, flags=re.I)
        result = []
        for part in re.split(r'\s+and\s+', text.strip(), flags=re.I):
            negative = part.lower().startswith('not ')
            part = re.sub(r'^not\s+', '', part, flags=re.I)
            value = self.noun(part, plural)
            if not value or not re.fullmatch(r'[a-z][a-z -]{0,80}', value):
                raise Unparsed('Unsupported property phrase')
            result.append((value, int(negative)))
        if not 1 <= len(result) <= 6:
            raise Unparsed('Too many conjuncts')
        return tuple(result)

    def parse(self, context):
        facts, rules = [], []
        for index, statement in enumerate(sentences(context), 1):
            original = statement
            lower = statement.lower()
            if lower.startswith('everything that is '):
                body, sep, head = lower[len('everything that is '):].rpartition(' is ')
                if not sep:
                    raise Unparsed('Incomplete universal rule')
                rules.append((self.properties(body), self.properties(head), index))
            elif re.match(r'(?i)^(?:every|each|all) ', statement):
                match = re.fullmatch(r'(?i)(every|each|all) (.+?) (is|are|can|need|have) (.+)', statement)
                if not match:
                    raise Unparsed('Incomplete universal rule')
                marker, body, verb, head = match.groups()
                head = head if verb.lower() in ('is', 'are') else verb.lower() + ' ' + head
                rules.append((self.properties(body, marker.lower() == 'all'), self.properties(head, verb.lower() == 'are'), index))
            elif lower.startswith('if '):
                match = re.fullmatch(r'(?i)if (?:someone|something|an? \w+|a thing) is (.+?) then (?:they|it|that thing) (?:is|are) (.+)', statement)
                if not match:
                    raise Unparsed('Unsupported conditional')
                rules.append((self.properties(match[1]), self.properties(match[2]), index))
            else:
                match = re.fullmatch(r'(?i)(.+?) (is|are) (.+)', statement)
                if not match:
                    raise Unparsed('Unrecognized premise: ' + original[:100])
                subject, verb, value = match.groups()
                if verb.lower() == 'are':
                    rules.append((self.properties(subject, True), self.properties(value, True), index))
                else:
                    name = re.sub(r'^the\s+', '', subject, flags=re.I).lower()
                    if not re.fullmatch(r'[a-z][a-z -]{0,60}', name):
                        raise Unparsed('Unsupported entity')
                    for prop, negative in self.properties(value):
                        facts.append(((name, prop, negative), index))
        if not facts or len(facts) > 128 or len(rules) > 128:
            raise Unparsed('The bounded solver needs facts and at most 128 rules')
        return facts, rules

    def close(self, context):
        facts, rules = self.parse(context)
        entities = sorted({fact[0] for fact, _ in facts})
        if len(entities)*len(rules)>4096:
            raise Unparsed('Too many grounded rule cells')
        active = {fact for fact, _ in facts}
        proof = {fact: {index} for fact, index in facts}
        depths = {fact: 0 for fact, _ in facts}
        grounded = [(tuple((entity, p, neg) for p, neg in body), tuple((entity, p, neg) for p, neg in head), index)
                    for entity in entities for body, head, index in rules]
        # Bipartite graph CA: rule cells read only connected premise fact cells;
        # conclusion fact cells read only connected rule cells. No neural weights.
        table = self.model.get('and_table', {})
        for tick in range(24):
            next_active = set(active)
            next_proof, next_depth = dict(proof), dict(depths)
            for body, head, index in grounded:
                mask = sum((1 << i) for i, atom in enumerate(body) if atom in active)
                if not table.get(f'{len(body)}:{mask}', 0):
                    continue
                support = {index}.union(*(proof[atom] for atom in body))
                depth = 1 + max(depths[atom] for atom in body)
                for atom in head:
                    next_active.add(atom)
                    if atom not in next_depth or depth < next_depth[atom]:
                        next_proof[atom], next_depth[atom] = support, depth
            if next_active == active:
                return active, proof, depths
            active, proof, depths = next_active, next_proof, next_depth
        raise Unparsed('The proof exceeded 24 rule-application rounds')

    def query(self, context, question):
        active, proofs, depths = self.close(context)
        question = re.sub(r'(?i)^(?:prove|true or false|question|query)\s*:\s*', '', question).strip(' ?.!.')
        question = re.sub(r'(?i)^is it true that ', '', question)
        wh = re.fullmatch(r'(?i)what is (.+?) afraid of', question)
        if wh:
            values = sorted((p[len('afraid of '):], proofs[(e,p,n)], depths[(e,p,n)]) for e,p,n in active
                            if e == wh[1].lower() and p.startswith('afraid of ') and not n)
            if len(values)==1:
                return dict(answer=values[0][0],status='proved',support=sorted(values[0][1]),depth=values[0][2])
            return dict(answer='unknown',support=[],depth=0)
        if question.lower().startswith('is '):
            body=question[3:]
            entity=next((name for name in sorted({e for e,_,_ in active},key=len,reverse=True)
                         if body.lower().startswith(name+' ')),None)
            if entity:
                subject=entity
                properties=self.properties(body[len(entity)+1:])
            else:
                match = re.fullmatch(r'(?i)is (.+?) (not )?(?:an? |the )?(.+)', question)
                if not match:
                    raise Unparsed('Unrecognized logical query')
                subject, neg, value = match.groups()
                properties = self.properties(('not ' if neg else '') + value)
        else:
            match = re.fullmatch(r'(?i)(.+?) is (.+)', question)
            if not match:
                wh = re.fullmatch(r'(?i)what is (.+?) afraid of', question)
                if wh:
                    values = sorted((p[len('afraid of '):], proofs[(e,p,n)], depths[(e,p,n)]) for e,p,n in active
                                    if e == wh[1].lower() and p.startswith('afraid of ') and not n)
                    if len(values) == 1:
                        return dict(answer=values[0][0], status='proved', support=sorted(values[0][1]), depth=values[0][2])
                raise Unparsed('Unrecognized logical query')
            subject, value = match.groups()
            properties = self.properties(value)
        subject = re.sub(r'(?i)^the ', '', subject).lower()
        targets = [(subject, prop, neg) for prop, neg in properties]
        positive = all(atom in active for atom in targets)
        negative = any((e,p,1-n) in active for e,p,n in targets)
        status = 'conflicting' if positive and negative else 'true' if positive else 'false' if negative else 'unknown'
        present = [atom for atom in targets if atom in active] + [(e,p,1-n) for e,p,n in targets if (e,p,1-n) in active]
        support = sorted(set().union(*(proofs[atom] for atom in present))) if present else []
        depth = max((depths[atom] for atom in present), default=0)
        return dict(answer=status, status=status, support=support, depth=depth)
