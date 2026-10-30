"""Finite, source-linked quantity/event graphs with checked exact arithmetic.

No learned answer lookup, neural model, global conversation state or native
generated-code execution. Every clause must be consumed. This is a bounded
semantic grammar; its arithmetic checks do not prove arbitrary prose parsing.
"""
from dataclasses import dataclass, field
from fractions import Fraction
import re

from .helper import UNITS, calculate, unit_key
from .verify import Unchecked, check_arithmetic

WORDS = dict(zero=0, one=1, two=2, three=3, four=4, five=5, six=6, seven=7, eight=8, nine=9, ten=10,
             half=Fraction(1, 2), quarter=Fraction(1, 4))
NUM = r'(?:-?\d+(?:\.\d+)?(?:/\d+)?|'+'|'.join(WORDS)+')'
ENTITY = r'[A-Za-z][A-Za-z0-9_]{0,29}'
COLORS = set('red blue green yellow white black orange purple violet teal gray grey pink brown'.split())
MATERIALS = set('wooden wood metal brass copper glass plastic silver gold paper'.split())
MONEY = {'dollar':'USD', 'dollars':'USD', 'usd':'USD', 'euro':'EUR', 'euros':'EUR', 'eur':'EUR'}
UNIT_ALIASES = {'milliliter':'ml', 'millilitre':'ml', 'litre':'liter', 'kilometre':'km', 'centimetre':'cm', 'millimetre':'mm'}


class Unclear(ValueError):
    pass


class Missing(Unclear):
    pass


def number(text):
    text = text.strip().lower()
    try:
        value = Fraction(WORDS[text]) if text in WORDS else Fraction(text)
    except (ValueError, ZeroDivisionError):
        raise Unclear('A quantity must be a finite exact number.')
    if abs(value) > 10**12 or value.denominator > 10**8:
        raise Unclear('Quantity magnitude or denominator exceeds the bounded domain.')
    return value


def singular(word):
    if word.endswith('ies') and len(word) > 4:return word[:-3]+'y'
    if word.endswith(('sses', 'ches', 'shes', 'xes')):return word[:-2]
    return word[:-1] if word.endswith('s') and not word.endswith(('ss', 'us')) else word


def product_unit(first, second):
    result = dict(first)
    for name, power in second:result[name] = result.get(name, 0)+power
    return tuple(sorted((name, power) for name, power in result.items() if power))


def inverse(unit):return tuple((name, -power) for name, power in unit)


@dataclass(frozen=True)
class Spec:
    head: str
    attributes: tuple
    unit: tuple
    scale: Fraction = field(compare=False)
    label: str = field(compare=False)


def spec(text):
    label = ' '.join(text.strip().split())
    words = re.sub(r'(?i)^(?:a|an|the)\s+', '', label).lower().split()
    if not words or len(words) > 5 or not all(re.fullmatch(r'[a-z]+', w) for w in words):
        raise Unclear('An item/unit phrase is outside the supported grammar: '+label+'.')
    if set(words) & set('unless except if when while before after than as per each every more fewer and or then at to from left now remaining'.split()):
        raise Unclear('An item phrase contains an unresolved modifier: '+label+'.')
    if len(words) == 1:
        word = words[0]
        if word in MONEY:
            return Spec('money:'+MONEY[word], (), (('currency:'+MONEY[word], 1),), Fraction(1), label)
        key = unit_key(UNIT_ALIASES.get(singular(word), word))
        if key:
            dimension, scale = UNITS[key]
            return Spec('dimension:'+dimension, (), ((dimension, 1),), Fraction(scale), label)
        if word in ('money',):return Spec('*money', (), (), Fraction(1), label)
        if word in ('items', 'objects', 'things'):return Spec('*items', (), (), Fraction(1), label)
    head = singular(words[-1])
    return Spec(head, tuple(words[:-1]), (('item:'+head, 1),), Fraction(1), label)


def compatible(actual, asked):
    return actual.unit == asked.unit and set(asked.attributes) <= set(actual.attributes)


