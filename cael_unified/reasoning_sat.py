"""Propositional entailment for category/property premises, including 'or' and negation.

Premises such as "Every wumpus is a jompus", "Everything that is a shumpus or a rompus is
an impus", "Fae is a sterpus or a lempus", "Sally is not a jompus" are translated into
clauses over atoms (individual, property). A question Q follows when premises + not-Q is
unsatisfiable (checked with a small DPLL solver); it is refuted when premises + Q is
unsatisfiable. This covers case analysis (disjunction elimination) and proof by
contradiction without separate proof rules. Authored algorithm; nothing is learned.
"""
import re

from .reasoning_logic import Unparsed, sentences

QUANT = r'(?:every|each|all)'


def lemma(word):
    """Fictional and ordinary nouns: 'sterpuses' -> 'sterpus', 'cats' -> 'cat'."""
    w = word.lower()
    if w.endswith('uses'):
        return w[:-2]
    if w.endswith('ies') and len(w) > 4:
        return w[:-3] + 'y'
    if w.endswith('es') and w[:-2].endswith(('s', 'x', 'ch', 'sh')):
        return w[:-2]
    if w.endswith('s') and not w.endswith(('ss', 'us', 'is')):
        return w[:-1]
    return w


def literal(phrase):
    """'not a rompus' -> ('rompus', False); 'a sterpus' -> ('sterpus', True); 'opaque' -> ('opaque', True)."""
    phrase = phrase.strip().lower().rstrip('.')
    positive = True
    if phrase.startswith('not '):
        positive, phrase = False, phrase[4:]
    phrase = re.sub(r'^(?:a|an|the)\s+', '', phrase)
    if not re.fullmatch(r'[a-z_]+', phrase):
        raise Unparsed('unsupported property phrase: ' + phrase)
    return lemma(phrase), positive


def split_list(phrase, joiner):
    """'a, b, and c' / 'a and b' / 'a or b or c' -> parts."""
    phrase = re.sub(r',\s*(?:and|or)\s+', ', ', phrase)
    parts = re.split(r'\s*,\s*|\s+' + joiner + r'\s+', phrase)
    return [p for p in parts if p]


def property_set(phrase):
    """'a dumpus, a lempus, and a gorpus' -> ('and', [...]); 'a or b' -> ('or', [...])."""
    has_or = re.search(r'\bor\b', phrase)
    kind = 'or' if has_or else 'and'
    return kind, [literal(p) for p in split_list(phrase, kind)]


def statement_parts(text, joiner='and'):
    """Split 'A is x, A is y, and B is z' into its statements (only where a new 'NAME is' begins)."""
    return [p for p in re.split(r'(?:,\s*(?:' + joiner + r'\s+)?|\s+' + joiner + r'\s+)(?=[a-z_]+ is\b)', text) if p]


def abilities(s):
    """'birds can fly' -> 'birds are can_fly'; 'tom cannot swim' -> 'tom is not can_swim'."""
    m = re.fullmatch(r'(.+?) (can not|cannot|can\'t|can) ([a-z]+)', s)
    if not m:
        return s
    subject, negative = m.group(1), m.group(2) != 'can'
    plural = re.match(r'(?:every|each|everything|no)\b', subject) is None and (re.match(r'all\b', subject) or subject.endswith('s'))
    verb = 'are' if plural else 'is'
    return f"{subject} {verb} {'not ' if negative else ''}can_{m.group(3)}"


class Problem:
    def __init__(self):
        self.atoms = {}
        self.clauses = []
        self.rules = []          # (antecedent kind, literals, consequent kind, literals)
        self.individuals = set()
        self.facts = []          # (individual, kind, literals)

    def atom(self, individual, prop):
        key = (individual, prop)
        if key not in self.atoms:
            self.atoms[key] = len(self.atoms) + 1
        return self.atoms[key]

    def lit(self, individual, item):
        prop, positive = item
        number = self.atom(individual, prop)
        return number if positive else -number

    def add_sentence(self, text):
        s = abilities(' '.join(text.lower().strip(' .').split()))
        if not re.match(r'(?:everything|every|each|all)\b', s):
            # "Max is a grimpus and Polly is a zumpus": several facts in one sentence.
            parts = statement_parts(s)
            if len(parts) > 1:
                for part in parts:
                    self.add_sentence(part)
                return
        rule = re.fullmatch(r'everything that is (.+?) is (.+)', s)
        if rule:
            self.rules.append((*property_set(rule.group(1)), *property_set(rule.group(2))))
            return
        rule = re.fullmatch(r'no ([a-z]+) (?:is|are) (.+)', s)
        if rule:
            kind, items = property_set(rule.group(2))
            self.rules.append(('and', [(lemma(rule.group(1)), True)], 'or' if kind == 'and' else 'and', [(p, not v) for p, v in items]))
            return
        rule = re.fullmatch(QUANT + r' ([a-z]+) (?:is|are) (.+)', s)
        if rule:
            self.rules.append(('and', [(lemma(rule.group(1)), True)], *property_set(rule.group(2))))
            return
        plural = re.fullmatch(r'([a-z]+) are (.+)', s)
        if plural:
            self.rules.append(('and', [(lemma(plural.group(1)), True)], *property_set(plural.group(2))))
            return
        fact = re.fullmatch(r'([a-z]+) is (.+)', s)
        if fact and not fact.group(1) in ('it', 'this', 'that', 'everything'):
            self.individuals.add(fact.group(1))
            self.facts.append((fact.group(1), *property_set(fact.group(2))))
            return
        raise Unparsed('unsupported premise: ' + text[:80])

    def ground(self):
        for individual, kind, items in self.facts:
            if kind == 'or':
                self.clauses.append([self.lit(individual, i) for i in items])
            else:
                for i in items:
                    self.clauses.append([self.lit(individual, i)])
        for individual in self.individuals:
            for a_kind, a_items, c_kind, c_items in self.rules:
                a = [self.lit(individual, i) for i in a_items]
                c = [self.lit(individual, i) for i in c_items]
                # (a1 and a2 ...) -> X  ==  not a1 or not a2 ... or X;  (a1 or a2) -> X  ==  each ai -> X
                premises = [[-x for x in a]] if a_kind == 'and' else [[-x] for x in a]
                consequents = [c] if c_kind == 'or' else [[x] for x in c]
                for p in premises:
                    for q in consequents:
                        self.clauses.append(p + q)


