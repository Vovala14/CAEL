"""Conversation memory (0.3.5): people, pronouns, updates with history, corrections vs contradictions vs disagreements,
plans, integer-record compression, and leaving unrelated questions alone."""
import unittest

from cael_unified import conversation_memory as cm


def chat(*lines):
    history = []
    for line in lines:
        history += [dict(role='user', content=line), dict(role='assistant', content='Okay.')]
    return history


def ask(history, question):
    answer = cm.reply(history + [dict(role='user', content=question)])
    return answer['response'] if answer else None


class ContextMemoryTests(unittest.TestCase):
    def test_people_relations_and_pronouns(self):
        h = chat('My aunt Greta just retired.', 'She lives in Lyon.', 'I talked to Bruno yesterday.', 'Greta has a parrot named Pico.')
        self.assertIn('Lyon', ask(h, 'Where does my aunt live?'))
        self.assertIn('Greta', ask(h, 'Who is my aunt?'))
        self.assertIn('Pico', ask(h, "What is Greta's parrot called?"))

    def test_updates_keep_history(self):
        h = chat('Omar lives in Quito.', 'Omar moved to Bogota last spring.')
        now = ask(h, 'Where does Omar live now?')
        self.assertIn('Bogota', now)
        self.assertIn('Before that: Quito', now)
        self.assertIn('Quito', ask(h, 'Where did Omar live before?'))

    def test_correction_is_not_a_conflict(self):
        h = chat('The recital is on Thursday.', 'Sorry, I meant Saturday, not Thursday.')
        reply = ask(h, 'When is the recital?')
        self.assertIn('Saturday', reply)
        self.assertNotIn('Which one is right', reply)

    def test_contradiction_and_disagreement_ask_for_clarification(self):
        self.assertIn('Which one is right', ask(chat('Ines is 40 years old.', 'Ines is 44.'), 'How old is Ines?'))
        reply = ask(chat('Paul says the market opens on Monday.', 'Vera says the market opens on Tuesday.'), 'When does the market open?')
        self.assertIn('disagree', reply)

    def test_plan_progress_skip_and_add(self):
        h = chat('I want to clean the garage. Steps: sort the boxes; sweep the floor; fix the shelf; paint the door.',
                 'Done: sort the boxes.', 'Skip "paint the door".', 'Add a step: buy hooks.')
        self.assertIn('sweep the floor', ask(h, 'What is the next step?'))
        left = ask(h, 'What is left in my plan?')
        self.assertIn('buy hooks', left)
        self.assertIn('Skipped: paint the door', left)

    def test_records_are_compact_integers(self):
        h = chat(*(['Nice weather today.'] * 20 + ['Lucia works as a chemist.']))
        raw, packed = cm.compression_stats(h)
        self.assertGreater(raw / packed, 10)
        store = cm.read_history(h).store
        self.assertEqual(store.data.typecode, 'i')
        self.assertEqual(len(store.data) % store.WIDTH, 0)

    def test_unrelated_questions_are_left_to_other_routes(self):
        h = chat('Ben is 30 years old.', 'My budget is 50 dollars.', 'I want to bake a cake. The steps are: buy flour, mix the batter, and bake it.')
        for question in ('How old is Ben Franklin?', 'How much does a car cost?', 'What steps are needed to learn Python?',
                         'What is the capital of France?', 'When is the next full moon?', 'What is the plan for world peace?'):
            with self.subTest(question=question):
                self.assertIsNone(ask(h, question))
        self.assertIsNone(cm.reply([dict(role='user', content='Where does Anna live?')]))


if __name__ == '__main__':
    unittest.main()
