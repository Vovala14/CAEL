"""Questions about CAEL itself ("what is CAEL?", "what's is cael", "who are you?") answered from CAEL's own
documented facts (README.md / MODEL_CARD.md), before any web or encyclopedia lookup.

Without this, "What's is CAEL?" went through the general fact routes and the web fallback, which found the
wrestling coach Cael Sanderson on Wikipedia. Questions clearly about someone else ("Who is Cael Sanderson?")
are left alone. Rule-based; no neural model.
"""
import json
from pathlib import Path
import re

from .bundle import VERSION, BUNDLE_VERSION

ABOUT = (f"I'm CAEL (version {VERSION}), a small experimental chat assistant built from non-neural symbolic, count and "
         "automaton engines, with no neural network. CAEL is source-available, non-commercial software. "
         "On vynly.co I'm the site's helper chatbot: I answer questions about Vynly and help write prompts.")
NOT_A_PERSON = "No, I'm a program, not a person. "
ACRONYM = "CAEL's documentation does not spell out the letters, so I won't guess. "
DETAILS = ("Answered from CAEL's own description (README.md / MODEL_CARD.md) by the self-identity guard "
           "(self_identity.py), before any web lookup. No neural model.")

WHAT = r"(?:what|whats|wats|wat|wht|waht|whta|wath)"
WHO = r"(?:who|whos|hu)"
BE = r"(?:(?:is|s|are|r|was)\s+)*"
SELF = (r"(?:cael|c a e l|you|u|ya|yourself|this (?:bot|chatbot|assistant|ai|chat|thing)"
        r"|the (?:vynly )?(?:bot|chatbot|assistant|helper))")
TAIL = (r"(?:\s+(?:ai|bot|chatbot|assistant|exactly|anyway|really|actually|here|then|again|even"
        r"|on vynly(?: co)?|from vynly(?: co)?))*")
LEAD = r"(?:(?:hey|hi|hello|so|ok|okay|and|but|um|cael)\s+)*"
PATTERNS = [
    (rf"{LEAD}(?:{WHAT}|{WHO})\s+{BE}(?:the\s+)?{SELF}{TAIL}", 'about'),
    (rf"{LEAD}(?:(?:can|could) you\s+|please\s+)*(?:tell me|explain|describe|say something|talk)\s+"
     rf"(?:(?:a bit|a little|more|something)\s+)?(?:about|of)\s+{SELF}{TAIL}(?:\s+please)?", 'about'),
    (rf"{LEAD}(?:please\s+)?(?:introduce|describe|explain)\s+(?:yourself|cael)(?:\s+please)?", 'about'),
    (rf"{LEAD}{WHAT}\s+(?:kind|sort|type)\s+of\s+(?:ai|bot|chatbot|assistant|thing|model|program)\s+{BE}(?:you|u|cael)", 'about'),
    (rf"{LEAD}(?:{WHAT}\s+{BE}(?:you|u|cael)\s+made\s+(?:of|from|with)|how\s+(?:do|does)\s+(?:you|cael)\s+work)", 'about'),
    (rf"{LEAD}(?:{WHAT}\s+(?:does|do|dose|did)\s+(?:the\s+)?(?:name\s+)?cael\s+(?:stand\s+for|mean|means)"
     rf"|{WHAT}\s+{BE}cael\s+(?:short\s+for|an?\s+acronym(?:\s+for)?)"
     rf"|{WHAT}\s+{BE}(?:the\s+)?(?:meaning|acronym)\s+of\s+cael|cael\s+(?:stands\s+for|meaning))", 'acronym'),
    (rf"{LEAD}(?:is|are)\s+(?:cael|you|u)\s+(?:an?\s+)?(?:real\s+)?"
     rf"(?:wrestler|wrestling coach|coach|person|human|man|guy|athlete|celebrity)", 'person'),
]


def normalize(text):
    t = text.lower().replace('\u2019', "'")
    t = re.sub(r"\b(\w+)'s\b", r"\1 s", t)            # "what's" -> "what s"
    t = re.sub(r"\bwhat s\b", 'what', t)
    t = re.sub(r"\bwho s\b", 'who', t)
    t = re.sub(r"[^a-z0-9 ]+", ' ', t)
    return re.sub(r'\s+', ' ', t).strip()


