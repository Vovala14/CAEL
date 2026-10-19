"""Resolve a public-topic pronoun using this conversation's user questions only.

This supplies a subject, never a remembered answer. Lookup still verifies the
current question and retains its existing freshness/abstention controls.
"""
import re
from .knowledge_query import canonical_question,content_words

IT=re.compile(r'\b(?:it|its)\b')
DEICTIC=re.compile(r'(?i:^(?:what|who)\s+(?:is|was|are|were)\s+)(?:this|that)[?.!]*$')
ACK=re.compile(r'(?i)^\s*(?:thanks|thank you|okay|ok|got it|understood|i see)[.!,\s]*$')
FORBIDDEN=re.compile(r'(?i)\b(?:i|my|our|your|you|story|poem|code|python|javascript|function|account|password|token|secret)\b|https?://|```')
NON_TOPIC=re.compile(r'(?i)\b(?:news|headlines|weather|forecast|live score|standings|stock price)\b')
LITERAL=re.compile(r'''(?i)[`"“'](?:it|its|this|that)[`"”']|\b(?:word|term|pronoun)\s+(?:it|its|this|that)\b''')
COMPARISON=re.compile(r'(?i)\b(?:compare|compares|comparison|differences?|versus|vs|differ|differs|distinguish\w*)\b')


def anaphoric(text):
    return bool(IT.search(text) or DEICTIC.fullmatch(text))


def needs_topic(text):
    canonical=canonical_question(text)
    return bool(len(canonical)<=1600 and anaphoric(canonical)
                and not (FORBIDDEN.search(canonical) or NON_TOPIC.search(canonical) or LITERAL.search(canonical))
                and re.match(r'(?i)^(?:what|who|when|where|why|which|how|explain|define|describe|tell me about)\b',canonical))


def substitute(text,topic):
    if DEICTIC.fullmatch(text):
        return re.sub(r'(?i)\b(?:this|that)\b',lambda _:topic,text)
    return IT.sub(lambda m:topic+("'s" if m[0].lower()=='its' else ''),text)


def topic_from_history(messages,policy):
    topic=None
    for i in range(max(0,len(messages)-41),len(messages)-1):
        item=messages[i]
        if item.get('role')!='user' or i+1>=len(messages)-1:continue
        if messages[i+1].get('role')!='assistant':continue
        text=canonical_question(item['content'])
        if ACK.fullmatch(text):continue
        if len(text)>1600 or FORBIDDEN.search(text) or NON_TOPIC.search(text) or LITERAL.search(text) or COMPARISON.search(text):
            topic=None;continue
        if anaphoric(text):
            if not topic:continue
            parsed=policy.parse(substitute(text,topic))
            if not parsed or parsed['kind']=='comparison':topic=None
            # The referred subject remains the topic, not the property noun
            # introduced by "its ..." or an answer returned by the assistant.
            continue
        parsed=policy.parse(text)
        if (not parsed or not parsed.get('static') or parsed['kind']=='comparison'
                or not parsed['terms'] or not 1<=len(content_words(parsed['subject']))<=8
                or len(parsed['subject'])>160):
            topic=None;continue
        topic=parsed['subject']
    return topic


def resolve(text,messages,policy):
    canonical=canonical_question(text)
    if not messages or not needs_topic(canonical):
        return text,None
    topic=topic_from_history(messages,policy)
    if not topic:return text,None
    rewritten=substitute(canonical,topic)
    return rewritten,dict(subject=topic,question=rewritten)
