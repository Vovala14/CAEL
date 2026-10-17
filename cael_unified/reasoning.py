"""Shared bounded reasoning interface. No network calls or cross-user state."""
import json
from pathlib import Path
import re
from .bundle import ROOT
from .reasoning_logic import LogicCA, Unparsed, sentences
from .reasoning_world import WorldCA
from .reasoning_relations import relations
from .reasoning_order import ordering
from .social_reasoning import SocialCA
from .reasoning_sat import query as case_query
from .reasoning_babi import compass_query, induction_query, load_table, motivation_query, position_query, rewrite, time_query

MODEL = ROOT/'models/cael-reasoning-v1/model.json'
MOTIVATIONS = ROOT/'models/cael-reasoning-v1/motivations.json'   # counted from bAbI task 20 training stories


NATURAL = r'(?:does it follow that|can we conclude(?: that)?|can you conclude(?: that)?|is it true that|must it be true that|must it be that|is it certain that|prove that)'


def split_problem(text):
    text=text.strip()
    explicit=bool(re.match(r'(?i)^(?:facts|premises|given|suppose|scenario|context)\s*:',text))
    text=re.sub(r'(?i)^(?:facts|premises|given|suppose|scenario|context)\s*:\s*','',text)
    markers=list(re.finditer(r'(?im)(?:^|(?<=[.\n])\s*)(?:question\s*:\s*|query\s*:\s*|prove\s*:\s*|true or false\s*:\s*|'+NATURAL+r'\s*|(?=(?:is|does|where|who|what|how|which|can|why)\b))',text))
    for marker in reversed(markers):
        context=text[:marker.start()].strip(' .\n')
        question=text[marker.end():].strip()
        if not question:
            continue
        if marker[0].strip().lower().startswith('prove') or re.match('(?i)'+NATURAL,marker[0].strip()):
            question='Prove: '+question.rstrip('?')
            explicit=True
        if context:
            return context,question,explicit
    return None


def phrase(question,answer):
    """Answer in a full sentence when the question has a familiar shape."""
    q=question.strip(' ?.')
    forms=[(r'(?i)where is (?:the )?(.+)',lambda m:f'{m[1]} is in the {answer}.'),
           (r'(?i)where (?:will|would|does) (\w+) (?:look|search) for the (\w+)',lambda m:f'{m[1]} will look for the {m[2]} in the {answer}.'),
           (r'(?i)where was (\w+) before the (\w+)',lambda m:f'{m[1]} was in the {answer} before the {m[2]}.'),
           (r'(?i)where will (\w+) go',lambda m:f'{m[1]} will most likely go to the {answer}.'),
           (r'(?i)why did (\w+) (?:go to|get|grab|take|pick up) the (\w+)',lambda m:f'Because {m[1]} was {answer}.'),
           (r'(?i)what colou?r is (\w+)',lambda m:f'{m[1]} is {answer}.'),
           (r'(?i)what is (north|south|east|west) of the (\w+)',lambda m:f'The {answer} is {m[1]} of the {m[2]}.'),
           (r'(?i)what is the (\w+) (north|south|east|west) of',lambda m:f'The {m[1]} is {m[2]} of the {answer}.')]
    for pattern,make in forms:
        m=re.fullmatch(pattern,q)
        if m:
            text=make(m)
            return text[0].upper()+text[1:]
    return answer[0].upper()+answer[1:]+'.'