# Whole-question readers: a site marker or the name "Cael" alone is not enough.
RELEASE_SUBJECT = (
    r"(?:(?:this|the|your|current|latest|new|installed)(?:\s+(?:current|latest|new|installed))?\s+"
    r"(?:version|release|update)(?:\s+of\s+(?:cael|this assistant|this chatbot))?"
    r"|cael(?:\s+(?:version|release|v))?(?:\s+\d+(?:\s+\d+){1,3})?"
    r"|your\s+(?:updates|changes))")
ASK = LEAD + r"(?:(?:please|can you|could you|would you)\s+)*(?:tell me\s+)?"
PRODUCT_PATTERNS = [
    (rf"{ASK}{WHAT}\s+(?:is\s+)?(?:new|different|improved|updated)\s+(?:in|with|about|for)\s+{RELEASE_SUBJECT}(?:\s+please)?", 'changes'),
    (rf"{ASK}{WHAT}\s+(?:has\s+)?changed\s+(?:in|with|about|for)\s+{RELEASE_SUBJECT}(?:\s+please)?", 'changes'),
    (rf"{ASK}{WHAT}\s+(?:are|were)\s+(?:the\s+)?(?:changes|new features|improvements|updates|fixes)\s+(?:in|to|for|with)\s+{RELEASE_SUBJECT}", 'changes'),
    (rf"{ASK}(?:show me|give me|summari[sz]e|explain)\s+(?:the\s+)?(?:changes|new features|release notes|changelog)\s+(?:in|for|to|of)\s+{RELEASE_SUBJECT}", 'changes'),
    (rf"{ASK}{WHAT}\s+(?:did|have)\s+you\s+(?:add|change|improve|fix)\s+(?:in|for|with)\s+{RELEASE_SUBJECT}", 'changes'),
    (rf"{ASK}(?:what|which)\s+(?:version|release)(?:\s+of cael)?\s+(?:are you(?:\s+(?:running|using|on))?|is this|is installed|is cael(?:\s+(?:running|using|on))?|do you run)", 'version'),
    (rf"{ASK}{WHAT}\s+(?:is\s+)?(?:your|cael s)\s+(?:(?:current|installed|latest)\s+)?(?:version|release)", 'version'),
    (rf"{ASK}(?:what|which)\s+(?:resource |model )?bundle\s+(?:do you use|are you using)", 'version'),
    (rf"{ASK}{WHAT}\s+(?:can\s+(?:you|cael)\s+do|(?:do|does)\s+(?:you|cael)\s+do|are\s+(?:your|cael s)\s+(?:features|capabilities)|are\s+you\s+capable\s+of)", 'capabilities'),
    (rf"{ASK}how\s+can\s+you\s+help(?:\s+me)?", 'capabilities'),
    (rf"{ASK}{WHAT}\s+(?:are\s+(?:your|cael s)\s+(?:limits|limitations|weaknesses)|can t\s+you\s+do|cannot\s+(?:you|cael)\s+do)", 'limitations'),
    (rf"{ASK}(?:are you (?:an? )?(?:llm|neural network|transformer)|do you use (?:qwen|transformers|neural networks)|what architecture do you use)", 'architecture'),
    (rf"{ASK}(?:did|have)\s+(?:you|cael)\s+(?:beat|beaten|outperform|outperformed)\s+qwen", 'evidence'),
]
FOLLOWUPS = [
    (r"(?:and |so )?what(?: is)? new(?: in this version| in this release)?", 'changes'),
    (r"(?:and |so )?what(?: else)? changed", 'changes'),
    (r"(?:please )?(?:tell me more|show me the changes|what improvements|what new features)", 'changes'),
    (r"what (?:did|have) you (?:add|change|improve|fix)", 'changes'),
    (r"what (?:new )?(?:features|improvements|fixes|changes) (?:did|have) you (?:add|added|make|made|implement|implemented)", 'changes'),
]


def kind(text):
    """Classify a complete question about this product, not another named entity."""
    if not isinstance(text, str) or len(text) > 240 or text.lstrip().startswith(('"', "'", '`')):
        return None
    t = normalize(text)
    for pattern, k in PATTERNS + PRODUCT_PATTERNS:
        if t and re.fullmatch(pattern, t):
            return k
    return None


