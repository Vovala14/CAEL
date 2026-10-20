import unittest

from cael_unified.codegen import explain, recurrence, specs
from cael_unified.codegen.chat import costs, model, reply
from cael_unified.codegen.synth import synthesize


def function(code, name):
    scope = {}
    exec(code, scope)
    return scope[name]


def code_of(answer):
    return answer['response'].split('```python\n')[1].split('```')[0]


class DescriptionTests(unittest.TestCase):
    def test_everyday_requests_are_written_and_checked(self):
        answer = reply('write a function that removes duplicates from a list')
        self.assertEqual(answer['route'], 'chat/code-from-description')
        dedupe = function(code_of(answer), 'remove_duplicates')
        self.assertEqual(dedupe([4, 4, 1, 4, 2]), [4, 1, 2])

    def test_how_to_question_gets_code(self):
        answer = reply('how do I sort a dictionary by value in python?')
        sort = function(code_of(answer), 'sort_by_value')
        self.assertEqual(list(sort({'a': 5, 'b': 2, 'c': 9})), ['b', 'a', 'c'])

    def test_lucky_fits_are_rejected_by_held_out_checks(self):
        task = next(t for t in specs.TASKS if t['name'] == 'is_even')
        code, checked = specs.solve(task, synthesize, lambda d: costs(model(), d))
        is_even = function(code, 'is_even')
        self.assertTrue(all(is_even(n) == (n % 2 == 0) for n in range(-20, 21)))
        self.assertGreater(checked, len(task['cases']))

    def test_loops_for_sequences(self):
        found = recurrence.search([((n,), v) for n, v in [(0, 0), (1, 1), (2, 1), (5, 5), (10, 55)]])
        fib = function(recurrence.render('fib', 'n', *found), 'fib')
        self.assertEqual([fib(n) for n in range(8)], [0, 1, 1, 2, 3, 5, 8, 13])

    def test_divisor_loop_for_prime(self):
        task = next(t for t in specs.TASKS if t['name'] == 'is_prime')
        found = recurrence.search_all(task['cases'])
        is_prime = function(recurrence.render_all('is_prime', 'n', *found), 'is_prime')
        self.assertEqual([n for n in range(30) if is_prime(n)], [2, 3, 5, 7, 11, 13, 17, 19, 23, 29])

    def test_parameter_rename_leaves_strings_alone(self):
        self.assertEqual(specs.rename("len([x for x in s if x in 'aeiou s'])", ['s'], ['text']),
                         "len([x for x in text if x in 'aeiou s'])")


class ExplainTests(unittest.TestCase):
    def test_fix_missing_colon(self):
        answer = reply('fix this code: def add(a, b) return a + b')
        self.assertEqual(answer['route'], 'chat/code-fixed')
        self.assertEqual(function(code_of(answer), 'add')(2, 3), 5)

    def test_fix_several_errors(self):
        fixed, notes = explain.repair('for i in range(3)\n    print i')
        self.assertEqual(fixed, 'for i in range(3):\n    print(i)')
        self.assertEqual(len(notes), 2)
        fixed, _ = explain.repair('if x = 5:\n    y = (1 + 2')
        self.assertIn('x == 5', fixed)
        self.assertIn('(1 + 2)', fixed)

    def test_explain_shows_result_of_safe_expression(self):
        answer = reply('what does this code do? [x*2 for x in range(5)]')
        self.assertEqual(answer['route'], 'chat/code-explained')
        self.assertIn('[0, 2, 4, 6, 8]', answer['response'])

    def test_unsafe_code_is_never_run(self):
        self.assertIsNone(explain.evaluate("__import__('os').system('echo hi')"))
        self.assertIsNone(explain.evaluate("open('x').read()"))
        self.assertIsNone(explain.evaluate('9 ** 9 ** 9'))

    def test_recursion_is_named(self):
        text = explain.explain('def f(n):\n    if n < 2:\n        return n\n    return f(n - 1) + f(n - 2)')
        self.assertIn('recursion', text)

    def test_concepts_and_recipes(self):
        self.assertEqual(reply('explain list comprehensions in python')['route'], 'chat/code-concept')
        self.assertEqual(reply('what is a lambda?')['route'], 'chat/code-concept')
        answer = reply('write python code to read a csv file and print the rows')
        self.assertEqual(answer['route'], 'chat/code-recipe')
        self.assertIn('csv.reader', answer['response'])
        self.assertIsNone(reply('what is the capital of France?'))


if __name__ == '__main__':
    unittest.main()
