"""A visible-turn automaton: updates trigger replies, not a prefix whitelist."""
import re

PREFIX=r'\s*(?:please\s+)?(?:(?:can|could|would) you\s+)?'
def clean(text):return text.strip().rstrip('.!? ')
def read_writing(text):
 match=re.match(r'(?is)^'+PREFIX+r'(?:rewrite|reword|rephrase|edit (?:this|the) (?:message|text)|make (?:this|the following) (?:message|text) (?:polite|clearer|friendlier))\b([^:]*):\s*(.+)$',text)
 if match:return {'kind':'rewrite','body':match[2].strip(),'polite':bool(re.search(r'(?i)polit|formal|profession',match[1])),'formal':bool(re.search(r'(?i)(?<!in)formal|profession',match[1])),'casual':bool(re.search(r'(?i)casual|informal',match[1])),'source':text}
 match=re.match(r'(?is)^'+PREFIX+r'(?:draft|write|compose|create) (?:me )?(?:an? |the )?(?:(?:short|quick|polite|formal|friendly|brief)\s+)*(?:e-?mail|message|note)\b(.*)$',text)
 if not match:return None
 tail=match[1].strip();recipient=re.match(r'(?i)^to\s+([\w -]{1,60}?)(?=\s+(?:asking|requesting|about|to ask|to request|saying|telling)|[:,]|$)',tail)
 to=recipient[1].strip() if recipient else None;purpose=tail[recipient.end():].strip(' ,:') if recipient else tail
 mood='request'
 if re.match(r'(?i)^(?:saying|telling (?:them|him|her))(?: that)?\s+',purpose):mood='inform';purpose=re.sub(r'(?i)^(?:saying|telling (?:them|him|her))(?: that)?\s+','',purpose)
 elif re.match(r'(?i)^(?:asking|to ask) (?:for|about)\s+',purpose):mood='request_object';purpose=re.sub(r'(?i)^(?:asking|to ask) (?:for|about)\s+','',purpose)
 else:purpose=re.sub(r'(?i)^(?:asking|to ask)(?: (?:them|him|her))?\s+(?:to\s+)?','',purpose)
 if purpose.lower().startswith('whether '):mood='question'
 return {'kind':'email','body':clean(purpose),'mood':mood,'to':to,'source':text,'missing':not purpose or purpose.lower().startswith('about ')}

def goal_task(text):
 normalized=text.replace('’',"'")
 match=re.search(r"(?i)\b(?:I (?:want|hope|aim|would like|'d like) to|help me) (learn|practice|practise|improve|organize|prepare)\s+(.+?)(?=[.!?]|$)",normalized)
 if match:verb,target=match[1].lower(),match[2]
 else:
  match=re.search(r"(?i)\b(?:I(?: am|'m| would like to|'d like to)? (?:want to |hope to |am trying to |get |getting )?get better at|I(?: am|'m) trying to improve)\s+(.+?)(?=[.!?]|$)",normalized)
  if not match:return None
  verb,target='practice',match[1]
 target=re.split(r'(?i),|\b(?:but|with only|and I (?:only )?have|before work|after work)\b|\s+for\s+\d+\s+minutes?\b',target,maxsplit=1)[0].strip()
 if not target or len(target)>160:return None
 return {'kind':'goal','goal':('practice' if verb in ('improve','practise') else verb)+' '+clean(target),'source':text,
   'unsupported_condition':bool(re.search(r'(?i)\b(?:unless|only if|if|despite|without|must not|doctor|medical)\b',normalized))}

def selection(text,size):
 from .choice_context import selection as read
 return read(text,['option-placeholder-'+str(i) for i in range(size)])

