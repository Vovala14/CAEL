"""Small trained linear news-intent and topic-slot model; no current facts stored."""
import json
from pathlib import Path
import re

from .bundle import ROOT

TOKEN = re.compile(r"[a-zA-Z0-9]+(?:['’-][a-zA-Z0-9]+)*")
MODEL = ROOT / 'models' / 'cael-news-policy-0.3.6-r1' / 'policy.json'
if not MODEL.is_file():
    MODEL = ROOT / 'models' / 'cael-news-policy-v1' / 'policy.json'
CUES = {'news', 'headlines', 'updates', 'happening', 'developments', 'happened'}
TIME = {'today', 'tonight', 'yesterday', 'latest', 'recent', 'newest', 'current', 'now', 'please', 'briefly', 'short', 'quick', 'brief', 'update', 'updates', 'news', 'headlines'}
FILLER = TIME | CUES | {'what', "what's", 'is', 'are', 'the', 'tell', 'me', 'give', 'show', 'any', 'about', 'on', 'in',
                       'for', 'from', 'with', 'of', 'to', 'a', 'an', 'and', 'can', 'could', 'you', 'around', 'right', 'going'}


def tokens(text):
    return TOKEN.findall(text.lower().replace('’', "'"))


def intent_features(words):
    features = {'bias': 1.}
    for word in words:
        features['w=' + word] = 1.
    for left, right in zip(words, words[1:]):
        features['b=' + left + '|' + right] = 1.
    return features


def slot_features(words, index):
    positions = [i for i, word in enumerate(words) if word in CUES]
    cue = min(positions, key=lambda i: abs(i - index)) if positions else index
    features = {'bias': 1., 'w=' + words[index]: 1., 'distance=' + str(max(-7, min(7, index - cue))): 1.}
    features['filler' if words[index] in FILLER else 'content'] = 1.
    for offset in (-2, -1, 1, 2):
        at = index + offset
        features[f'context{offset}=' + (words[at] if 0 <= at < len(words) else '<edge>')] = 1.
    if index == 0:
        features['first'] = 1.
    if index == len(words) - 1:
        features['last'] = 1.
    return features


def score(weights, features):
    return sum(weights.get(name, 0.) * value for name, value in features.items())


class NewsPolicy:
    def __init__(self, path=None):
        path = Path(path or MODEL)
        self.model = json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
        if self.model and self.model.get('format') != 'cael-news-policy-v1':
            raise ValueError('Unsupported news policy')

    def parse(self, text):
        from .news_time import NON_NEWS, news_scope_request, unsupported_period
        if NON_NEWS.search(text):
            return None
        if news_scope_request(text):
            return dict(topic='', limit=3, max_words=75, learned=False,
                        period='unsupported', requested_period=unsupported_period(text))
        period = 'yesterday' if re.search(r'\byesterday\b', text, re.I) else 'today' if re.search(r'\btoday\b', text, re.I) else 'recent'
        clean = re.sub(r'(?i)\b(?:this week|last week|past week|past (?:7|seven) days|last 24 hours|right now|this morning)\b', '', text)
        words = tokens(clean)
        if not words or not self.model:
            return None
        # A positive out-of-domain score is not sufficient evidence that an
        # ordinary chat request is asking for current events.
        if not set(words)&(CUES|{'latest','newest','recent','update'}) and not re.search(r"(?i)\bwhat(?:'s| is) (?:new|going on)\b",clean):
            return None
        if score(self.model['intent'], intent_features(words)) <= 0:
            return None
        selected = [word for index, word in enumerate(words)
                    if score(self.model['topic'], slot_features(words, index)) > 0 and word not in TIME]
        topic = ' '.join(selected).strip()
        if topic in ('world', 'global', 'international', 'the world', 'around the world'):
            topic = ''
        return dict(topic=topic[:180], limit=3, max_words=75, learned=True, period=period)


def shorten(text, words=55, sentences=2):
    """Bounded extractive reply: never invent a replacement sentence."""
    text = re.sub(r'\s+', ' ', text).strip()
    protected = re.sub(r'\b(?:Mr|Mrs|Ms|Dr|Prof|St|Sr|Jr|vs|etc|e\.g|i\.e|c|ca)\.',
                       lambda match: match[0].replace('.', '\ue000'), text, flags=re.I)
    protected = re.sub(r'\b(?:[A-Za-z]\.){2,}', lambda match: match[0].replace('.', '\ue000'), protected)
    protected = re.sub(r'\b[A-Z]\.(?=\s+[A-Z])', lambda match: match[0].replace('.', '\ue000'), protected)
    parts = [part.replace('\ue000', '.') for part in re.split(r'(?<=[.!?])\s+(?=[A-Z])', protected)]
    selected = []
    count = 0
    for part in parts[:sentences]:
        tokens_ = part.split()
        if count + len(tokens_) > words:
            if not selected:
                return ' '.join(tokens_[:words]).rstrip(' ,;:') + '…'
            break
        selected.append(part)
        count += len(tokens_)
    return ' '.join(selected)


def topical(text, topic, source_category=None):
    if not topic:
        return True
    from .news_relevance import broad_topic_match
    learned = broad_topic_match(text, topic, source_category=source_category)
    if learned is not None:
        return learned
    groups = {
        'technology': {'technology', 'tech', 'software', 'computer', 'computing', 'chip', 'semiconductor', 'robot', 'robotics', 'artificial intelligence'},
        'ai': {'ai', 'artificial intelligence', 'machine learning', 'openai', 'anthropic'},
        'artificial intelligence': {'ai', 'artificial intelligence', 'machine learning', 'openai', 'anthropic'},
        'sports': {'sports', 'sport', 'football', 'soccer', 'basketball', 'tennis', 'olympic'},
        'space': {'space', 'nasa', 'spacecraft', 'satellite', 'astronaut', 'rocket'},
        'israel': {'israel', 'israeli', 'jerusalem', 'tel aviv', 'gaza'},
        'uk': {'uk', 'britain', 'british', 'united kingdom'},
        'usa': {'usa', 'united states', 'u.s.', 'american'},
        'us': {'usa', 'united states', 'u.s.', 'american'},
        'climate change': {'climate', 'global warming', 'greenhouse', 'carbon emissions'},
    }
    lower = text.lower()
    phrases = groups.get(topic.lower())
    if phrases:
        return any(re.search(r'(?<!\w)' + re.escape(phrase) + r'(?!\w)', lower) for phrase in phrases)
    def stem(word):
        if word.endswith("'s"):
            word = word[:-2]
        if word.endswith('ies') and len(word) > 4:
            return word[:-3] + 'y'
        if word.endswith('s') and not word.endswith('ss') and len(word) > 3:
            return word[:-1]
        return word
    wanted = {stem(word) for word in tokens(topic)} - {'the', 'in', 'of', 'and', 'about'}
    return bool(wanted) and wanted <= {stem(word) for word in tokens(text)}
