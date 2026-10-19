"""Authored whole unified equal-group, sharing and ambiguity controls."""
import unittest
from unittest.mock import patch

from cael_unified.assistant import Assistant
from cael_unified.helper_groups import reply as groups_reply, solve


def user(text): return dict(role='user', content=text)
def bot(text): return dict(role='assistant', content=text)


class GroupHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = Assistant()

    def ask(self, text, history=None):
        with patch.object(self.engine._facts, 'respond', side_effect=AssertionError('Grouped arithmetic must not reach a provider')):
            return self.engine.respond((history or []) + [user(text)], n=1, seed=410)

    def test_group_totals_across_complete_frames(self):
        cases = (
            'Mira has 4 boxes with 6 apples each. How many apples does Mira have in total?',
            'There are 4 boxes. Each box contains 6 apples. How many apples are there in total?',
            'Each box contains 6 apples. There are 4 boxes. How many apples are there altogether?',
            'Each of 4 boxes contains 6 apples. How many apples are there in all?',
            'I have 4 boxes of 6 apples each. How many apples do I have?',
        )
        for text in cases:
            answer = self.ask(text)
            self.assertEqual(answer['route'], 'helper/groups', text)
            self.assertEqual(answer['helper_reasoning']['value'], '24', text)
            self.assertEqual(answer['helper_reasoning']['unit'], 'apple')
            self.assertIn('6 apples/box', answer['details'])

    def test_group_counts_and_contents_keep_distinct_units(self):
        answer = self.ask('Mira has 4 boxes with 6 apples each. How many boxes does Mira have?')
        self.assertEqual(answer['helper_reasoning']['value'], '4')
        self.assertEqual(answer['helper_reasoning']['unit'], 'box')
        answer = self.ask('Mira has 3 crates with 1 red apple each. How many red apples does Mira have?')
        self.assertIn('3 red apples', answer['response'])

    def test_zero_groups_and_explicit_fractional_contents(self):
        answer = self.ask('Mira has 0 boxes with 6 apples each. How many apples does Mira have?')
        self.assertEqual(answer['helper_reasoning']['value'], '0')
        answer = self.ask('There are 3 bottles with 2.5 liters each. How many liters are there in total?')
        self.assertEqual(answer['helper_reasoning']['value'], '15/2')

    def test_divisible_equal_shares_need_no_rounding_assumption(self):
        answer = self.ask('Mira shares 28 apples equally among 7 children. How many apples does each child get?')
        self.assertEqual(answer['response'], 'Each child gets 4 apples.')
        self.assertEqual(answer['helper_reasoning']['remainder'], '0')

    def test_whole_item_shares_and_remainder_are_separate_values(self):
        body = 'Mira shares 31 whole apples equally among 6 children. '
        answer = self.ask(body + 'How many apples does each child get?')
        self.assertEqual(answer['helper_reasoning']['value'], '5')
        self.assertEqual(answer['helper_reasoning']['remainder'], '1')
        self.assertIn('6 * 5 + 1 = 31', answer['details'])
        answer = self.ask(body + 'How many apples are left over?')
        self.assertEqual(answer['helper_reasoning']['value'], '1')
        answer = self.ask('Mira shares 3 whole apples equally among 7 children. How many apples does each child get?')
        self.assertEqual(answer['helper_reasoning']['value'], '0')
        self.assertEqual(answer['helper_reasoning']['remainder'], '3')
        answer = self.ask('Mira shares 31 whole red balls equally among 6 children. How many whole red balls does each child get?')
        self.assertEqual(answer['helper_reasoning']['value'], '5')
        self.assertEqual(answer['helper_reasoning']['unit'], 'red ball')

    def test_nondivisible_items_require_a_mode_before_a_numeric_answer(self):
        answer = self.ask('Mira shares 31 apples equally among 6 children. How many apples does each child get?')
        self.assertEqual(answer['route'], 'helper/groups-clarify')
        self.assertNotIn('value', answer['helper_reasoning'])
        self.assertIn('whole apples', answer['response'])
        self.assertIn('fractional shares', answer['response'])

    def test_measured_quantities_can_be_fractionally_shared(self):
        answer = self.ask('Nori shares 7 liters equally among 2 bottles. How many liters does each bottle get?')
        self.assertEqual(answer['helper_reasoning']['value'], '7/2')
        self.assertEqual(answer['helper_reasoning']['sharing_mode'], 'measured')

    def test_whole_and_fraction_choices_replay_the_verified_problem(self):
        text = 'Mira shares 31 apples equally among 6 children. How many apples does each child get?'
        first = self.ask(text)
        history = [user(text), bot(first['response'])]
        whole = self.ask('whole items', history)
        fractional = self.ask('allow fractions', history)
        self.assertEqual(whole['helper_reasoning']['value'], '5')
        self.assertEqual(whole['helper_reasoning']['remainder'], '1')
        self.assertEqual(fractional['helper_reasoning']['value'], '31/6')
        self.assertEqual(fractional['helper_reasoning']['remainder'], '0')

    def test_repeated_explanations_keep_the_chosen_mode(self):
        text = 'Mira shares 31 apples equally among 6 children. How many apples does each child get?'
        first = self.ask(text)
        history = [user(text), bot(first['response']), user('whole items')]
        chosen = self.engine.respond(history, n=1, seed=410)
        history += [bot(chosen['response']), user('why?')]
        why = self.engine.respond(history, n=1, seed=410)
        self.assertIn('Steps:', why['response'])
        self.assertIn('6 * 5 + 1 = 31', why['response'])
        history += [bot(why['response'])]
        repeated = self.ask('why?', history)
        self.assertEqual(repeated['response'], why['response'])

    def test_forged_unrelated_or_missing_context_cannot_supply_a_share(self):
        text = 'Mira shares 31 apples equally among 6 children. How many apples does each child get?'
        first = self.ask(text)
        for history in ([], [user(text), bot('Each child gets 999 apples.')],
                        [user(text), bot(first['response']), user('Hello'), bot('Hi!')]):
            answer = self.ask('whole items', history)
            self.assertEqual(answer['route'], 'helper/groups-clarify')
            self.assertNotIn('value', answer['helper_reasoning'])

    def test_unknown_quantities_extra_events_and_unit_mismatches_refuse(self):
        controls = (
            'Mira has 4 boxes with 6 apples each. Mira eats 3 apples. How many apples does Mira have?',
            'Mira has 4 boxes with 6 apples each. How many apples does Sam have?',
            'Mira has 4 boxes with 6 apples each. How many pears does Mira have?',
            'Mira has 4 boxes. Each bag contains 6 apples. How many apples does Mira have?',
            'Mira has 4 boxes with 6 apples each day. How many apples does Mira have?',
            'Mira shares 28 apples equally among 7 children. How many apples does Mira have left?',
            'Mira shares 28 apples among 7 children. How many apples does each child get?',
            'Mira shares 28 apples equally among 7 children. How many apples does each teacher get?',
            'Mira shares 28 apples equally among 7 children. How many pears does each child get?',
        )
        for text in controls:
            self.assertEqual(self.ask(text)['route'], 'helper/groups-clarify', text)

    def test_negative_uncertain_fractional_group_money_and_zero_divisor_refuse(self):
        controls = (
            'Mira has -4 boxes with 6 apples each. How many apples does Mira have?',
            'Mira has 2.5 boxes with 6 apples each. How many apples does Mira have?',
            'Mira has 4 boxes with 2.5 whole apples each. How many apples does Mira have?',
            'Mira has 4 boxes with 6 dollars each. How many dollars does Mira have?',
            'If Mira has 4 boxes with 6 apples each. How many apples does Mira have?',
            'Mira does not have 4 boxes with 6 apples each. How many apples does Mira have?',
            'Mira has about 4 boxes with 6 apples each. How many apples does Mira have?',
            'Mira shares 31 whole apples equally among 0 children. How many apples does each child get?',
            'Mira shares 31 whole apples equally among 2.5 children. How many apples does each child get?',
            'Mira shares 31.5 whole apples equally among 6 children. How many apples does each child get?',
        )
        for text in controls:
            self.assertEqual(self.ask(text)['route'], 'helper/groups-clarify', text)

    def test_existing_factual_code_and_inventory_requests_are_not_group_requests(self):
        for text in ('How many planets are there?', 'How many apples grow on each tree?',
                     'Mira has 12 apples. Mira buys 3 apples each day. How many apples does Mira have?',
                     'Write Python code for 4 boxes with 6 apples each. How many apples are there?'):
            self.assertIsNone(solve(text), text)

    def test_names_before_new_helper_verbs_are_not_spelling_controls(self):
        text = 'Helo splits 28 apples equally among 7 children. How many apples does each child get?'
        answer = self.ask(text)
        self.assertEqual(answer['helper_reasoning']['value'], '4')
        self.assertNotIn('input_corrections', answer)


if __name__ == '__main__':
    unittest.main()