def segments(text):
    result, begin = [], 0
    for mark in re.finditer(r'[.!?](?=\s|$)', text):
        value = text[begin:mark.start()].strip()
        if value:result.append((value, (begin, mark.end())))
        begin = mark.end()
    if text[begin:].strip():result.append((text[begin:].strip(), (begin, len(text))))
    return result


def owners(text):
    parts = re.split(r'\s+and\s+', text.strip(), flags=re.I)
    if not 1 <= len(parts) <= 4 or any(not re.fullmatch(ENTITY, p) for p in parts):
        raise Unclear('Use explicit unambiguous owner names in the quantity question.')
    if len({p.casefold() for p in parts})!=len(parts):
        raise Unclear('The question repeats the same owner; clarify the intended total.')
    return [p.casefold() for p in parts]


def query(text):
    text = re.sub(r'(?i)^(?:question|query)\s*:\s*', '', text.strip())
    forms = [
        (r'How many (.+?) (?:do|does) (.+?) (?:have|hold|own)(?: altogether| in total| now| left| remaining)?', 'stock'),
        (r'How many (.+?) remain with (.+)', 'stock'),
        (r'What is ('+ENTITY+r")'s (?:total|remaining) (?:number|amount) of (.+)", 'possessive'),
        (r'How many (.+?) did (.+?) (?:buy|purchase)', 'bought'),
        (r'How much (money|dollars|euros) (?:do|does) (.+?) have(?: left| remaining| now)?', 'stock'),
        (r'How much did (.+?) spend', 'cost'),
    ]
    for pattern, kind in forms:
        match = re.fullmatch(pattern, text, re.I)
        if not match:continue
        if kind == 'cost':return dict(kind=kind, owners=owners(match[1]), asked=None)
        a, b = match.groups()
        if kind == 'possessive':a, b, kind = b, a, 'stock'
        return dict(kind=kind, owners=owners(b), asked=spec(a))
    return None


# Ordinary change verbs, normalised onto the graph's canonical event forms.
# Base forms cover first-person narration ("I receive 15"); every verb keeps an
# explicit direction, and anything else stays an unsupported clause.
GAIN = r'(?:receives?|received|gets?|got|finds?|found|earns?|earned|gains?|gained|wins?|won|collects?|collected|picks? up|picked up)'
LOSS = r'(?:give?s? away|gave away|loses?|lost|drops?|dropped|eats?|ate|breaks?|broke|throws? away|threw away|donates?|donated)'
SPEND = r'(?:spends?|spent)'
USE = r'(?:uses?|used)'
SELL = r'(?:sells?|sold)'
BUY = r'(?:buys?|bought|purchases?|purchased)'
GIVE = r'(?:gives?|gave|hands?|handed)'
NOUNP = r'(?!to\b)[a-z]+(?: (?!to\b)[a-z]+){0,4}'
HAVE = r'(?:has|have|holds?|owns?|starts with|start with)'


def _event(who, verb, amount, noun, recipient=None):
    verb = verb.lower()
    if recipient:return who+' gives '+amount+' '+noun+' to '+recipient
    for pattern, canonical in ((GAIN,'receives'),(LOSS,'loses'),(SPEND,'spends'),(USE,'uses'),(SELL,'sells'),(BUY,'buys')):
        if re.fullmatch(pattern, verb):return who+' '+canonical+' '+amount+' '+noun
    raise Unclear('Unsupported change verb: '+verb+'.')


