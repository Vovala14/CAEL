"""Conversation-local explicit preferences/notes as bounded integer records.

No persistence or inferred personality. Rebuilt from user assertions on each
request; quotations, hypothetical examples and assistant statements are ignored.
The existing graph/reasoning memory still owns people, locations and plans.
"""
from array import array
import re

DETAILS = ('Explicit facts from user messages in this conversation, stored as bounded '
           'interned integer records with message provenance. Corrections replace values; '
           'unmarked disagreements ask for clarification. Forgetting removes facts from '
           'this reader, not from the visible chat transcript. No persistent profile.')
STATE, CHANGE, FORGET = range(3)
MAX_RECORDS, MAX_KEYS, MAX_VALUE = 4096, 1024, 512
ALIASES = {
    'preferred name': ('preferred name', 'name to use', 'nickname'),
    'reply style': ('reply style', 'response style', 'answer style', 'reply length'),
    'preferred language': ('preferred language', 'language preference'),
    'editor': ('preferred editor', 'editor', 'code editor'),
    'operating system': ('operating system', 'os'),
    'learning': ('learning', 'learning topic', 'study topic'),
    'goal': ('goal', 'current goal'),
    'project': ('project', 'project name'),
    'favourite music': ('favourite music', 'favorite music', 'music preference'),
    'favourite food': ('favourite food', 'favorite food'),
    'hobby': ('hobby', 'favourite hobby', 'favorite hobby'),
    'pronouns': ('pronouns', 'preferred pronouns'),
    'accessibility preference': ('accessibility preference',),
    'timezone': ('timezone', 'time zone'),
}


def clean(text):
    return ' '.join(text.replace('’', "'").split()).strip(' .!?')


def key(text):
    value = clean(text).lower()
    value = re.sub(r'^(?:my|the|your)\s+', '', value)
    for canonical, aliases in ALIASES.items():
        if value in aliases:
            return canonical
    return value


def assertion(text):
    """(key, value, opcode); only explicit first-person frames / note syntax."""
    if '\n' in text:
        return None
    text = clean(text)
    if not text or '?' in text or '```' in text:
        return None
    if re.search(r'(?i)\b(?:suppose|imagine|hypothetically|for example|pretend|if i|i might|i may|maybe i|i wish)\b', text):
        return None
    op = STATE
    prefix = re.match(r'(?i)^(?:actually[, ]+|correction[: ,]+|update[: ,]+|from now on[, ]+|now )', text)
    if prefix:
        op, text = CHANGE, text[prefix.end():]
    if re.fullmatch(r'(?i)(?:please )?forget (?:everything|all (?:my )?(?:facts|preferences|notes))', text):
        return '*', '', FORGET
    forgotten = re.fullmatch(r'(?i)(?:please )?(?:forget|do not remember|don\'t remember) (?:my |the )?([\w -]{1,64})', text)
    if forgotten:
        return key(forgotten[1]), '', FORGET
    note = re.fullmatch(r'(?i)(?:please )?remember(?: that)?\s*:\s*([\w -]{1,64})\s*(?:=|:)\s*(.{1,512})', text)
    if note:
        return key(note[1]), note[2], op
    text = re.sub(r'(?i)^(?:please )?remember that\s+', '', text)
    text = re.sub(r'(?i)^i\'m\b', 'I am', text)
    text = re.sub(r'(?i)^i\'ve been\b', 'I have been', text)
    frames = [
        (r'my (preferred name|nickname|reply style|response style|preferred language|preferred editor|operating system|goal|project name|pronouns|accessibility preference|timezone|time zone) is (.+)', None),
        (r'my project is (?:called|named) (.+)', 'project'),
        (r'i (?:am|have been) (?:currently )?(?:learning|studying) (.+)', 'learning'),
        (r'i (?:use|am using) (.+)', 'operating system'),
        (r'i prefer (?:my )?(concise|short|brief|detailed|long|step.by.step|plain.language) (?:replies|responses|answers|explanations)', 'reply style'),
        (r'my (favourite music|favorite music|favourite food|favorite food|hobby) is (.+)', None),
    ]
    for pattern, slot in frames:
        match = re.fullmatch(pattern, text, re.I)
        if not match:
            continue
        slot, value = (key(match[1]), match[2]) if slot is None else (slot, match[1])
        if slot == 'operating system' and not re.fullmatch(r'(?i)(?:windows|linux|ubuntu|debian|fedora|macos|mac os|android|ios)(?: [\w. -]{1,30})?', value):
            return None
        if re.search(r'(?i)\b(?:but|or|if|maybe|perhaps|unless)\b|["“”=]', value):
            return None
        return slot, value, op
    return None


