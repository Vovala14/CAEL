"""Long-term memory: what CAEL learns across sessions, never what people type.

Stored (state/ltm.json, outside the release bundle and git):
* rules     - functions CAEL learned from examples and validated on held-out cases: name, parameters, code,
              a few description words, how many checks it passed, and use/feedback counts.
* engines   - per engine route: answers given, verified, failed verification, corrected, marked wrong.
* failures  - per engine route and reason: a count only.

Not stored: message text, names, example values that are not plain numbers, or anything that identifies a
person. The conversation-memory promise ("nothing is stored after the window closes") stays true for what
people say; only CAEL's own learned rules and counters persist.
"""
import json
import os
from pathlib import Path
import re
import threading
import time

from .bundle import ROOT

PATH = Path(os.environ.get('CAEL_LTM') or ROOT / 'state/ltm.json')
MAX_RULES = 500
MIN_CONFIDENCE = 0.35
STOP = set('a an the to of in for and or is are be by with from given write function python program find check whether '
           'that this it its as on at all using which into list string number numbers me please make create returns return '
           'code def learn rule called named'.split())


def plain_example(value):
    """Only numbers, booleans and short lists of them are kept as stored examples."""
    if isinstance(value, bool) or isinstance(value, (int, float)):
        return abs(value) < 1e12
    if isinstance(value, (list, tuple)):
        return len(value) <= 8 and all(plain_example(v) for v in value)
    return False


def words(text):
    """Lowercase description words for finding a rule again. Capitalised words (names, places) are left out, so a
    description like "area for John Smith" never stores the name."""
    return sorted({w for w in re.findall(r'(?<![\w@.])[a-z]{3,}(?![\w@.])', text) if w not in STOP})[:12]


class Memory:
    def __init__(self, path=None):
        self.path = Path(path or PATH)
        self.lock = threading.Lock()
        self.data = dict(version=1, rules={}, engines={}, failures={})
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding='utf-8'))
                if loaded.get('version') == 1:
                    self.data.update(loaded)
            except (OSError, ValueError):
                pass

    def save(self):
        """Write atomically. Another process may hold the file for a moment (Windows refuses the rename then);
        retry briefly, and if it still fails keep the data in memory: a reply must never fail over a counter."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_name(f'{self.path.stem}.{os.getpid()}.{threading.get_ident()}.tmp')
            temp.write_text(json.dumps(self.data, indent=1, sort_keys=True), encoding='utf-8')
        except OSError:
            return False
        for attempt in range(5):
            try:
                os.replace(temp, self.path)
                return True
            except PermissionError:
                time.sleep(0.02 * (attempt + 1))
            except OSError:
                break
        try:
            temp.unlink()
        except OSError:
            pass
        return False

    # Engines ------------------------------------------------------------------------------------
    def record(self, route, event, reason=None):
        """event: answered | verified | failed | corrected | wrong."""
        family = route_family(route)
        with self.lock:
            stats = self.data['engines'].setdefault(family, dict(answered=0, verified=0, failed=0, corrected=0, wrong=0))
            stats[event] = stats.get(event, 0) + 1
            if reason and event in ('failed', 'wrong'):
                key = f'{family}: {reason[:80]}'
                self.data['failures'][key] = self.data['failures'].get(key, 0) + 1
            self.save()

    def confidence(self, route):
        stats = self.data['engines'].get(route_family(route))
        if not stats:
            return None
        good = stats.get('verified', 0)
        bad = stats.get('failed', 0) + stats.get('wrong', 0)
        return round((good + 1) / (good + bad + 2), 3)

    # Rules --------------------------------------------------------------------------------------
    def add_rule(self, name, params, code, description, checks, examples=()):
        kept = [[list(args), out] for args, out in examples if all(plain_example(a) for a in args) and plain_example(out)][:6]
        with self.lock:
            rules = self.data['rules']
            old = rules.get(name)
            if old and old['code'] != code and old['checks'] >= checks and confidence(old) >= 0.5:
                return old            # keep the better-tested rule already known under this name
            rules[name] = dict(name=name, params=list(params), code=code, words=words(description + ' ' + name.replace('_', ' ')),
                               checks=int(checks), examples=kept, uses=0, good=0, wrong=0,
                               learned=time.strftime('%Y-%m-%d'))
            if len(rules) > MAX_RULES:
                worst = min(rules.values(), key=lambda r: (confidence(r), r['uses']))
                rules.pop(worst['name'], None)
            self.save()
            return rules[name]

    def rule(self, name):
        found = self.data['rules'].get(name)
        return found if found and confidence(found) >= MIN_CONFIDENCE else None

    def find_rule(self, text):
        """The learned rule a request names or best describes, or None."""
        lower = text.lower()
        for name, rule in self.data['rules'].items():
            if re.search(r'\b' + re.escape(name.lower()) + r'\b', lower) and confidence(rule) >= MIN_CONFIDENCE:
                return rule
        asked = set(words(text))
        best, score = None, 0.0
        for rule in self.data['rules'].values():
            if confidence(rule) < MIN_CONFIDENCE or not rule['words']:
                continue
            overlap = len(asked & set(rule['words'])) / len(set(rule['words']))
            if overlap > score:
                best, score = rule, overlap
        return best if score >= 0.75 else None

    def rule_feedback(self, name, good):
        with self.lock:
            rule = self.data['rules'].get(name)
            if not rule:
                return None
            rule['good' if good else 'wrong'] += 1
            if not good and confidence(rule) < MIN_CONFIDENCE:
                self.data['rules'].pop(name)      # repeatedly marked wrong: forget it
            self.save()
            return rule

    def used(self, name):
        with self.lock:
            if name in self.data['rules']:
                self.data['rules'][name]['uses'] += 1
                self.save()

    def summary(self):
        rules = sorted(self.data['rules'].values(), key=lambda r: -r['uses'])
        engines = sorted(self.data['engines'].items(), key=lambda kv: -kv[1].get('answered', 0))
        return dict(rules=[(r['name'], r['checks'], confidence(r), r['uses']) for r in rules],
                    engines=[(name, stats, self.confidence(name)) for name, stats in engines],
                    failures=sorted(self.data['failures'].items(), key=lambda kv: -kv[1])[:10])


def confidence(rule):
    """Checks passed count as evidence; each 'that's wrong' from a person counts against it."""
    good = min(rule.get('checks', 0), 10) + rule.get('good', 0)
    return (good + 1) / (good + 3 * rule.get('wrong', 0) + 2)


def route_family(route):
    """'chat/code-from-description' -> 'chat/code'; 'helper/arithmetic' stays."""
    route = route or 'unknown'
    if route.startswith('chat/'):
        return 'chat/' + route[5:].split('-')[0]
    return route


_memory = None


def memory():
    global _memory
    if _memory is None or _memory.path != Path(os.environ.get('CAEL_LTM') or PATH):
        _memory = Memory()
    return _memory
