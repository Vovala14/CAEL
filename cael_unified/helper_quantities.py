"""Typed quantity-event automaton for explicit chat word problems.

Only complete recognised clauses execute. Unknown inventories stay unknown;
transfers debit the giver and credit the recipient. No model, eval or network.
"""
from fractions import Fraction
import re

N=r'(?:\d{1,8}(?:\.\d{1,4})?)'
A=r"(?:[A-Za-z][A-Za-z'\-]{0,30})"
U=r'(?:[A-Za-z]+(?:\s+[A-Za-z]+)?)'
STOCK=r'(?:has|had|have|owns|owned|starts? with|started with)'
ADD=r'(?:buys?|bought|finds?|found|receives?|received|gets?|got|gains?|gained|collects?|collected|picks? up|picked up|adds?|added)'
SUB=r'(?:loses?|lost|eats?|ate|uses?|used|removes?|removed|drops?|dropped|gives? away|gave away|sells?|sold|donates?|donated|spends?|spent)'
TRANSFER=r'(?:gives?|gave|sends?|sent|hands?|handed)'
VERBS='(?:'+STOCK+'|'+ADD+'|'+SUB+'|'+TRANSFER+')'
WHY=re.compile(r'(?i)^\s*(?:why|explain(?: that| this| your answer| the answer)?|show(?: me)? (?:the )?(?:steps|working))[?.!]*\s*$')


class Unclear(ValueError):pass


def fmt(value):return str(value.numerator) if value.denominator==1 else str(value)


def unit_key(unit):
    words=unit.lower().split()
    last=words[-1]
    irregular={'people':'person','children':'child','feet':'foot','mice':'mouse','buses':'bus'}
    if last in irregular:last=irregular[last]
    elif last.endswith('ies') and len(last)>3:last=last[:-3]+'y'
    elif last.endswith(('ches','shes','xes','sses')):last=last[:-2]
    elif last.endswith('s') and not last.endswith(('ss','us')):last=last[:-1]
    return ' '.join(words[:-1]+[last])


def split_question(text):
    matches=list(re.finditer(r'(?i)\bhow (?:many|much)\b',text))
    if len(matches)!=1:return None
    m=matches[0]
    context=re.sub(r'(?i)(?:question|query)\s*:\s*$','',text[:m.start()])
    return context.strip(' .;\n:'),text[m.start():].strip(' .?\n')


