"""Offline checks for chat_memory.py: recall from the user's own words, a consistent persona, replies to statements.

run: python test_chat_memory.py   (from dev_runtime; no network: Wikipedia descriptions are stubbed or absent)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cael_unified import chat_memory as M
from cael_unified.network import LookupUnavailable


class Offline:
    def json(self, url, **kw):
        raise LookupUnavailable('offline')


def convo(*turns, replies=None):
    m = []
    for i, t in enumerate(turns):
        m.append(dict(role='user', content=t))
        m.append(dict(role='assistant', content=(replies or {}).get(i, '...')))
    return m[:-1]


def said(r):
    return r['response'] if r else None


def run():
    import cael_unified.network as net
    net.NETWORK = Offline()
    M._PAGES.clear()
    life = ["Hi! I'm Maya.", 'I just moved to Lisbon for a new job.', "I'm a nurse at a children's hospital.",
            'I have a cat called Pixel, so I need a pet-friendly place.', 'Actually my sister Ana is visiting next month.']
    # 1. direct answers about the profile, before any other route
    assert 'Pixel' in said(M.before(convo(*life, 'Do you remember my cat\'s name?')))
    assert 'nurse' in said(M.before(convo(*life, 'What do I do for work?')))
    assert 'Ana' in said(M.before(convo(*life, "What did I say my sister's name was?")))
    assert said(M.before(convo(*life, "What's my name?"))) == "You're Maya."
    s = said(M.before(convo(*life, 'Can you summarise what you know about me?')))
    assert all(w in s for w in ('Maya', 'Lisbon', 'nurse', 'Pixel', 'Ana')), s
    # 2. a later statement updates the profile
    assert 'Porto' in said(M.before(convo(*life, 'I moved to Porto last week.', 'Where do I live now?')))
    # 3. unknown slots: an honest answer, never a guess
    assert M.before(convo(*life, "What's my dog's name?")) is None          # the main routes give their own abstention
    late = M.after(convo(*life, "What's my dog's name?"), dict(route='chat/core-open', response='Some forum answer.'))
    assert "don't think you've told me your dog's name" in late['response'], late
    # 4. general recall happens after CAEL's own memory routes, from the best-matching sentence
    garden = ['I live in a flat with a small balcony that gets afternoon sun.', 'My tomato leaves are turning yellow. Why?',
              "I think I've been overwatering them.", 'What problem did I have with my tomatoes?']
    m = convo(*garden)
    assert M.before(m) is None
    r = M.after(m, dict(route='chat/core-open', response='Some forum answer.'))
    assert 'yellow' in r['response'] and 'overwatering' in r['response'], r
    kept = dict(route='chat/core-recall', response='You said your tomato leaves are turning yellow.')
    assert M.after(m, kept) is kept                                  # a memory route that answered is kept
    # 5. "What role is it for?": the answer is only in the user's own words
    r = M.before(convo("I'm stressed about a job interview on Friday.", "It's for a data analyst role at a bank.", 'What role is it for?'))
    assert 'data analyst role at a bank' in said(r), r
    # 6. persona: fixed and repeated, never contradicted
    first = M.before(convo("What's your favourite sci-fi book?"))
    assert 'Hyperion' in said(first)
    again = M.before(convo("What's your favourite sci-fi book?", 'Cool.', 'What was your favourite sci-fi book again?',
                           replies={0: said(first)}))
    assert 'Still "Hyperion"' in said(again), said(again)
    assert said(M.before(convo('Do you like science fiction?'))).startswith('I do!')
    # 7. statements get a reply built from what was said
    r = M.after(convo(*life[:3]), dict(route='chat/talk-converse', response='Interesting! How did that come about?'))
    assert 'nurse' in r['response'] and r['route'] == 'chat/memory-talk-job', r
    r = M.after(convo(*life[:4]), dict(route='chat/core-fallback', response='I see. Tell me a bit more about what you would like.'))
    assert 'Pixel' in r['response'], r
    r = M.after(convo(garden[0]), dict(route='chat/core-fallback', response='I see. Tell me a bit more about that.'))
    assert 'you live in a flat with a small balcony' in r['response'] and r['route'] == 'chat/memory-talk-noted', r
    good = dict(route='chat/emotional', response='That sounds really hard. Do you want to talk about it?')
    assert M.after(convo('My dog died yesterday.'), good) is good     # a real reply is never replaced
    # 8. a title in chat gets a fact when Wikipedia is reachable
    class Wiki:
        def json(self, url, **kw):
            if 'list=search' in url:
                return dict(query=dict(search=[dict(title='Oppenheimer (film)')]))
            return dict(query=dict(pages={'1': dict(title='Oppenheimer (film)', description='2023 film by Christopher Nolan',
                                                     extract='Oppenheimer is a 2023 epic biographical film.')}))
    net.NETWORK = Wiki(); M._PAGES.clear()
    r = M.after(convo('Not much, just finished watching Oppenheimer.'), dict(route='chat/smalltalk-quiet+topic', response='A quiet moment, then.'))
    assert 'Christopher Nolan' in r['response'] and 'What did you think' in r['response'], r
    net.NETWORK = Offline(); M._PAGES.clear()
    # 9. encouragement from what the user said
    r = M.before(convo('I studied economics and worked two years in retail.', "I'm worried they'll ask about Python.", "Do you think I'm ready?"))
    assert 'economics' in said(r) and r['route'] == 'chat/memory-reassure', r
    print('chat_memory: all checks passed')


import unittest


class ChatMemoryTest(unittest.TestCase):
    def test_all(self):
        run()


if __name__ == '__main__':
    unittest.main()
