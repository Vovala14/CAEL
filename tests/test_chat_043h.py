"""0.4.3 round h: the losses found in the LFM2-700M comparison, fixed on development wordings (not the sealed ones)."""
from cael_unified import calc_agent, chat_core, python_answers, tips


def talk(fn, turns):
    msgs, out = [], []
    for t in turns:
        msgs.append(dict(role='user', content=t))
        r = fn(msgs)
        out.append(r)
        msgs.append(dict(role='assistant', content=(r or {}).get('response', '')))
    return out


def test_paying_a_share_up_front_then_the_rest():
    a, b, c = talk(calc_agent.respond, ['A bike costs $800 and we pay 25% up front. How much is that?', 'How much is left?', 'Over 5 months, how much a month?'])
    assert '**$200**' in a['response'] and '$600' in b['response'] and '$120' in c['response']
    rise = calc_agent.respond([dict(role='user', content='The rent is $1,000 and it is going up 4%. What is the new rent?')])
    assert '$1,040' in rise['response']


def test_python_comparisons():
    for q, word in [('Difference between a dict and a list?', 'dictionary'), ('list vs tuple in python', 'tuple'), ('When should I use a set or a list in Python?', 'set')]:
        r = python_answers.respond([dict(role='user', content=q)])
        assert r and word in r['response'].lower() and '`is`' not in r['response'], q


def test_science_follow_ups_take_the_subject_from_before():
    a, b = talk(chat_core.explain_reply, ['Why does it rain?', 'And hail?'])
    assert 'evaporat' in a['response'] and 'updraught' in b['response']
    a, b = talk(chat_core.explain_reply, ['What makes the sky blue?', 'Then why is it black in space?'])
    assert 'scatter' in a['response'] and 'space' in b['response']


def test_ranked_tips_and_their_follow_ups():
    a, b, c, d = talk(tips.respond, ['Any tips to spend less on food shopping?', 'Which one saves the most?', 'Tell me about the third one', 'Any others?'])
    assert a['response'].startswith(tips.LEAD)
    assert 'list' in b['response'] and 'own brands' in c['response'] and 'more' in d['response'].lower()
    assert tips.respond([dict(role='user', content='Which one saves the most?')]) is None


def test_wordings_from_the_fix_check():
    a, b, c = talk(calc_agent.respond, ['The tent is $500 and they want 20% now. How much is that?', 'What remains?', 'Over 2 months, how much a month?'])
    assert '$100' in a['response'] and '$400' in b['response'] and '$200' in c['response']
    r = python_answers.respond([dict(role='user', content='Python: use a dictionary rather than a list?')])
    assert 'dictionary' in r['response']
    r = python_answers.respond([dict(role='user', content='Python: how to read the final entry of a list')])
    assert '-1' in r['response']
    a, b = talk(chat_core.explain_reply, ['Why do we get winter and summer?', 'Why does it feel colder far from the equator?'])
    assert 'tilt' in a['response']
    a, b = talk(chat_core.explain_reply, ['What causes earthquakes?', 'Is there any warning?'])
    assert 'predict' in b['response']
