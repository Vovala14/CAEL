"""CAEL's own script library: scripts it wrote are checked, reused by the search, and written out with new code."""
import unittest

from cael_unified.codegen import script_library as sl
from cael_unified.codegen.synth import synthesize


def entry(name, params, expression, tests, origin=0, round_=0):
    return sl.script_from(name, params, expression, 'practice task', tests, origin, round_)


class Checks(unittest.TestCase):
    def test_rejects_code_outside_the_search_vocabulary(self):
        for bad in ('def f(s):\n    return open(s)\n', 'def f(s):\n    return s.__class__\n',
                    'import os\n\ndef f(s):\n    return s\n', 'def f(s):\n    return eval(s)\n'):
            with self.assertRaises(sl.Rejected):
                sl.check_source(bad)

    def test_script_must_pass_its_own_tests(self):
        lib = sl.Library()
        self.assertFalse(lib.add(entry('double_it', ['n'], 'n * 3', [((2,), 4)])))
        self.assertTrue(lib.add(entry('double_it', ['n'], 'n * 2', [((2,), 4), ((5,), 10)])))


class Reuse(unittest.TestCase):
    def setUp(self):
        self.lib = sl.Library()
        self.lib.add(entry('digit_sum', ['n'], 'sum(int(x) for x in str(n))', [((123,), 6), ((40,), 4)]))

    def test_search_builds_on_own_script(self):
        # digit sum of every element, then the largest: one step on top of the script.
        inputs, outputs = [([19, 5],), ([123, 40, 7],)], [10, 7]
        expr, params, _ = synthesize(inputs, outputs, 'largest digit sum', seconds=3.0, library=self.lib.ops())
        self.assertIn('digit_sum(', expr)
        code = self.lib.render('best', params, expr)
        self.assertIn('def digit_sum(n):', code)
        space = dict(__builtins__=sl.BUILTINS)
        exec(code, space)
        self.assertEqual(space['best']([99, 1]), 18)

    def test_scripts_can_call_scripts(self):
        self.assertTrue(self.lib.add(entry('digit_sum_twice', ['n'], 'digit_sum(digit_sum(n))', [((99,), 9), ((123,), 6)], round_=1)))
        self.assertEqual(self.lib.uses('digit_sum_twice(n)'), ['digit_sum', 'digit_sum_twice'])

    def test_own_name_is_renamed(self):
        code = self.lib.render('digit_sum', ['n'], 'digit_sum(n) + 1')
        self.assertIn('def digit_sum_helper(n):', code)
        space = dict(__builtins__=sl.BUILTINS)
        exec(code, space)
        self.assertEqual(space['digit_sum'](12), 4)

    def test_guard_stops_huge_loops(self):
        with self.assertRaises(ValueError):
            self.lib.scripts['digit_sum']['fn'](10 ** 9)


class PairLoops(unittest.TestCase):
    def test_two_lists_element_by_element(self):
        expr, _, _ = synthesize([([1, 2], [10, 20]), ([3, 4, 5], [1, 1, 1])], [[11, 22], [4, 5, 6]], 'add the lists', seconds=3.0)
        self.assertIn('zip(', expr)

    def test_neighbouring_pairs(self):
        expr, _, _ = synthesize([([2, 5, 9],), ([1, 4, 4, 10],)], [[3, 4], [3, 0, 6]], 'differences', seconds=3.0)
        self.assertIn('[1:]', expr)


class Chat(unittest.TestCase):
    def test_question_about_own_scripts(self):
        from cael_unified.codegen import chat
        self.assertTrue(chat.OWN_SCRIPTS.search('What scripts have you written for yourself?'))
        self.assertTrue(chat.OWN_SCRIPTS.search('Show me your script library'))
        self.assertFalse(chat.OWN_SCRIPTS.search('Write a script that renames my files'))


if __name__ == '__main__':
    unittest.main()
