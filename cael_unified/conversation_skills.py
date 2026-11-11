"""Bounded text-task plans with user-grounded fields and explicit unknowns.

Composes invitation briefs, small starting plans and elementary reasoning
explanations; not a general-purpose language generator or learned world model.
"""
import re
from . import natural_relations as nr

RESET=re.compile(r'(?i)^(?:start over|new topic|reset (?:the |this )?(?:chat|conversation)|never mind|nevermind)[.!?]*$')
STYLE=re.compile(r'(?i)^(?:please )?(?:make (?:it|that|the (?:draft|invitation|message)) (?:more )?(casual|formal|friendly|shorter)|(?:keep|leave) (?:the )?(?:missing|unknown) details as placeholders|use placeholders)(?: and keep (?:the )?(?:missing|unknown) details as placeholders)?[.!]*$')
EXAMPLE=re.compile(r'(?i)^(?:(?:can|could) you )?(?:give|show|illustrate)(?: me)?(?: that with)? (?:an? |one )?(?:everyday |simple |concrete )?example[.!?]*$')
WHY=re.compile(r'(?i)^(?:why|explain (?:that|your (?:answer|suggestion|plan)))[.!?]*$')
TEMPORAL=r'(?:'+nr.NUMBER+r')'


def response(text,kind,frame):
    return dict(route='chat/skill-'+kind,response=text,sources=[],
                conversation_skill=dict(kind=frame['kind'],evidence=frame['evidence'],fields={k:v for k,v in frame.items() if k not in ('evidence',)},
                  authored_composition=True,user_grounded=True,native_generated_code=False,
                  limitations='Finite task/readers and authored plans, not unrestricted understanding.'))


def invitation(text,at):
    t=text.strip().replace('’',"'").rstrip('.!?')
    m=re.fullmatch(r'(?i)(?:(?:can|could) you |please )?(?:write|draft|compose|create) (?:me )?(?:an? )?((?:(?:friendly|casual|formal|short|brief|two-sentence)\s+)*)(?:invitation|invite) (?:to|for) (.+)',t)
    if not m:return None
    style,body=m.groups();body=body.strip()
    # A complete no-invented-details contract can be removed, never arbitrary
    # trailing instructions/conditions disguised as the event's name.
    body=re.sub(r'(?i)\s+(?:without inventing (?:the )?(?:date|time|address|location)(?:\s*(?:,|or|and)\s*(?:the )?(?:date|time|address|location))*|(?:using|with) placeholders(?: for (?:the )?(?:missing|unknown) details)?)$','',body)
    if len(body)>200 or re.search(r'(?i)\b(?:if|unless|except|but|must|include|invent|without|promise|guarantee|and (?:tell|say|make|write|keep))\b',body):
        return dict(kind='invitation',unsupported=True,evidence=[dict(message=at,text=text)])
    fields=dict(kind='invitation',event=body,tone='formal' if 'formal' in style.lower() else 'casual' if 'casual' in style.lower() else 'friendly',
                date='[date]',time='[time]',location='[location]',two_sentences=True,evidence=[dict(message=at,text=text)])
    # Structured explicit details use key/value clauses instead of extracting
    # an incidental number as a date/time or inventing a venue.
    details=re.split(r'\s*,\s*(?=(?:date|time|location|address)\s*:)',body,flags=re.I)
    if len(details)>1:
        fields['event']=details[0]
        for part in details[1:]:
            match=re.fullmatch(r'(?i)(date|time|location|address)\s*:\s*([^,;\n]{1,100})',part)
            if not match:fields['unsupported']=True;continue
            key,value=match.groups();fields['location' if key.lower()=='address' else key.lower()]=value
    if not fields['event']:fields['unsupported']=True
    return fields


def starting(text,at):
    t=text.strip().replace('’',"'")
    if re.search(r'(?i)\b(?:suicid\w*|self.harm|kill myself|hurt myself|overdose|chest pain|cannot breathe|medical advice)\b',t):return None
    match=re.fullmatch(r"(?i)I keep (?:putting off|postponing|avoiding|delaying) ([^.!?\n]{1,200}?)(?: because ([^.!?\n]{1,300}?))?[.!]\s*(?:Help me (?:think through|find|choose|take) (?:a |one )?(?:manageable |small |realistic )?first step|How (?:can|do) I get started)[.!?]*",t)
    direct=re.fullmatch(r'(?i)(?:(?:can|could) you )?(?:help me get started (?:on|with)|help me take (?:a |the )?first step (?:on|with)) ([^.!?\n]{1,200}?)[.!?]*',t)
    if not match and not direct:return None
    task=match[1] if match else direct[1];reason=match[2] if match else None
    if len(task)>200 or re.search(r'(?i)\b(?:unless|except|if|but|doctor|surgery|diagnos\w*)\b',task):return None
    return dict(kind='starting',task=task.rstrip('.!?'),stated_reason=reason.rstrip('.!?') if reason else None,minutes=None,
                evidence=[dict(message=at,text=text)])


