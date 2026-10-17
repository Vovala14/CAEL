"""Case analysis ('or', contradiction), the remaining bAbI story types, and chat explanations."""
import unittest
from cael_unified.reasoning import MOTIVATIONS, Reasoner, split_problem
from cael_unified.reasoning_sat import query as case_query


class CaseAnalysisTests(unittest.TestCase):
    def test_or_elimination(self):
        context='Everything that is a cat or a dog is a pet. Every pet is loved. Rex is a cat or a dog'
        self.assertEqual(case_query(context,'Prove: Rex is loved')['answer'],'true')

    def test_proof_by_contradiction(self):
        context='Every wumpus is a jompus. Sally is not a jompus'
        self.assertEqual(case_query(context,'Prove: Sally is not a wumpus')['answer'],'true')

    def test_no_rule_and_universal_question(self):
        context='Every whale is a mammal. No mammal is a fish'
        self.assertEqual(case_query(context,'Is it true that every whale is a fish')['answer'],'false')

    def test_abilities(self):
        self.assertEqual(case_query('All birds can fly. Penguins are birds','Can penguins fly')['answer'],'true')

    def test_open_or_is_unknown(self):
        self.assertEqual(case_query('Rex is a cat or a dog','Prove: Rex is a cat')['answer'],'unknown')

    def test_contradictory_premises(self):
        self.assertEqual(case_query('Every cat is a mammal. Tom is a cat. Tom is not a mammal','Prove: Tom is a cat')['answer'],'conflicting')


class StoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine=Reasoner()

    def solve(self,context,question):
        return self.engine.solve(context,question)

    def test_pairs_and_pronouns(self):
        context='Sam and Lily went to the kitchen. Then they moved to the garden. Afterwards she went to the office.'
        self.assertEqual(self.solve(context,'Where is Lily?')['answer'],'office')
        self.assertEqual(self.solve(context,'Where is Sam?')['answer'],'garden')

    def test_time_order(self):
        context='Yesterday Ann went to the park. This morning Ann went to the school. This evening Ann went to the cinema.'
        self.assertEqual(self.solve(context,'Where was Ann before the cinema?')['answer'],'school')

    def test_induction(self):
        result=self.solve('Lily is a swan. Lily is white. Bernhard is a swan.','What colour is Bernhard?')
        self.assertEqual((result['answer'],result['family'],result.get('inferred')),('white','induction',True))

    def test_positions(self):
        context='The red box is to the left of the blue box. The blue box is above the green box.'
        self.assertEqual(self.solve(context,'Is the red box to the left of the green box?')['answer'],'yes')
        self.assertEqual(self.solve(context,'Is the green box above the red box?')['answer'],'no')

    def test_compass(self):
        context='The kitchen is north of the hallway. The garden is west of the kitchen.'
        self.assertEqual(self.solve(context,'What is north of the hallway?')['answer'],'kitchen')
        self.assertEqual(self.solve(context,'What is the kitchen east of?')['answer'],'garden')

    def test_motivation(self):
        if not MOTIVATIONS.exists():
            self.skipTest('motivation table is installed with the model bundle')
        self.assertEqual(self.solve('Ann is tired.','Where will Ann go?')['answer'],'bedroom')
        self.assertEqual(self.solve('Ann is hungry. Ann went to the kitchen.','Why did Ann go to the kitchen?')['answer'],'hungry')


class ChatTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine=Reasoner()

    def test_natural_question_forms_become_proofs(self):
        for lead in ('Does it follow that','Can we conclude that','Is it true that'):
            context,question,explicit=split_problem(f'Every cat is a mammal. Tom is a cat. {lead} Tom is a mammal?')
            self.assertEqual(question,'Prove: Tom is a mammal')
            self.assertTrue(explicit)

    def test_answer_shows_premises_and_method(self):
        out=self.engine.respond('Everything that is a cat or a dog is a pet. Every pet is loved. Rex is a cat or a dog. Does it follow that Rex is loved?')
        self.assertEqual(out['route'],'chat/reasoning-logic-cases')
        self.assertIn('every possible case',out['response'])
        self.assertIn('Based on:',out['response'])
        self.assertIn('3. Rex is a cat or a dog.',out['response'])

    def test_full_sentence_answers(self):
        out=self.engine.respond('Sam and Lily went to the kitchen. Then they moved to the garden. Where is Lily?')
        self.assertTrue(out['response'].startswith('Lily is in the garden.'))

    def test_inferred_answers_are_labelled(self):
        out=self.engine.respond('Lily is a swan. Lily is white. Bernhard is a swan. What colour is Bernhard?')
        self.assertIn('by analogy',out['response'])

    def test_contradiction_is_reported(self):
        out=self.engine.respond('Every cat is a mammal. Tom is a cat. Tom is not a mammal. Is Tom a cat?')
        self.assertIn('conflict',out['response'])

    def test_ordinary_conversation_is_left_to_chat(self):
        self.assertIsNone(self.engine.respond('I went to the store yesterday. What should I cook tonight?'))
        self.assertIsNone(self.engine.respond('My brother and I went to the park. What games can we play?'))


if __name__=='__main__':
    unittest.main()
