"""Classical integer-count news classifier trained on dated Wikimedia summaries."""
import json
import math
from pathlib import Path
import re

from .bundle import ROOT

STOP = set('a an the and or of for to in on at by with from is are was were has have its it that this as after before during new into their who which'.split())


def words(text):
    return [word for word in re.findall(r'[a-z]+', text.lower()) if len(word) > 2 and word not in STOP]


class NewsRelevance:
    def __init__(self, path=None):
        path = Path(path or ROOT / 'models' / 'cael-news-policy-v1' / 'relevance.json')
        self.state = json.loads(path.read_text(encoding='utf-8')) if path.exists() else None

    def classify(self, text):
        if not self.state:
            return None, 0.
        tokens = set(words(text)) & self.state['vocabulary'].keys()
        if len(tokens) < 2:
            return None, 0.
        scores = []
        vocabulary = len(self.state['vocabulary'])
        for category in self.state['categories']:
            counts = self.state['counts'][category]
            total = self.state['totals'][category]
            # Equal class priors prevent common war/crime stories dominating.
            score = sum(math.log((counts.get(word, 0) + .5) / (total + .5 * vocabulary)) for word in tokens)
            scores.append((score, category))
        scores.sort(reverse=True)
        return scores[0][1], scores[0][0] - scores[1][0]


_MODEL = None


def broad_topic_match(text, topic, source_category=None):
    mapping = {'politics': 'Politics and elections', 'elections': 'Politics and elections',
               'business': 'Business and economy', 'economy': 'Business and economy',
               'science': 'Science and technology', 'technology': 'Science and technology',
               'sports': 'Sports', 'sport': 'Sports', 'crime': 'Law and crime',
               'arts': 'Arts and culture', 'culture': 'Arts and culture'}
    expected = mapping.get(topic.lower())
    if not expected:
        return None
    if topic.lower() == 'technology':
        return bool(re.search(r'\b(?:technolog\w*|software|computer\w*|chip\w*|semiconductor\w*|robot\w*|AI|artificial intelligence|internet|cyber\w*|smartphone\w*)\b', text, re.I))
    if source_category:
        return source_category == expected
    global _MODEL
    if _MODEL is None:
        _MODEL = NewsRelevance()
    category, margin = _MODEL.classify(text)
    if category is None:
        return None
    return category == expected and margin >= .5