def expand(text):
    """Split one sentence with a shared subject into complete canonical clauses.

    "I have 8 tokens, receive 15, then give away 6" -> three clauses. A
    predicate without a noun reuses the most recent explicit noun; it never
    borrows across owners. Anything not fully consumed is returned unchanged
    so the strict clause grammar can still refuse it.
    """
    verb = r'(?:'+GAIN+'|'+LOSS+'|'+SPEND+'|'+USE+'|'+SELL+'|'+BUY+'|'+GIVE+')'
    single = re.fullmatch(r'('+ENTITY+r') ('+verb+r') ('+NUM+r')(?: more)?(?: ('+NOUNP+r'))?(?: to ('+ENTITY+r'))?', text, re.I)
    if single and single[5] is None and single[4] is None:return [text]
    if single:
        who, v, amount, noun, recipient = single.groups()
        if re.fullmatch(GIVE, v, re.I) and not recipient:return [text]
        if noun:return [_event(who, v, amount, noun, recipient)]
        return [text]
    head = re.fullmatch(r'('+ENTITY+r') ('+HAVE+r') ('+NUM+r') ([a-z][a-z ]{0,40}?)((?:\s*,\s*(?:and\s+)?(?:then\s+)?|\s+(?:and\s+)?then\s+|\s+and\s+)'+verb+r'\b.+)', text, re.I)
    if not head:return [text]
    who, have, amount, noun, rest = head.groups()
    clauses = [who+' '+('has' if who.lower()!='i' else 'have')+' '+amount+' '+noun]
    last = noun
    for piece in re.split(r'\s*,\s*(?:and\s+)?(?:then\s+)?|\s+(?:and\s+)?then\s+|\s+and\s+(?=(?:'+verb+r')\b)', re.sub(r'^(?:and\s+)?(?:then\s+)?', '', rest.strip(' ,'), flags=re.I), flags=re.I):
        piece = piece.strip()
        if not piece:continue
        m = re.fullmatch(r'('+verb+r') ('+NUM+r')(?: more)?(?: ('+NOUNP+r'))?(?: to ('+ENTITY+r'))?', piece, re.I)
        if not m:return [text]
        v, n, explicit, recipient = m.groups()
        if re.fullmatch(GIVE, v, re.I) and not recipient:return [text]
        if explicit:last = explicit
        clauses.append(_event(who, v, n, last, recipient))
    return clauses


@dataclass
class Node:
    op: str
    args: tuple
    span: tuple
    label: str


