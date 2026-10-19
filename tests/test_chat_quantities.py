"""Exact role/unit transitions and refusal controls, using authored text only."""
import unittest
from unittest.mock import patch

from cael_unified.helper_chat import reply
from cael_unified.reasoning import Reasoner


def user(text):return dict(role='user',content=text)
def bot(text):return dict(role='assistant',content=text)


class QuantitiesTests(unittest.TestCase):
    def test_running_inventory_with_explicit_and_omitted_subjects(self):
        questions=[
            'Mira has 12 apples. Mira buys 5 apples. Mira gives 3 apples to Sam. How many apples does Mira have now?',
            'I have 12 apples, then buy 5 more, and give away 3 apples. How many apples do I have left?',
            'Mira has 12 apples. She buys 5 apples. She loses 3 apples. How many apples does Mira have?',
            'Facts: Mira has 12 apples. Add: Mira buys 5 apples. Also: Mira loses 3 apples. Question: How many apples does Mira have?',
        ]
        for text in questions:
            with self.subTest(text=text):
                answer=reply(text)
                self.assertEqual(answer['route'],'helper/quantity')
                self.assertEqual(answer['helper_reasoning']['value'],'14')
                self.assertNotIn('away',answer['helper_reasoning']['actors'])

    def test_transfer_roles_and_conservation(self):
        context='Tavi has 20 shells. Leena has 7 shells. Tavi gives 4 shells to Leena.'
        for subject,expected in [('Tavi','16'),('Leena','11'),('Tavi and Leena','27')]:
            answer=reply(context+f' How many shells does {subject} have?')
            self.assertEqual(answer['helper_reasoning']['value'],expected)
        for event in ('Tavi gives Leena 4 shells.','Leena receives 4 shells from Tavi.'):
            answer=reply('Tavi has 20 shells. Leena has 7 shells. '+event+' How many shells does Leena have?')
            self.assertEqual(answer['helper_reasoning']['value'],'11')

    def test_unrelated_units_are_not_added_and_unknown_starts_are_not_zero(self):
        answer=reply('Ravi has 31 apples. Ravi has 9 friends. Ravi buys 4 apples. How many apples does Ravi have?')
        self.assertEqual(answer['helper_reasoning']['value'],'35')
        answer=reply('Ravi has 31 apples. Ravi gives 4 apples to Mira. How many apples does Mira have?')
        self.assertEqual(answer['route'],'helper/quantity-clarify')
        self.assertIn('not assume it is zero',answer['response'])

    def test_decimals_colors_and_plural_units(self):
        for text,expected in [
            ('Nori has 2.5 liters. Nori buys 1.25 liters. How much liters does Nori have?','15/4'),
            ('Nori has 9 red apples. Nori has 4 blue balls. Nori loses 2 red apples. How many red apples does Nori have?','7'),
            ('Nori has 4 boxes. Nori buys 1 box. How many boxes does Nori have?','5'),
        ]:
            with self.subTest(text=text):self.assertEqual(reply(text)['helper_reasoning']['value'],expected)

    def test_conflicts_negation_and_ambiguity_get_no_numeric_guess(self):
        controls=[
            'Mira has 12 apples. Mira loses 13 apples. How many apples does Mira have?',
            'Mira has 12 apples. Mira has 13 apples. How many apples does Mira have?',
            'Mira has 12 more apples. How many apples does Mira have?',
            'Mira has 12 apples. Mira did not lose 3 apples. How many apples does Mira have?',
            'Mira has 12 apples. If Sam arrives, Mira gets 5 apples. How many apples does Mira have?',
            'Mira has 12 apples. Sam has 3 apples. She loses 2 apples. How many apples does Mira have?',
            'Mira has 12 apples. Mira has 3 pears. Mira buys 2 more. How many apples does Mira have?',
            'Mira has 12 apples. Mira gives 3 apples to Mira. How many apples does Mira have?',
            'Mira has 12 apples. Sam has 3 apples. How many pears does Mira have?',
            'Mira has 12 apples. The sky is blue. How many apples does Mira have?',
            'Mira has 12 apples. Mira buys 3 apples each day. How many apples does Mira have?',
            'Mira has 12 dollars. Mira buys 3 apples. How many dollars does Mira have?',
            'Mira has 12 apples. Mira gives 3 apples to Sam. Sam started with 0 apples. How many apples does Sam have?',
        ]
        for text in controls:
            with self.subTest(text=text):self.assertEqual(reply(text)['route'],'helper/quantity-clarify')

    def test_factual_questions_and_code_are_left_to_their_own_routes(self):
        for text in ('How many people live in London?',
                     'What is the population of Paris?',
                     'Write a Python function. How many elements are in [2, 3]?',
                     'The year is 2026. How many planets are there?'):
            self.assertIsNone(reply(text),text)

    def test_reasoning_facts_context_and_why_can_explain_quantity_events(self):
        engine=Reasoner();messages=[]
        for text in ('Facts: Mira has 12 apples.','Add: Mira buys 3 apples.'):
            messages.append(user(text));answer=engine.respond(text,messages);messages.append(bot(answer['response']))
        messages.append(user('How many apples does Mira have?'))
        with patch('cael_unified.network.NETWORK.json',side_effect=AssertionError('No network')):
            answer=reply(messages[-1]['content'],messages)
            self.assertEqual(answer['helper_reasoning']['value'],'15')
            messages += [bot(answer['response']),user('why?')]
            explanation=reply('why?',messages)
        self.assertIn('12 + 3 = 15 apples',explanation['response'])
        self.assertIsNone(reply('How many apples does Mira have?',[user('How many apples does Mira have?')]))

    def test_unknown_receiver_quantity_does_not_corrupt_known_giver(self):
        text='Mira has 12 apples. Mira gives 3 apples to Sam. Sam gives 1 apple to Mira. How many apples does Mira have?'
        self.assertEqual(reply(text)['helper_reasoning']['value'],'10')


class UnifiedQuantitiesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from cael_unified.assistant import Assistant
        cls.engine=Assistant()

    def test_quantity_and_explanation_do_not_go_to_web_or_smalltalk(self):
        text='Ravi has 12 coins. Ravi receives 5 coins. Ravi loses 3 coins. How many coins does Ravi have?'
        with patch.object(self.engine._facts,'respond',side_effect=AssertionError('Lookup forbidden')):
            answer=self.engine.respond([user(text)],seed=1)
            self.assertEqual(answer['helper_reasoning']['value'],'14')
            why=self.engine.respond([user(text),bot(answer['response']),user('why?')],seed=1)
            self.assertIn('Steps:',why['response'])


if __name__=='__main__':unittest.main()