def satisfiable(clauses):
    """Small DPLL with unit propagation."""
    def assign(cls, literal_value):
        out = []
        for clause in cls:
            if literal_value in clause:
                continue
            reduced = [x for x in clause if x != -literal_value]
            if not reduced:
                return None
            out.append(reduced)
        return out

    def solve(cls):
        while True:
            unit = next((c[0] for c in cls if len(c) == 1), None)
            if unit is None:
                break
            cls = assign(cls, unit)
            if cls is None:
                return False
        if not cls:
            return True
        choice = cls[0][0]
        for value in (choice, -choice):
            reduced = assign(cls, value)
            if reduced is not None and solve(reduced):
                return True
        return False

    return solve([list(c) for c in clauses])


def query_clauses(problem, question):
    """CNF for 'question is FALSE' and for 'question is TRUE'."""
    q = ' '.join(question.lower().strip(' .?').split())
    q = re.sub(r'^(?:prove|true or false|is it true that)\s*:?\s*', '', q)
    asked = re.fullmatch(r'(?:is|are) ([a-z]+) (.+)', q)
    if asked and not re.match(r'(?:every|each|all|no)\b', asked.group(1)):
        q = f'{asked.group(1)} is {asked.group(2)}'
    asked = re.fullmatch(r'(?:can|could) ([a-z]+) ([a-z]+)', q)
    if asked:
        q = f"{asked.group(1)} {'are' if asked.group(1).endswith('s') else 'is'} can_{asked.group(2)}"
    q = abilities(q)
    universal = re.fullmatch(r'(?:every|each|all) ([a-z]+) (?:is|are) (.+)', q) or re.fullmatch(r'([a-z]+) are (.+)', q)
    if universal:
        # A fresh, otherwise unknown member of the class stands for all of them.
        individual = 'any_' + lemma(universal.group(1))
        problem.individuals.add(individual)
        problem.facts.append((individual, 'and', [(lemma(universal.group(1)), True)]))
        q = f'{individual} is {universal.group(2)}'
    # "Sally is not a rompus and Sally is not a shumpus" / "A is x, A is y, and A is z" -> statements.
    parts = statement_parts(q, 'and')
    joiner = 'and'
    if len(parts) == 1:
        parts = statement_parts(q, 'or')
        joiner = 'or' if len(parts) > 1 else 'and'
    statements = []
    for part in parts:
        m = re.fullmatch(r'([a-z_]+) is (.+)', part)
        if not m:
            raise Unparsed('unsupported question')
        individual = m.group(1)
        problem.individuals.add(individual)
        kind, items = property_set(m.group(2))
        statements.append((individual, kind, items))
    # Each statement as a formula; build "Q true" and "Q false" in CNF (statements are small).
    def stmt_literals(stmt):
        individual, kind, items = stmt
        return kind, [problem.lit(individual, i) for i in items]
    forms = [stmt_literals(s) for s in statements]
    if joiner == 'and' and all(k == 'and' for k, _ in forms):
        lits = [x for _, ls in forms for x in ls]
        return [[-x for x in lits]], [[x] for x in lits]          # not Q is a single clause
    if joiner == 'or' or any(k == 'or' for k, _ in forms):
        lits = [x for _, ls in forms for x in ls]
        if all(k == 'or' for k, _ in forms) or joiner == 'or':
            return [[-x] for x in lits], [lits]
    raise Unparsed('mixed and/or question')


def entails(context, question):
    problem = Problem()
    statements = sentences(context)
    for statement in statements:
        problem.add_sentence(statement)
    false_q, true_q = query_clauses(problem, question)
    problem.ground()
    if len(problem.atoms) > 400:
        raise Unparsed('too many properties for exhaustive checking')
    base = problem.clauses
    if not satisfiable(base):
        return dict(answer='conflicting', support=[])
    if not satisfiable(base + false_q):
        return dict(answer='true', support=relevant(statements, question), method='checked all cases')
    if not satisfiable(base + true_q):
        return dict(answer='false', support=relevant(statements, question), method='checked all cases')
    return dict(answer='unknown', support=[])


def relevant(statements, question):
    """Premises sharing a property word with the question (for the explanation shown to people)."""
    words = {lemma(w) for w in re.findall(r'[a-z]+', question.lower())} - {'is', 'not', 'and', 'or', 'a', 'an', 'prove'}
    picked = []
    for index, s in enumerate(statements, 1):
        if words & {lemma(w) for w in re.findall(r'[a-z]+', s.lower())}:
            picked.append(index)
    return picked[:8]


def query(context, question):
    return entails(context, question)
