"""0.4.3 round b: the Programmer, ideas, concepts, beginner guides, new Supporter situations and money follow-ups.
Development conversations only; none is from a sealed test set."""
import contextlib
import io
import os
import re
import tempfile

from cael_unified import beginner, calc_agent, concepts, ideas, python_answers, support


def talk(module, turns):
    msgs, out = [], []
    for t in turns:
        msgs.append(dict(role='user', content=t))
        r = module.respond(msgs)
        out.append(r)
        msgs.append(dict(role='assistant', content=(r or {}).get('response', '')))
    return out


def test_every_programmer_code_block_runs():
    here = os.getcwd()
    os.chdir(tempfile.mkdtemp())
    try:
        open('data.csv', 'w').write('name,age\nAda,36\n')
        open('notes.txt', 'w').write('x\n')
        open('data.json', 'w').write('{"a": 1}')
        texts = [t['answer'] for t in python_answers.T.values()] + [a for t in python_answers.T.values() for _, a in t['follow']]
        blocks = [b for s in texts for b in re.findall(r'```python\n(.*?)```', s, re.S)]
        blocks += [e[3] for e in python_answers.E if e[3]] + [r[1] for r in python_answers.RECURSIVE.values()]
        for b in blocks:
            if 'input(' in b or 'requests.get' in b or 'argparse' in b:
                continue
            with contextlib.redirect_stdout(io.StringIO()):
                exec(compile(b, '<answer>', 'exec'), {'__name__': 'x', 'text': '5'})
        assert len(blocks) > 50
    finally:
        os.chdir(here)


def test_topic_follow_up_and_error():
    r = talk(python_answers, ['How do I read a CSV file in Python?', 'And how do I skip the header row?'])
    assert 'csv.reader' in r[0]['response'] and 'next(' in r[1]['response']
    e = python_answers.respond([dict(role='user', content="ModuleNotFoundError: No module named 'numpy'")])
    assert 'pip install numpy' in e['response']


def test_make_it_recursive():
    msgs = [dict(role='user', content='Write a function to compute the factorial of n.'),
            dict(role='assistant', content='```python\ndef factorial(n):\n    result = 1\n    for i in range(2, n + 1):\n        result *= i\n    return result\n```'),
            dict(role='user', content='Now make it recursive.')]
    assert 'factorial(n - 1)' in python_answers.respond(msgs)['response']


def test_write_requests_stay_with_the_code_writer():
    assert python_answers.respond([dict(role='user', content='Write a Python story generator')]) is None


def test_ideas_and_detail():
    r = talk(ideas, ["Give me three ideas for a 10-year-old's birthday party.", 'The second one sounds good. What would we need?'])
    assert r[0]['response'].count('**') == 6 and 'you\'d need' in r[1]['response']


def test_concept_follow_ups():
    r = talk(concepts, ['Can you explain what inflation is in simple terms?', 'Why does it happen?', 'Can you give me an example?'])
    assert 'prices' in r[0]['response'] and 'demand' in r[1]['response'] and 'loaf' in r[2]['response']


def test_beginner_gear():
    r = talk(beginner, ["I'm interested in photography, any tips?", 'What do I need?'])
    assert 'rule of thirds' in r[0]['response'] and 'phone' in r[1]['response'].lower()


def test_supporter_new_situations():
    r = talk(support, ["I'm driving on the motorway for the first time tomorrow and I'm petrified.", 'What if I panic?', 'Any tips for the morning?'])
    assert 'left lane' in r[1]['response'] and 'slip road' in r[2]['response']
    r = talk(support, ['I had a biopsy last week and I am worried while I wait to hear back.', 'I keep imagining the worst.', 'How do I get through the next few days?'])
    assert 'retake' not in ' '.join(x['response'] for x in r if x) and 'clinic' in r[2]['response']
    r = talk(support, ['My daughter starts high school next week and she is anxious.', 'How can I help her?'])
    assert 'disappointment' not in ' '.join(x['response'] for x in r) and 'school' in r[1]['response']


def test_pay_over_months_is_not_yearly():
    msgs = [dict(role='user', content='The repair is $600.'), dict(role='assistant', content='**$600**.'),
            dict(role='user', content='If I pay that over 4 months, how much is each payment?')]
    assert '**$150 per month**' in calc_agent.respond(msgs)['response']


