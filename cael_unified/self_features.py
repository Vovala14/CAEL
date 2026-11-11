"""Installed capability facts and typed visible-topic follow-through.

These are curated software facts, not generated endorsements or a knowledge
claim about another product. User text cannot replace the installed catalogue.
"""
import importlib.util
import json
from pathlib import Path
import re
from .bundle import VERSION,BUNDLE_VERSION


def normalized(text):
    text=text.casefold().replace('’',"'")
    text=re.sub(r"\b(\w+)'s\b",r'\1 s',text)
    text=re.sub(r"\b(?:can't|cannot)\b",'can not',text)
    return re.sub(r'\s+',' ',re.sub(r'[^a-z0-9 ]',' ',text)).strip()


def catalogue():
    try:
        value=json.loads(Path(__file__).with_suffix('.json').read_text(encoding='utf-8'))
        if value.get('format')!='cael-self-features-v1' or VERSION not in value.get('versions',[]):return {}
        features=value['features']
        if type(features) is not dict:return {}
        for key,feature in features.items():
            if type(key) is not str or type(feature) is not dict:return {}
            if not all(type(feature.get(k)) is str and 0<len(feature[k])<1000 for k in ['overview','quality','usage','architecture','limits','module']):return {}
            if not isinstance(feature.get('aliases'),list) or not feature['aliases'] or not all(type(x) is str and x for x in feature['aliases']):return {}
        return features
    except (OSError,ValueError,TypeError,KeyError):return {}


def direct(text):
    if not isinstance(text,str) or not 0<len(text)<=600 or text.lstrip().startswith(('"',"'",'`')):return None
    t=normalized(text)
    t=re.sub(r'^(?:(?:hey|hi|hello|so|and|okay|ok|please|cael)\s+)+','',t)
    for name,facts in catalogue().items():
        aliases='(?:'+'|'.join(re.escape(a) for a in sorted(facts['aliases'],key=len,reverse=True))+')'
        subject=r'(?:(?:your|the|cael s|this) )'+aliases
        patterns=[
            (r'(?:what|how) about '+subject+r'(?: (?:is it|are they) (?:actually |really |any )?(?:good|useful|helpful|reliable))?', 'quality'),
            (r'(?:is|are) '+subject+r' (?:actually |really |any )?(?:good|useful|helpful|reliable)', 'quality'),
            (r'are you (?:any |actually |really )?good at '+aliases,'quality'),
            (r'how (?:good|useful|helpful|reliable) is '+subject,'quality'),
            (r'what (?:can '+subject+r' do|does '+subject+r' do|is '+subject+r'|are the (?:features|capabilities) of '+subject+r')','overview'),
            (r'(?:(?:(?:can|could) you )?(?:tell me about|explain|describe) '+subject+r'|what is '+subject+r' (?:for|good for|useful for)|do you have (?:a )?'+aliases+r')','overview'),
            (r'how (?:do i|can i|should i) (?:use|try) '+subject,'usage'),
            (r'why (?:should|would) i use '+subject,'quality'),
            (r'how does '+subject+r' work','architecture'),
            (r'(?:does '+subject+r' use|is '+subject+r' based on) (?:an? )?(?:llm|neural network|transformer|qwen|chatgpt)','architecture'),
            (r'what are (?:the )?(?:limits|limitations|weaknesses) of '+subject,'limits'),
            (r'(?:is '+subject+r' better than|can '+subject+r' beat) (?:chatgpt|qwen|an llm|other models)','comparison')]
        if any(re.fullmatch(p,t) for p,intent in patterns):
            return name,next(intent for p,intent in patterns if re.fullmatch(p,t))
    if re.fullmatch(r'do you (?:only|just) use wikipedia|can you use (?:sources? other than|anything besides) wikipedia',t):return 'lookup','overview'
    # Unknown owned feature claims do not turn into claims about a stranger's
    # software or a made-up capability. Mixed requests retain their clause.
    if re.match(r'(?:what|how) about your ',t):return '?','unknown'
    return None


