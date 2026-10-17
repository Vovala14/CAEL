"""Text prompts from CAEL's existing counted integer CA grammar."""
import json
from pathlib import Path
import re
from cael import CAEL
from .bundle import ROOT, digest

REQUEST = re.compile(r'(?is)^\s*(?:please\s+)?(?:(?:can|could) you\s+(?:please\s+)?)?(?:help me\s+(?:to\s+)?)?'
    r'(?:write|create|generate|make(?:\s+up)?|draft|compose|improve|rewrite|polish|give)\s+'
    r'(?:me\s+)?(?:(?:an?|the|my|this|some)\s+)?(?:(?:\d+|one|two|three|four|five)\s+)?'
    r'(?:(?:image|photo|picture|story|writing|assistant|system|general|ai|better|detailed|short|different|alternative|creative|strong|concise|following)\s+)*prompts?\b')
CODE_TOOL = re.compile(r'(?i)\bprompt\s+(?:generator|function|script|program|app)\b')


def is_prompt_request(text):
    return bool(REQUEST.match(text) and not CODE_TOOL.search(text))


def parse(text, forced=False):
    match=REQUEST.match(text)
    if not match and not forced:return None
    prefix=text[:match.end()] if match else ''
    brief=text[match.end():].strip() if match else text.strip()
    brief=re.sub(r'(?i)^(?:\s*[:\-]\s*|(?:for|about|of)\s+)', '', brief, count=1).strip()
    count=1
    requested=re.search(r'(?i)\b(\d+|one|two|three|four|five)\s+(?:[a-z]+\s+)*prompts?\b',prefix)
    if requested:
        count=dict(one=1,two=2,three=3,four=4,five=5).get(requested[1].lower()) or int(requested[1])
        if not 1<=count<=5:raise ValueError('Choose between one and five prompt variants.')
    if re.search(r'(?i)\b(?:assistant|system|general|ai)\s+prompts?\b',prefix):kind='task'
    elif re.search(r'(?i)\b(?:story|writing)\s+prompts?\b',prefix):kind='story'
    elif re.search(r'(?i)\b(?:image|photo|picture)\s+prompts?\b',prefix):kind='image'
    elif re.match(r'(?i)(?:an?\s+)?(?:story|tale|fable)\b',brief):kind='story'
    elif re.match(r'(?i)(?:an?\s+)?(?:image|photo|picture|portrait|drawing|painting|illustration)\b',brief):kind='image'
    else:kind='task'
    if len(brief)>8000:raise ValueError('Keep the prompt brief under 8,000 characters.')
    return dict(kind=kind,brief=brief,count=count)


class PromptGenerator:
    def __init__(self,path=None):
        config=ROOT/'research/active_models.json'
        entry=json.loads(config.read_text()).get('prompt') if path is None and config.is_file() else None
        path=Path(path) if path is not None else Path(entry['path']) if entry else ROOT/'models/cael-prompts-0.3.7-r2/model.json'
        if entry and digest(path)!=entry['sha256']:raise ValueError('Active prompt model checksum changed')
        self.model=CAEL(path)

    def respond(self,text,seed=0,forced=False):
        try:request=parse(text,forced)
        except ValueError as error:
            return dict(route='chat/prompt-clarify',response=str(error),sources=[])
        if request is None:return None
        if not request['brief']:
            return dict(route='chat/prompt-clarify',response='What should the prompt be for? Give me an image idea, a story idea, or an assistant task.',sources=[])
        marker='__CAEL_BRIEF_SLOT__'
        while marker in request['brief']:marker+='X'
        event='PROMPT_'+request['kind'].upper()
        output=[]
        for i in range(request['count']):
            for attempt in range(100):
                template=self.model.render_slots(self.model.eid[event],{'<Q>':marker},(seed,i,attempt))
                result=template.replace(marker,request['brief'])
                if result not in output:break
            else:raise ValueError('The selected prompt model cannot supply that many distinct variants.')
            output.append(result)
        response=output[0] if len(output)==1 else '\n\n'.join(f'{i+1}. {value}' for i,value in enumerate(output))
        response={'image':'Image prompt','story':'Story prompt','task':'Assistant prompt'}[request['kind']]+':\n'+response
        return dict(route='chat/prompt-'+request['kind'],response=response,sources=[],prompts=output,
            details='Prompt text from counted authored structures using the same integer CA grammar as stories. Your brief is preserved; no images are generated.',
            prompt_generation=dict(kind=request['kind'],variants=len(output),neural_networks=False))
