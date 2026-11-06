"""Finite text transforms with preserved lexical conditions, modality and data.

These checks guard supported transforms; they do not establish arbitrary English
equivalence. The caller supplies a complete draft, not retrieved page instructions.
"""
import re

EXPAND={"can't":'cannot',"won't":'will not',"don't":'do not',"doesn't":'does not',"isn't":'is not',"aren't":'are not',"I'm":'I am',"I'll":'I will',"we're":'we are',"we'll":'we will',"you're":'you are',"it's":'it is',"that's":'that is'}
CONTRACT={v:k for k,v in EXPAND.items()}
def canonical(text):
 text=text.replace('’',"'")
 for a,b in sorted(EXPAND.items(),key=lambda kv:-len(kv[0])):text=re.sub(r'(?i)\b'+re.escape(a)+r'\b',b,text)
 text=re.sub(r'(?i)in order to','to',text)
 return ' '.join(text.casefold().split()).strip(' .!?')
def signature(text):
 canon=canonical(text)
 return {'numbers':re.findall(r'(?<!\w)[+-]?\d+(?:\.\d+)?(?:/\d+)?',canon),
   'negative':len(re.findall(r'\b(?:not|no|never|cannot|without)\b',canon)),
   'modal':re.findall(r'\b(?:must|may|might|should|shall|can|cannot|will|would)\b',canon),
   'conditions':[m[0] for m in re.finditer(r'\b(?:until|unless|if|only when|only after)\b[^.!?]*',canon)],
   'data_tokens':re.findall(r'\b[A-Z][\w-]+\b',text)}
def protected(before,after):
 a,b=signature(before),signature(after)
 names=[n for n in a['data_tokens'] if n not in {'I','Please','Could','Would','Send','Give','Do','Never','Keep','The','A','An'}]
 return a['numbers']==b['numbers'] and a['negative']==b['negative'] and a['modal']==b['modal'] and a['conditions']==b['conditions'] and all(re.search(r'(?i)\b'+re.escape(n)+r'\b',after) for n in names)
def transform(body,formal=False,casual=False,shorter=False,polite=False,bullets=False):
 original=body;body=body.strip().replace('’',"'");statement=bool(re.match(r'(?i)^(?:I|we|you|he|she|they|it|the [\w-]+|[A-Z][a-z-]+)\s+(?:am|are|is|was|were|have|has|had|cannot|can|must|may|might|should|will|would|do|does|need)\b',canonical(body)))
 if formal:
  for a,b in sorted(EXPAND.items(),key=lambda kv:-len(kv[0])):body=re.sub(r'(?i)\b'+re.escape(a)+r'\b',b,body)
 if casual:
  for a,b in sorted(CONTRACT.items(),key=lambda kv:-len(kv[0])):body=re.sub(r'(?i)\b'+re.escape(a)+r'\b',b,body)
  body=re.sub(r'(?i)^I would be grateful if you could\s+','Please ',body)
 if shorter:
  body=re.sub(r'(?i)\bin order to\b','to',body)
  body=re.sub(r'(?i)\bplease kindly\b','Please',body)
 if (polite or formal) and not casual and not shorter:
  if statement:body=body.rstrip('.!?')+'. Thank you for your understanding.'
  elif not re.match(r'(?i)^(?:please|could|would|do not|don.t|never)\b',body):body='Please '+body[:1].lower()+body[1:]
 body=re.sub(r'(?<!\w)i(?=\s|[’\'])','I',body)
 if not protected(original,body):return None
 body=body[:1].upper()+body[1:]
 if bullets:body='\n'.join('- '+part.strip().rstrip('.!?')+'.' for part in re.split(r'(?<=[.!?])\s+',body) if part.strip())
 else:body=body.rstrip('.!?')+'.'
 return body

def render(task,chosen):
 from .dialogue import answer
 if task.get('missing'):return answer('What should the message ask or tell the recipient?','writing-clarify')
 if task.get('correction_unsupported'):return answer('I could not locate that exact wording in the current draft. Give the text to replace and its replacement.','writing-clarify')
 body=task['body'].strip();formal=task.get('formal',False);casual=task.get('casual',False)
 if task['kind']=='email':
  if chosen=='subject':return answer('Request: '+body,'email-subject')
  if task.get('mood')=='inform':request=body[:1].upper()+body[1:].rstrip('.!?')+'.'
  elif task.get('mood')=='request_object':request='I am writing to ask for '+body.rstrip('.!?')+'.'
  elif task.get('mood')=='question':request='Could you confirm '+body.rstrip('.!?')+'?'
  else:
   move=re.match(r'(?i)^(move|reschedule|postpone) (.+?) (?:to|until) (.+)$',body)
   request=('Could we '+move[1].lower()+' '+move[2]+' to '+move[3]+'?' if move else 'Could you '+body[:1].lower()+body[1:].rstrip('.!?')+'?')
  if task.get('bullets') or chosen=='bullets':return answer('- '+request,'email-bullets')
  greeting=('Dear ' if formal and not casual else 'Hi ')+(task.get('to') or '[Name]')+','
  close='Thanks!' if task.get('shorter') or casual else 'Thanks,\n[Your name]'
  return answer(greeting+'\n\n'+request+'\n\n'+close,'email',draft_contract={'body':body,'to':task.get('to'),'mood':task.get('mood')})
 output=transform(body,formal=formal,casual=casual,shorter=task.get('shorter',False),polite=task.get('polite',False),bullets=task.get('bullets') or chosen=='bullets')
 if output is None:return answer('I cannot make that wording change while preserving all the conditions I can check. Please restate the intended wording.','writing-clarify',preserved_input=body)
 return answer(output,'rewrite',preserved_input=body,transformation_checks={'protected_signature':signature(body),'lexical_contract_preserved':True,'not_general_semantic_proof':True})
