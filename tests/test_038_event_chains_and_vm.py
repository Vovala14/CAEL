"""Authored (not benchmark-derived) regressions for CAEL 0.3.8: event-chain counting and VM-only codegen."""
import ast, inspect, re
import pytest
from cael_unified.assistant import Assistant
from cael_unified import quantity_graph
from cael_unified.codegen import recurrence, specs


def ask(text, tmp_path):
    a = Assistant(output_root=tmp_path)
    return a.respond([dict(role='user', content=text)], n=1, seed=137, mode='chat')


def first_number(reply):
    m = re.search(r'-?\d+', reply.split('\n\n')[0])
    return int(m.group()) if m else None


@pytest.mark.parametrize('text,expected', [
    ('I have 8 pencils, receive 15, then give away 6. How many pencils do I have?', 17),
    ('I have 12 shells, find 5 more and lose 3. How many shells do I have now?', 14),
    ('Mia has 7 badges, earns 10, then loses 4. How many badges does Mia have?', 13),
    ('Omar has 20 cards, buys 4 more, and gives 9 to Lena. How many cards does Omar have?', 15),
    ('I have 30 beads, use 12, then collect 5 more. How many beads do I have?', 23),
    ('Theo has 9 stamps and gets 6 more. How many stamps does Theo have?', 15),
    ('I have 4 tickets and 3 tickets. How many tickets do I have?', 7),
])
def test_event_chains_answer(text, expected, tmp_path):
    out = ask(text, tmp_path)
    assert first_number(out['response']) == expected, out


@pytest.mark.parametrize('text', [
    'I have 3 widgets and 2 gadgets. How many gizmos do I have?',
    'I have 8 tokens, receive some, then give away 6. How many tokens do I have?',
    'Sam has 20 stickers, gives 9 to Ana. How many stickers does Ana have?',
])
def test_event_chains_refuse_or_do_not_invent(text, tmp_path):
    out = ask(text, tmp_path)
    n = first_number(out['response'])
    # Ana's own starting count is unknown, so 9 must not be asserted as her total; the others are unanswerable.
    assert n is None or 'clarify' in out.get('route', '') or 'not' in out['response'].lower(), out


def test_expand_canonical_clauses():
    got = quantity_graph.expand('Sam has 20 stickers, buys 4 more, and gives 9 to Ana')
    assert got == ['Sam has 20 stickers', 'Sam buys 4 stickers', 'Sam gives 9 stickers to Ana']
    assert quantity_graph.expand('Sam has 20 stickers, maybe trades some') == ['Sam has 20 stickers, maybe trades some']


def test_recurrence_has_no_native_eval():
    tree = ast.parse(inspect.getsource(recurrence))
    calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not calls & {'eval', 'exec', 'compile'}


def test_recurrence_semantics_kept():
    assert [recurrence.run((0, 1), 'a + b', n) for n in range(8)] == [0, 1, 1, 2, 3, 5, 8, 13]
    prime = ('n > 1', '2', 'int(n ** 0.5) + 1', 'n % d != 0', 'all')
    assert [n for n in range(20) if recurrence.check_all(*prime, n)] == [2, 3, 5, 7, 11, 13, 17, 19]
    with pytest.raises(ValueError):
        recurrence.run((0, 1), '__import__("os").getpid()', 3)
    with pytest.raises(ValueError):
        recurrence.check_all('__import__("os")', '1', 'n', 'n != d', 'all', 3)


def test_specs_run_uses_vm_only():
    assert 'eval(' not in inspect.getsource(specs.run)
    assert specs.run('x * 2 + y', ['x', 'y'], [3, 1]) == 7
    assert specs.run('sorted(s)', ['s'], [[3, 1, 2]]) == [1, 2, 3]
    with pytest.raises(Exception):
        specs.run('__import__("os").getpid()', ['x'], [1])
    with pytest.raises(Exception):
        specs.run('open("x").read()', ['x'], [1])
    assert specs.passes('x + 1', ['x'], [((1,), 2), ((5,), 6)]) == []


def test_vm_dict_fromkeys_is_bounded():
    from cael_unified.codegen.python_vm import run_cases
    ok = run_cases('def f(x):\n    return list(dict.fromkeys(x))\n', [dict(name='f', args=[[3, 1, 3, 2]])])
    assert ok['cases'][0] == dict(status='value', value=[3, 1, 2], events=ok['cases'][0]['events'])
    big = run_cases('def f(n):\n    return len(dict.fromkeys(range(n)))\n', [dict(name='f', args=[10 ** 9])])
    assert big['cases'][0]['status'] in ('limit', 'error')
    other = run_cases('def f(x):\n    return dict.items\n', [dict(name='f', args=[1])])
    assert other['cases'][0]['status'] == 'unsupported'
