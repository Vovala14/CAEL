import unittest

from cael_unified.smalltalk import reply


def say(*turns, seed=0):
    messages = []
    for index, text in enumerate(turns):
        messages.append(dict(role='user' if index % 2 == 0 else 'assistant', content=text))
    return reply(messages, seed)


class SmalltalkTests(unittest.TestCase):
    def test_everyday_messages_get_matching_replies(self):
        cases = {
            'How are you?': 'how-are-you', "what's up?": 'how-are-you', 'hey how are you doing today': 'how-are-you',
            'Hi': 'greeting', 'Good morning': 'greeting', 'Thank you!': 'thanks', 'bye': 'goodbye', 'Good night': 'goodbye',
            'sorry': 'apology', 'I feel sad today': 'feeling', 'I am stressed about work': 'feeling', 'I am bored': 'feeling',
            'You are great': 'compliment', 'You are stupid': 'criticism', 'Tell me a joke': 'joke', 'Are you a robot?': 'identity',
            'What can you do?': 'help', 'Do you like music?': 'preferences', 'I went hiking yesterday': 'activity',
        }
        for text, kind in cases.items():
            answer = say(text)
            self.assertIsNotNone(answer, text)
            self.assertEqual(answer['route'], 'chat/smalltalk-' + kind, text)

    def test_mood_answers_depend_on_the_question_asked(self):
        self.assertEqual(say('How are you?', "I'm doing well, thanks! How are you?", 'ok')['route'], 'chat/smalltalk-mood')
        self.assertEqual(say('ok')['route'], 'chat/smalltalk-ack')
        self.assertIn('too', say("I'm good, how about you?")['response'])
        self.assertIn('sorry', say('How are you?', 'Good, and you?', 'not great')['response'].lower())

    def test_names_are_remembered_within_the_conversation(self):
        self.assertIn('Alex', say('My name is Alex')['response'])
        self.assertEqual(say('My name is Alex', 'Nice to meet you!', 'What is my name?')['response'], 'Your name is Alex.')
        self.assertIn("haven't told me", say('What is my name?')['response'])

    def test_messages_with_several_clauses_answer_each_part(self):
        combined = say('How are you?', "I'm doing well! How are you?", "I'm good, thanks. My name is Alex")
        self.assertEqual(combined['route'], 'chat/smalltalk-mood+name')
        self.assertIn('Alex', combined['response'])
        self.assertEqual(say('thanks, bye')['route'], 'chat/smalltalk-thanks+goodbye')
        self.assertEqual(say('ok, thanks')['route'], 'chat/smalltalk-thanks')
        self.assertIsNone(say('Hello. What is photosynthesis?'))  # never answer only part of a message

    def test_replies_are_reproducible_for_a_seed(self):
        self.assertEqual(say('Hi', seed=4), say('Hi', seed=4))

    def test_questions_and_tasks_are_left_to_other_routes(self):
        for text in ('What is photosynthesis?', 'When was Metallica formed?', 'What is 2+2?', 'I got a new job!',
                     'Tell a story about a fox finding a key', 'Write a python function to sort a list'):
            self.assertIsNone(say(text), text)


if __name__ == '__main__':
    unittest.main()
