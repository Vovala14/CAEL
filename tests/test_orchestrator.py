import unittest

from cael_unified import orchestrator, reasoning_compose as compose
from cael_unified.reasoning import Reasoner


class PlanTests(unittest.TestCase):
    def test_splits_only_real_multi_part_requests(self):
        self.assertEqual(orchestrator.plan('What is 12 * 7? Then multiply it by 3, and then subtract 10 from the result'),
                         ['What is 12 * 7', 'multiply it by 3', 'subtract 10 from the result'])
        self.assertEqual(orchestrator.plan('I have 3 apples and buy 5 more, how many do I have? Then double it'),
                         ['I have 3 apples and buy 5 more, how many do I have', 'double it'])
        self.assertIsNone(orchestrator.plan('Mary went to the kitchen, then John went to the garden. Where is Mary?'))
        self.assertIsNone(orchestrator.plan('hi, how are you?'))
        self.assertIsNone(orchestrator.plan('What is it like to live in Japan?'))

    def test_spoken_arithmetic(self):
        self.assertEqual(orchestrator.spoken_arithmetic('multiply 84 by 3'), '(84) * (3)')
        self.assertEqual(orchestrator.spoken_arithmetic('subtract 10 from 252'), '(252) - (10)')
        self.assertEqual(orchestrator.spoken_arithmetic('double 8'), '(8) * 2')
        self.assertIsNone(orchestrator.spoken_arithmetic('multiply the apples by love'))

    def test_board_passes_results_between_engines(self):
        answers = {'What is 12 * 7': dict(route='helper/arithmetic', response='12 * 7 = 84'),
                   '(84) * (3)': dict(route='helper/arithmetic', response='(84) * (3) = 252')}
        board = orchestrator.run(['What is 12 * 7', 'multiply it by 3'], lambda text, history: answers[text])
        self.assertEqual([e.value for e in board.entries], ['84', '252'])
        self.assertIn('"it" = 84', board.entries[1].notes[0])

    def test_runs_code_written_by_an_earlier_step(self):
        code = '```python\ndef square(n):\n    return n * n\n```'
        board = orchestrator.run(['write a function that squares a number', 'run it on 12'],
                                 lambda text, history: dict(route='chat/code-from-description', response=code))
        self.assertEqual(board.entries[1].value, 144)
        self.assertIn('square(12)', board.entries[1].response)

    def test_values_from_replies(self):
        self.assertEqual(orchestrator.classify('chat/web-wikidata-faq', 'The capital of Japan is Tokyo.'), ('short', 'Tokyo'))
        self.assertEqual(orchestrator.classify('chat/everyday-figure', 'The Moon is about **384,400 km** from Earth.')[1], '384400')


class ComposeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reasoner = Reasoner()

    def ask(self, text):
        return self.reasoner._respond(text)

    def test_sub_question_feeds_the_main_question(self):
        answer = self.ask('Daniel picked up the football. Daniel went to the garden. Sandra went to the kitchen. '
                          'Where is the person who has the football?')
        self.assertTrue(answer['response'].startswith('Daniel is in the garden.'))
        self.assertIn('Who has the football? → Daniel', answer['response'])

    def test_who_is_in_a_room(self):
        answer = self.ask('Mary went to the kitchen. John went to the garden. Sandra went to the kitchen. Who is in the kitchen?')
        self.assertTrue(answer['response'].startswith('Mary and Sandra'))

    def test_several_questions_and_then_clauses(self):
        answer = self.ask('Mary went to the kitchen, then John went to the garden. Where is Mary? Where is John?')
        self.assertEqual(answer['route'], 'chat/reasoning-several')
        self.assertIn('Mary is in the kitchen', answer['response'])
        self.assertIn('John is in the garden', answer['response'])

    def test_hypothetical_does_not_change_the_facts(self):
        context = 'Mary went to the kitchen. John went to the garden.'
        answer = self.ask(context + ' If John goes to the kitchen, where would John be?')
        self.assertIn('Supposing John went to the kitchen: John is in the kitchen', answer['response'])
        self.assertEqual(compose.hypothetical(context + ' If John goes to the kitchen, where would John be?')[0], context)

    def test_normalise(self):
        self.assertEqual(compose.normalise('Mary went home, then John left.'), 'Mary went home. John left.')


if __name__ == '__main__':
    unittest.main()
