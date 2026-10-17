import tempfile
import unittest

from cael_unified.codegen.chat import examples, reply
from cael_unified.codegen.synth import render, synthesize
from cael_unified.codegen.train import costs, fit, tags_in_code


def run(source, name, *args):
    import math
    namespace = {'math': math}
    exec(source, namespace)
    return namespace[name](*args)


class SynthesisTests(unittest.TestCase):
    def test_writes_working_functions_that_generalise(self):
        cases = [
            ('count_vowels', 'count vowels in a string', [('hello',), ('sky',), ('aeiou',)], [2, 0, 5], ('banana',), 3),
            ('sort_rows', 'sort a matrix by the sum of its rows', [([[3, 3], [1, 1]],), ([[0], [5], [2]],)],
             [[[1, 1], [3, 3]], [[0], [2], [5]]], ([[9], [1, 2]],), [[1, 2], [9]]),
            ('squares', 'square every number in a list', [([1, 2, 3],), ([4],)], [[1, 4, 9], [16]], ([5, 6],), [25, 36]),
            ('reverse_words', 'reverse the words in a sentence', [('hello world',), ('a b c',)], ['world hello', 'c b a'],
             ('one two',), 'two one'),
        ]
        for name, description, inputs, outputs, new_input, expected in cases:
            expr, params, _ = synthesize(inputs, outputs, description, seconds=5)
            self.assertIsNotNone(expr, name)
            source = render(name, params, expr)
            self.assertEqual(run(source, name, *new_input), expected, source)

    def test_yes_no_answers_must_be_booleans(self):
        expr, _, _ = synthesize([({},), ({1: 2},)], [True, False], 'check if a dictionary is empty', seconds=3)
        self.assertIsNotNone(expr)
        self.assertNotIn(expr, ('0', '1'))

    def test_training_reads_operations_from_syntax_only(self):
        self.assertLessEqual({'sorted', 'sortkey', 'reverse'}, tags_in_code('def f(s):\n    return sorted(s, key=len)[::-1]'))
        model = fit([('convert a string to upper case', 'def f(s):\n    return s.upper()')] * 3 +
                    [('add two numbers', 'def f(a, b):\n    return a + b')] * 3)
        table = costs(model, 'make this string upper case')
        self.assertLess(table['upper'], table['add'])

    def test_search_reports_the_operations_it_used(self):
        expr, _, stats = synthesize([('hello',), ('sky',), ('aeiou',)], [2, 0, 5], 'count vowels', seconds=5)
        self.assertIn('aeiou', expr)
        self.assertIn("const:'aeiou'", stats['tokens'])
        self.assertIn('iter:each', stats['tokens'])

    def test_uniform_search_has_no_hand_rules_but_still_works(self):
        from cael_unified.codegen.synth import uniform_costs
        expr, params, _ = synthesize([([1, 2, 3],), ([4],)], [[1, 4, 9], [16]], 'square every number', uniform_costs(),
                                     seconds=5, hand=False)
        self.assertEqual(run(render('f', params, expr), 'f', [5, 6]), [25, 36])

    def test_collect_keeps_searching_past_the_first_fit(self):
        _, _, stats = synthesize([(2,), (3,)], [4, 6], 'double a number', seconds=5, collect=1)
        sources = [c[2] for c in stats['candidates']]
        self.assertGreater(len(sources), 1)

    def test_self_training_learns_from_cael_solutions(self):
        from cael_unified.codegen.train import fit_self, lift_costs
        solutions = [(i, 'convert the text to upper case', ['upper']) for i in range(4)]
        solutions += [(10 + i, 'add the two numbers', ['add']) for i in range(4)]
        model = fit_self(solutions, alpha=1.0)
        table = lift_costs(model, 'make the text upper case')
        self.assertLess(table['upper'], table['add'])


class ChatTests(unittest.TestCase):
    def test_examples_on_separate_lines_or_one_line(self):
        self.assertEqual(examples('f(1, 2) == 3\nf(2, 2) == 4'), ('f', [((1, 2), 3), ((2, 2), 4)]))
        self.assertEqual(examples('Count: c("ab") == 2, c("") == 0, c("x") -> 1'), ('c', [(('ab',), 2), (('',), 0), (('x',), 1)]))
        self.assertEqual(examples('pair(1) == (1,), pair(2) == (2,)')[1], [((1,), (1,)), ((2,), (2,))])

    def test_requests_without_examples_ask_for_them(self):
        answer = reply('Write a python function to sort a list')
        self.assertEqual(answer['route'], 'chat/code-needs-examples')
        self.assertIn('==', answer['response'])
        self.assertIsNone(reply('How are you?'))

    def test_synthesized_reply_contains_checked_code(self):
        answer = reply('Write a function that doubles a number. double(2) == 4, double(5) == 10, double(0) == 0')
        self.assertEqual(answer['route'], 'chat/code-synthesized')
        code = answer['response'].split('```python\n')[1].split('```')[0]
        self.assertEqual(run(code, 'double', 21), 42)

    def test_assistant_routes_code_requests_to_the_synthesizer(self):
        from cael_unified.assistant import Assistant
        with tempfile.TemporaryDirectory() as folder:
            engine = Assistant(output_root=folder)
            result = engine.respond([dict(role='user', content='Write a function: inc(1) == 2, inc(5) == 6')], seed=1)
            self.assertEqual(result['route'], 'chat/code-synthesized')


if __name__ == '__main__':
    unittest.main()
