import os
import tempfile
import unittest

from cael_unified import ltm, orchestrator, rules, verify


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.old = os.environ.get('CAEL_LTM')
        os.environ['CAEL_LTM'] = os.path.join(self.folder, 'ltm.json')

    def tearDown(self):
        os.environ['CAEL_LTM'] = self.old

    def test_rules_and_counts_persist_without_text(self):
        memory = ltm.memory()
        memory.add_rule('area', ['n', 'm'], 'def area(n, m):\n    return n * m\n', 'area of a rectangle for John Smith',
                        6, [((2, 3), 6), (('John', 3), 'x')])
        memory.record('helper/arithmetic', 'verified')
        again = ltm.Memory(memory.path)
        rule = again.rule('area')
        self.assertEqual(rule['examples'], [[[2, 3], 6]])          # non-numeric examples are never stored
        self.assertNotIn('john', ' '.join(rule['words']))           # nor names
        self.assertGreaterEqual(again.data['engines']['helper/arithmetic']['verified'], 1)  # other tests' workers may also count
        self.assertIs(again.find_rule('run area on 3, 4'), rule)

    def test_feedback_forgets_bad_rules(self):
        memory = ltm.memory()
        memory.add_rule('half', ['n'], 'def half(n):\n    return n / 3\n', 'half', 3)
        for _ in range(3):
            memory.rule_feedback('half', False)
        self.assertIsNone(memory.rule('half'))

    def test_learn_validates_on_hidden_examples(self):
        learned = rules.learn('area', [((2, 3), 6), ((4, 5), 20), ((1, 7), 7), ((3, 3), 9)], 'area of a rectangle')
        self.assertTrue(learned['validated'])
        self.assertTrue(learned['stored'])
        self.assertEqual(rules.run_rule(ltm.memory().rule('area'), (6, 7)), 42)
        answer = rules.reply('run area on 6, 7')
        self.assertIn('**42**', answer['response'])
        self.assertIn('learned rule `area`', answer['response'])


class SequenceTests(unittest.TestCase):
    def test_sequences(self):
        self.assertEqual(rules.next_term([2, 6, 12, 20, 30])[0], 42)
        self.assertEqual(rules.next_term([1, 1, 2, 3, 5, 8])[0], 13)
        self.assertEqual(rules.next_term([2, 4, 8, 16, 32])[0], 64)
        self.assertIsNone(rules.next_term([3, 1, 4, 1, 5]))
        self.assertIn('**25**', rules.reply('5, 10, 15, 20?')['response'])


class VerifyTests(unittest.TestCase):
    def test_wrong_arithmetic_is_corrected(self):
        fixed = verify.apply('what is 2+2', dict(route='helper/arithmetic', response='2+2 = 5'), record=False)
        self.assertEqual(fixed['verification']['status'], 'corrected')
        self.assertTrue(fixed['response'].startswith('2+2 = 4'))
        right = verify.apply('what is 7/2', dict(route='helper/arithmetic', response='7/2 = 7/2'), record=False)
        self.assertEqual(right['verification']['status'], 'verified')

    def test_equation_substitution(self):
        good = verify.check('solve 2*x + 3 = 11', dict(route='helper/equation', response='x = 4'))
        bad = verify.check('solve 2*x + 3 = 11', dict(route='helper/equation', response='x = 5'))
        self.assertEqual((good['status'], bad['status']), ('verified', 'failed'))

    def test_code_is_run_on_the_examples(self):
        request = 'double(2) == 4, double(5) == 10'
        good = verify.check(request, dict(route='chat/code-synthesized', response='```python\ndef double(n):\n    return n * 2\n```'))
        bad = verify.check(request, dict(route='chat/code-synthesized', response='```python\ndef double(n):\n    return n + 2\n```'))
        self.assertEqual(good['status'], 'verified')
        self.assertEqual(bad['status'], 'failed')
        flagged = verify.apply(request, dict(route='chat/code-synthesized', response='```python\ndef double(n):\n    return n + 2\n```'), record=False)
        self.assertIn('My own check found a problem', flagged['response'])

    def test_unchecked_answers_are_left_alone(self):
        answer = dict(route='chat/web-wikidata-faq', response='The capital of Japan is Tokyo.')
        self.assertEqual(verify.apply('capital of japan', answer, record=False)['response'], answer['response'])

    def test_plan_uses_rule_results(self):
        self.assertEqual(orchestrator.classify('chat/rules-use', '`area(6, 7)` = **42**, using my learned rule'), ('number', '42'))


if __name__ == '__main__':
    unittest.main()
