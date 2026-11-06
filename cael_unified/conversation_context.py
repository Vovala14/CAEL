"""Contextual follow-up retrieval and explicit-event reflection; no neural text.

Retrieval is a labelled corpus quotation, not an inferred fact or verification.
Unsupported specific example constraints never disappear from the query.
"""
import re
import ast

def workflow_reply(text):
 """The same checked mapping workflow owns its initial guide, not just edits."""
 hit=re.fullmatch(r'(?i)(?:please\s+)?(?:how (?:do|can|should) I|explain how to|show me how to|how to)\s+(.+?)[?!]?',text.strip())
 if not hit:return None
 subject=hit[1].strip(' .?!')
 if not re.search(r'(?i)\b(?:dictionary|dictionaries|dict)\b',subject) or not re.search(r'(?i)\b(?:loop|iterate|iteration)\b',subject):return None
 worked=mapping_example(subject,'Show a worked example.')
 if worked is not None:return worked
 from .dialogue import answer
 return answer('I cannot compile that whole dictionary workflow yet. I can show keys, values, or key/value pairs, but I have not applied the extra filter or constraint. State the complete rule and examples so it is not dropped.','mapping-clarify',unsupported_workflow=subject)

def mapping_example(subject,latest):
 """A full literal-mapping iteration example, checked by the existing VM.

 Only this explicit workflow is owned; added filters/output constraints do not
 disappear. The AST literal and every produced pair are bounded by the VM.
 """
 if not re.search(r'(?i)\b(?:dictionary|dictionaries|dict)\b',subject) or not re.search(r'(?i)\b(?:iterate|loop|iteration)\b',subject):return None
 allowed=set('how do does i you we to can could would a an the in python loop iterate iteration through over of dictionary dictionaries dict its keys values key value pairs and only for'.split())
 if not set(re.findall(r'[a-z]+',subject.casefold()))<=allowed:return None
 mode='keys' if re.search(r'(?i)\bkeys?\b',subject) and not re.search(r'(?i)\bvalues?\b',subject) else 'values' if re.search(r'(?i)\bvalues?\b',subject) and not re.search(r'(?i)\bkeys?\b',subject) else 'items'
 lead=r'(?is)(?:please\s+)?(?:show|give)(?: me)?\s+(?:(?:an?|one)\s+)?(?:(?:small|worked|concrete|short|simple|specific)\s+)*(?:example|case|illustration)'
 hit=re.fullmatch(lead+r'\s+(?:using|with)\s+(.+?)[.!]?\s*',latest)
 generic=bool(re.fullmatch(lead+r'(?:\s+with\s+(?:actual|explicit|real)\s+keys)?[.!]?\s*',latest))
 if not hit and not generic:return None
 from .codegen.python_vm import Machine,run_cases,Unsupported
 try:
  illustrative=generic
  value={'alpha':3,'beta':5} if illustrative else ast.literal_eval(hit[1])
  if type(value)!=dict or len(value)>12 or any(type(k) not in (str,int,float,bool) or type(v) not in (str,int,float,bool) for k,v in value.items()):return None
  Machine().bounded(value)
  variables='key, value' if mode=='items' else 'item';stored='(key, value)' if mode=='items' else 'item'
  source='def mapping_pairs():\n    mapping = '+repr(value)+'\n    pairs = []\n    for '+variables+' in mapping.'+mode+'():\n        pairs.append('+stored+')\n    return pairs\n'
  result=run_cases(source,[{'name':'mapping_pairs','args':[]}])
  if result['status']!='ok' or result['cases'][0]['status']!='value':return None
  pairs=result['cases'][0]['value']
 except (ValueError,SyntaxError,TypeError,RecursionError,Unsupported):return None
 from .dialogue import answer
 code='mapping = '+repr(value)+'\nfor '+variables+' in mapping.'+mode+'():\n    print('+variables+')'
 output='\n'.join(str(k)+' '+str(v) for k,v in pairs) if mode=='items' else '\n'.join(str(v) for v in pairs)
 shown='Expected output:\n```text\n'+output+'\n```' if pairs else 'No output: the empty dictionary has no '+('items' if mode=='items' else mode)+' to iterate over.'
 explanation={'items':'each key and its value','keys':'each key','values':'each value'}[mode]
 return answer(('Here is an illustrative mapping, not data from your files:\n\n' if illustrative else '')+'```python\n'+code+'\n```\n\n'+shown+'\n`.'+mode+'()` supplies '+explanation+' in insertion order.','mapping-example',verification={'status':'verified','check':'The literal mapping and every produced item were interpreted in the existing bounded AST VM, not native generated code.'},understood_as=subject)

