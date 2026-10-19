"""Non-neural question analysis and conservative freshness controls."""
import json
from pathlib import Path
import re
import unicodedata

from .bundle import ROOT
from .news_policy import intent_features, score

MODEL = ROOT / 'models/cael-knowledge-v1/query_policy.json'
FORM_WORDS = set('what who where when why which how is are was were do does did explain define describe tell me about give a definition of exactly cause causes caused happen happens important process produced formed work works occur occurs located country found in invented first developed born start began begin compare difference differences between versus vs and differ distinguishes from'.split())
STOP = set('a an the of to in on for and or is are was were do does did what who how why which when where please can could would you me i my we get tell explain about define definition meaning mean simple terms detailed answer give some briefly short more really exactly it work works happen happens caused cause causes using used use between difference differences compare versus vs'.split())
DYNAMIC = re.compile(r'\b(?:today|tonight|tomorrow|yesterday|now|latest|current|currently|recent|news|headlines|updates?|live|price|cost|worth|forecast|weather|score|scores|fixtures?|standings|schedule|president|prime minister|ceo|population|exchange rate|stock|election|available|availability|opening hours|released?|version|best|recommend|buy)\b', re.I)
HIGH_STAKES = re.compile(r'\b(?:symptoms?|diagnos\w*|treat\w*|medicin\w*|medication|dosage|dose|pain|bleeding|pregnan\w*|legal|laws?|regulations?|tax|invest\w*|medical|suicid\w*)\b', re.I)
EXPLICIT_WEB = re.compile(r'\b(?:search|look up|browse|verify|check the web|on the internet|on the web|search online)\b', re.I)
PERSONAL = re.compile(r'\b(?:your|my|our|i|story|poem|write|draw|generate|create|debug|fix)\b', re.I)


def canonical_question(text):
    """Remove request politeness without changing the subject or personal scope."""
    text = re.sub(r"(?i)\bwhat['’]?s\b", 'what is', text.strip())
    # Strip only complete request frames. "Who are you?" and "my ..." remain personal.
    text = re.sub(r'(?i)^(?:(?:can|could|would|will) you\s+(?:please\s+)?|please\s+)(?=(?:explain|define|describe|tell me|search|look up|check)\b)', '', text)
    text = re.sub(r"(?i)^(?:(?:do you know|can you tell me|could you tell me|would you tell me|tell me)\s+|(?:i (?:would like|want) to know|i['’]d like to know)\s+)(?=(?:what|who|where|when|why|which|how)\b)", '', text)
    text = re.sub(r'(?i)^explain\s+(?=(?:what|how|why)\b)', '', text)
    # Conversational public-topic requests, including topic-first wording.
    topic_first = re.fullmatch(r'(?is)(.+?)\s*[,;—]\s*(?:what (?:do you know|can you tell me) about (?:it|them|that)|tell me about (?:it|them|that))[?.!]*', text)
    overview = re.fullmatch(r'(?is)(?:what (?:do you know|can you tell me|could you tell me|can you say)|tell me (?:something|more)) about (.+?)[?.!]*', text)
    if topic_first:
        text = 'Tell me about ' + topic_first[1].strip()
    elif overview:
        text = 'Tell me about ' + overview[1].strip()
    indirect = re.fullmatch(r'(?i)(what|who|where)\s+(.+?)\s+(is|are|was|were)[?.!]*', text)
    if indirect:
        text = indirect[1] + ' ' + indirect[3] + ' ' + indirect[2] + '?'
    meaning = re.fullmatch(r'(?i)what\s+(?:does|do)\s+(.+?)\s+mean[?.!]*', text)
    if meaning:
        text = 'what is ' + meaning[1] + '?'
    text = re.sub(r'(?i)^check\s+(?:the\s+)?(?:web|internet)\s+for\s+', 'search for ', text)
    return text


def words(text):
    text = ''.join(c for c in unicodedata.normalize('NFKD', text.lower().replace('’', "'")) if not unicodedata.combining(c))
    return re.findall(r'[^\W_]+', text, flags=re.UNICODE)


def normalize(text):
    return ' '.join(words(text))


def content_words(text):
    return [w for w in words(text) if w not in STOP]


def form_features(tokens):
    return intent_features([token if token in FORM_WORDS else '<topic>' for token in tokens])