def read_frame(messages):
 from .dialogue import act,budget,options,ACTS
 current=None
 for index,message in enumerate(messages):
  if message['role']!='user':continue
  text=message['content'];chosen,_=act(text);writing=read_writing(text);new_goal=goal_task(text);opts=options(text)
  if writing:current=writing;current['updated_at']=index;continue
  if opts and re.search(r'(?i)\b(?:decide|choose|ideas|options|between)\b',text) and not re.search(r'(?i)correct|right answer|\d\s*[+*/=]',text):
   current={'kind':'choice','options':opts,'source':text,'updated_at':index};continue
  if new_goal:current=new_goal;current['updated_at']=index
  elif re.search(r'(?i)\b(?:presentation|speech)\b',text) and re.search(r'(?i)\b(?:prepare|preparing|need help|plan|help)\b',text):
   current={'kind':'presentation','source':text,'topic':None,'audience':None,'updated_at':index}
  if current is None:continue
  updated=current.get('updated_at')==index
  if (minutes:=budget(text)) is not None:
   current['minutes']=minutes;updated=True
   if re.search(r'\b\d+\.\d+\s*(?:minutes?|mins?)\b',text):current['unsupported_condition']=True
  if current['kind']=='presentation':
   about=re.search(r'(?i)\babout (.+?)(?:[.!?]|$)',text);audience=re.search(r'(?i)\bfor (.+?)(?=\s+about\b|[.!?]|$)',text)
   if about:current['topic']=clean(about[1]);updated=True
   if audience:current['audience']=clean(audience[1]);updated=True
  if current['kind']=='choice':
   from .choice_context import update
   if update(current,text):updated=True
  if current['kind'] in ('email','rewrite'):
   correction=re.fullmatch(r'(?is)(?:actually[, ]+)?(?:change|replace)\s+["\']?(.+?)["\']?\s+(?:to|with)\s+["\']?(.+?)["\']?[.!]?',text.strip())
   if correction:
    if correction[1] in current.get('body',''):current['body']=current['body'].replace(correction[1],clean(correction[2]));current.pop('correction_unsupported',None)
    else:current['correction_unsupported']=True
    updated=True
   if chosen in ('formal','casual','shorter','bullets'):
    current[chosen]=True;updated=True
    if chosen in ('formal','casual'):current['casual' if chosen=='formal' else 'formal']=False
  if chosen in ('subject','number','source','recheck'):updated=True
  if chosen=='one_step':current['one_step']=True;updated=True
  elif chosen=='expand':current['one_step']=False;updated=True
  if updated:current['updated_at']=index
  elif not chosen and re.match(r"(?i)^(?:what|who|when|where|why|how|calculate|compute|explain|I |my )",text):current=None
 if current:current['changed']=current.get('updated_at')==len(messages)-1
 return current

def render_plan(task,chosen):
 from .dialogue import answer,plan
 if task.get('unsupported_condition'):return answer('I cannot safely fit every condition in that request into the current plan. Restate the time budget and the constraints to preserve.','goal-clarify')
 if task.get('selection_unsupported'):return answer('That selection contains a conflicting or unsupported option reference. Name the option you want to use.','decision-clarify')
 if task['kind']=='choice':
  from .choice_context import resolve
  uncertainty=resolve(task)
  if uncertainty:return answer(uncertainty,'decision-condition-clarify')
  rendered=plan(task,chosen)
  if task.get('selection_reason'):rendered['response']=task['selection_reason']+rendered['response']
  return rendered
 if task['kind']!='goal':return plan(task,chosen)
 goal=task['goal'];minutes=task.get('minutes');limit=str(minutes)+' minutes' if minutes else 'one short session'
 activity=goal.split(' ',1)[1]
 first='For '+limit+', choose one beginner exercise in '+activity+' and try it once, then repeat the same exercise.'
 if chosen=='one_step' or task.get('one_step'):return answer(first,'goal-step')
 return answer('For your goal to '+goal+', keep the session to '+limit+':\n\n1. Choose one small exercise in '+activity+'.\n2. Try it, check one mistake, and repeat.\n3. Write down the one part to practice next time.','goal-plan')