class Graph:
    def __init__(self, source):
        self.source, self.nodes, self.initial, self.current = source, [], {}, {}
        self.rates, self.prices, self.transactions, self.purchases = [], {}, {}, {}
        self.facts, self.events, self.cache, self.stack, self.trace = [], [], {}, set(), set()
        self.event_owners = set()
        self.links, self.closures, self.consistency_checks = {}, {}, []

    def add(self, op, args, span, label):
        if len(self.nodes) >= 180:raise Unclear('Quantity graph exceeds its node budget.')
        self.nodes.append(Node(op, tuple(args), span, label))
        index=len(self.nodes)-1
        self.links[index]=list(args[:2]) if op in ('add','subtract','multiply') else [args[0]] if op in ('recount','cost') else []
        return index

    def constant(self, value, unit, span):return self.add('constant', (value, unit), span, 'literal')

    def initial_ref(self, owner, item, span):return self.add('initial', (owner, item), span, 'initial quantity dependency')

    def combine(self, op, left, right, span):return self.add(op, (left, right), span, op)

    def define(self, owner, item, node):
        if owner in self.event_owners:
            raise Unclear('An initial quantity is stated after that owner already acted; clarify its time.')
        key = owner, item
        if key in self.initial:
            raise Unclear('Repeated or conflicting initial quantities for '+owner+'; clarify whether they are separate groups.')
        self.initial[key] = self.current[key] = node

    def parse(self, text, span):
        text = re.sub(r'(?i)^(?:facts|given|context|scenario)\s*:\s*', '', text)
        for clause in expand(text):self.parse_one(clause, span)

    def parse_one(self, text, span):
        text = re.sub(r'(?i)^(?:initially|at first),?\s+', '', text)
        relation = re.fullmatch(r'('+ENTITY+r') (?:has|have|holds|owns) ('+NUM+r') (more|fewer|less) (.+?) than ('+ENTITY+r')', text, re.I)
        if relation:
            who, amount, comparison, noun, other = relation.groups()
            item = spec(noun)
            value = self.constant(number(amount)*item.scale, item.unit, span)
            dependency = self.initial_ref(other.casefold(), item, span)
            self.define(who.casefold(), item, self.combine('add' if comparison.lower()=='more' else 'subtract', dependency, value, span))
            return
        ratio = re.fullmatch(r'('+ENTITY+r') (?:has|have|holds|owns) (twice|double|half|'+NUM+r' times) as (?:many|much) (.+?) as ('+ENTITY+r')', text, re.I)
        if ratio:
            who, factor, noun, other = ratio.groups()
            item = spec(noun)
            multiplier = {'twice':Fraction(2), 'double':Fraction(2), 'half':Fraction(1,2)}.get(factor.lower())
            if multiplier is None:multiplier = number(re.sub(r'(?i) times$', '', factor))
            dependency = self.initial_ref(other.casefold(), item, span)
            self.define(who.casefold(), item, self.combine('multiply', dependency, self.constant(multiplier, (), span), span))
            return
        grouping = re.fullmatch(r'(?:Each|Every) (.+?) (?:contains|holds|weighs) ('+NUM+r') (.+)', text, re.I)
        if grouping:
            container, amount, contents = grouping.groups()
            first, last = spec(container), spec(contents)
            if first.head == last.head or not first.unit[0][0].startswith('item:'):
                raise Unclear('A group conversion needs different explicit container and content types.')
            if any(a==first and b==last for a,b,_ in self.rates):
                raise Unclear('Repeated or conflicting group conversion.')
            if number(amount)<0:raise Unclear('A container cannot have a negative quantity of contents.')
            rate = self.constant(number(amount)*last.scale/first.scale, product_unit(last.unit, inverse(first.unit)), span)
            self.rates.append((first, last, rate))
            return
        pricing = re.fullmatch(r'(?:Each|Every) (.+?) costs? ('+NUM+r') (dollars?|euros?|USD|EUR)', text, re.I)
        if pricing:
            noun, amount, currency = pricing.groups()
            item, money = spec(noun), spec(currency)
            if item in self.prices:raise Unclear('Repeated or conflicting unit prices; specify the transaction time.')
            if number(amount)<0:raise Unclear('Specify a nonnegative purchase price or an explicit refund event.')
            self.prices[item] = self.constant(number(amount), product_unit(money.unit, inverse(item.unit)), span)
            return
        transfer = re.fullmatch(r'('+ENTITY+r') (?:gives|gave|hands) ('+NUM+r') (.+?) to ('+ENTITY+r')', text, re.I)
        if transfer:
            who, amount, noun, recipient = transfer.groups()
            self.events.append(('transfer', who.casefold(), spec(noun), number(amount), recipient.casefold(), span))
            self.event_owners.update((who.casefold(), recipient.casefold()))
            return
        purchase = re.fullmatch(r'('+ENTITY+r') (?:buys|bought|purchases|purchased) ('+NUM+r') (.+?)(?: at ('+NUM+r') (dollars?|euros?|USD|EUR) each)?', text, re.I)
        if purchase:
            who, amount, noun, price, currency = purchase.groups()
            if price and number(price)<0:raise Unclear('Specify a nonnegative purchase price or an explicit refund event.')
            self.events.append(('purchase', who.casefold(), spec(noun), number(amount), (number(price),spec(currency)) if price else None, span))
            self.event_owners.add(who.casefold())
            return
        event = re.fullmatch(r'('+ENTITY+r') (loses|lost|spends|spent|sells|sold|uses|used|receives|received|gets|got) ('+NUM+r') (.+)', text, re.I)
        if event:
            who, action, amount, noun = event.groups()
            item = spec(noun)
            self.events.append((action.lower(), who.casefold(), item, number(amount), None, span))
            self.event_owners.add(who.casefold())
            return
        base = re.fullmatch(r'('+ENTITY+r') (?:has|have|holds|owns|starts with) (.+)', text, re.I)
        if base:
            who, body = base.groups()
            pieces = re.split(r'\s+and\s+(?='+NUM+r'\s)', body, flags=re.I)
            for piece in pieces:
                literal = re.fullmatch(r'('+NUM+r') (.+)', piece, re.I)
                if not literal:raise Unclear('The complete initial quantity was not understood: '+piece+'.')
                item, value = spec(literal[2]), number(literal[1])
                if item.head.startswith('*'):raise Unclear('Initial quantities need a specific unit or commodity.')
                self.define(who.casefold(), item, self.constant(value*item.scale, item.unit, span))
            return
        raise Unclear('Unsupported complete clause: '+text+'. No clause was discarded.')

    def update(self, who, item, delta, sign, span):
        key = who, item
        prior = self.current.get(key)
        if prior is None:prior = self.initial_ref(who, item, span)
        self.current[key] = self.combine('add' if sign>0 else 'subtract', prior, delta, span)
        # A known total includes a changed explicit subgroup. Conversely, an
        # unqualified change does not establish which subgroup changed.
        for (owner,other),old in list(self.current.items()):
            if owner!=who or other==item or other.unit!=item.unit:continue
            if set(other.attributes) < set(item.attributes):
                self.current[(owner,other)]=self.combine('add' if sign>0 else 'subtract',old,delta,span)
            elif set(item.attributes) < set(other.attributes):
                self.current[(owner,other)]=self.add('missing',('The event does not establish the changed amount for subgroup '+other.label+'.',),span,'unknown subgroup change')

    def price(self, item):
        options = [node for chosen,node in self.prices.items() if compatible(item, chosen)]
        if len(options) != 1:raise Missing('A unique applicable unit price is missing or ambiguous for '+item.label+'.')
        return options[0]

    def apply_events(self):
        for action, who, item, amount, extra, span in self.events:
            if amount < 0:raise Unclear('Event quantities must be nonnegative; use the stated event direction.')
            value = self.constant(amount*item.scale, item.unit, span)
            if action == 'transfer':
                if extra == who:raise Unclear('A transfer to the same owner needs clarification.')
                self.update(who,item,value,-1,span)
                self.update(extra,item,value,1,span)
            elif action == 'purchase':
                self.purchases.setdefault(who,[]).append((item,value))
                self.update(who,item,value,1,span)
                if extra:
                    price, currency = extra
                    rate = self.constant(price*currency.scale/item.scale,product_unit(currency.unit,inverse(item.unit)),span)
                    cost = self.combine('multiply',value,rate,span)
                else:
                    cost = self.add('cost', (value,item), span, 'quantity times applicable unit price')
                self.transactions.setdefault(who,[]).append(cost)
                cash = [(chosen,node) for (owner,chosen),node in list(self.current.items()) if owner==who and chosen.head.startswith('money:')]
                for chosen,prior in cash:
                    self.current[(who,chosen)] = self.add('cash_after_purchase',(prior,cost,chosen),span,'purchase cash dependency')
                if cash:
                    try:
                        _,currency_unit,_=self.value(cost)
                    except Missing:currency_unit=None
                    if currency_unit and all(chosen.unit!=currency_unit for chosen,_ in cash):
                        currency=currency_unit[0][0].split(':',1)[-1]
                        unknown=Spec('money:'+currency,(),currency_unit,Fraction(1),currency)
                        self.current[(who,unknown)]=self.add('missing',('The starting balance in '+currency+' is not stated.',),span,'unknown other-currency cash flow')
            else:
                sign = 1 if action in ('receives','received','gets','got') else -1
                self.update(who,item,value,sign,span)
                if action in ('spends','spent') and item.head.startswith('money:'):
                    self.transactions.setdefault(who,[]).append(value)
                # A sale without a price cannot justify unchanged cash.
                if action in ('sells','sold'):
                    for (owner,chosen),prior in list(self.current.items()):
                        if owner==who and chosen.head.startswith('money:'):
                            self.current[(owner,chosen)] = self.add('missing',('Sale proceeds are not stated.',),span,'unknown cash flow')

    def disjoint(self, specs):
        if len(specs) <= 1:return True
        for i, first in enumerate(specs):
            for other in specs[i+1:]:
                if first.unit != other.unit:continue
                a,b = set(first.attributes),set(other.attributes)
                if not ((a & COLORS and b & COLORS and a & COLORS != b & COLORS) or
                        (a & MATERIALS and b & MATERIALS and a & MATERIALS != b & MATERIALS)):
                    raise Unclear('The counted groups may overlap; specify separate quantities or one total.')
        return True

    def select(self, mapping, who, asked, span, allow_groups=True):
        entries = [(item,node) for (owner,item),node in mapping.items() if owner==who]
        if asked.head == '*money':
            entries = [(item,node) for item,node in entries if item.head.startswith('money:')]
            if not entries:raise Missing('The starting money/currency is not stated for '+who+'.')
            if len({item.unit for item,_ in entries})!=1:raise Unclear('Currencies are incompatible; no exchange rate was stated.')
            return self.sum_nodes([n for _,n in entries],span)
        if asked.head == '*items':
            entries = [(item,node) for item,node in entries if len(item.unit)==1 and item.unit[0][0].startswith('item:')]
            if not entries:raise Missing('No explicit counted items are stated for '+who+'.')
            if any(compatible(item,a) for item,_ in entries for a,_,_ in self.rates):
                raise Unclear('Specify which level of containers/contents counts as an item.')
            entries=[(item,node) for item,node in entries if not any(other.unit==item.unit and set(other.attributes)<set(item.attributes) for other,_ in entries)]
            self.disjoint([i for i,_ in entries])
            values = [self.add('recount',(node,),span,'explicit generic item count') for _,node in entries]
            return self.sum_nodes(values,span)
        paths=[]
        direct=[(item,node) for item,node in entries if compatible(item,asked)]
        # An explicit broad total is not a separate group to add to its parts.
        broad=[(item,node) for item,node in direct if item.attributes==asked.attributes]
        if len(broad)==1:
            total=self.value(broad[0][1])
            for part,node in direct:
                if part.attributes!=asked.attributes:
                    try:known=self.value(node)
                    except Missing:continue
                    if known[0]>total[0]:raise Unclear('A stated subgroup exceeds its explicit total; check the quantities.')
                    self.consistency_checks.append(dict(kind='subgroup_within_total',subgroup=str(known[0]),total=str(total[0])))
            return broad[0][1]
        for item,node in entries:
            if compatible(item, asked):paths.append((item,node))
            elif allow_groups:
                found=self.convert(item,node,asked,span,(),0)
                if len(found)>1:raise Unclear('There are multiple container paths; clarify whether their contents are separate or overlapping.')
                paths.extend(found)
        if not paths:raise Missing('The complete quantity dependency is missing for '+who+' and '+asked.label+'.')
        if any(i.head != asked.head for i,_ in paths) and len(paths)>1:
            raise Unclear('Direct and contained quantities may overlap; specify separate groups.')
        self.disjoint([i for i,_ in paths])
        return self.sum_nodes([node for _,node in paths],span)

    def convert(self, item, node, asked, span, visited, depth):
        if depth>=6 or item in visited:return []
        found=[]
        for start,end,rate in self.rates:
            if not compatible(item,start):continue
            converted=self.combine('multiply',node,rate,span)
            if compatible(end,asked):found.append((item,converted))
            else:found.extend(self.convert(end,converted,asked,span,visited+(item,),depth+1))
        return found

    def sum_nodes(self, nodes, span):
        if not nodes:raise Missing('No quantities establish that total.')
        total=nodes[0]
        for node in nodes[1:]:total=self.combine('add',total,node,span)
        return total

    def value(self, index):
        if index in self.cache:
            self.trace.update(self.closures[index])
            return self.cache[index]
        if index in self.stack:raise Unclear('The quantity dependencies form a cycle; no starting quantity is established.')
        if len(self.stack)>20:raise Unclear('Quantity dependency depth exceeds the bound.')
        self.stack.add(index)
        self.trace.add(index)
        node=self.nodes[index]
        try:
            if node.op=='constant':
                value,unit=node.args
                result=(value,unit,str(value))
            elif node.op=='initial':
                who,item=node.args
                candidates=[(other,n) for (owner,other),n in self.initial.items() if owner==who and compatible(other,item)]
                if not candidates:raise Missing('The initial quantity is not stated for '+who+' and '+item.label+'.')
                self.disjoint([i for i,_ in candidates])
                selected=self.sum_nodes([n for _,n in candidates],node.span)
                self.links[index]=[selected]
                result=self.value(selected)
            elif node.op in ('add','subtract','multiply'):
                left,right=map(self.value,node.args)
                if node.op!='multiply' and left[1]!=right[1]:raise Unclear('Incompatible units in a required quantity dependency.')
                op={'add':'+','subtract':'-','multiply':'*'}[node.op]
                amount=left[0]+right[0] if op=='+' else left[0]-right[0] if op=='-' else left[0]*right[0]
                unit=product_unit(left[1],right[1]) if op=='*' else left[1]
                result=(amount,unit,'('+left[2]+')'+op+'('+right[2]+')')
            elif node.op=='recount':
                amount,_,expression=self.value(node.args[0])
                result=(amount,(('item:*',1),),expression)
            elif node.op=='cost':
                count,item=node.args
                computed=self.combine('multiply',count,self.price(item),node.span)
                self.links[index]=[computed]
                result=self.value(computed)
            elif node.op=='cash_after_purchase':
                prior,cost,currency=node.args
                before,spent=self.value(prior),self.value(cost)
                computed=self.combine('subtract',prior,cost,node.span) if spent[1]==currency.unit else prior
                self.links[index]=[computed]
                result=self.value(computed)
            elif node.op=='missing':raise Missing(node.args[0])
            else:raise Unclear('Unsupported internal quantity operation.')
            if abs(result[0])>10**30 or result[0].denominator>10**12:raise Unclear('Exact result exceeds the resource bound.')
            self.cache[index]=result
            self.closures[index]={index}.union(*(self.closures.get(child,{child}) for child in self.links[index]))
            return result
        finally:self.stack.remove(index)

    def solve(self, question, qspan):
        self.apply_events()
        # Reject known impossible inventories anywhere in the supplied facts,
        # but do not invent unrelated missing starting states.
        for (who,item),node in self.current.items():
            try:value,unit,_=self.value(node)
            except Missing:continue
            if value<0 and not item.head.startswith('money:'):
                raise Unclear('The stated events produce a negative inventory for '+who+'; check the quantities.')
        self.trace=set()
        totals=[]
        for who in question['owners']:
            if question['kind']=='stock':totals.append(self.select(self.current,who,question['asked'],qspan))
            elif question['kind']=='bought':
                options=[(i,n) for i,n in self.purchases.get(who,[]) if compatible(i,question['asked'])]
                if not options:raise Missing('No matching purchases are stated for '+who+'.')
                totals.append(self.sum_nodes([n for _,n in options],qspan))
            else:totals.append(self.sum_nodes(self.transactions.get(who,[]),qspan))
        total=self.sum_nodes(totals,qspan)
        amount,unit,expression=self.value(total)
        asked=question.get('asked')
        if asked is not None and not asked.head.startswith('*'):
            if unit!=asked.unit:raise Unclear('The established quantity has a different unit than the question.')
            amount/=asked.scale
            if asked.scale!=1:expression='('+expression+')/('+str(asked.scale)+')'
        if question['kind']=='cost' and not (len(unit)==1 and unit[0][0].startswith('currency:')):
            raise Unclear('The established spending total lacks one consistent currency.')
        computation=calculate('What is '+expression+'?')
        if not computation or not computation.get('exact'):raise Unclear('The independent exact arithmetic checker cannot verify this graph size.')
        try:
            checked=check_arithmetic('What is '+expression+'?',computation)
            numeric=Fraction(computation['response'].rsplit(' = ',1)[-1])
        except (Unchecked,ValueError,ZeroDivisionError):raise Unclear('Independent arithmetic verification did not establish the result.')
        if numeric!=amount or checked['status']!='verified':raise Unclear('Independent arithmetic disagrees with the quantity graph.')
        used=sorted(self.trace)
        proof=dict(value=str(amount),unit=asked.label if asked else unit[0][0].split(':',1)[-1],
            expression=expression,arithmetic_check=checked,parsed_facts=self.facts,
            dependencies=[dict(id=i,operation=self.nodes[i].op,span=list(self.nodes[i].span),
                source=self.source[slice(*self.nodes[i].span)],dependencies=self.links[i]) for i in used],
            whole_clauses_consumed=True,initial_states_not_assumed_zero=True,consistency_checks=self.consistency_checks)
        return amount,proof


