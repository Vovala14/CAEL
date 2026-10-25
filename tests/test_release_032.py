"""CAEL 0.3.2: web answers that say the asked thing, confirmation without a name/number, and A-D questions routed
to multiple choice. Offline: search providers and pages are fixtures."""
import unittest
from unittest.mock import patch

from cael_unified import web_search as W
from cael_unified.assistant import choice_problem


class WebAnswerTests(unittest.TestCase):
    def setUp(self):
        W._CACHE.clear()
        W._RECENT.clear()

    def run_answer(self, question, results, pages):
        with patch.object(W, 'PROVIDERS', (('Fixture', lambda q: results),)), \
                patch.object(W, 'wikipedia', lambda q: []), patch.object(W, 'read', lambda url: pages.get(url, '')):
            return W.answer(question)

    def test_in_what_year_questions_are_searched(self):
        self.assertTrue(W.should_search('In what year did the Berlin Wall fall?'))
        self.assertTrue(W.should_search('In which ocean is the Mariana Trench?'))

    def test_a_sentence_that_only_names_the_subject_is_not_an_answer(self):
        self.assertFalse(W.says_asked('What is the national animal of Scotland?',
                                      'Scotland is a country that is part of the United Kingdom.'))
        self.assertTrue(W.says_asked('What is the national animal of Scotland?',
                                     'The unicorn is the national animal of Scotland.'))
        self.assertFalse(W.says_asked('What is the largest bone in the human foot?', 'Testing confirmed that the foot was human.'))
        result = W.Result('Scotland', 'https://en.wikipedia.org/wiki/Scotland', '', 'Fixture')
        page = 'Scotland is a country that is part of the United Kingdom. Scotland has a long coast with many islands.'
        self.assertIsNone(self.run_answer('What is the national animal of Scotland?', [result], {result.url: page}))

    def test_two_websites_saying_the_same_answer_word_confirm_it(self):
        results = [W.Result('Hardest minerals', 'https://minerals.example.org/hardest', '', 'Fixture'),
                   W.Result('Mohs scale', 'https://geology.example.com/mohs', '', 'Fixture')]
        pages = {results[0].url: 'Diamond is the hardest natural mineral known on the Mohs scale of hardness.',
                 results[1].url: 'Diamond is always at the top of the scale, being the hardest natural mineral.'}
        answer = self.run_answer('What is the hardest natural mineral?', results, pages)
        self.assertEqual(answer['route'], 'chat/web-search')
        self.assertIn('2 different websites agree', answer['response'])


class MultipleChoiceRoutingTests(unittest.TestCase):
    def test_then_in_a_lettered_question_is_still_multiple_choice(self):
        text = 'Rotate "abcdef" left by 2 characters, then reverse the result.\nA) fedcba\nB) bafedc\nC) abcdef\nD) cdefab'
        self.assertIsNotNone(choice_problem(text))
        from cael_unified import orchestrator
        with patch.object(orchestrator, 'plan', side_effect=AssertionError('planned a multiple-choice question')):
            from cael_unified.assistant import Assistant
            answer = Assistant().respond([dict(role='user', content=text)])
        self.assertRegex(answer['response'], r'^[A-D]\. ')


if __name__ == '__main__':
    unittest.main()
