"""Source-linked typed numerical relations, with a deliberately finite grammar.

Units, actors, actions and temporal bases are explicit; all clauses must parse.
No answer corpus, lexical template ranker, external model, native generated code
or persistent request state is used. Arithmetic verification checks the program,
not an assertion of arbitrary English understanding.
"""
from dataclasses import dataclass
from fractions import Fraction
import re

from .quantity_graph import (NUM, Unclear, Missing, compatible, inverse, number,
                             product_unit, segments, spec)
from .helper import calculate
from .verify import Unchecked, check_arithmetic

ACTOR = r'(?:(?:a|an|the)\s+)?[A-Za-z][A-Za-z0-9_-]{0,30}'
CURRENCY = r'(?:dollars?|euros?|USD|EUR)'
TIME = r'(?:seconds?|minutes?|hours?)'
ACTIONS = {'produces':'produce','prints':'print','delivers':'deliver','processes':'process',
           'assembles':'assemble','travels':'travel','makes':'make'}
ACTION = '(?:'+'|'.join(ACTIONS)+')'
ROOT_ACTION = '(?:'+'|'.join(ACTIONS.values())+')'
PRONOUNS = {'he','she','it','they','his','her','its','their'}
POSSESSOR = r"(?:its|his|her|their|the|"+ACTOR+r"'s)"


def interested(text):
    if not isinstance(text,str) or not 0<len(text)<=6000:return False
    if any(x in text for x in ('```','>>>','"')) or text.lstrip().startswith("'"):return False
    if re.search(r'(?i)\b(?:python|javascript|docstring|quoted|sentence|phrase|story)\b',text):return False
    if re.search(r'(?m)^\s*(?:\([A-Z]\)|[A-Z][.)])\s',text):return False
    # The established whole-frame rate helper keeps its exact contracts/routes,
    # including its negative and unsupported forms.
    if re.search(r'(?i)\bat (?:a|an) (?:(?:constant|average|variable|changing) )?(?:rate|speed) of\b',text):return False
    parts=segments(text)
    if not 2<=len(parts)<=16 or not re.match(r'(?i)^(?:how (?:many|much)|what is)\b',parts[-1][0]):return False
    return bool(re.search(r'(?i)\bpercent\b|%|\b(?:profit|revenue)\b|\bper (?:second|minute|hour)\b|'
                         r'\b\d+/\d+ of\b|\b(?:she|he|it|they) (?:buys|purchases)\b',text))


def actor_name(text):
    return re.sub(r'(?i)^(?:a|an|the)\s+','',text.strip()).casefold()


def item(text):
    # Do not let a noun slot swallow an unsupported event/condition/qualifier.
    if re.search(r'(?i)\b(?:not|unless|except|if|while|because|but|and|or|at|per|for|from|to|'
                 r'costs?|sells?|buys?|owes?|discount|tax|fee|original|remaining|whole|complete)\b',text):
        raise Unclear('An item/unit slot contains an unsupported clause or modifier: '+text+'.')
    value=spec(text)
    if value.head.startswith('*'):raise Unclear('State a specific item or measurement unit.')
    return value


@dataclass(frozen=True)
class Node:
    value: Fraction
    unit: tuple
    expression: str
    operation: str
    children: tuple
    span: tuple


