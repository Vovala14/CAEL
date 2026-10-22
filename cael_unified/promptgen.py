"""Text prompts from CAEL's existing counted integer CA grammar."""
import json
from pathlib import Path
import re
from cael import CAEL
from .bundle import ROOT, digest

IMAGE_TOOLS = r'midjourney|stable\s+diffusion|sdxl|sd|dall-?e(?:\s*\d)?|flux|leonardo|ideogram|mage(?:\.space)?|firefly'
REQUEST = re.compile(r'(?is)^\s*(?:please\s+)?(?:(?:can|could) you\s+(?:please\s+)?)?(?:help me\s+(?:to\s+)?)?'
    r'(?:(?:write|create|generate|make(?:\s+up)?|draft|compose|improve|rewrite|polish|give)\s+'
    r'(?:me\s+)?(?:(?:an?|the|my|this|some)\s+)?(?:(?:\d+|one|two|three|four|five)\s+)?'
    r'|(?:an?\s+)?(?=(?:(?:[\w.-]+\s+){0,3})prompts?\s+(?:for|of|about)\b))'
    r'(?:(?:image|photo|picture|story|writing|assistant|system|general|ai|better|detailed|short|different|alternative|creative|strong|'
    r'concise|following|art|' + IMAGE_TOOLS + r')\s+)*prompts?\b')
CODE_TOOL = re.compile(r'(?i)\bprompt\s+(?:generator|function|script|program|app)\b')
# Words that make a brief a task for a chatbot rather than something to picture.
TASK_WORDS = re.compile(r'(?i)\b(?:write|writes|writing|summar\w*|e-?mails?|essays?|code|coding|program\w*|answer\w*|explain\w*|translat\w*|'
                        r'chat\s*bot|chatbot|assistant|agent|customer|support|report|plan\w*|list\w*|analy\w*|review\w*|classif\w*|tutor\w*|'
                        r'teach\w*|interview\w*|tweets?|blog|posts?\s+about|copy\s*writ\w*|marketing|reply|replies|respond\w*|questions?|'
                        r'steps?|instructions?|role|act as|you are)\b')
VISUAL_TAIL = re.compile(r'(?i)\s+(?:image|photo|photograph|picture|pic|portrait|drawing|painting|illustration|wallpaper|artwork|art|render)s?\s*$')


def is_prompt_request(text):
    return bool(REQUEST.match(text) and not CODE_TOOL.search(text))


def parse(text, forced=False, default_kind='task'):
    match=REQUEST.match(text)
    if not match and not forced:return None
    prefix=text[:match.end()] if match else ''
    brief=text[match.end():].strip() if match else text.strip()
    brief=re.sub(r'(?i)^(?:\s*[:\-]\s*|(?:for|about|of)\s+)', '', brief, count=1).strip()
    if '\n' not in brief:
        brief=brief.rstrip(' .!?')
    count=1
    requested=re.search(r'(?i)\b(\d+|one|two|three|four|five)\s+(?:[a-z]+\s+)*prompts?\b',prefix)
    if requested:
        count=dict(one=1,two=2,three=3,four=4,five=5).get(requested[1].lower()) or int(requested[1])
        if not 1<=count<=5:raise ValueError('Choose between one and five prompt variants.')
    if re.search(r'(?i)\b(?:assistant|system|general|ai)\s+prompts?\b',prefix):kind='task'
    elif re.search(r'(?i)\b(?:story|writing)\s+prompts?\b',prefix):kind='story'
    elif re.search(r'(?i)\b(?:image|photo|picture|art|' + IMAGE_TOOLS + r')\s+prompts?\b',prefix):kind='image'
    elif re.match(r'(?i)(?:an?\s+)?(?:story|tale|fable)\b',brief):kind='story'
    elif re.match(r'(?i)(?:an?\s+)?(?:image|photo|picture|portrait|drawing|painting|illustration)\b',brief):kind='image'
    elif VISUAL_TAIL.search(brief) or re.search(r'(?i)\b(?:' + IMAGE_TOOLS + r')\b', brief):kind='image'   # "a dog image"
    elif default_kind=='task' and brief and not TASK_WORDS.search(brief) and len(brief.split())<=25:
        kind='image'          # "a dog on a beach": something to picture, not a task for a chatbot
    else:kind=default_kind
    if kind=='image':
        # "a dog image" -> "a dog"; "for Midjourney" is about the tool, not the picture.
        brief=re.sub(r'(?i)\s*\b(?:for|in|with|on)\s+(?:' + IMAGE_TOOLS + r')\b\s*', ' ', brief).strip()
        stripped=VISUAL_TAIL.sub('', brief).strip()
        brief=stripped if re.search(r'[A-Za-z]', stripped) else brief
    if len(brief)>8000:raise ValueError('Keep the prompt brief under 8,000 characters.')
    return dict(kind=kind,brief=brief,count=count)


class PromptGenerator:
    def __init__(self,path=None):
        config=ROOT/'research/active_models.json'
        entry=json.loads(config.read_text()).get('prompt') if path is None and config.is_file() else None
        path=Path(path) if path is not None else Path(entry['path']) if entry else ROOT/'models/cael-prompts-0.3.7-r2/model.json'
        if entry and digest(path)!=entry['sha256']:raise ValueError('Active prompt model checksum changed')
        self.model=CAEL(path)

    def respond(self,text,seed=0,forced=False,default_kind='task'):
        try:request=parse(text,forced,default_kind)
        except ValueError as error:
            return dict(route='chat/prompt-clarify',response=str(error),sources=[])
        if request is None:return None
        if not request['brief']:
            return dict(route='chat/prompt-clarify',response='What should the prompt be for? Give me an image idea, a story idea, or an assistant task.',sources=[])
        if request['kind']=='image':
            # A detailed, ready-to-use image prompt built from the idea (cael_unified/image_prompt.py).
            from .image_prompt import image_prompts
            try:prompts,notes=image_prompts(request['brief'],request['count'],seed)
            except ValueError as error:
                return dict(route='chat/prompt-clarify',response=str(error),sources=[])
            response=prompts[0] if len(prompts)==1 else '\n\n'.join(f'{i+1}. {value}' for i,value in enumerate(prompts))
            return dict(route='chat/prompt-image',response='Image prompt:\n'+response,sources=[],prompts=prompts,
                details=(f'Subject: {notes["subject"]}. Medium: {notes["style"]}. Your scene and written constraints are kept at the start. '
                         f'Added visual detail: {"; ".join(notes["additions"])}. '
                         f'Optional avoidance terms (separate from the copyable prompt): {notes["avoid"]}.'),
                prompt_generation=dict(kind='image',variants=len(prompts),neural_networks=False))
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
