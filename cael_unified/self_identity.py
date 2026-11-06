"""Questions about CAEL itself ("what is CAEL?", "what's is cael", "who are you?") answered from CAEL's own
documented facts (README.md / MODEL_CARD.md), before any web or encyclopedia lookup.

Without this, "What's is CAEL?" went through the general fact routes and the web fallback, which found the
wrestling coach Cael Sanderson on Wikipedia. Questions clearly about someone else ("Who is Cael Sanderson?")
are left alone. Rule-based; no neural model.
"""
import re

from .bundle import VERSION

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


def kind(text):
    """'about', 'acronym' or 'person' when the whole message asks about CAEL itself, else None."""
    if not isinstance(text, str) or len(text) > 120:
        return None
    t = normalize(text)
    for pattern, k in PATTERNS:
        if t and re.fullmatch(pattern, t):
            return k
    return None


def reply(messages):
    """CAEL's own short self-description for a question about CAEL itself, else None."""
    if not isinstance(messages, list) or not messages or not isinstance(messages[-1], dict) \
            or messages[-1].get('role') != 'user' or not isinstance(messages[-1].get('content'), str):
        return None
    k = kind(messages[-1]['content'])
    if k is None:
        return None
    text = dict(about=ABOUT, acronym=ACRONYM + ABOUT, person=NOT_A_PERSON + ABOUT)[k]
    return dict(route='chat/self-identity', response=text, sources=[], details=DETAILS)