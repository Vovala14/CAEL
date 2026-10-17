"""Small classical request classifier and location/topic slot taggers."""
import json
from pathlib import Path
import re

from .bundle import ROOT
from .news_policy import tokens, intent_features, score

MODEL = ROOT / 'models' / 'cael-request-policy-0.3.6-r1' / 'policy.json'
if not MODEL.is_file():
    MODEL = ROOT / 'models' / 'cael-request-policy-v1' / 'policy.json'
FILLER = set('what is are the in for at of will it be how hot cold rain rainy raining snow snowy snowing windy weather forecast temperature wind today tomorrow tonight now right please tell me give show latest recent updates update news headlines briefly a an any like going to this week'.split())


def slot_features(words, index):
    result = {'bias': 1., 'w=' + words[index]: 1., 'filler' if words[index] in FILLER else 'content': 1.}
    for offset in (-2, -1, 1, 2):
        at = index + offset
        result[f'c{offset}=' + (words[at] if 0 <= at < len(words) else '<edge>')] = 1.
    return result


class RequestPolicy:
    def __init__(self, path=None):
        path = Path(path or MODEL)
        self.model = json.loads(path.read_text(encoding='utf-8')) if path.exists() else None

    def parse(self, text):
        words = tokens(text)
        if not self.model or not words:
            return dict(intent='other', subject='')
        # Creative requests and personal assistance are separate from public facts.
        if re.search(r'\b(?:write|draw|generate|create|code|script|python|javascript|your|my)\b', text, re.I):
            return dict(intent='other', subject='')
        features = intent_features(words)
        intent = max(self.model['intents'], key=lambda label: score(self.model['intents'][label], features))
        subject = ''
        if intent in self.model['slots']:
            weights = self.model['slots'][intent]
            subject = ' '.join(word for i, word in enumerate(words)
                               if word not in FILLER and score(weights, slot_features(words, i)) > 0)
        return dict(intent=intent, subject=subject[:180], learned=True)
