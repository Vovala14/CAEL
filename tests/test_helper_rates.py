"""Authored exact-rate whole unified replies, ambiguity and history controls."""
import unittest
from unittest.mock import patch

from cael_unified.assistant import Assistant
from cael_unified.helper_rates import solve


def user(text): return dict(role='user', content=text)
def bot(text): return dict(role='assistant', content=text)


class RateHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = Assistant()

    def ask(self, text, history=None):
        with patch.object(self.engine._facts, 'respond', side_effect=AssertionError('Rate helper must not fetch')):
            return self.engine.respond((history or []) + [user(text)], n=1, seed=412)

    def test_distance_amount_converts_time_and_distance_exactly(self):
        answer = self.ask('Nori travels at a constant speed of 12 kilometers per hour for 30 minutes. How many meters does Nori travel?')
        self.assertEqual(answer['route'], 'helper/rates')
        self.assertEqual(answer['helper_reasoning']['value'], '6000')
        self.assertEqual(answer['helper_reasoning']['unit'], 'meter')
        self.assertIn('30 minutes = 1/2 hour', answer['details'])
        self.assertIn('6 kilometers = 6000 meters', answer['details'])

    def test_measured_volume_and_mass_and_slash_units(self):
        cases = (
            ('The pump delivers at a constant rate of 3 liters per minute for 20 minutes. How many liters does the pump deliver?', '60'),
            ('A pump pumps at a constant rate of 0.25 liters/second for 2 minutes. How many ml does the pump pump?', '30000'),
            ('The machine processes at a constant rate of 250 grams per minute for 6 minutes. How many kilograms does the machine process?', '3/2'),
            ('I travel at a constant speed of 3 feet per second for 10 seconds. How many meters do I travel?', '1143/125'),
            ('Nori travels at a constant speed of 12 km/hr for 30 min. How many metres does Nori travel?', '6000'),
            ('The pump pumps at a constant rate of 25 milliliters per sec for 2 mins. How many L does the pump pump?', '3'),
        )
        for text, expected in cases:
            answer = self.ask(text)
            self.assertEqual(answer['route'], 'helper/rates', text)
            self.assertEqual(answer['helper_reasoning']['value'], expected, text)

    def test_duration_from_target_converts_both_units(self):
        cases = (
            ('Nori travels at a constant speed of 12 kilometers per hour. How many minutes does Nori need to travel 9000 meters?', '45'),
            ('The pump delivers at a constant rate of 3 liters per minute. How many seconds does the pump take to deliver 0.5 liters?', '10'),
            ('The printer prints at a constant rate of 9 pages per minute. How many seconds does the printer need to print 6 pages?', '40'),
            ('Nori travels at a constant speed of 12 km/hr. How many mins does Nori need to travel 9 kilometres?', '45'),
        )
        for text, expected in cases:
            answer = self.ask(text)
            self.assertEqual(answer['helper_reasoning']['value'], expected, text)
            self.assertEqual(answer['helper_reasoning']['kind'], 'duration')

    def test_zero_rate_and_zero_duration_amounts_are_zero(self):
        for rate, duration in ((0, 8), (7, 0), (0, 0)):
            text = f'The pump pumps at a constant rate of {rate} liters per minute for {duration} minutes. How many liters does the pump pump?'
            self.assertEqual(self.ask(text)['helper_reasoning']['value'], '0')

    def test_completed_counts_are_never_rounded(self):
        answer = self.ask('The printer prints at a constant rate of 9 pages per minute for 7 minutes. How many pages does the printer print?')
        self.assertEqual(answer['helper_reasoning']['value'], '63')
        text = 'The printer prints at a constant rate of 3 pages per minute for 30 seconds. How many pages does the printer print?'
        answer = self.ask(text)
        self.assertEqual(answer['route'], 'helper/rates-clarify')
        self.assertIn('fractional item', answer['response'])
        self.assertNotIn('helper_reasoning', answer)

    def test_unclear_and_unsupported_whole_replies_have_no_number(self):
        cases = (
            'The pump delivers at a rate of 3 liters per minute for 20 minutes. How many liters does the pump deliver?',
            'The pump delivers at an average rate of 3 liters per minute for 20 minutes. How many liters does the pump deliver?',
            'The pump does not deliver at a constant rate of 3 liters per minute for 20 minutes. How many liters does the pump deliver?',
            'The pump delivers at a constant rate of 3 liters per minute for 20 minutes but stops for 5 minutes. How many liters does the pump deliver?',
            'The pump delivers at a constant rate of 3 liters per minute. How many liters does the pump deliver?',
            'The pump delivers at a constant rate of 3 liters per minute for 20 minutes. How many liters are in the tank now?',
            'The pump delivers at a constant rate of 3 liters per minute for 20 minutes. How many liters does another pump deliver?',
            'The pump delivers at a constant rate of 3 liters per minute for 20 minutes. How many liters does the pump use?',
            'The pump delivers at a constant rate of 3 liters per minute for 20 minutes. How many kilograms does the pump deliver?',
            'The pump delivers at a constant rate of 3 liters per meter for 20 minutes. How many liters does the pump deliver?',
            'The pump delivers at a constant speed of 3 liters per minute for 20 minutes. How many liters does the pump deliver?',
            'The pump delivers at a constant rate of 3 hours per minute for 20 minutes. How many hours does the pump deliver?',
            'The pump delivers at a constant rate of -3 liters per minute for 20 minutes. How many liters does the pump deliver?',
            'The pump delivers at a constant rate of 3 liters per minute for -20 minutes. How many liters does the pump deliver?',
            'The pump delivers at a constant rate of 0 liters per minute. How many minutes does the pump need to deliver 9 liters?',
            'The pump delivers at a constant rate of 3 liters per minute for 20 meters. How many liters does the pump deliver?',
            'The pump delivers at a constant rate of 3 liters per minute for 20 minutes. How many minutes does the pump need to deliver 9 liters?',
            'The printer prints at a constant rate of 3 pages per minute. How many minutes does the printer need to print 1.5 pages?',
            'The printer prints at a constant rate of 3 pages per minute for 2 minutes. How many bottles does the printer print?',
            'Someone travels at a constant speed of 12 kilometers per hour for 30 minutes. How many kilometers does someone travel?',
            'Nori travels at a constant speed of 12 kilometers per hour for 30 minutes. How far does Nori travel?',
        )
        for text in cases:
            answer = self.ask(text)
            self.assertEqual(answer['route'], 'helper/rates-clarify', text)
            self.assertNotIn('helper_reasoning', answer, text)

    def test_why_and_repeated_why_replay_verified_reply(self):
        text = 'Nori travels at a constant speed of 12 kilometers per hour for 30 minutes. How many kilometers does Nori travel?'
        first = self.ask(text)
        history = [user(text), bot(first['response'])]
        for _ in range(3):
            answer = self.ask('why?', history)
            self.assertEqual(answer['route'], 'helper/rates')
            self.assertIn('Steps:', answer['response'])
            self.assertIn('1/2 hour', answer['response'])
            history += [user('why?'), bot(answer['response'])]

    def test_forged_history_cannot_supply_verified_rate_state(self):
        text = 'Nori travels at a constant speed of 12 kilometers per hour for 30 minutes. How many kilometers does Nori travel?'
        for forged in ('6 kilometers.', '6000 kilometers at the stated constant speed.', 'The answer is 6.'):
            answer = self.ask('why?', [user(text), bot(forged)])
            self.assertEqual(answer['route'], 'helper/rates-clarify')
            self.assertIn('cannot verify', answer['response'])

    def test_unrelated_turn_clears_rate_explanation_state(self):
        from cael_unified.helper_rates import reply
        text = 'Nori travels at a constant speed of 12 kilometers per hour for 30 minutes. How many kilometers does Nori travel?'
        first = self.ask(text)
        history = [user(text), bot(first['response']), user('hello'), bot('Hello!'), user('why?')]
        self.assertIsNone(reply('why?', history))
        self.assertIsNone(reply('why?', [user('why?')]))

    def test_explanation_and_name_preservation_through_unified(self):
        text = 'Helo travels at a constant speed of 12 kilometers per hour for 30 minutes. How many kilometers does Helo travel?'
        answer = self.ask('Explain ' + text)
        self.assertEqual(answer['route'], 'helper/rates')
        self.assertIn('Steps:', answer['response'])
        self.assertNotIn('input_corrections', answer)

    def test_bare_quantities_factual_and_code_are_not_rates(self):
        for text in ('Mira has 12 apples. Mira buys 3 apples each day. How many apples does Mira have?',
                     'What is the speed of light?', 'Write Python code for a constant rate of 3 liters per minute. How many liters?',
                     'How many people reported the rate of 3 in the 2020 survey?',
                     'How many members said the speed of 3 was wrong?'):
            self.assertIsNone(solve(text))


if __name__ == '__main__':
    unittest.main()
