"""Context disambiguates controls while protecting names, real words and code."""
import unittest
from cael_unified.bundle import ROOT
from cael_unified.text_repair import TextRepair
from cael_unified.news_policy import NewsPolicy
from cael_unified.assistant import Assistant
from unittest.mock import patch


class TypoContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.model=TextRepair(ROOT/'models/cael-text-repair-0.4.4-r1/model.json')

    def test_numeric_request_does_not_get_mistaken_for_code(self):
        self.assertEqual(self.model.repair('Could you calclate (137 + 9) * 4?')[0],'Could you calculate (137 + 9) * 4?')
        for code in ('calclate(137)', 'def calclate(x): return x', 'Could you calclate(value)',
                     'Please use calclate(137)', '`calclate(137)`'):
            self.assertEqual(self.model.repair(code),(code,[]),code)

    def test_narrow_help_anagram_and_weather_time_controls(self):
        for text,expected in [
            ('please hlpe me','please help me'),
            ('what is the wether tomorrow?','what is the weather tomorrow?'),
            ('what is the weather for tommorow?','what is the weather for tomorrow?'),
        ]:
            self.assertEqual(self.model.repair(text)[0],expected)
        for text in ('What is a wether?', 'What is Wether?', 'Tell me about hlpe', 'I feel tried',
                     'Wher has 12 apples.', 'Facts: Wher has 12 apples.', 'Helo went to the garden.'):
            self.assertEqual(self.model.repair(text),(text,[]),text)

    def test_polite_help_is_a_chat_request_even_after_spelling_repair(self):
        engine=Assistant()
        with patch.object(engine._facts,'respond',side_effect=AssertionError('Help must not be sent to lookup')):
            for text in ('please hlpe me','Please help me','Could you please help me?', 'Would you help me please?'):
                answer=engine.respond([dict(role='user',content=text)],seed=46,n=1)
                self.assertEqual(answer['route'],'chat/smalltalk-help',text)
                self.assertIn('What do you need help with?',answer['response'])

    def test_ordinary_chat_does_not_become_news_from_classifier_score(self):
        policy=NewsPolicy()
        for text in ('please help me', 'could you explain this', 'tell me more', 'I need help with a problem', 'Can you calculate 2 plus 3?'):
            self.assertIsNone(policy.parse(text),text)


if __name__=='__main__':unittest.main()
