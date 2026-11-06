"""Source-grounded extraction, explicit conflict/coverage; no neural synthesis.

Agreement is evidence support, not proof. Snippets and duplicate publisher/text
are never independent confirmation. Read pages remain untrusted source data.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import json,os,re,time
from urllib.parse import urlparse,urldefrag
from . import web_fetch

PRIVATE=re.compile(r'(?i)\b(?:my|mine|myself|our|ours|password|api[ _-]?key|access token|client secret)\b|[\w.+-]+@[\w.-]+\.[a-z]{2,}|[A-Z]:\\|(?:^|\s)/(?:home|users|etc)/')
WIKI=('wikipedia.org','wikidata.org','wikimedia.org','grokipedia.com')
INSTRUCTION=re.compile(r'(?i)^(?:ignore (?:all|previous|the)|system prompt|assistant:|you must now|send (?:the |your )?(?:password|token))')
def publisher(url):
    host=(urlparse(url).hostname or '').casefold().removeprefix('www.');parts=host.split('.')
    if len(parts)<2:return host
    suffix='.'.join(parts[-2:]);second={'co.uk','org.uk','ac.uk','gov.uk','com.au','org.au','co.nz','co.jp','co.il','org.il','gov.il','com.br'}
    return '.'.join(parts[-3:]) if suffix in second and len(parts)>2 else suffix
def excluded(url):
    host=(urlparse(url).hostname or '').casefold()
    return any(host==site or host.endswith('.'+site) for site in WIKI)

def relation_present(question,sentence,ws):
    definition=re.fullmatch(r'(?i)\s*what (?:is|are) (?:a |an |the )?([\w -]+?)\??\s*',question)
    if definition:
        return bool(re.match(r'(?i)^(?:a |an |the )?'+re.escape(definition[1])+r'\s+(?:is|are)\b',sentence))
    if ws.says_asked(question,sentence):return True
    # Bounded creator paraphrase: an explicitly attributed implementation is
    # relevant to "who created". This does not equate all design/author roles.
    return bool(re.match(r'(?i)^who created\b',question) and
                re.search(r'(?i)\bimplementation was (?:started|begun)\b.{0,60}\bby\s+[A-Z]',sentence))
def public_query(text):
    text=re.sub(r'(?i)^\s*(?:please\s+)?(?:(?:can|could|would) you\s+)?(?:search(?: the web| online)? for|look up|find out|check online(?: whether)?|google)\s+','',text).strip()
    return text if text and len(text)<=320 and not PRIVATE.search(text) and '```' not in text else None

def literal_sentences(text):
    """Original contiguous spans; no removed negation/asides or invented quote."""
    index=0
    for line in text.splitlines():
        for sentence in re.split(r'(?<=[.!?])\s+(?=[A-Z"“])',line.strip()):
            sentence=sentence.strip()
            if 5<=len(sentence.split())<=80 and sentence.endswith(('.','!')) and '\ufffd' not in sentence:
                if re.search(r'(?i)cookie|sign in|subscribe|privacy policy|all rights reserved|\|',sentence):continue
                index+=1;yield index,sentence

def excerpt(sentence,question,key,ws):
    """One original <=25-word span with entity, relation, key, qualifications.

    Omitted surrounding text is marked, never stitched into a new quotation.
    Multiple dates/negation/conditional qualifiers must remain in the span;
    otherwise abstain. This is conservative lexical extraction, not entailment.
    """
    words=list(re.finditer(r'\S+',sentence))
    if len(words)<=25:return sentence
    required=set(ws.terms(ws.subject_of(question)))|set(ws.terms(str(key or '')))
    focus=set(ws.terms(question))-set(ws.terms(ws.subject_of(question)))-ws.ANSWER_TYPES
    required|=focus & set(ws.terms(sentence))
    positions=[]
    for i,w in enumerate(words):
        if (set(ws.terms(w[0])) & required or re.search(r'(?i)\b(?:not|never|no|only|except|but|however|if|unless|allegedly|claimed|incorrect|false|before|after)\b|\b(?:1\d{3}|20\d{2})\b',w[0])):positions.append(i)
    if not positions:return None
    left=max(0,min(positions)-2);right=min(len(words),max(positions)+3)
    if right-left>25:return None
    if right-left<25:
        left=max(0,right-25);right=min(len(words),left+25)
    return ('… ' if left else '')+sentence[words[left].start():words[right-1].end()]+(' …' if right<len(words) else '')
def result(response,state,query,providers=(),records=(),**extras):
    sources=[]
    for item in records:
        if item.get('status')=='read' and item.get('quoted'):
            sources.append({'source':item['title'],'url':item['url'],'licence':'Short source excerpt; see publisher terms','licence_url':item['url'],'attribution':item['publisher']})
    return {'response':response,'route':'chat/web-evidence-'+state,'sources':sources,
      'verification':{'status':'unchecked','check':'Source passages are evidence support, not an independent proof of truth.'},
      'lookup':{'attempted':state!='disabled','status':state,'query':query,'providers':list(providers),'checked_at':datetime.now(timezone.utc).isoformat()},
      'evidence':{'state':state,'records':list(records),'not_independent_proof':True,**extras},
      'details':'Public lookup attempts and read-page coverage are recorded. Relevant complete excerpts use fixed lexical/type checks. Publisher and duplicated-text grouping limits agreement. No neural model or execution of page content.'}
def answer(text,force=False,exclude_wikipedia=False,source_urls=None):
    from . import web_search as ws
    question=public_query(text)
    if not question:return None
    if os.environ.get('CAEL_WEB_SEARCH','1')=='0':
        return result('Web lookup is turned off in this run. I cannot check that against live sources.','disabled',question)
    exclude_wikipedia=exclude_wikipedia or bool(re.search(r'(?i)(?:not|other than|except|without|beyond)\s+(?:just\s+)?wikipedia',text))
    try:
        if source_urls:
            results=[ws.Result('User-supplied public source',url,'','supplied URL') for url in source_urls[:3] if not PRIVATE.search(url)]
            providers=['user-supplied public source; no search query']
        else:results,providers=ws.search(question,force=force,exclude_wikipedia=exclude_wikipedia)
    except Exception:return result('I could not reach the search providers, so I have not verified that answer. You can give me a public source link to check.','unavailable',question)
    if exclude_wikipedia:results=[r for r in results if not excluded(r.url)]
    # Search suggestions are not evidence. Read a small diverse set of pages.
    selected=[];seen_urls=set();per_site={}
    for r in results:
        url=urldefrag(r.url)[0];site=publisher(url)
        if not site or url in seen_urls or per_site.get(site,0)>=2:continue
        if not url.startswith(('https://','http://')):continue
        selected.append(r);seen_urls.add(url);per_site[site]=per_site.get(site,0)+1
        if len(selected)==4:break
    if not selected:
        return result('I did not find a usable public source for that question. I will not substitute an unrelated answer.','no_results',question,providers)
    with ThreadPoolExecutor(max_workers=4) as pool:pages=list(pool.map(lambda r:ws.read_page(r.url,force=force),selected))
    records=[];readable=[]
    for r,page in zip(selected,pages):
        item={'url':page.get('url',r.url),'requested_url':r.url,'title':r.title or publisher(r.url),'publisher':publisher(page.get('url',r.url)),
              'status':page.get('status','error'),'http_status':page.get('http_status'),'reason':page.get('reason'),'checked_at':page.get('fetched_at'),'text_truncated':page.get('text_truncated',False),'quoted':False}
        records.append(item)
        if page.get('status')=='read' and page.get('text'):
            source=ws.Result(r.title,page.get('url',r.url),r.snippet,r.provider)
            readable.append((source,page['text']))
    scored=ws.best_sentences(question,readable,web_index=True,sentence_reader=literal_sentences)
    subject=set(ws.terms(ws.subject_of(question)));kind=ws.kind_of(question);candidates=[]
    for score,sentence,r,key in scored:
        # Keep original complete wording, including negation and parenthetical
        # qualifications. Old sentence normalization is not quoted as a source.
        original=next((body for source,body in readable if source is r),'')
        if sentence not in original:continue
        # A matching page title never licenses a sidebar sentence about another
        # entity. The quote itself must name the question's complete subject.
        if subject and not subject<=set(ws.terms(sentence)):continue
        if not relation_present(question,sentence,ws) or INSTRUCTION.search(sentence):continue
        if score<1.6:continue
        if kind in ('year','number','name','place') and not key:continue
        shown=excerpt(sentence,question,key,ws)
        if not shown:continue
        norm=re.sub(r'\W+',' ',sentence.casefold()).strip()
        candidates.append({'score':score,'sentence':shown,'result':r,'key':key,'text_id':norm,'publisher':publisher(r.url),
                           'negative':bool(re.search(r"(?i)\b(?:not|never|incorrect|false|no longer)\b|n.t\b",sentence))})
    if not candidates:
        hints=[r for r in selected if r.snippet][:2]
        links=' '.join(ws.link(r) for r in hints)
        message='I found pages, but could not read a passage that answers the question reliably.'
        if hints:message+=' These search results may help, but their snippets are not verification: '+links
        return result(message,'insufficient',question,providers,records)
    best=candidates[0];cut=best['score']*.65;close=[c for c in candidates if c['score']>=cut]
    # Other-key answers or a negation cannot become confirmation of the top hit.
    keys={str(c['key']).casefold() for c in close if c['key'] and not c['negative']}
    conflict=best['negative'] or (best['key'] is not None and any(c['negative'] and c['key']==best['key'] for c in close)) or len(keys)>1
    if conflict:
        examples=[];seen=set()
        for c in close:
            marker=(c['key'],c['negative'])
            if marker in seen or any(c['result'].url==old['result'].url for old in examples):continue
            seen.add(marker);examples.append(c)
            if len(examples)==2:break
        body='The retrieved passages conflict or contain a qualification, so I cannot confirm one answer.\n\n'
        for c in examples:body+='> '+c['sentence']+'\n\n'+ws.link(c['result'])+'\n\n'
        for item in records:
            for c in examples:
                if item['url']==c['result'].url:item.update(quoted=True,excerpt=c['sentence'],key=c['key'])
        return result(body.rstrip(),'conflict',question,providers,records,answer_key=None,publishers_supporting=0)
    support=[];pubs=set();texts=set()
    for c in close:
        same=(c['key'] is not None and str(c['key']).casefold()==str(best['key']).casefold()) or (c['key'] is None and c['text_id']==best['text_id'])
        if not same or c['publisher'] in pubs or c['text_id'] in texts or c['negative']:continue
        pubs.add(c['publisher']);texts.add(c['text_id']);support.append(c)
    # An untyped lexical overlap is not semantic agreement; show one excerpt.
    if best['key'] is None:support=support[:1];pubs={c['publisher'] for c in support}
    shown=support[:2] or [best]
    for item in records:
        for c in shown:
            if item['url']==c['result'].url:item.update(quoted=True,excerpt=c['sentence'],key=c['key'])
    lead=('The pages I read support **'+str(best['key'])+'**.' if best['key'] else 'Here is a relevant passage from a page I read:')
    body=lead+'\n\n> '+best['sentence']+'\n\n'+'; '.join(ws.link(c['result']) for c in shown)
    body+= ('\n\nTwo distinct publishers support this answer; that is corroboration, not proof.' if len(pubs)>=2 else
            '\n\nThis is one source, not independent confirmation.')
    return result(body,'supported' if len(pubs)>=2 else 'single-source',question,providers,records,answer_key=best['key'],publishers_supporting=len(pubs))