def problem(text):
    if not isinstance(text,str) or not 0<len(text)<=6000 or any(marker in text for marker in ('```','>>>','"""',"'''")):
        return None
    if re.search(r'(?m)^\s*(?:\([A-Z]\)|[A-Z][.)])\s',text):return None
    parts=segments(text)
    if not 2<=len(parts)<=18:return None
    body=parts[:-1]
    if not any(re.search(r'(?i)\b(?:has|have|holds|owns|starts with|each|every|buys|bought|purchases|purchased|receives|received|loses|lost)\b',clause) and re.search(r'\b(?:'+NUM+r'|twice|double)\b',clause,re.I) for clause,_ in body):
        return None
    return parts


def interested(text):
    parts=problem(text)
    question=re.sub(r'(?i)^(?:question|query)\s*:\s*', '', parts[-1][0]) if parts else ''
    return bool(parts and re.match(r'(?i)^(?:how (?:many|much)|what is .+? (?:total|remaining))\b',question))


def reply(text):
    parts=problem(text)
    if not parts:return None
    graph=Graph(text)
    try:
        question=query(parts[-1][0])
        if question is None:return None
        for clause,span in parts[:-1]:
            graph.parse(clause,span)
            graph.facts.append(dict(span=list(span),source=text[slice(*span)],parsed=True))
        amount,proof=graph.solve(question,parts[-1][1])
    except (Unclear,ValueError,TypeError,ZeroDivisionError,RecursionError) as error:
        return dict(route='helper/quantity-graph-clarify',response=str(error),sources=[],
            details='The governing quantity question stayed local. No complete numerical result was claimed; unknown clauses/units/dependencies were not dropped.')
    return dict(route='helper/quantity-graph',response=str(amount)+'\n\nQuantity: '+proof['unit']+'.',sources=[],exact=True,
        details='Built a source-linked quantity/event dependency graph from every complete supported clause; retained owners, units, starting states, transactions and group conversions. '
                'The numerical expression passed the existing independent exact arithmetic checker. Finite symbolic grammar, not proof of arbitrary-language understanding; no neural model, native generated code or external lookup.',
        quantity_graph=proof)