class Reasoner:
    def __init__(self,path=None):
        path=Path(path or MODEL)
        self.model=json.loads(path.read_text(encoding='utf-8')) if path.exists() else None

    def solve(self,context,question):
        if not self.model:
            raise Unparsed('Reasoning model missing')
        if len(context)>40000 or len(sentences(context))>400:
            raise Unparsed('Keep the scenario within 400 premises and 40,000 characters')
        errors=[]
        table=getattr(self,'_motivations',None)
        if table is None:
            table=self._motivations=load_table(MOTIVATIONS) or {}
        for family,solver in [('belief',SocialCA().query),('ordering',ordering),
                              ('motivation',lambda c,q:motivation_query(c,q,table)),('time',time_query),
                              ('induction',induction_query),('position',position_query),('compass',compass_query),
                              ('relations',relations),('state',self.state_query),('logic',LogicCA(self.model).query),
                              ('logic-cases',case_query)]:
            try:
                result=solver(context,question)
                if family=='logic' and result.get('answer')!='unknown':
                    # A proof from contradictory premises proves nothing: say so instead.
                    try:
                        if case_query(context,question)['answer']=='conflicting':
                            return dict(answer='conflicting',support=[],family='logic-cases')
                    except Unparsed:
                        pass
                if family=='logic' and result.get('answer')=='unknown':
                    # Rule chaining found no proof; exhaustive case analysis may still settle it ("or", contradiction).
                    try:
                        cases=case_query(context,question)
                        if cases['answer']!='unknown':
                            cases['family']='logic-cases'
                            return cases
                    except Unparsed:
                        pass
                result['family']=family
                return result
            except Unparsed as error:
                errors.append(str(error))
        raise Unparsed(errors[-1])

    def state_query(self,context,question):
        """Event tracking; stories with pairs ('A and B went') or pronouns are rewritten to one person per sentence first."""
        rewritten,origin=rewrite(context)
        if rewritten is None:
            return WorldCA(self.model).query(context,question)
        result=WorldCA(self.model).query(rewritten,question)
        result['support']=sorted({origin[i-1] for i in result.get('support',[]) if 1<=i<=len(origin)})
        return result

    def respond(self,text,messages=None):
        if not self.model:
            return None
        problem=split_problem(text)
        if problem is None and messages and re.match(r'(?i)^(?:is|does|where|who|what|how|which|why)\b',text):
            previous=next((m['content'] for m in reversed(messages[:-1]) if m.get('role')=='user'), '')
            previous_problem=split_problem(previous)
            if previous_problem:
                problem=(previous_problem[0],text,previous_problem[2])
        if problem is None:
            return None
        context,question,explicit=problem
        # Recognize premise scenarios, not arbitrary multi-sentence conversation.
        scenario=explicit or re.search(r'(?i)\b(?:all|every|each|everything that|moved to|went to|journeyed to|travelled to|picked up|gave the|bigger than|fits inside|'
                                       r'is north of|is south of|is east of|is west of|entered the|left the|told .+? that|to the left of|to the right of|is above|is below|'
                                       r'this morning|this afternoon|this evening|yesterday|is hungry|is thirsty|is tired|is bored|is an? \w+\. \w+ is \w+|'
                                       r'\w+ or an? \w+|are not|is not an?)\b',context)
        if not scenario:
            return None
        try:
            result=self.solve(context,question)
        except Unparsed as error:
            if not explicit:
                return None          # looked like a puzzle but is not one we can read: let normal chat answer
            return dict(route='chat/reasoning-unsupported',response='I cannot reliably parse that scenario. Use simple facts and rules, events, or an explicit list with ordering clues.',
                        details='The scenario was not sent to an internet provider. '+str(error),sources=[])
        answer=result['answer']
        if answer=='unknown':
            response='The stated premises do not determine the answer.'
        elif answer=='conflicting':
            response='The stated premises conflict, so there is no single consistent answer.'
        elif answer in ('true','false'):
            response='Yes, that follows from the premises.' if answer=='true' else 'No—the premises establish its opposite.'
        elif answer in ('yes','no','maybe'):
            response={'yes':'Yes.','no':'No.','maybe':'It is possible, but not certain from the stated premises.'}[answer]
        elif 'directions' in result:
            response=' → '.join(result['directions']) + '.'
        elif question.lower().startswith('how many'):
            count={'none':'0','one':'1','two':'2','three':'3','four':'4','five':'5'}.get(answer,answer)
            response=f'{count} object(s) are carried after the listed events.'
        elif answer=='nothing':
            response='No carried objects are specified after the listed events.'
        else:
            display=re.search(r'(?i)\b'+re.escape(answer)+r'\b',context)
            response=phrase(question,display[0] if display else answer)
        premises=sentences(context)
        support=[f'{index}. {premises[index-1]}.' for index in sorted(set(result.get('support',[]))) if 1<=index<=len(premises)]
        # Show the reasoning, not only the verdict.
        if answer not in ('unknown','conflicting'):
            if result['family']=='logic-cases':
                response+=' I checked every possible case the premises allow, and in each one the answer is the same.'
            elif result.get('inferred') and result['family']=='motivation':
                response+=' This is what people in that state typically do, not something the premises state outright.'
            elif result.get('inferred'):
                response+=' This is a best guess by analogy, not something the premises state outright.'
            if support:
                response+='\n\nBased on:\n'+'\n'.join(support[:6])
        result['internet_used']=False
        details='Reasoned only from your stated premises; no internet request. '
        if result['family']=='state':
            details+='Events are chronological. Inventory counts include only the listed pickup, drop and transfer events. '
        if result['family']=='belief':
            details+='Tracks first-order beliefs separately from reality using only explicit observations, room presence and reports. A report need not be true. '
        if result['family']=='logic-cases':
            details+='Exhaustive case analysis: the premises were translated into true/false constraints and the opposite of the conclusion was shown to be impossible (or the conclusion itself, for a "no"). '
        details+='\nBounded non-neural hybrid: trained count grammars/transition tables with authored proof, state, ordering and path algorithms. Training credits are on the sources page.'
        return dict(route='chat/reasoning-'+result['family'],response=response,details=details,sources=[],reasoning=result)