class Profile:
    WIDTH = 4  # message, key-id, value-id, opcode

    def __init__(self):
        self.strings, self.ids, self.records = [], {}, array('i')
        self.keys, self.limited = set(), False

    def intern(self, text):
        if text not in self.ids:
            self.ids[text] = len(self.strings)
            self.strings.append(text)
        return self.ids[text]

    def add(self, message, item):
        name, value, op = item
        if op == FORGET:
            # Erase superseded interned values too; a tombstone cannot be queried
            # as a value and a summary cannot leak an earlier forgotten fact.
            kept = [(self.strings[k], self.strings[v], m, mode)
                    for m, k, v, mode in zip(*[iter(self.records)]*self.WIDTH)
                    if name != '*' and self.strings[k] != name]
            self.__init__()
            for old_key, old_value, old_message, old_op in kept:
                self.add(old_message, (old_key, old_value, old_op))
            self.records.extend((message, self.intern(name), self.intern(''), FORGET))
            self.keys.add(name)
            return True
        if len(value) > MAX_VALUE or len(self.records)//self.WIDTH >= MAX_RECORDS or name not in self.keys and len(self.keys) >= MAX_KEYS:
            self.limited = True
            return False
        self.keys.add(name)
        self.records.extend((message, self.intern(name), self.intern(value), op))
        return True

    def values(self, name):
        values = []
        for message, k, v, op in zip(*[iter(self.records)]*self.WIDTH):
            if self.strings[k] != name:
                continue
            value = self.strings[v]
            if op in (CHANGE, FORGET):
                values = []
            if op != FORGET and value.casefold() not in [old.casefold() for old, _ in values]:
                values.append((value, message))
        return values

    @classmethod
    def read(cls, messages):
        profile = cls()
        for index, message in enumerate(messages):
            if message.get('role') != 'user':
                continue
            # Do not reinterpret multiline pasted source/dialogue as user facts.
            raw = message.get('content', '')
            if '\n' in raw or '```' in raw:
                continue
            for sentence in re.split(r'(?<=[.!])\s+|;\s*', raw):
                item = assertion(sentence)
                if item:
                    profile.add(index, item)
        return profile


def question_key(text):
    text = clean(text).lower()
    fixed = {
        'what name should you use for me': 'preferred name',
        'what should you call me': 'preferred name',
        'what am i learning': 'learning', 'what am i studying': 'learning',
        'what goal am i working toward': 'goal',
        'what is my project called': 'project',
        'which operating system do i use': 'operating system',
        'what operating system do i use': 'operating system',
        'which editor do i prefer': 'editor',
        'what reply style do i prefer': 'reply style',
    }
    if text in fixed:
        return fixed[text]
    match = re.fullmatch(r'(?:what is|what\'s|remind me of|do you remember) my ([\w -]{1,64})', text)
    if match:
        return key(match[1])
    return None


def reply(messages):
    if not messages or messages[-1].get('role') != 'user':
        return None
    text = messages[-1]['content']
    item = assertion(text)
    out = lambda response, **extra: dict(response=response, route='chat/session-profile',
                                          sources=[], details=DETAILS, **extra)
    if item and (item[2] == FORGET or re.match(r'(?i)^\s*(?:please )?remember\b', text)):
        current = Profile.read(messages)
        if current.limited:
            return out('That fact exceeds the conversation memory budget; I have not recorded it.')
        if item[2] == FORGET:
            return out('I will leave '+('those facts' if item[0]=='*' else 'your '+item[0])+
                       ' out of my conversation memory. The original messages remain in the chat transcript.')
        return out('I will remember your '+item[0]+': '+item[1]+', within this conversation.')
    wanted = question_key(text)
    summary = clean(text).lower() in {'what do you remember about me', 'what have i told you about myself'}
    if wanted is None and not summary:
        return None
    profile = Profile.read(messages[:-1])
    # Only own generic keys when they were explicitly recorded. Known profile
    # questions can abstain; other personal questions belong to existing memory.
    if wanted is not None and wanted not in ALIASES and wanted not in profile.keys and '*' not in profile.keys:
        return None
    if profile.limited:
        return out('The conversation profile exceeded its record budget. I cannot reliably claim these are your current preferences; please restate the relevant fact.')
    def describe(name):
        rows = profile.values(name)
        if len(rows) > 1:
            return 'You gave conflicting values for your '+name+': '+ ' or '.join(v for v, _ in rows)+'. Which should I use?'
        if rows:
            if name == 'learning':
                return 'You are learning '+rows[0][0]+'.'
            if name == 'reply style':
                return 'You prefer '+rows[0][0]+' replies.'
            return 'Your '+name+' is '+rows[0][0]+'.'
        return 'You have not told me a current '+name+' in this chat, or asked me to forget it.'
    if wanted is not None:
        values = profile.values(wanted)
        return out(describe(wanted), memory_provenance=[i for _, i in values],
                   memory_conflict=len(values)>1)
    names = sorted(k for k in profile.keys if profile.values(k))
    if not names:
        return out('I do not have explicit profile facts to recall in this conversation.')
    lines = [describe(k) for k in names[:16]]
    if len(names)>16:
        lines.append('There are '+str(len(names)-16)+' more recorded topics; ask about one by name.')
    return out('\n'.join(lines))