def followup_kind(text):
    if not isinstance(text, str) or len(text) > 120 or text.lstrip().startswith(('"', "'", '`')):
        return None
    t = normalize(text)
    return next((k for pattern, k in FOLLOWUPS if re.fullmatch(pattern, t)), None)


def self_context(messages):
    """Only explicit visible self-questions and uninterrupted supported follow-ups."""
    active = False
    saw_user = False
    for message in messages:
        if not isinstance(message, dict):
            return False
        if message.get('role') != 'user':
            continue
        text = message.get('content')
        explicit = kind(text)
        if explicit == 'changes' and saw_user and not active and not named_product(text):
            explicit = None
        active = explicit is not None or (active and followup_kind(text) is not None)
        saw_user = True
    return active


def named_product(text):
    return isinstance(text, str) and bool(re.search(r'\bcael\b|\byour\s+(?:current|latest|new|installed|version|release|update)\b', normalize(text)))


def release_facts():
    """Installed, version-bound facts only. External pages and messages cannot replace them."""
    try:
        facts = json.loads(Path(__file__).with_name('self_knowledge.json').read_text(encoding='utf-8'))
        if facts.get('version') != VERSION:
            return None
        for field in ('changes', 'capabilities', 'limitations'):
            values = facts.get(field)
            if not isinstance(values, list) or not values or not all(isinstance(x, str) and 0 < len(x) < 400 for x in values):
                return None
        return facts
    except (OSError, ValueError, TypeError):
        return None


def requested_version(text):
    found = re.search(r'(?i)\b(?:cael\s+(?:version\s+)?|version\s+|release\s+|v(?=\d))(\d+(?:\.\d+){1,3})\b', text)
    return found[1] if found else None


def reply(messages):
    """Describe identity/current release before spelling, fact lookup or public search."""
    if not isinstance(messages, list) or not messages or not isinstance(messages[-1], dict) \
            or messages[-1].get('role') != 'user' or not isinstance(messages[-1].get('content'), str):
        return None
    question = messages[-1]['content']
    k = kind(question)
    context = self_context(messages[:-1])
    if k == 'changes' and not named_product(question) and not context and any(isinstance(m, dict) and m.get('role') == 'user' for m in messages[:-1]):
        return None  # "this release" after a Python discussion can mean Python.
    if k is None and context:
        k = followup_kind(question)
    if k is None:
        return None
    facts = release_facts()
    version = requested_version(question)
    if k in ('changes', 'version') and version and version != VERSION:
        text = f"I'm running CAEL {VERSION}. I don't have confirmed release details for CAEL {version} in my installed metadata, so I won't invent its changes."
    elif k == 'version':
        text = f"I'm running CAEL {VERSION}. That's the application/runtime version. The unchanged public resource bundle is version {BUNDLE_VERSION}; it is versioned separately."
    elif k in ('about', 'acronym', 'person', 'architecture'):
        text = {'about': ABOUT, 'acronym': ACRONYM + ABOUT, 'person': NOT_A_PERSON + ABOUT,
                'architecture': ABOUT + ' Qwen and Transformers are not part of my runtime.'}[k]
    elif facts is None:
        text = f"I'm running CAEL {VERSION}, but my installed release metadata is missing or doesn't match. I can't confirm the change list from it."
    elif k == 'changes':
        text = f"I'm running CAEL {VERSION}. Here's what's new in this release:\n\n" + '\n'.join('- ' + x for x in facts['changes'])
        text += '\n\nI still have gaps in wording and follow-ups; this is not a claim that I can handle every conversation.'
    elif k == 'capabilities':
        text = "I'm CAEL, a non-neural assistant. I can:\n\n" + '\n'.join('- ' + x for x in facts['capabilities'])
        text += '\n\nWhen a request is outside my supported patterns, I should clarify or say I cannot establish an answer.'
    elif k == 'limitations':
        text = '\n'.join('- ' + x for x in facts['limitations'])
    else:
        text = facts['evidence']
    sources = facts['sources'] if facts and k in ('changes', 'capabilities', 'limitations', 'evidence') else []
    return dict(route='chat/self-identity', response=text, sources=sources,
                details='Answered from installed, version-bound CAEL product metadata and documented runtime facts. No web lookup or external instructions.',
                self_information={'kind': k, 'application_version': VERSION, 'resource_bundle_version': BUNDLE_VERSION})