def test_round_c_python_topics_and_follow_ups():
    r = talk(python_answers, ['How do I check if a key exists in a dictionary in Python?', "And how do I get a default value if it doesn't?"])
    assert "'Ada' in ages" in r[0]['response'] and '.get' in r[1]['response']
    r = talk(python_answers, ['How can I make a list of numbers from 1 to 100 in Python?', 'Now only the even ones.'])
    assert 'range(1, 101)' in r[0]['response'] and 'range(2, 101, 2)' in r[1]['response']


def test_round_c_habits_and_flying():
    r = talk(beginner, ["What's a good way to stop procrastinating?", "What if I still can't get started?"])
    assert 'timer' in r[0]['response'].lower() and 'smaller' in r[1]['response']
    r = talk(support, ["I'm flying for the first time next week and I'm terrified.", "What if there's turbulence?"])
    assert 'normal and safe' in r[1]['response']


def test_round_c_money_follow_ups():
    r = talk(calc_agent, ['I take home $2,600 a month and spend $2,180. How much do I save each month?', "How long until I've saved $3,000?"])
    assert '**$420 a month**' in r[0]['response'] and '**8 months**' in r[1]['response']
    msgs = [dict(role='user', content='My phone contract is $38 a month.'), dict(role='assistant', content='ok'),
            dict(role='user', content='How much is that a year?')]
    assert '**$456 a year**' in calc_agent.respond(msgs)['response']


def test_round_d_operations_reference_and_order():
    r = talk(python_answers, ['How do I take something out of a list in Python?', 'What if I only know its index?'])
    assert '.remove(' in r[0]['response'] and 'pop(' in r[1]['response']
    r = talk(python_answers, ['In Python how do I write my list to a file with one value per line?'])
    assert 'join(items)' in r[0]['response']
    r = talk(python_answers, ['How do I read a CSV file in Python?', 'And how do I skip the header row?'])
    assert 'csv.reader' in r[0]['response'] and 'next(' in r[1]['response']


def test_round_d_gift_beats_party_and_hypothetical_fail():
    assert 'experience' in ideas.respond([dict(role='user', content="Any gift ideas for my mum's birthday?")])['response'].lower()
    r = talk(support, ['My exam results come out tomorrow and I am so worried.', 'What if I failed?'])
    assert 'options' in r[1]['response']


def test_round_e_word_overlap_and_context_follow_ups():
    r = talk(python_answers, ['In Python, how can I drop the repeated values from a list without changing the order?'])
    assert 'dict.fromkeys' in r[0]['response']
    r = talk(python_answers, ['How do I read a text file into a list of lines in Python?', 'And how do I write them back?'])
    assert 'splitlines' in r[0]['response'] and 'join(items)' in r[1]['response']
    assert python_answers.respond([dict(role='user', content='How do I build a neural network in Python?')]) is None


def test_round_e_empty_guard_and_two_part_concept():
    msgs = [dict(role='user', content='x'), dict(role='assistant', content='```python\ndef find_largest(numbers):\n    return max(numbers)\n```'),
            dict(role='user', content='Now make it handle an empty list.')]
    assert 'if not numbers:' in python_answers.respond(msgs)['response']
    r = concepts.respond([dict(role='user', content='What is a credit score and why does it matter?')])
    assert 'number lenders use' in r['response'] and 'saves money' in r['response']


def test_round_f_supporter_recognises_shown_feelings_and_situations():
    r = talk(support, ['Our cat had to be put down this morning.'])
    assert 'sorry' in r[0]['response'].lower()
    r = talk(support, ["I'm waiting to hear back about a job and I keep refreshing my email.", 'What if they say no?'])
    assert 'feedback' in r[1]['response']
    r = talk(support, ["My knee operation is on Monday and I've got a knot in my stomach about it.", 'What if something goes wrong?'])
    assert 'surgeon' in r[1]['response']
    r = talk(support, ['I keep leaving my tax return to the last minute.', "What if I still don't do it?"])
    assert 'smaller' in r[1]['response']
    r = talk(support, ['My daughter cries every time I drop her at nursery.', 'How can I help her?'])
    assert 'goodbye' in r[1]['response'].lower() and 'form tutor' not in r[1]['response']
