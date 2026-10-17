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

MODEL = ROOT/'models/cael-reasoning-v1/model.json'


def split_problem(text):
    text=text.strip()
    explicit=bool(re.match(r'(?i)^(?:facts|premises|given|suppose|scenario|context)\s*:',text))
    text=re.sub(r'(?i)^(?:facts|premises|given|suppose|scenario|context)\s*:\s*','',text)
    markers=list(re.finditer(r'(?im)(?:^|(?<=[.\n])\s*)(?:question\s*:\s*|query\s*:\s*|prove\s*:\s*|true or false\s*:\s*|(?=(?:is|does|where|who|what|how|which|can)\b))',text))
    for marker in reversed(markers):
        context=text[:marker.start()].strip(' .\n')
        question=text[marker.end():].strip()
        if not question:
            continue
        if marker[0].strip().lower().startswith('prove'):
            question='Prove: '+question
        if context:
            return context,question,explicit
    return None


class Reasoner:
    def __init__(self,path=None):
        path=Path(path or MODEL)
        self.model=json.loads(path.read_text(encoding='utf-8')) if path.exists() else None

    def solve(self,context,question):
        if not self.model:
            raise Unparsed('Reasoning model missing')
        if len(context)>20000 or len(sentences(context))>128:
            raise Unparsed('Keep the scenario within 128 premises and 20,000 characters')
        errors=[]
        for family,solver in [('belief',SocialCA().query),('ordering',ordering),('relations',relations),
                              ('state',WorldCA(self.model).query),('logic',LogicCA(self.model).query)]:
            try:
                result=solver(context,question)
                result['family']=family
                return result
            except Unparsed as error:
                errors.append(str(error))
        raise Unparsed(errors[-1])

    def respond(self,text,messages=None):
        if not self.model:
            return None
        problem=split_problem(text)
        if problem is None and messages and re.match(r'(?i)^(?:is|does|where|who|what|how|which)\b',text):
            previous=next((m['content'] for m in reversed(messages[:-1]) if m.get('role')=='user'), '')
            previous_problem=split_problem(previous)
            if previous_problem:
                problem=(previous_problem[0],text,previous_problem[2])
        if problem is None:
            return None
        context,question,explicit=problem
        # Recognize premise scenarios, not arbitrary multi-sentence conversation.
        scenario=explicit or re.search(r'(?i)\b(?:all|every|each|everything that|moved to|went to|picked up|gave the|bigger than|fits inside|is north of|is south of|is east of|is west of|entered the|left the|told .+? that)\b',context)
        if not scenario:
            return None
        try:
            result=self.solve(context,question)
        except Unparsed as error:
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
            response=(display[0] if display else answer) + '.'
        premises=sentences(context)
        support=[f'{index}. {premises[index-1]}.' for index in result.get('support',[]) if 1<=index<=len(premises)]
        result['internet_used']=False
        details='Reasoned only from your stated premises; no internet request. '
        if result['family']=='state':
            details+='Events are chronological. Inventory counts include only the listed pickup, drop and transfer events. '
        if result['family']=='belief':
            details+='Tracks first-order beliefs separately from reality using only explicit observations, room presence and reports. A report need not be true. '
        details+='\nSupporting premises:\n'+'\n'.join(support)
        details+='\nBounded non-neural hybrid: trained count grammars/transition tables with authored proof, state, ordering and path algorithms. Training credits are on the sources page.'
        return dict(route='chat/reasoning-'+result['family'],response=response,details=details,sources=[],reasoning=result)