FOLLOWUPS=[
    (r'(?:is it|is that|does it seem) (?:actually |really |any )?(?:good|useful|helpful|reliable)','quality'),
    (r'how (?:do i|can i|should i) (?:use|try) it|how do i get started','usage'),
    (r'how does (?:it|that) work|tell me more(?: about it)?','architecture'),
    (r'does it use (?:an? )?(?:llm|neural network|qwen|chatgpt)|is it neural','architecture'),
    (r'what (?:can it do|is it for)','overview'),
    (r'what (?:are its (?:limits|limitations|weaknesses)|can t it do|can not it do)|can it run any program|will you remember this in a new chat|can you verify every answer','limits'),
    (r'is it better than (?:chatgpt|qwen|an llm|other models)|can it beat (?:qwen|chatgpt)','comparison'),
    (r'can it (?:create|generate|make|draw) images(?: itself)?','images'),
    (r'can you check your answers','usage')]


def followup(text):
    if not isinstance(text,str) or len(text)>200 or text.lstrip().startswith(('"',"'",'`')):return None
    t=normalized(text)
    return next((intent for pattern,intent in FOLLOWUPS if re.fullmatch(pattern,t)),None)


def generate(text):
    """A complete prompt-use request, with every brief word retained."""
    if not isinstance(text,str) or len(text)>3000:return None
    if re.fullmatch(r'(?i)\s*(?:please )?(?:(?:can|could) you )?(?:show|give)(?: me)? (?:an? )?example[.!?]*\s*',text):
        return dict(brief='an assistant that summarizes release notes in five concise bullets and flags missing information instead of inventing it',example=True)
    m=re.fullmatch(r'(?is)\s*(?:please )?(?:(?:can|could) you )?(?:make|write|create|generate|draft|give)(?: me)? (?:one|a prompt|an? example|one prompt) (?:for|about)\s+(.+?)\s*',text)
    if m:return dict(brief=m[1],example=False)
    return None


def context(messages):
    active=None
    for message in messages:
        if not isinstance(message,dict) or message.get('role')!='user':continue
        text=message.get('content');found=direct(text)
        if found:active=found[0] if found[0]!='?' else None
        elif active and (followup(text) or active=='prompt' and generate(text)):continue
        else:active=None
    return active


def reply(messages):
    if not isinstance(messages,list) or not messages or not isinstance(messages[-1],dict) or messages[-1].get('role')!='user':return None
    text=messages[-1].get('content');found=direct(text)
    if found is None:
        active=context(messages[:-1]);intent=followup(text) if active else None
        if not intent:return None
        found=active,intent
    name,intent=found;features=catalogue();facts=features.get(name)
    if not facts:
        return dict(route='chat/self-capability-clarify',response="I don't have a confirmed feature by that name, or the complete question is outside my feature reader. I can explain my prompt helper, memory, arithmetic, Python helper or public-source lookup. Which one do you mean?",sources=[])
    try:available=importlib.util.find_spec('cael_unified.'+facts['module']) is not None
    except (ValueError,ModuleNotFoundError):available=False
    if not available:
        body='That feature is described in my catalogue, but its module is not available in this installation. I should not claim I can run it.'
    elif intent=='quality':body=facts['overview']+' '+facts['quality']+' '+facts['limits']
    elif intent=='comparison':body="I don't have a fair, independent comparison showing that this feature is better than ChatGPT, Qwen or another model. "+facts['quality']
    elif intent=='images':
        body=facts.get('images',"That feature is not an image renderer. Tell me whether you want prompt text or an image, so I don't claim the wrong capability.")
    else:body=facts[intent]
    return dict(route='chat/self-capability',response=body,sources=[],
        details='Curated installed software facts with a bounded feature/question reader; no public lookup or external model.',
        self_information=dict(kind='feature',feature=name,intent=intent,available=available,application_version=VERSION,
            resource_bundle_version=BUNDLE_VERSION,source_files=facts.get('source_files',[])))


def task_request(messages):
    if context(messages[:-1])!='prompt':return None
    request=generate(messages[-1]['content'])
    if request is None:return None
    brief=request['brief']
    kind='story' if re.match(r'(?i)(?:a |an )?(?:story|tale)\b',brief) else 'image' if re.match(r'(?i)(?:a |an )?(?:image|photo|picture|portrait)\b',brief) else 'assistant'
    return dict(text='Write '+('a ' if kind=='story' else 'an ')+kind+' prompt for '+brief,brief=brief,example=request['example'])
