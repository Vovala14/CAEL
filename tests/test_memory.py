import unittest

from cael_unified.memory import facts, recall
from cael_unified.public_worker import MAX_REQUEST_BYTES
from cael_unified.assistant import MAX_CHARACTERS, MAX_MESSAGES


def chat(*user_turns):
    messages = []
    for text in user_turns:
        messages += [dict(role='user', content=text), dict(role='assistant', content='Okay.')]
    return messages[:-1]


class MemoryTests(unittest.TestCase):
    def test_stated_facts_are_recalled_with_original_capitals(self):
        history = chat('I live in Paris and I like jazz and hiking', 'My dog is called Rex', 'I am 34 years old',
                       "I don't like mushrooms", 'I work as a nurse')
        for question, expected in [('Where do I live?', 'You live in Paris.'), ("What's my dog's name?", 'Your dog is Rex.'),
                                   ('How old am I?', 'You are 34 years old.'), ('What do I do?', 'You are a nurse.'),
                                   ('What do I like?', 'You told me you like jazz and hiking.'),
                                   ('Do I like mushrooms?', "No, you told me you don't like mushrooms.")]:
            self.assertEqual(recall(history + [dict(role='user', content=question)])['response'], expected, question)

    def test_later_statements_replace_earlier_ones(self):
        known = facts(chat('I live in Paris', 'I like tea', 'Actually I live in Rome', "I don't like tea"))
        self.assertEqual(known['attributes']['home'], 'Rome')
        self.assertEqual((known['likes'], known['dislikes']), ([], ['tea']))

    def test_unknown_facts_are_not_invented(self):
        self.assertIn("haven't told me", recall(chat('Hi', 'Where do I live?'))['response'])
        self.assertIn("haven't told me anything", recall(chat('What do you know about me?'))['response'])

    def test_whole_conversation_is_available(self):
        history = chat(*[f'message {i}' for i in range(300)], 'What was my first message?')
        self.assertEqual(recall(history)['response'], 'Your first message was: "message 0"')
        self.assertGreaterEqual(MAX_MESSAGES, 600)
        self.assertGreaterEqual(MAX_REQUEST_BYTES, MAX_CHARACTERS)

    def test_new_facts_are_acknowledged_and_questions_left_alone(self):
        self.assertIn('your dog is Rex', recall(chat('My dog is called Rex'))['response'])
        self.assertIsNone(recall(chat('I like pizza')))
        self.assertIsNone(recall(chat('What is photosynthesis?')))


if __name__ == '__main__':
    unittest.main()
