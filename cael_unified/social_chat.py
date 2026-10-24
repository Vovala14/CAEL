"""Bounded, authored small talk with conversation-local topic follow-ups."""
import random
import re

DETAILS = 'Authored non-neural small-talk patterns and questions. Context comes only from this conversation; no factual lookup or persistent profile.'
TOPICS = {
    'music': (r'music|jazz|rock|pop|classical|metal|hip hop|rap|songs?|guitar|piano', [
        'What kind of music have you been listening to lately?',
        'What draws you to a song: the melody, the lyrics, or the rhythm?',
        'Do you usually listen while doing something else, or give the music your full attention?',
        'Is there a song you keep coming back to?']),
    'movies': (r'movies?|films?|cinema|sci fi|science fiction|comedies|comedy|thrillers?', [
        'What kind of movie are you usually in the mood for?',
        'Do you prefer a clever plot, interesting characters, or a great atmosphere?',
        'Is there a movie you enjoy watching again?',
        'Do you tend to watch movies on your own or with someone else?']),
    'books': (r'books?|reading|novels?|fiction|fantasy|poetry', [
        'What do you enjoy reading?',
        'Do you prefer getting lost in a story or learning something new?',
        'What makes you keep turning the pages?',
        'Do you have a favourite place to read?']),
    'games': (r'games?|gaming|video games?|board games?|chess|puzzles?', [
        'What kind of games do you enjoy?',
        'Do you prefer a challenge, a good story, or something relaxing?',
        'Do you usually play on your own or with friends?',
        'What keeps you coming back to a game?']),
    'outdoors': (r'hiking|walking|walks|camping|cycling|biking|nature|outdoors|gardening', [
        'What do you like doing outdoors?',
        'Do you prefer a familiar route or exploring somewhere new?',
        'Is being outdoors a way to relax for you, or more of an adventure?',
        'What would make an ideal afternoon outside?']),
    'food': (r'food|cooking|baking|recipes?|pizza|pasta|coffee|tea', [
        'What is something you enjoy cooking or eating?',
        'Do you like trying new flavours or sticking with familiar favourites?',
        'Is there a dish you would like to learn to make?',
        'Do you enjoy the cooking itself, or mostly the finished meal?']),
    'hobbies': (r'hobbies|photography|painting|drawing|crafts|knitting|dancing', [
        'What do you enjoy doing in your spare time?',
        'Do you prefer making something, practising a skill, or just relaxing?',
        'Is there a hobby you would like to try?',
        'What is a small project you would enjoy spending an afternoon on?']),
    'day': (r'my day|today|weekend|my week', [
        'How has your day been?',
        'Was there a small moment you enjoyed today?',
        'Would you rather talk about your day or take your mind off it?',
        'Is there anything you are looking forward to?']),
}
MENU = 'Would you like to talk about music, movies, hobbies, or how your day went?'
FUN = [
    'Would you rather explore a forest or a lively city?',
    'Would you rather learn a musical instrument or a new language?',
    'Would you rather have a quiet weekend or try something completely new?',
    'Would you rather invent a board game or write a short story?',
]
FUN_CHOICES = [('forest','city'), ('instrument','language'), ('quiet','new'), ('board game','story')]
FUN_WHY = 'What makes that choice appealing to you?'
FUN_MORE = 'Would you like another light question?'
LABELS = {'day':'your day','outdoors':'getting outdoors', **{k:k for k in TOPICS if k not in ('day','outdoors')}}
INVITE = re.compile(r"(?i)^(?:(?:can|could) we (?:just )?(?:chat|talk)|let'?s (?:just )?(?:chat|talk)|"
                    r"(?:please )?(?:chat with me|talk to me|keep me company)|"
                    r"i (?:just )?(?:want|would like) to (?:chat|talk)|i'?m just here to chat|"
                    r"what (?:shall|should|can) we talk about|start a conversation)$")
CHANGE = re.compile(r"(?i)^(?:let'?s )?(?:change (?:the )?(?:subject|topic)|talk about something else|"
                    r"something else|another topic|ask me another question|ask something else)$")
