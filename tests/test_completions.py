"""Finishing well-known rhymes and sayings (completions.py)."""
import unittest

from cael_unified import completions


class CompletionTests(unittest.TestCase):
    def test_requests_and_bare_starts_are_completed(self):
        for text, rest in (('complite, roses are red', 'violets are blue'), ('roses are red, violets are', 'blue'),
                           ('Finish the sentence: an apple a day', 'keeps the doctor away'),
                           ('twinkle twinkle little', 'star'), ('what comes next: the early bird', 'catches the worm'),
                           ('I think therefore', 'I am')):
            with self.subTest(text=text):
                answer = completions.reply(text)
                self.assertEqual(answer['route'], 'chat/complete-line')
                self.assertIn(rest, answer['response'])

    def test_unknown_lines_are_not_invented(self):
        answer = completions.reply('complete: my cat likes to')
        self.assertEqual(answer['route'], 'chat/complete-unknown')

    def test_other_messages_pass_through(self):
        for text in ('roses are lovely', 'Hello there', 'What is 5 times 6?', 'continue the story about a dragon',
                     'Where does the early bird live?'):
            with self.subTest(text=text):
                self.assertIsNone(completions.reply(text))


if __name__ == '__main__':
    unittest.main()