def static_allowed(text):
    if re.fullmatch(r'(?i)(?:what is|define|explain) (?:an? |the )?(?:weather|forecast|temperature|stock|price|population|president|prime minister|ceo|fixture|fixtures|score|version)[?.!]*', text.strip()):
        return True
    return not (DYNAMIC.search(text) or HIGH_STAKES.search(text) or EXPLICIT_WEB.search(text)
                or re.search(r'\b20(?:2[6-9]|[3-9]\d)\b', text))


class KnowledgeQuery:
    def __init__(self, path=None):
        path = Path(path or MODEL)
        self.model = json.loads(path.read_text(encoding='utf-8')) if path.exists() else None

    def parse(self, text):
        clean = canonical_question(text)
        question = bool(re.match(r'(?i)^(?:in (?:what|which) year|what|who|where|when|why|which|how|explain|define|describe|tell me about|give a definition|compare|difference|search|look up)\b', clean) or re.search(r'(?i)\bversus\b', clean))
        if PERSONAL.search(clean.replace('tell me about', 'explain')) or not question:
            return None
        tokens = words(clean)
        kind = 'definition'
        if self.model:
            features = form_features(tokens)
            kind = max(self.model['intents'], key=lambda label: score(self.model['intents'][label], features))
        if kind == 'comparison' and not re.search(r'(?i)\b(?:compare|difference|versus|vs|differ|distinguish\w*)\b', clean):
            kind = 'definition'
        mechanism = re.fullmatch(r'(?i)how\s+(?:(?:does|do|did)\s+)?(?:an?\s+|the\s+)?(.+?)\s+(?:work|works|operate|operates|function|functions)(?:\s+(?:in simple terms|briefly|please|exactly))*[?.!]*', clean)
        if mechanism:
            subject = mechanism[1].strip(' ?.!,')
            return dict(kind='mechanism', subject=subject[:240], terms=content_words(subject)[:16],
                        static=static_allowed(clean), original=clean)
        # Accept both question order and common declarative order. Strip the
        # question frame before retrieval so grammar cannot become topic text.
        temporal = re.fullmatch(r'(?i)(?:when|(?:in\s+)?(?:what|which)\s+year)\s+(?:(?:was|were|is|did)\s+)?(?:an?\s+|the\s+)?(.+?)\s+(?:(?:was|were|is)\s+)?(?:first\s+)?(invented|born|developed|founded|discovered|created|formed|established|started|start|begin|began)[?.!]*', clean)
        inventor = re.fullmatch(r'(?i)who\s+(invented|developed|founded|discovered|created|formed|established|started)\s+(?:an?\s+|the\s+)?(.+?)[?.!]*', clean)
        if temporal or inventor:
            event, subject = (temporal[2], temporal[1]) if temporal else inventor.groups()
            event = {'start':'started', 'begin':'started', 'began':'started', 'established':'founded'}.get(event.lower(), event.lower())
            subject = re.sub(r'(?i)\s+(?:was|were|is)$', '', subject).strip(' ?.!,')
            return dict(kind='time', event=event.lower(), focus='date' if temporal else 'agent',
                        subject=subject[:240], terms=content_words(subject)[:16], static=static_allowed(clean), original=clean)
        query = clean
        patterns = [r'(?i)^(?:please )?(?:what|who) (?:exactly )?(?:is|are|was|were) (?:an? |the )?',
                    r'(?i)^give (?:me )?(?:a )?definition of (?:an? |the )?',
                    r'(?i)^explain the process of (?:an? |the )?',
                    r'(?i)^(?:explain|define|describe|tell me about) (?:an? |the )?',
                    r'(?i)^how (?:does|do|did) (?:an? |the )?', r'(?i)^why (?:does|do|did|is|are|was|were) (?:an? |the )?',
                    r'(?i)^where (?:is|are|was|were) (?:an? |the )?', r'(?i)^when (?:was|were|did|is) (?:an? |the )?',
                    r'(?i)^(?:search(?: the (?:web|internet))? for|look up) ']
        for pattern in patterns:
            replacement, count = re.subn(pattern, '', query, count=1)
            if count:
                query = replacement
                break
        query = re.sub(r'(?i)\s+(?:work|works|in simple terms|briefly|please)[?.!]*$', '', query).strip(' ?.!,')
        if kind == 'time':
            query = re.sub(r'(?i)\s+(?:first )?(?:invented|born|developed|founded|discovered|created|happen|start|begin)[?.!]*$', '', query)
        return dict(kind=kind, subject=query[:240], terms=content_words(query)[:16], static=static_allowed(clean), original=clean)