class Inventory:
    def __init__(self):
        self.values={};self.names={};self.units={};self.steps=[];self.last_actor=None;self.events_started=False

    def actor(self,name):
        key=name.lower()
        if key in ('away','then','more','less','fewer','to','from','and','or','each','every','someone','somebody','nobody'):
            raise Unclear('Use an explicit name for each person in the quantity events.')
        if key in ('he','she','they','him','her','them'):
            if len(self.names)!=1:raise Unclear('Use an explicit name; that pronoun could refer to more than one person.')
            return next(iter(self.names))
        if key in ('you','your'):raise Unclear('Use “I” or an explicit name for the quantities.')
        self.names.setdefault(key,'You' if key=='i' else name)
        return key

    def unit(self,text,actor):
        text=re.sub(r'(?i)^(?:more|extra|additional)\s+','',text.strip())
        if text.lower() in ('','more','extra'):
            options={u for a,u in self.values if a==actor}
            if len(options)!=1:raise Unclear('What kind of item does that quantity refer to?')
            return next(iter(options))
        if not re.fullmatch(U,text) or re.search(r'(?i)\b(?:more|less|fewer|than|each|per|every|not|no|to|from|and|or|now|left|remaining)\b',text):
            raise Unclear('Use one explicit item type per quantity; comparisons and grouped quantities need different wording.')
        key=unit_key(text)
        if key in ('dollar','euro','pound','yen','rupee','cent','penny','nickel','dime','quarter'):
            raise Unclear('This item-count parser does not track money or prices. Use an explicit arithmetic expression for the amounts.')
        self.units.setdefault(key,text)
        return key

    def change(self,actor,unit,delta,label):
        old=self.values.get((actor,unit))
        if old is not None:
            new=old+delta
            if new<0:raise Unclear(f'{self.names[actor]} would have a negative inventory. Check the starting amount and transfers.')
            self.values[actor,unit]=new
            self.steps.append(f'{label}: {fmt(old)} {"+" if delta>=0 else "-"} {fmt(abs(delta))} = {fmt(new)} {self.units[unit]}.')
        else:
            self.values[actor,unit]=None
            self.steps.append(f'{label}: starting quantity is unknown, so the resulting quantity is unknown.')

    def clause(self,text):
        text=re.sub(r'(?i)^(?:add|also|update)\s*:\s*','',text.strip())
        text=re.sub(r'(?i)^(?:(?:and|then|now|next|afterward|afterwards|finally|at first|initially)\s*,?\s*)+','',text.strip())
        if not re.match(r'(?i)^'+A+r'\s+'+VERBS+r'\b',text):
            if self.last_actor and re.match(r'(?i)^'+VERBS+r'\b',text):text=self.last_actor+' '+text
        subject=re.match(r'(?i)^('+A+r')\s+',text)
        if not subject:raise Unclear('Use a named person or “I” and a complete quantity event in each clause.')
        actor=self.actor(subject[1]);body=text[subject.end():]
        self.last_actor=subject[1]
        stock=re.fullmatch('('+STOCK+r')\s+('+N+r')\s+('+U+r')',body,re.I)
        if stock:
            if self.events_started and re.match(r'(?i)^(?:starts? with|started with)$',stock[1]):
                raise Unclear('Put starting quantities before the events. I cannot safely apply a late starting quantity to the earlier transfers.')
            if re.match(r'(?i)^(?:more|extra|additional)\b',stock[3]):
                raise Unclear('The starting quantity must be absolute, not “more” than an unspecified amount.')
            amount=Fraction(stock[2]);unit=self.unit(stock[3],actor);key=actor,unit
            if key in self.values and self.values[key] is not None and self.values[key]!=amount:
                raise Unclear(f'The stated amount for {self.names[actor]} conflicts with the listed events. Check that quantity.')
            self.values[key]=amount
            self.steps.append(f'Stated quantity: {self.names[actor]} {"have" if actor=="i" else "has"} {fmt(amount)} {self.units[unit]}.')
            return
        transfer=re.fullmatch('('+TRANSFER+r')\s+('+N+r')\s+('+U+r')\s+to\s+('+A+r')',body,re.I)
        to_first=re.fullmatch('('+TRANSFER+r')\s+('+A+r')\s+('+N+r')\s+('+U+r')',body,re.I)
        if re.match(SUB+r'\s+'+N+r'\b',body,re.I):to_first=None
        incoming=re.fullmatch(r'(?:receives?|received|gets?|got)\s+('+N+r')\s+('+U+r')\s+from\s+('+A+r')',body,re.I)
        if transfer or to_first or incoming:
            self.events_started=True
            if transfer:quantity,item,other=transfer[2],transfer[3],transfer[4]
            elif to_first:quantity,item,other=to_first[3],to_first[4],to_first[2]
            else:quantity,item,other=incoming[1],incoming[2],incoming[3]
            other=self.actor(other);unit=self.unit(item,actor);amount=Fraction(quantity)
            giver,receiver=(other,actor) if incoming else (actor,other)
            if giver==receiver:raise Unclear('Giving an item to the same person is ambiguous here; state the inventory change directly.')
            self.change(giver,unit,-amount,f'{self.names[giver]} {"give" if giver=="i" else "gives"} to {self.names[receiver]}')
            self.change(receiver,unit,amount,f'{self.names[receiver]} {"receive" if receiver=="i" else "receives"} from {self.names[giver]}')
            return
        event=re.fullmatch('('+ADD+'|'+SUB+r')\s+('+N+r')(?:\s+('+U+r'))?',body,re.I)
        if not event:raise Unclear('I cannot reliably parse every event. Use simple “has”, “buys”, “loses” or “gives … to …” clauses.')
        self.events_started=True
        unit=self.unit(event[3] or '',actor);amount=Fraction(event[2]);addition=bool(re.fullmatch(ADD,event[1],re.I))
        self.change(actor,unit,amount if addition else -amount,f'{self.names[actor]} {event[1].lower()}')

    def answer(self,question,explain=False):
        question=re.sub(r'(?i)\s+(?:now|left|remaining|in total|altogether|in all)$','',question)
        question=re.sub(r'(?i)\s+(?:now|left|remaining|in total|altogether|in all)$','',question)
        found=re.fullmatch(r'how (?:many|much)\s+('+U+r')\s+(?:does|do)\s+('+A+r'(?:\s+and\s+'+A+r')?)\s+(?:have|own)',question,re.I)
        have_left=re.fullmatch(r'how (?:many|much)\s+('+U+r')\s+(?:does|do)\s+('+A+r')\s+have\s+left',question,re.I)
        found=found or have_left
        # "How many do I have?" names no item: fine when the facts track exactly one kind of item.
        bare=None if found else re.fullmatch(r'how (?:many|much)\s+(?:does|do)\s+('+A+r'(?:\s+and\s+'+A+r')?)\s+(?:have|own)(?:\s+left)?',question,re.I)
        if bare and len(self.units)==1:
            found=(None,next(iter(self.units.values())),bare[1])
        if not found:raise Unclear('Ask “How many [items] does [name] have?” and specify the person and item type.')
        actor_text=found[2]
        if actor_text.lower()=='they':actors=list(self.names)
        else:
            names=re.split(r'\s+and\s+',actor_text,flags=re.I)
            actors=[self.actor(name) for name in names]
        if not actors or len(set(actors))!=len(actors):raise Unclear('Specify each person once in the question.')
        unit=unit_key(found[1]);values=[self.values.get((actor,unit)) for actor in actors]
        if any(value is None for value in values):
            raise Unclear('The listed facts do not establish the requested starting quantity and item type. I will not assume it is zero.')
        total=sum(values,Fraction(0));label=self.units[unit]
        subject=' and '.join(self.names[a] for a in actors)
        if len(actors)>1:
            self.steps.append('Total: '+' + '.join(fmt(value) for value in values)+' = '+fmt(total)+' '+label+'.')
        response=subject+(' have ' if len(actors)>1 or actors==['i'] else ' has ')+fmt(total)+' '+label+'.'
        if explain:response+='\n\nSteps:\n'+'\n'.join(f'{i+1}. {step}' for i,step in enumerate(self.steps))
        return dict(route='helper/quantity',response=response,sources=[],exact=True,
                    details='Typed quantity-event automaton, using only your complete stated clauses; unknown quantities are never assumed zero. No network or neural model.\n'+'\n'.join(self.steps),
                    helper_reasoning=dict(value=fmt(total),unit=unit,actors=actors,steps=self.steps,exact=True))


