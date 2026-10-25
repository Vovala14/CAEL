"""Everyday understanding (0.3.4): misspellings and chat shorthand, abbreviations, job descriptions, stories about
any subject, occasion messages, pet names, riddles and compliments, and common science facts. Offline."""
import unittest

from cael_unified import spelling, acronyms, free_story, compose_text, world_facts
from cael_unified.assistant import Assistant


class SpellingTests(unittest.TestCase):
    def test_common_slips_are_corrected(self):
        for typed, meant in (('whats the captial of australia', "what's the capital of australia"),
                             ('what is fotosynthesis', 'what is photosynthesis'),
                             ('what is the largets planet', 'what is the largest planet'),
                             ('how do i deal with stres', 'how do i deal with stress'),
                             ('wich planet is called the red planet', 'which planet is called the red planet'),
                             ('what is a blackhole', 'what is a black hole'),
                             ('what is 3 sqared', 'what is 3 squared'),
                             ('how can i relaks after work', 'how can i relax after work'),
                             ('r u smart', 'are you smart'), ('ur funny', "you're funny"), ('whats ur name', "what's your name"),
                             ('how do i loose weight', 'how do i lose weight'), ('what is 12 x 12', 'what is 12 * 12')):
            with self.subTest(typed=typed):
                self.assertEqual(spelling.correct(typed)[0], meant)

    def test_correct_text_names_and_code_are_left_alone(self):
        for text in ('Theo puts the marble in the basket and leaves the room.', 'Who is Kofi Annan?',
                     'Felix opens the jar and sees a coin inside.', 'Write a Python function that reverses a string.',
                     'Helo splits 28 apples equally among 7 children.', 'def foo(x): return x', 'I love Vynly and CAEL',
                     'Whose company designed and built the Eiffel Tower?', 'What is the GDP of Uzbekistan?'):
            with self.subTest(text=text):
                self.assertEqual(spelling.correct(text), (text, []))

    def test_two_equal_readings_are_offered_not_guessed(self):
        self.assertEqual(spelling.correct('what is the talest animal')[0], 'what is the talest animal')
        self.assertIn('what is the tallest animal', spelling.variants('what is the talest animal'))


class EverydayAnswerTests(unittest.TestCase):
    def test_abbreviations_and_jobs(self):
        self.assertIn('central processing unit', acronyms.reply('What does CPU stand for?')['response'])
        self.assertIn('National Aeronautics and Space Administration', acronyms.reply('what does nasa stand for')['response'])
        self.assertIn('licensed medical practitioner', acronyms.reply('What does a doctor do?')['response'])
        self.assertIn('operates a farm', acronyms.reply('what does a farmer do')['response'])
        self.assertIsNone(acronyms.reply('What does a cat do?'))

    def test_stories_about_any_subject(self):
        story = free_story.story('Tell me a short story about a dragon.', seed=3)
        self.assertEqual(story['route'], 'chat/story-free')
        self.assertIn('dragon', story['response'])
        self.assertIsNone(free_story.story('What is a dragon?'))

    def test_occasion_messages_and_names(self):
        note = compose_text.reply('Write a birthday message for my mom.')
        self.assertIn('birthday', note['response'].lower())
        self.assertIn('Mom', note['response'])
        self.assertIn('Anna', compose_text.reply('write a get well soon card for Anna')['response'])
        dog = compose_text.reply('Give me a name for my dog.')['response']
        self.assertTrue(any(n in dog for n in compose_text.PET_NAMES['dog']))
        self.assertIn('coffee shop', compose_text.reply('Suggest a name for a coffee shop.')['response'])

    def test_new_facts(self):
        for question, word in (('How many players are on a soccer team?', '11'), ('What gas do humans breathe out?', 'carbon dioxide'),
                               ('Who discovered gravity?', 'Newton'), ('Why is the sky blue?', 'scatter'),
                               ('What is the moon made of?', 'rock'), ('Why do leaves change color in autumn?', 'chlorophyll')):
            with self.subTest(question=question):
                self.assertIn(word, world_facts.reply(question)['response'])


class AssistantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = Assistant()

    def ask(self, text):
        return self.a.respond([dict(role='user', content=text)])

    def test_misspelled_questions_get_answers(self):
        self.assertIn('Canberra', self.ask('whats the captial of australia')['response'])
        self.assertIn('giraffe', self.ask('what is the talest animal')['response'])
        self.assertEqual(self.ask('tell me a joek')['route'], 'chat/smalltalk-joke')
        self.assertIn('Spelling interpretation', self.ask('what is the fastest land aminal')['details'])

    def test_chit_chat(self):
        self.assertEqual(self.ask('Tell me a riddle.')['route'], 'chat/smalltalk-riddle')
        self.assertEqual(self.ask('ur funny')['route'], 'chat/smalltalk-compliment')
        self.assertEqual(self.ask('Can we be friends?')['route'], 'chat/smalltalk-friendship')


if __name__ == '__main__':
    unittest.main()
