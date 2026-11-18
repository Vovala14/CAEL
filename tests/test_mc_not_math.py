"""A lettered multiple-choice question goes to the choice path, not the arithmetic solver (authored case, not benchmark text)."""
from cael_unified import meesix


def test_lettered_options_skip_exact_solvers():
    text = ('Every bird is an animal.\nEvery robin is a bird.\nPip is a robin.\n'
            "Is 'Pip is an animal' true, false, or unknown?\nA) unknown\nB) true\nC) false\nD) inconsistent")
    assert meesix.specialists([dict(role='user', content=text)]) is None


def test_plain_word_problem_still_solved():
    got = meesix.specialists([dict(role='user', content='I have 8 apples and buy 5 more. How many apples do I have?')])
    assert got is None or '13' in got['response']