def reflection(messages):
 from .dialogue import answer
 from .emotional_chat import preferences
 text=messages[-1]['content'].strip()
 if len(text)>450 or '```' in text or re.match(r'["“\']',text):return None
 if re.search(r'(?i)\b(?:suppose|imagine|hypothetical|for example|my friend|my colleague|my partner)\b',text):return None
 prefix=r'(?:(?:no questions(?: please)?|no advice(?: please)?)[.!]\s*)?'
 hit=re.fullmatch(r'(?i)'+prefix+r'I (enjoyed|liked|loved|finished|completed|managed to finish) (.+?)[.!]?',text)
 listen,questions=preferences(messages)
 if hit:
  verb,obj=hit.groups();obj=obj.rstrip('.!')
  lead=('You '+verb.lower()+' '+obj+'.')
  if not questions or listen:body=lead+' I can stay with what you wanted to share.'
  else:body=lead+' What part stood out to you?'
  return answer(body,'event-reflection',user_evidence={'message':len(messages)-1,'statement':text})
 hit=re.fullmatch(r'(?i)'+prefix+r'(?:the )?part I (liked|enjoyed|loved)(?: most)? was (.+?)[.!]?',text)
 if hit:
  body='You '+hit[1].lower()+' '+hit[2].rstrip('.!')+'.'
  body+=(' I can stay with that experience.' if listen or not questions else ' What stood out about that part?')
  return answer(body,'event-reflection',user_evidence={'message':len(messages)-1,'statement':text})
 hit=re.fullmatch(r'(?i)'+prefix+r'(?:I (?:just )?want to (?:say|share) (?:this|that)[: ]+)?(.{3,180}?) (?:felt|was) (satisfying|rewarding|relieving|disappointing|frustrating|gratifying)[.!]?',text)
 if hit:
  subject,feeling=hit.groups()
  if re.search(r'(?i)\b(?:not|never|no longer)\b',subject):return None
  subject=re.sub(r'(?i)\bmy\b','your',subject)
  body='You described '+subject[:1].lower()+subject[1:]+' as '+feeling.lower()+'.'
  body+=(' I can listen without turning it into a plan.' if listen or not questions else ' What part of that experience mattered most to you?')
  return answer(body,'event-reflection',user_evidence={'message':len(messages)-1,'statement':text})
 return None

def topic_request(messages):
 from .dialogue import act,ACTS
 for m in reversed(messages[:-1]):
  if m['role']!='user':continue
  text=m['content']
  if act(text)[0] in ACTS:continue
  if len(text)>500 or re.search(r'(?i)\b(?:my|our|password|secret|account|appointment)\b',text):return None
  match=re.match(r'(?i)^\s*(?:(?:can|could|would) you\s+|please\s+)?(?:explain|describe|tell me about|what (?:is|are)|how (?:does|do (?:I|you|we)|to))\s+(.+?)[?.!]?$',text)
  if match:return text,match[1].strip(' .?!')
  return None
 return None

def followup(messages,chosen):
 from .dialogue import answer
 topic=topic_request(messages)
 if topic is None:return None
 original,subject=topic;latest=messages[-1]['content'];resolved=None
 if re.fullmatch(r'(?i)(?:and )?what (?:happens|about)(?: (?:for|with|when))? (?:an? |the )?empty (?:dictionary|dict)(?: (?:in|for) python)?[?.!]*',latest.strip()):
  return mapping_example(subject,'Show an example using {}.')
 if chosen not in ('example','simpler','expand','shorter'):return None
 if chosen=='example':
  worked=mapping_example(subject,latest)
  if worked is not None:return worked
 if chosen=='example':resolved='Give an example of '+subject+'. '+latest
 elif chosen=='simpler':resolved='Explain '+subject+' in simple terms.'
 elif chosen=='expand':resolved=original
 elif chosen=='shorter':
  previous=next((m['content'] for m in reversed(messages[:-1]) if m['role']=='assistant'),'')
  if '```' in previous or len(previous)>5000:return None
  from .text_contract import transform,protected
  paragraphs=re.split(r'\n\s*\n',previous);body=paragraphs[-1] if previous.startswith('I found a similar request:') else previous
  sentences=re.split(r'(?<=[.!?])\s+',body)
  short=' '.join(sentences[:2])
  if short!=body and protected(body,short):return answer(short,'topic-summary',understood_as='Shorten the explanation of '+subject,verification={'status':'unchecked','check':'Extracted from the preceding visible answer; not an independent fact check.'})
  return None
 from . import chat_corpus
 terms=chat_corpus.topic_terms(subject)
 score,row=chat_corpus.best_match(resolved,required_terms=terms)
 if row is None:return None
 matched={chat_corpus.stem(w) for w in chat_corpus.content(row[1])}
 body=row[2].strip();have={chat_corpus.stem(w) for w in chat_corpus.content(body)}
 if not terms or not terms<=matched or not terms<=have:return None
 if chosen=='example' and not (re.search(r'(?i)\b(?:example|illustrat|demonstrat)',row[1]) or re.search(r'(?i)\bfor (?:example|instance)\b|```',body)):return None
 if chosen=='simpler' and not re.search(r'(?i)\b(?:simple|beginner|basic|easy|plain|child)\b',row[1]):return None
 # Preserve specific user-supplied example scope, rather than substituting a
 # different case just because the topic happened to match.
 scope=re.search(r'(?i)\b(?:using|with|involving|for)\s+(?:an? |the )?(.+?)[.!?]?$',latest)
 if scope and chosen=='example':
  required={chat_corpus.stem(w) for w in chat_corpus.content(scope[1])}
  if not required<=have:return None
 name,license=chat_corpus.SOURCES.get(row[4],(row[4],''))
 url={'oasst1':'https://huggingface.co/datasets/OpenAssistant/oasst1','oasst2':'https://huggingface.co/datasets/OpenAssistant/oasst2','dolly':'https://huggingface.co/datasets/databricks/databricks-dolly-15k'}.get(row[4])
 if not url:return None
 return answer(chat_corpus.shorten(body)+'\n\nRetrieved from ['+name+']('+url+') ('+license+'); not independently verified.',
   'context-corpus',sources=[{'source':name,'url':url,'licence':license}],understood_as=resolved,
   retrieval={'row':row[0],'matched':row[1],'score':score,'original_topic':original},verification={'status':'unchecked','check':'Licensed local corpus retrieval, not a checked generated solution.'})
