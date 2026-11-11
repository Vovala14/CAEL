"""Offline checks for web_check.py: a don't-know reply is replaced only by a checked answer.

run: python test_web_check.py   (from dev_runtime; no network used)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from urllib.parse import urlparse, parse_qs
from cael_unified import web_check
from cael_unified.network import LookupUnavailable

PAGES = {
    ('en.wikipedia.org', 'Rainbow'): 'A rainbow is an optical phenomenon. The rainbow is curved because the set of all the raindrops that have '
                                     'the right angle between the observer, the drop, and the Sun lies on a cone pointing at the sun.',
    ('en.wikipedia.org', 'Mona Lisa'): 'The Mona Lisa is a portrait by Leonardo da Vinci. It was believed to have been painted between 1503 and '
                                       '1506; however, Leonardo may have continued working on it as late as 1517.',
    ('simple.wikipedia.org', 'Mona Lisa'): 'The Mona Lisa is a famous painting. Leonardo painted it between 1503 and 1506 in Florence.',
    ('en.wikipedia.org', 'Mona Lisa (film)'): 'Mona Lisa is a 1986 film. It took 42 days to shoot the film in London.',
    ('simple.wikipedia.org', 'Houseplant'): 'A houseplant is a plant grown indoors. Many houseplants are easy to grow.',
}


WEB = {   # open-web pages: url -> (title, text)
    'https://www.catvet.example/purr': ('Why Do Cats Purr? | Cat Vet', 'Cats purr when they are content. Cats purr because the brain sends '
                                        'signals to the laryngeal muscles, which twitch and make the vocal folds vibrate as the cat breathes.'),
    'https://pets.sample.org/cats/purring': ('Cat purring explained', 'Purring in cats happens because nerve signals make the laryngeal muscles '
                                              'twitch, so the vocal folds vibrate with each breath in and out.'),
    'https://www.catvet.example/purr-2': ('Why cats purr - Cat Vet', 'Cats purr because the laryngeal muscles twitch rapidly.'),
    'https://copy.sample.net/rainbow': ('Rainbow facts', 'The rainbow is curved because the set of all the raindrops that have the right '
                                         'angle between the observer, the drop, and the Sun lies on a cone pointing at the sun.'),
}


class Hit:
    def __init__(self, url):
        self.url, self.title = url, WEB[url][0]


def stub_web(urls):
    from cael_unified import web_search, web_fetch
    calls = []
    web_search.metasearch = lambda q: calls.append(q) or [Hit(u) for u in urls]
    web_search.duckduckgo = lambda q: []
    web_fetch.fetch = lambda url, timeout=6: dict(status='read', url=url, text=WEB[url][1] + ' ' + 'Filler sentence about pets here. ' * 10)
    web_search._CACHE.clear()
    return calls


class Stub:
    def __init__(self, down=False):
        self.down = down

    def json(self, url, **kw):
        if self.down:
            raise LookupUnavailable('offline')
        u = urlparse(url); q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if q.get('list') == 'search':
            words = set(q['srsearch'].lower().split())
            hits = [t for (h, t) in PAGES if h == u.hostname and words & set(t.lower().replace('(', '').replace(')', '').split())]
            return dict(query=dict(search=[dict(title=t) for t in hits]))
        text = PAGES.get((u.hostname, q['titles']))
        return dict(query=dict(pages={'1': dict(title=q['titles'], extract=text, fullurl='https://x/' + q['titles'])} if text else {}))


def convo(*turns):
    m = []
    for t in turns:
        m += [dict(role='user', content=t), dict(role='assistant', content='...')]
    return m[:-1]


DONT_KNOW = dict(route='fallback', response='I do not have a reliable answer to that stored here, and I would rather not make one up.')


def run():
    import os
    os.environ['CAEL_WEB_SEARCH'] = '1'
    stub_web([])
    web_check.NETWORK = Stub()
    # 1. Follow-up borrows the topic; answered from the subject's own article.
    r = web_check.improve(convo('How does a rainbow form?', 'Why is it curved?'), DONT_KNOW)
    assert r['route'] == 'chat/web-checked' and 'cone' in r['response'] and 'Rainbow' in r['response'], r
    # 2. A duration question gets a passage with a duration, corroborated by a second source; the film page is skipped.
    r = web_check.improve(convo('Who painted the Mona Lisa?', 'How long did it take?'), DONT_KNOW)
    assert r['route'] == 'chat/web-checked' and '1503' in r['response'] and 'Simple English' in r['response'] and 'film' not in r['response'], r
    # 3. No passage passes the check: say so, never guess.
    r = web_check.improve(convo('My houseplants keep dying. What am I doing wrong?', 'I water them every day.'), DONT_KNOW)
    assert r['route'] == 'chat/web-checked-none' and 'rather not guess' in r['response'], r
    # 4. A real answer, a feeling, a writing request or arithmetic are never replaced.
    good = dict(route='x', response='Thunder is the sound of air expanding when lightning heats it.')
    assert web_check.improve(convo('What causes thunder?'), good) is good
    for turn in ('Write a poem about rain.', 'What is 17 times 23?', 'I had a rough day at work.'):
        assert web_check.improve(convo(turn), DONT_KNOW) is DONT_KNOW, turn
    # 5. Open web: an answer found only outside Wikimedia, confirmed by a second, different publisher.
    calls = stub_web(['https://www.catvet.example/purr', 'https://pets.sample.org/cats/purring'])
    r = web_check.improve(convo('Why do cats purr?'), DONT_KNOW)
    assert r['route'] == 'chat/web-checked' and 'laryngeal' in r['response'] and 'catvet.example' in r['response'], r
    assert {s['source'] for s in r['sources']} == {'catvet.example', 'sample.org'}, r['sources']
    assert any('cats purr' in q.lower() for q in calls), calls
    assert len(r['response'].split('\n\n')[0].split()) <= 55, r['response']           # a short quote, not the page
    # 5b. The older single-pass web lookup giving up is also a don't-know: the wider check runs.
    old = dict(route='chat/web-evidence-insufficient', response='I found pages, but could not read a passage that answers the question reliably.')
    r = web_check.improve(convo('Why do cats purr?'), old)
    assert r['route'] == 'chat/web-checked' and r['replaced_route'] == 'chat/web-evidence-insufficient', r
    # 6. Two pages from one publisher do not confirm each other.
    stub_web(['https://www.catvet.example/purr', 'https://www.catvet.example/purr-2'])
    r = web_check.improve(convo('Why do cats purr?'), DONT_KNOW)
    assert r['route'] == 'chat/web-checked-none', r
    # 7. A site that copied Wikipedia's sentence is not independent support (falls back to the main-article rule).
    stub_web(['https://copy.sample.net/rainbow'])
    r = web_check.improve(convo('How does a rainbow form?', 'Why is it curved?'), DONT_KNOW)
    assert r['route'] == 'chat/web-checked' and 'which says the same' not in r['response'], r
    # 8. A private turn is searched by keywords only, never sent as typed ("my" ... ).
    calls = stub_web([])
    web_check.improve(convo('Why does my cat purr so loudly at night?'), DONT_KNOW)
    assert calls and all('my' not in q.lower().split() for q in calls), calls
    # 9. CAEL_WEB_SEARCH=0 (benchmarks): nothing is fetched (neither Wikimedia nor the open web) and the reply is untouched.
    os.environ['CAEL_WEB_SEARCH'] = '0'
    calls = stub_web(['https://www.catvet.example/purr', 'https://pets.sample.org/cats/purring'])
    web_check.NETWORK = Stub(down=True)          # any Wikimedia call would raise and be noticed below
    r = web_check.improve(convo('Why do cats purr?'), DONT_KNOW)
    assert not calls and r is DONT_KNOW, (calls, r)
    # 9b. an answer from the conversation's own state is never replaced by the web
    web_check.NETWORK = Stub()
    os.environ['CAEL_WEB_SEARCH'] = '1'
    mine = dict(route='chat/context-reasoning', response='652.')
    assert web_check.improve(convo('My locker is 652.', 'Which locker is mine?'), mine) is mine
    os.environ['CAEL_WEB_SEARCH'] = '1'
    # 10. Network down: an honest "could not reach" reply, no exception.
    stub_web([])
    web_check.NETWORK = Stub(down=True)
    r = web_check.improve(convo('Why is the sky blue?'), DONT_KNOW)
    assert r['route'] == 'chat/web-checked-none', r
    print('web_check: all checks passed')


import unittest


class WebCheckTest(unittest.TestCase):
    def test_all(self):
        run()


if __name__ == '__main__':
    unittest.main()