DECLINE = re.compile(r"(?i)^(?:no|nope|nah|not really|not now|no thanks|rather not|"
                     r"i (?:do not|don't) want to (?:talk about (?:it|that)|answer)|i'?d rather not say)$")
RECIPROCAL = re.compile(r'(?i)^(?:and you|what about you|how about you|your turn)$')
STOP = re.compile(r"(?i)^(?:stop|let'?s stop|that'?s enough|no more questions|stop asking(?: me)? questions|"
                  r"leave me alone|i (?:do not|don't) want to (?:chat|talk)(?: anymore)?)$")
NEW_TASK = re.compile(r'(?i)\b(?:what|who|where|when|why|how|which|explain|define|calculate|compute|'
                      r'write|fix|correct|check|translate|generate|draw|search|look up|latest|news|weather|'
                      r'can you|could you|tell me about|read|delete|remove|touch|find|run|test|debug|review|'
                      r'install|download|help|summari[sz]e|convert|solve|show)\b')
DISTRESS = re.compile(r'(?i)\b(?:sad|tired|stressed|lonely|sick|ill|hurt|died|dead|death|lost|crying|'
                     r'suicide|kill|abuse|scared|afraid|anxious|depressed|unhappy)\b')


def clean(text):
    return re.sub(r'\s+', ' ', text.strip().replace('’', "'")).rstrip(' .!?').lower()


def topic(text):
    found = [key for key,(pattern,_) in TOPICS.items() if re.search(r'(?i)\b(?:'+pattern+r')\b', text)]
    return found[0] if len(found)==1 else None


def context(messages):
    if len(messages)<3 or messages[-2].get('role')!='assistant':
        return None
    previous=messages[-2]['content'].strip()
    if previous.endswith(MENU):return 'menu'
    if any(previous.endswith(q) for q in FUN):return 'fun'
    if previous.endswith(FUN_WHY):return 'fun-reason'
    if previous.endswith(FUN_MORE):return 'fun-more'
    for key,(_,questions) in TOPICS.items():
        if any(previous.endswith(q) for q in questions):return key
    return None


