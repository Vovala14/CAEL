"""Conversation-local grammar editing; no persistent state or generative model."""
import re

from . import grammar

PREFIX = re.compile(
    r'(?is)^\s*(?:(?:hi|hello|hey)[,!]?\s+)?(?:please\s+)?'
    r'(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?)?'
    r'(?:correct|fix|check|proofread|edit|improve)\s+'
    r'(?:(?:the|my|this|following)\s+)?'
    r'(?:english\s+)?(?:grammar|grammer|gramar|spelling|sentence|text|paragraph|english)\b')
BARE = re.compile(r'(?is)^\s*(?:please\s+)?(?:correct|fix|proofread)\s*:\s*(.*)$')
CODE = re.compile(r'```|(?m:^\s*(?:def |class |import |from \w+ import |return |\w+\s*=))')
PLAIN = re.compile(r'(?i)^(?:please\s+)?(?:just (?:the )?(?:corrected |fixed )?(?:sentence|text|answer)|'
                   r'(?:only|show only|give me only) (?:the )?(?:corrected |fixed )?(?:sentence|text|answer)|'
                   r'no explanation(?: please)?|without (?:an? )?explanation)\s*[.!?]*$')
WHY = re.compile(r'(?i)^(?:why|why is that|explain(?: (?:that|it|the changes|the correction))?|'
                 r'what did you change|why did you change (?:it|that))\s*[.!?]*$')
ASK = 'Send the sentence or paragraph you want me to check (up to 2,000 characters).'
NEW_TASK = re.compile(r'(?i)^(?:what|who|where|when|why|how|calculate|compute|write|generate|draw|find|search|stop|cancel)\b')


def request(text):
    """(is explicit editing request, target), preserving the original target case."""
    m = BARE.match(text)
    if m:
        return True, m[1].strip()
    m = PREFIX.match(text)
    if not m:
        return False, None
    rest = text[m.end():].strip()
    # Do not consume a word merely containing a grammar command or a factual
    # question such as "check the grammar of Python code" as prose to rewrite.
    rest = re.sub(r'(?i)^[,\s]*(?:please|for me)\s*[?.!]*\s*$', '', rest)
    rest = re.sub(r'(?i)^and\s+(?:the\s+)?(?:grammar|spelling)\b', '', rest).strip()
    rest = re.sub(r'(?i)^\s*(?:in|of|for|on)\s+', '', rest)
    rest = re.sub(r'(?i)^(?:this|the following)(?:\s+(?:sentence|text|paragraph))?\s*[:\u2014-]\s*', '', rest)
    if re.fullmatch(r'(?i)(?:this|the following)(?:\s+(?:sentence|text|paragraph))?\s*[?.!]*', rest):
        rest = ''
    rest = re.sub(r'(?i)^(?:please|for me)\s*[?.!]*\s*$', '', rest)
    rest = rest.lstrip(':?\u2014- \n').strip()
    if re.fullmatch(r'[?.!]*', rest):
        rest = ''
    return True, rest


def result_text(answer):
    m = re.match(r'(?:Corrected|Almost correct, just tidied): \*\*(.*?)\*\*(?:\n|$)', answer, re.S)
    if m:
        return m[1]
    m = re.match(r'I found no common-rule errors in "(.*?)"', answer, re.S)
    return m[1] if m else None


def editing_answer(answer):
    return answer == ASK or result_text(answer) is not None or answer.startswith('Grammar changes:\n')


def last_edit(messages):
    """Recover one explicit editing task through its own short follow-ups only."""
    if len(messages) < 3 or messages[-2].get('role') != 'assistant':
        return None
    previous_user = messages[-3]['content'] if messages[-3].get('role')=='user' else ''
    if not editing_answer(messages[-2]['content']) and not (PLAIN.fullmatch(previous_user.strip()) or WHY.fullmatch(previous_user.strip())):
        return None
    for index in range(len(messages)-3, max(-1,len(messages)-13), -1):
        msg = messages[index]
        if msg.get('role') != 'user':
            continue
        if index+1 >= len(messages) or messages[index+1].get('role') != 'assistant':
            return None
        explicit, target = request(msg['content'])
        if explicit:
            return target, messages[index+1]['content']
        # Only traverse replies that belong to this editing exchange. No
        # factual topic or another user's/system text becomes the edit target.
        if PLAIN.fullmatch(msg['content'].strip()) or WHY.fullmatch(msg['content'].strip()):
            continue
        again = re.match(r'(?is)^(?:and (?:this|this one)|now this|another (?:sentence|one))\s*:\s*(.+)$', msg['content'].strip())
        if again and editing_answer(messages[index+1]['content']):
            return again[1], messages[index+1]['content']
        if index and messages[index-1].get('role')=='assistant' and messages[index-1]['content']==ASK:
            return msg['content'], messages[index+1]['content']
        return None
    return None


def fix(target):
    if not target:
        return grammar.out(ASK, 'ask')
    if len(target)>2000:
        return grammar.out('Please send one paragraph at a time, up to 2,000 characters.', 'limit')
    if CODE.search(target):
        return None
    return grammar.fix_reply(target)


def protect_input(text, messages):
    """The grammar editor, not the chat typo model, owns the original edit target."""
    if request(text)[0] or grammar.ASK_FIX.match(text) or grammar.ASK_CHECK.match(text):
        return True
    if not last_edit(messages):
        return False
    current = text.strip()
    return bool(PLAIN.fullmatch(current) or WHY.fullmatch(current)
                or re.match(r'(?i)^(?:and (?:this|this one)|now this|another (?:sentence|one))\s*:', current)
                or (messages[-2]['content']==ASK and not NEW_TASK.match(current)))


def reply(text, messages):
    explicit, target = request(text)
    if explicit:
        return fix(target)
    active = last_edit(messages)
    if not active:
        return None
    target, previous = active
    current = text.strip()
    if messages[-2]['content']==ASK:
        # A clear new task cancels the pending edit. Question-form learner
        # sentences ("Does she likes tea?") can still be submitted for editing.
        if NEW_TASK.match(current):
            return None
        return fix(current)
    if PLAIN.fullmatch(current):
        corrected = result_text(previous)
        if corrected:
            return grammar.out(corrected, 'plain')
    if WHY.fullmatch(current):
        notes = previous.split('What I changed:\n',1)
        if len(notes)==2:
            return grammar.out('Grammar changes:\n'+notes[1], 'explain')
        if result_text(previous):
            return grammar.out('No common-rule errors were found. This is a limited rule check, not a guarantee of perfect English.', 'explain')
    again = re.match(r'(?is)^(?:and (?:this|this one)|now this|another (?:sentence|one))\s*:\s*(.+)$', current)
    if again:
        return fix(again[1])
    return None