def reply(text,messages=None,explain=False):
    if len(text)>5000 or re.search(r'(?i)\b(?:python|javascript|function|script|code|program)\b|```',text):return None
    problem=split_question(text)
    if problem is None:return None
    context,question=problem
    additive=bool(re.match(r'(?i)^(?:add|also|update)\s*:',context))
    if (not context or additive) and messages:
        from .reasoning_chat import context_from_history
        previous,_=context_from_history(messages)
        if additive:
            if not previous:return dict(route='helper/quantity-clarify',response='Start with “Facts:” and the starting quantities before adding more events.',sources=[])
            context=previous+'. '+context
        else:
            # An unrelated count question must still reach ordinary lookup.
            ignored=set('how many much does do has have own owns is are the a an now left remaining in total altogether all'.split())
            common=({unit_key(w) for w in re.findall(r'[A-Za-z]+',previous.lower()) if w not in ignored}
                    & {unit_key(w) for w in re.findall(r'[A-Za-z]+',question.lower()) if w not in ignored})
            if not common:return None
            context=previous
    context=re.sub(r'(?i)^(?:facts|given|premises|scenario|context)\s*:\s*','',context)
    if not context or not re.search(r'(?i)\b'+A+r'\s+'+VERBS+r'\s+'+N+r'\b',context):return None
    try:
        if re.search(r"(?i)\b(?:not|never|no|unless|if|either|or|maybe|might|could|about|approximately|at least|at most|didn't|doesn't|don't|didn’t|doesn’t|don’t)\b",context):
            raise Unclear('These quantities are negated, conditional or uncertain. State exact known quantities/events to calculate a definite result.')
        # Split sentence punctuation without splitting decimal quantities.
        clauses=[p.strip() for p in re.split(r'(?<!\d)\.|\.(?!\d)|[;\n]+|,\s*(?:and\s+)?(?:then\s+)?|\s+and\s+(?=(?:then\s+)?(?:'+A+r'\s+)?'+VERBS+r'\b)',context,flags=re.I) if p.strip()]
        if len(clauses)>40:raise Unclear('Keep the quantity scenario to 40 events or fewer.')
        inventory=Inventory()
        for clause in clauses:inventory.clause(clause)
        return inventory.answer(question,explain)
    except (Unclear,ValueError,ZeroDivisionError) as error:
        return dict(route='helper/quantity-clarify',response=str(error),sources=[],details='No numeric answer was guessed and no internet request was made.')