def reply(messages, seed=0):
    if not messages or messages[-1].get('role')!='user':return None
    raw=messages[-1]['content'].strip()
    if not raw or len(raw)>240 or '\n' in raw or '```' in raw:return None
    text=clean(raw)
    rng=random.Random(f'{seed}:{text}')
    recent='\n'.join(m['content'] for m in messages[-13:-1] if m.get('role')=='assistant')
    def pick(choices):
        fresh=[q for q in choices if q not in recent]
        return rng.choice(fresh or choices)
    def out(answer,kind):
        return dict(response=answer,route='chat/smalltalk-'+kind,sources=[],details=DETAILS)
    def ask(key,lead=''):
        return out((lead+' ' if lead else '')+pick(TOPICS[key][1]),'topic')
    active=context(messages)
    if active and STOP.fullmatch(text):
        return out('No problem. We can stop here.','pause')
    if INVITE.fullmatch(text):
        return out(pick(['Sure, we can just chat.', "Of course. What's on your mind?"])+' '+MENU,'invite')
    if re.fullmatch(r'(?:ask me (?:a |something )?(?:fun|interesting)(?: question)?|ask me a question|ask me something|let\'?s play would you rather)',text):
        return out(pick(FUN),'fun-question')
    if re.fullmatch(r'how (?:was|is) your (?:day|weekend)|how has your day been',text):
        return ask('day', "I don't have a day like a person does, but I'm here and ready to chat.")
    if CHANGE.fullmatch(text) or (active and DECLINE.fullmatch(text)):
        if active in TOPICS:
            choices=[k for k in TOPICS if k!=active]
            unused=[k for k in choices if not any(q in recent for q in TOPICS[k][1])]
            chosen=rng.choice(unused or choices)
            return ask(chosen,f'No problem, we can switch topics and talk about {LABELS[chosen]}.')
        if DECLINE.fullmatch(text):
            return out('No problem. We can leave that there. '+MENU,'change-topic')
        return out('No problem. '+pick(FUN),'change-topic')
    if active and RECIPROCAL.fullmatch(text):
        if active in TOPICS:
            return ask(active,"I don't have personal experiences or favourites, but I can explore what you enjoy.")
        return out("I don't have personal preferences, but I'm happy to hear yours. "+pick(FUN),'reciprocal')
    if active=='fun-more' and text in {'yes','please','sure','okay','another one','yes please'}:
        return out(pick(FUN),'fun-question')
    if active=='fun-reason' and 1<=len(text.split())<=20 and not raw.endswith('?') \
            and not NEW_TASK.search(text) and not DISTRESS.search(text) \
            and text not in {'hello','hi','hey','thanks','thank you','bye','goodbye','sorry'}:
        return out('Thanks for explaining your choice. '+FUN_MORE,'fun-followup')
    # Every direct preference/topic request must match in full. A question,
    # task, quotation or unrelated clause is never consumed as casual news.
    preference=re.fullmatch(r"i (?:really )?(?:like|love|enjoy|am into) ([a-z][a-z0-9 '\-]{0,70})",text)
    discuss=re.fullmatch(r"(?:let'?s (?:talk|chat) about|can we (?:talk|chat) about|i (?:want|would like) to (?:talk|chat) about) ([a-z][a-z '\-]{0,50})",text)
    negative=re.fullmatch(r"i (?:do not|don't) (?:really )?(?:like|enjoy) ([a-z][a-z '\-]{0,50})",text)
    match=preference or discuss or negative
    if match and not NEW_TASK.search(match[1]) and not DISTRESS.search(match[1]) \
            and not re.search(r'\b(?:but|because|although|however)\b',match[1]) \
            and (not raw.endswith('?') or discuss):
        key=topic(match[1])
        if key and negative:
            chosen=rng.choice([k for k in TOPICS if k!=key])
            result=ask(chosen,f'Fair enough; we could talk about {LABELS[chosen]} instead.')
            result['route']='chat/smalltalk-preference'
            return result
        if key:return ask(key)
    if re.fullmatch(r"my day (?:was|is|has been) (?:pretty |really |very )?(?:good|great|fine|okay|ok|quiet|busy|rough|tiring|bad)",text):
        if re.search(r'\b(?:rough|tiring|bad)\b',text):
            return ask('day','That sounds like a demanding day.')
        return ask('day')
    if not active or raw.endswith('?') or NEW_TASK.search(text) or DISTRESS.search(text):return None
    if re.fullmatch(r'(?:hi|hello|hey|thanks|thank you|thank you very much|bye|goodbye|sorry|ok|okay|got it)',text) \
            or re.match(r'(?:my name is|call me|i am called|i (?:am|feel) (?:not |very |really )?)\b',text):
        return None
    if active=='menu':
        key=topic(text)
        if key and len(text.split())<=6:return ask(key)
        if text in {'hobbies','my hobbies'}:return out('What do you enjoy doing in your spare time?','hobbies')
        if text in {'both','either','anything','you choose','surprise me'}:return out(pick(FUN),'fun-question')
        return None
    if active=='fun':
        if 1<=len(text.split())<=12 and not re.search(r'[=:<>`]',raw):
            offered=FUN_CHOICES[next(i for i,q in enumerate(FUN) if messages[-2]['content'].strip().endswith(q))]
            if (not any(choice in text for choice in offered) and text not in {'both','neither','either','not sure'}) \
                    or (re.search(r"\b(?:not|never|don't)\b",text) and text!='not sure'):
                return out('Which of those two would you choose? '+messages[-2]['content'].strip(),'fun-clarify')
            return out(FUN_WHY,'fun-followup')
        return None
    if active in TOPICS:
        if text in {'more','tell me more','another question','go on','continue','both','either','not sure','i do not know',"i don't know"}:
            return ask(active)
        # A short reply is acknowledged without inferring factual claims or
        # emotional polarity from a name/song title/genre it cannot interpret.
        if 1<=len(text.split())<=12 and re.fullmatch(r"[\w '\-]+",text):
            return ask(active,'Thanks for sharing.')
    return None