class Plan:
    def __init__(self,source,clauses):
        self.source=source;self.nodes=[];self.facts=[];self.bindings=[]
        self.stocks={};self.original={};self.rates={};self.durations={}
        self.costs={};self.prices={};self.sales=[];self.price_levels={};self.acted=set();self.unresolved_cash=set()
        self.actors=set()
        for clause,_ in clauses:
            clause=re.sub(r'(?i)^then\s+','',clause)
            match=re.match(r'('+ACTOR+r') (?:has|holds|owns|starts with|contains|'+ACTION+
                           r'|works|runs|uses|loses|gains|buys|purchases|sells|costs)\b',clause,re.I)
            if match and actor_name(match[1]) not in PRONOUNS:self.actors.add(actor_name(match[1]))
            part=re.fullmatch(r'('+NUM+r') of ('+ACTOR+r') is ('+NUM+r') (.+)',clause,re.I)
            if part:self.actors.add(actor_name(part[2]))

    def resolve(self,label,span):
        key=actor_name(label)
        if key in PRONOUNS or key=='the':
            if len(self.actors)!=1:raise Unclear('A pronoun/reference has more than one or no explicit antecedent. Use the owner name.')
            key=next(iter(self.actors))
            self.bindings.append(dict(span=list(span),reference=label,owner=key,candidates=sorted(self.actors)))
        if key not in self.actors:raise Missing('The requested owner or machine is not established: '+label+'.')
        return key

    def add(self,value,unit,expression,operation,children,span):
        value=Fraction(value)
        if len(self.nodes)>=160 or abs(value)>10**30 or value.denominator>10**12:
            raise Unclear('The exact numerical plan exceeds its bounded resources.')
        self.nodes.append(Node(value,unit,expression,operation,tuple(children),span))
        return len(self.nodes)-1

    def literal(self,value,unit,span):
        value=Fraction(value)
        return self.add(value,unit,str(value),'literal',(),span)

    def quantity(self,value,unit_text,span,whole=True):
        chosen=item(unit_text);amount=number(value)
        if amount<0:raise Unclear('A rate, duration, price or quantity must be nonnegative; state the event direction.')
        if whole:self.whole(amount,chosen.unit)
        return chosen,self.literal(amount*chosen.scale,chosen.unit,span)

    def op(self,operation,left,right,span):
        a,b=self.nodes[left],self.nodes[right]
        if operation in ('add','subtract'):
            if a.unit!=b.unit:raise Unclear('Required quantities have different items, units or currencies.')
            value=a.value+b.value if operation=='add' else a.value-b.value;unit=a.unit
        elif operation=='multiply':value=a.value*b.value;unit=product_unit(a.unit,b.unit)
        elif operation=='divide':
            if b.value==0:raise Unclear('A required rate or fraction denominator is zero.')
            value=a.value/b.value;unit=product_unit(a.unit,inverse(b.unit))
        else:raise Unclear('Unsupported numerical operation.')
        symbol={'add':'+','subtract':'-','multiply':'*','divide':'/'}[operation]
        return self.add(value,unit,'('+a.expression+')'+symbol+'('+b.expression+')',operation,(left,right),span)

    @staticmethod
    def whole(value,unit):
        if len(unit)==1 and unit[0][0].startswith('item:') and unit[0][1]==1 and value.denominator!=1:
            raise Unclear('The stated relation gives a fractional whole item; clarify partial/completed-item rules. No rounding was assumed.')

    def define(self,owner,chosen,node):
        key=owner,chosen
        if key in self.stocks or owner in self.acted:raise Unclear('An initial amount is repeated or stated after an event. Clarify its time.')
        self.stocks[key]=self.original[key]=node

    def select(self,owner,chosen,original=False):
        if chosen.head.startswith('money:') and owner in self.unresolved_cash and not original:
            raise Missing('A sale changes this cash balance; specify when production costs were paid and how proceeds affect the balance, or ask for revenue/profit.')
        values=[(key,node) for key,node in (self.original if original else self.stocks).items()
                if key[0]==owner and compatible(key[1],chosen)]
        if len(values)!=1:raise Missing('A unique starting/current amount with that owner and unit is missing or ambiguous.')
        return values[0]

    def nonnegative(self,node):
        chosen=self.nodes[node]
        if chosen.value<0:raise Unclear('The declared event exceeds the available quantity/budget. No credit or negative inventory was assumed.')
        self.whole(chosen.value,chosen.unit)

    def parse(self,clause,span):
        clause=re.sub(r'(?i)^then\s+','',clause)
        match=re.fullmatch(r'('+ACTOR+r') ('+ACTION+r') ('+NUM+r') (.+?) per ('+TIME+r')(?: for ('+NUM+r') ('+TIME+r'))?',clause,re.I)
        if match:
            who,verb,amount,noun,base,duration,dunit=match.groups();who=self.resolve(who,span)
            chosen,node=self.quantity(amount,noun,span,whole=False);time,divisor=self.quantity('1',base,span)
            if time.unit!=(('time',1),) or chosen.unit==(('time',1),):raise Unclear('A production/movement rate needs quantity per time.')
            action=ACTIONS[verb.casefold()];key=who,action,chosen
            if action=='travel' and chosen.unit!=(('length',1),):raise Unclear('A travel rate must measure distance per time, not mass, money or item count.')
            if key in self.rates:raise Unclear('Repeated or changing rates need explicit time intervals.')
            self.rates[key]=self.op('divide',node,divisor,span)
            if duration:self.duration(who,duration,dunit,span)
            return 'quantity_per_time'
        match=re.fullmatch(r'('+ACTOR+r') (?:works|runs|travels) for ('+NUM+r') ('+TIME+r')',clause,re.I)
        if match:self.duration(self.resolve(match[1],span),match[2],match[3],span);return 'duration'
        match=re.fullmatch(r'(?:each|every) (.+?) (?:costs ('+NUM+r') ('+CURRENCY+r') to make|sells for ('+NUM+r') ('+CURRENCY+r'))',clause,re.I)
        if match:
            noun,cost,cunit,price,punit=match.groups();chosen=item(noun)
            _,money=self.quantity(cost or price,cunit or punit,span)
            one=self.literal(chosen.scale,chosen.unit,span)
            table=self.costs if cost is not None else self.prices
            if chosen in table:raise Unclear('Repeated unit prices/costs need an explicit transaction scope.')
            table[chosen]=self.op('divide',money,one,span)
            return 'manufacturing_unit_cost' if cost is not None else 'unit_sale_price'
        match=re.fullmatch(r'('+ACTOR+r') sells ('+NUM+r') (.+)',clause,re.I)
        if match:
            who=self.resolve(match[1],span);chosen,count=self.quantity(match[2],match[3],span)
            self.sales.append((who,chosen,count,span));self.acted.add(who)
            if any(owner==who and unit.head.startswith('money:') for owner,unit in self.stocks):
                self.unresolved_cash.add(who)
            existing=[(key,node) for key,node in self.stocks.items() if key[0]==who and compatible(key[1],chosen)]
            if len(existing)>1:raise Unclear('The sale has multiple possible inventory scopes.')
            if existing:
                key,prior=existing[0];new=self.op('subtract',prior,count,span);self.nonnegative(new);self.stocks[key]=new
            return 'quantity_sold'
        match=re.fullmatch(r'('+ACTOR+r') (?:buys|purchases) ('+NUM+r') (.+?) at ('+NUM+r') ('+CURRENCY+r') each',clause,re.I)
        if match:
            who=self.resolve(match[1],span);chosen,count=self.quantity(match[2],match[3],span)
            currency,price=self.quantity(match[4],match[5],span)
            cost=self.op('multiply',count,self.op('divide',price,self.literal(chosen.scale,chosen.unit,span),span),span)
            key,prior=self.select(who,currency);new=self.op('subtract',prior,cost,span);self.nonnegative(new)
            self.stocks[key]=new;self.acted.add(who)
            existing=[(key,node) for key,node in self.stocks.items() if key[0]==who and key[1].unit==chosen.unit]
            if len(existing)>1 or any(key[1].attributes!=chosen.attributes for key,_ in existing):
                raise Unclear('The purchase has ambiguous total/subgroup inventory scope.')
            if existing:
                key,prior=existing[0];new=self.op('add',prior,count,span);self.nonnegative(new);self.stocks[key]=new
            return 'purchase_from_explicit_budget'
        match=re.fullmatch(r'('+ACTOR+r') costs ('+NUM+r') ('+CURRENCY+r')',clause,re.I)
        if match:
            who=self.resolve(match[1],span);chosen,node=self.quantity(match[2],match[3],span)
            if who in self.price_levels:raise Unclear('The original price is repeated or conflicting.')
            self.price_levels[who]=(chosen,node,node)
            return 'original_price'
        match=re.fullmatch(r'('+POSSESSOR+r') price (increases|decreases) by ('+NUM+r') (?:percent|%)(?: of ('+POSSESSOR+r') original price)?',clause,re.I)
        if match:
            who=self.possessor(match[1],span)
            if who not in self.price_levels:raise Missing('The price before the change is not stated.')
            if match[4] and self.possessor(match[4],span)!=who:raise Unclear('The original-price reference names a different object.')
            chosen,prior,original=self.price_levels[who];ratio=number(match[3])/100
            if ratio<0 or (match[2].casefold()=='decreases' and ratio>1):raise Unclear('The percentage decrease must be between0 and100.')
            basis=original if match[4] else prior
            delta=self.op('multiply',basis,self.literal(ratio,(),span),span)
            new=self.op('add' if match[2].casefold()=='increases' else 'subtract',prior,delta,span);self.nonnegative(new)
            self.price_levels[who]=(chosen,new,original);self.acted.add(who)
            return 'percentage_price_change_original' if match[4] else 'percentage_price_change_current'
        match=re.fullmatch(r'('+ACTOR+r') (uses|loses|gains) ('+NUM+r') (percent\s+of|%\s+of|of) ('+POSSESSOR+r') (?:(remaining|original) )?(.+)',clause,re.I)
        if match:
            who=self.resolve(match[1],span)
            if self.possessor(match[5],span,who)!=who:raise Unclear('The event and fractional amount have different owners.')
            chosen=item(match[7]);key,prior=self.select(who,chosen)
            basis=self.original[key] if (match[6] or '').casefold()=='original' else prior
            ratio=number(match[3]);ratio=ratio/100 if match[4].casefold()!='of' else ratio
            if ratio<0 or (match[2].casefold()!='gains' and ratio>1):raise Unclear('The used/lost fraction must be between0 and1.')
            delta=self.op('multiply',basis,self.literal(ratio,(),span),span)
            new=self.op('add' if match[2].casefold()=='gains' else 'subtract',prior,delta,span);self.nonnegative(new)
            self.stocks[key]=new;self.acted.add(who)
            return 'relative_quantity_change'
        match=re.fullmatch(r'('+NUM+r') of ('+ACTOR+r') is ('+NUM+r') (.+)',clause,re.I)
        if match:
            factor=number(match[1])
            if not 0<factor<=1:raise Unclear('This part/whole reader supports fractions greater than 0 and at most 1. Restate multiples of a whole explicitly; no result was guessed.')
            who=self.resolve(match[2],span);chosen,part=self.quantity(match[3],match[4],span)
            total=self.op('divide',part,self.literal(factor,(),span),span);self.nonnegative(total);self.define(who,chosen,total)
            return 'part_to_whole'
        match=re.fullmatch(r'('+ACTOR+r') (?:has|holds|owns|starts with|contains) ('+NUM+r') (.+)',clause,re.I)
        if match:
            who=self.resolve(match[1],span);chosen,node=self.quantity(match[2],match[3],span)
            self.define(who,chosen,node);return 'initial_quantity'
        raise Unclear('Unsupported complete clause: '+clause+'. No clause or condition was discarded.')

    def duration(self,who,value,unit_text,span):
        chosen,node=self.quantity(value,unit_text,span)
        if chosen.unit!=(('time',1),):raise Unclear('The duration must have time units.')
        if who in self.durations:raise Unclear('Multiple durations need explicit, non-overlapping intervals.')
        self.durations[who]=node

    def possessor(self,label,span,subject=None):
        if label.casefold()=='the' and subject is not None:return subject
        return self.resolve(re.sub(r"(?i)'s$",'',label),span)

    def rate(self,who,verb,chosen):
        entries=[node for (owner,action,unit),node in self.rates.items()
                 if owner==who and action==verb.casefold() and compatible(unit,chosen)]
        if len(entries)!=1:raise Missing('One matching explicit actor/action/item rate is required.')
        return entries[0]

    def sale_total(self,who,profit,span):
        nodes=[]
        for owner,chosen,count,event_span in self.sales:
            if owner!=who:continue
            prices=[node for unit,node in self.prices.items() if compatible(chosen,unit)]
            costs=[node for unit,node in self.costs.items() if compatible(chosen,unit)]
            if len(prices)!=1 or (profit and len(costs)!=1):raise Missing('A unique matching sale price and, for profit, manufacturing cost are required.')
            rate=self.op('subtract',prices[0],costs[0],span) if profit else prices[0]
            nodes.append(self.op('multiply',count,rate,event_span))
        if not nodes:raise Missing('No matching quantity sold was stated.')
        total=nodes[0]
        for node in nodes[1:]:total=self.op('add',total,node,span)
        return total

    def solve(self,question,span):
        match=re.fullmatch(r'How (?:many|much) (?:complete |whole )?(.+?) (?:does|did|do) ('+ACTOR+r') ('+ROOT_ACTION+r')(?: in total)?',question,re.I)
        if match:
            chosen=item(match[1]);who=self.resolve(match[2],span);rate=self.rate(who,match[3],chosen)
            if who not in self.durations:raise Missing('The explicit operating duration is missing; no working-day hours were assumed.')
            return self.op('multiply',rate,self.durations[who],span),chosen
        match=re.fullmatch(r'How many ('+TIME+r') (?:does|did|do) ('+ACTOR+r') (?:need|take) to ('+ROOT_ACTION+r') ('+NUM+r') (.+)',question,re.I)
        if match:
            who=self.resolve(match[2],span);chosen,target=self.quantity(match[4],match[5],span)
            if who in self.durations:raise Unclear('A duration and a target were both supplied; clarify the interval being asked about.')
            return self.op('divide',target,self.rate(who,match[3],chosen),span),item(match[1])
        match=re.fullmatch(r'How much (profit|revenue) (?:does|did) ('+ACTOR+r') (?:earn|make)',question,re.I)
        if match:
            result=self.sale_total(self.resolve(match[2],span),match[1].casefold()=='profit',span)
            return result,None
        match=re.fullmatch(r"What is ("+ACTOR+r")'s (profit|revenue)",question,re.I)
        if match:return self.sale_total(self.resolve(match[1],span),match[2].casefold()=='profit',span),None
        match=re.fullmatch(r'What is ('+POSSESSOR+r') final price in ('+CURRENCY+r')',question,re.I)
        if match:
            who=self.possessor(match[1],span)
            if who not in self.price_levels:raise Missing('The requested price is not established.')
            return self.price_levels[who][1],item(match[2])
        match=re.fullmatch(r'How (?:many|much) (?:whole |complete )?(.+?) (?:does|do) ('+ACTOR+r') have(?: left| now| remaining)?',question,re.I)
        if match:
            who=self.resolve(match[2],span)
            if match[1].casefold()=='money':
                if who in self.unresolved_cash:raise Missing('The timing of sale proceeds and production costs is not established for this cash balance.')
                choices=[(key,node) for key,node in self.stocks.items() if key[0]==who and key[1].head.startswith('money:')]
                if len(choices)!=1:raise Missing('A unique current currency/balance is missing.')
                return choices[0][1],choices[0][0][1]
            chosen=item(match[1]);return self.select(who,chosen)[1],chosen
        match=re.fullmatch(r'How many (.+?) (?:remain in|are in the whole) ('+ACTOR+r')',question,re.I)
        if match:
            chosen=item(match[1]);return self.select(self.resolve(match[2],span),chosen)[1],chosen
        raise Unclear('The complete numerical query is outside the supported owner/action/unit grammar.')

    def answer(self,root,chosen,qspan):
        node=self.nodes[root];amount=node.value;expression=node.expression
        if chosen is not None:
            if chosen.unit!=node.unit:raise Unclear('The requested unit/item/currency differs from the established result.')
            amount/=chosen.scale
            if chosen.scale!=1:expression='('+expression+')/('+str(chosen.scale)+')'
            label=chosen.label
        else:
            if len(node.unit)!=1 or not node.unit[0][0].startswith('currency:'):raise Unclear('The financial total lacks a single consistent currency.')
            label=node.unit[0][0].split(':',1)[1]
        self.whole(amount,node.unit)
        arithmetic=calculate('What is '+expression+'?')
        if not arithmetic or not arithmetic.get('exact'):raise Unclear('Independent exact arithmetic could not verify the complete program.')
        check=check_arithmetic('What is '+expression+'?',arithmetic)
        if check['status']!='verified' or Fraction(arithmetic['response'].rsplit(' = ',1)[-1])!=amount:
            raise Unclear('The two exact arithmetic evaluations disagree.')
        used=set()
        def visit(index):
            if index in used:return
            used.add(index)
            for child in self.nodes[index].children:visit(child)
        visit(root)
        return dict(route='helper/semantic-quantities',response=str(amount)+'\n\nQuantity: '+label+'.',sources=[],exact=True,
            details='Complete finite owner/action/unit/time relations with source coverage and independently checked rational arithmetic. Unsupported context is clarified. No claim of arbitrary English understanding.',
            semantic_quantities=dict(value=str(amount),unit=label,expression=expression,arithmetic_check=check,
                whole_clauses_consumed=True,starting_balances_not_assumed_zero=True,clauses=self.facts,reference_bindings=self.bindings,
                nodes=[dict(id=i,value=str(n.value),unit=list(n.unit),operation=n.operation,dependencies=list(n.children),
                            span=list(n.span),source=self.source[slice(*n.span)],used_for_answer=i in used) for i,n in enumerate(self.nodes)]))


def reply(text):
    if not interested(text):return None
    parts=segments(text);plan=Plan(text,parts[:-1])
    try:
        for clause,span in parts[:-1]:
            relation=plan.parse(clause,span)
            plan.facts.append(dict(span=list(span),source=text[slice(*span)],relation=relation))
        root,chosen=plan.solve(parts[-1][0],parts[-1][1])
        return plan.answer(root,chosen,parts[-1][1])
    except (Unclear,Unchecked,ValueError,TypeError,ZeroDivisionError,RecursionError) as error:
        return dict(route='helper/semantic-quantities-clarify',response=str(error),sources=[],
            details='No numerical answer asserted. The complete supplied relations, actor references, units, conditions and query must be established.')