def budget(text):
    m=re.fullmatch(r"(?i)(?:I (?:only )?have|I can spare|give me a plan for|limit (?:it|the plan) to)\s+("+TEMPORAL+r")\s+minutes?(?:\s+(?:today|for this))?[.!]?(?:\s*(?:Keep (?:it|the (?:plan|suggestion)) (?:realistic|brief|short)|What can I do in that time))?[.!?]*",text.strip())
    if not m:return None
    value=nr.number(m[1])
    return value if value.denominator==1 and 0<=value<=240 else 'unsupported'


def epistemic(text,at):
    t=text.strip().rstrip('.!?')
    # Only the conceptual contrast owns these explanations; named factual
    # disputes, prior answer verification and arbitrary subjects still defer.
    m=re.fullmatch(r'(?i)(?:explain (?:to me )?why|why (?:can|could|might|does)) (?:an? |the )?(?:convincing|plausible|confident|persuasive|well-written|fluent|detailed|coherent|believable|nice-sounding|plausible-sounding) (?:answer|explanation|claim|argument|story) (?:can |could |might )?(?:still )?(?:be |turn out to be )?(?:wrong|false|incorrect|unreliable)',t)
    other=re.fullmatch(r'(?i)how (?:can|do) I (?:tell|spot) the difference between (?:a |an )?(?:useful|sound|reliable|correct) (?:explanation|answer|argument) and (?:a |an )?(?:plausible-sounding|convincing|confident) (?:guess|answer|story)',t)
    if not m and not other:return None
    return dict(kind='epistemic',concept='presentation-versus-evidence',evidence=[dict(message=at,text=text)])


def reply(messages):
    if not messages or len(messages)>256 or sum(len(m['content']) for m in messages)>400000:return None
    frame=None;action=None
    for at,m in enumerate(messages):
        if m['role']!='user':continue
        text=m['content'].strip().replace('’',"'")
        if RESET.fullmatch(text):frame=None;action=None;continue
        new=invitation(text,at) or starting(text,at) or epistemic(text,at)
        if new:frame=new;action='initial';continue
        if frame is None:continue
        style=STYLE.fullmatch(text)
        if frame['kind']=='invitation' and style:
            value=style[1]
            if value and value.lower()!='shorter':frame['tone']=value.lower()
            frame['evidence'].append(dict(message=at,text=text));action='style';continue
        minutes=budget(text) if frame['kind']=='starting' else None
        if minutes is not None:
            frame['minutes']=str(minutes) if minutes!='unsupported' else minutes
            frame['evidence'].append(dict(message=at,text=text));action='budget';continue
        if frame['kind']=='epistemic' and EXAMPLE.fullmatch(text):action='example';continue
        if frame['kind']=='starting' and WHY.fullmatch(text):action='why';continue
        # Unknown turns do not inherit an unrelated task or assistant content.
        action=None
    if frame is None or action is None:return None
    if frame.get('unsupported'):return response('I have not preserved every instruction in that writing brief. State the event and any date, time, place or other required content explicitly.','writing-clarify',frame)
    if frame['kind']=='invitation':
        event=frame['event'];where=frame['date']+' at '+frame['time']+', '+frame['location']
        if frame['tone']=='formal':body='You are invited to '+event+' on '+where+'. Please let us know whether you can attend.'
        elif frame['tone']=='casual':body='Come join us for '+event+' on '+where+'. Hope you can make it!'
        else:body='You’re invited to '+event+' on '+where+'. Come along if you can; it would be lovely to see you!'
        return response(body,'invitation',frame)
    if frame['kind']=='starting':
        minutes=frame.get('minutes')
        if minutes=='unsupported':return response('I can make a bounded starting plan, but I need an explicit whole-minute budget from0to240.','plan-clarify',frame)
        if minutes=='0':return response('With zero minutes available, leave the task for later rather than pretending there is time to work on it.','starting',frame)
        task=frame['task'];prefix='For '+minutes+' minutes, ' if minutes else 'For a first step, '
        body=prefix+'make starting “'+task+'” smaller than finishing it: set out one needed item or open the relevant file, then do just the first concrete action.'
        if minutes:body+=' Stop when the '+minutes+' minutes are up; completing the whole task is not the requirement.'
        else:body+=' You can stop after that action; the point is to make a start.'
        if action=='why':body+=' This is a suggestion for reducing the size of the immediate action, not a guarantee about how you will feel or how much you will finish.'
        return response(body,'starting',frame)
    if action=='example':
        return response('For example, “The street is wet, so it must have rained” sounds plausible, but a sprinkler could also wet the street. The observation fits more than one explanation, so it does not establish rain by itself.','reasoning-example',frame)
    return response('A convincing explanation can be internally coherent while using false assumptions, overlooking alternatives, or lacking evidence. Clear wording and confidence tell you how it is presented; they do not establish that its premises or conclusion are true. Check the evidence, whether the conclusion follows, and what could show it is wrong.','reasoning-explanation',frame)