def routed_reply(text):
    # Preserve the older whole-frame groups solver and its structured output.
    # A graph can still solve a complete multi-clause problem beyond that frame.
    from .helper_groups import solve as groups_reply
    grouped=groups_reply(text)
    if grouped is not None and grouped.get('exact'):return grouped
    answer=reply(text)
    if answer is not None and not answer.get('exact') and grouped is not None:return grouped
    return answer


def choice_reply(context, options):
    if not 2<=len(options)<=8 or not all(re.fullmatch(r'[+-]?\d+(?:\.\d+)?(?:/\d+)?',option.strip()) for option in options):return None
    answer=routed_reply(context)
    if not answer:return None
    if not answer.get('exact'):
        return dict(answer,route='chat/choice-quantity-clarify')
    try:
        expected=Fraction(answer.get('quantity_graph',answer.get('helper_reasoning',{}))['value'])
        matches=[i for i,option in enumerate(options) if Fraction(option.strip())==expected]
    except (ValueError,ZeroDivisionError):return None
    if len(matches)!=1:
        return dict(answer,route='chat/choice-quantity-clarify',exact=False,response='The checked quantity is '+str(expected)+', but no unique option matches it. Please check the choices.')
    index=matches[0]
    return dict(answer,route='chat/choice-helper-quantity-graph',choice=index,response='ABCDEFGH'[index]+'. '+options[index])
