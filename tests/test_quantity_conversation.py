"""Quantity contexts survive verified answers; unrelated/tampered text cannot seed them."""
import unittest
from unittest.mock import patch
from cael_unified.assistant import Assistant
from cael_unified.reasoning_chat import context_from_history


def user(text):return dict(role='user',content=text)
def bot(text):return dict(role='assistant',content=text)


class QuantityConversationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.engine=Assistant()

    def turn(self,messages,text):
        messages.append(user(text))
        answer=self.engine.respond(messages,n=1,seed=47)
        messages.append(bot(answer['response']))
        return answer

    def test_add_after_answers_and_repeated_why(self):
        messages=[]
        with patch.object(self.engine._facts,'respond',side_effect=AssertionError('No web for scenarios')):
            self.turn(messages,'Facts: Mira has 10 apples.')
            self.turn(messages,'Add: Mira buys 2 apples.')
            self.assertEqual(self.turn(messages,'How many apples does Mira have?')['helper_reasoning']['value'],'12')
            self.assertIn('10 + 2 = 12',self.turn(messages,'why?')['response'])
            self.assertIn('10 + 2 = 12',self.turn(messages,'why?')['response'])
            self.turn(messages,'Add: Mira buys 3 apples.')
            self.assertEqual(self.turn(messages,'How many apples does Mira have?')['helper_reasoning']['value'],'15')
            self.assertIn('12 + 3 = 15',self.turn(messages,'why?')['response'])

    def test_inline_problem_then_add_with_query(self):
        messages=[]
        with patch.object(self.engine._facts,'respond',side_effect=AssertionError('No web for scenarios')):
            self.turn(messages,'Nori has 25 shells. Nori loses 4 shells. How many shells does Nori have?')
            answer=self.turn(messages,'Add: Nori buys 7 shells. Question: How many shells does Nori have?')
            self.assertEqual(answer['helper_reasoning']['value'],'28')
            self.assertIn('21 + 7 = 28',self.turn(messages,'show me the steps')['response'])

    def test_clarification_preserves_facts_and_snapshot_can_resolve_missing_amount(self):
        messages=[]
        with patch.object(self.engine._facts,'respond',side_effect=AssertionError('No web for scenarios')):
            self.turn(messages,'Facts: Leena has 14 marbles.')
            self.turn(messages,'Add: Leena gives 3 marbles to Tavi.')
            self.assertEqual(self.turn(messages,'How many marbles does Tavi have?')['route'],'helper/quantity-clarify')
            self.turn(messages,'Add: Tavi has 7 marbles.')
            self.assertEqual(self.turn(messages,'How many marbles does Tavi have?')['helper_reasoning']['value'],'7')

    def test_tampered_or_incidental_numbers_do_not_seed_context(self):
        messages=[user('Facts: Mira has 10 apples.'),bot('Premises saved. Ask your question.'),
                  user('How many apples does Mira have?'),bot('Mira has 999 apples.'),user('Add: Mira buys 3 apples.')]
        self.assertEqual(context_from_history(messages),('',None))
        answer=self.engine.respond(messages,n=1,seed=47)
        self.assertEqual(answer['route'],'chat/reasoning-clarify')
        messages=[user('When was the company formed?'),bot('It was formed in 1981.'),user('Add: Mira buys 3 apples.')]
        self.assertEqual(self.engine.respond(messages,n=1,seed=47)['route'],'chat/reasoning-clarify')

    def test_new_facts_reset_and_other_sessions_are_independent(self):
        messages=[]
        with patch.object(self.engine._facts,'respond',return_value=dict(route='chat/fixture',response='No quantity context.',sources=[])):
            self.turn(messages,'Facts: Ravi has 11 coins.')
            self.turn(messages,'How many coins does Ravi have?')
            self.turn(messages,'Facts: Ravi has 4 coins.')
            self.assertEqual(self.turn(messages,'How many coins does Ravi have?')['helper_reasoning']['value'],'4')
            other=self.engine.respond([user('How many coins does Ravi have?')],n=1,seed=47)
            self.assertEqual(other['route'],'chat/fixture')

    def test_unrelated_factual_count_question_reaches_lookup(self):
        messages=[]
        self.turn(messages,'Facts: Mira has 10 apples.')
        self.turn(messages,'How many apples does Mira have?')
        with patch.object(self.engine._facts,'respond',return_value=dict(route='chat/fixture',response='Fixture astronomy evidence.',sources=[])) as lookup:
            answer=self.turn(messages,'How many planets are in the Solar System?')
        # Not hijacked by the quantity context: answered by the world-facts table, or by the factual lookup.
        self.assertIn(answer['route'],('chat/fixture','chat/world-fact'))
        if answer['route']=='chat/world-fact':
            self.assertIn('eight',answer['response'])
            lookup.assert_not_called()
        else:
            lookup.assert_called_once()


if __name__=='__main__':unittest.main()
