"""Vynly help: "why does an AI-art site check for AI?" (asked on vynly.co, often spelled "A.I." or "a I"), and how to
check an image. General "why" questions stay with normal chat."""
import unittest

from cael_unified.vynly import VynlyHelp


class WhyCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.help = VynlyHelp()

    def route(self, text):
        if not self.help.about_vynly(text):
            return None
        return self.help.answer(text)['route']

    def test_why_check_questions_get_the_authored_answer(self):
        for text in ('Why does Vynly detect A.I. art?', 'why do you have an ai detector if everything here is ai made',
                     'Why detect a I art', 'Why check uploads for AI?'):
            with self.subTest(text=text):
                self.assertTrue(self.help.about_vynly(text))
                self.assertIn('only for AI-made art', self.help.answer(text)['response'])

    def test_checking_an_image_points_to_the_checker(self):
        self.assertIn('vynly.co/check', self.help.answer('How do I check if an image is AI?')['response'])

    def test_general_why_questions_are_not_vynly(self):
        for text in ('Why is the sky blue?', 'Why did the Roman Empire fall?', 'Why do cats purr?'):
            with self.subTest(text=text):
                self.assertIsNone(self.route(text))


if __name__ == '__main__':
    unittest.main()
