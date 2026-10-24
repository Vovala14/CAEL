"""Web search fallback (web_search.py), offline: providers and page reads are replaced by fixtures."""
import unittest
from unittest.mock import patch

from cael_unified import web_search as W

BERLIN = ('Jump to content\nMain menu\nContents\nReferences\nThe Berlin Wall was a guarded concrete barrier that encircled West Berlin '
          'from 1961 to 1989. The Berlin Wall fell on 9 November 1989, and German reunification followed on 3 October 1990.\n'
          'References\n"The Wall" (1990). Retrieved 2020.')
CONCERT = 'The Wall – Live in Berlin was a concert held on 21 July 1990 to commemorate the fall of the Berlin Wall eight months earlier.'


class WebSearchTests(unittest.TestCase):
    def setUp(self):
        W._CACHE.clear()
        W._RECENT.clear()

    def run_answer(self, question, results, pages):
        with patch.object(W, 'PROVIDERS', (('Fixture', lambda q: results),)), \
                patch.object(W, 'wikipedia', lambda q: []), patch.object(W, 'read', lambda url: pages.get(url, '')):
            return W.answer(question)

    def test_subject_page_answers_and_side_articles_do_not(self):
        results = [W.Result('The Wall – Live in Berlin', 'https://en.wikipedia.org/wiki/The_Wall_Live', '', 'Fixture'),
                   W.Result('Berlin Wall', 'https://en.wikipedia.org/wiki/Berlin_Wall', '', 'Fixture')]
        answer = self.run_answer('When did the Berlin Wall fall?', results,
                                 {results[0].url: CONCERT, results[1].url: BERLIN})
        self.assertIn('fell on 9 November 1989', answer['response'])
        self.assertEqual(answer['route'], 'chat/web-search-unconfirmed')      # one website only: not presented as confirmed
        self.assertIn('```python', answer['details'])                         # the search, as a script
        self.assertEqual(answer['sources'][0]['url'], 'https://en.wikipedia.org/wiki/Berlin_Wall')
        self.assertIn('**Source:** [Berlin Wall (en.wikipedia.org)](https://en.wikipedia.org/wiki/Berlin_Wall)', answer['response'])

    def test_agreement_across_websites_is_confirmed(self):
        results = [W.Result('Octopus facts', 'https://a.example/octopus', '', 'Fixture'),
                   W.Result('Octopus anatomy', 'https://b.example/octopus', '', 'Fixture')]
        pages = {results[0].url: 'An octopus has three hearts that pump blue blood around its body.',
                 results[1].url: 'Every octopus has three hearts: two pump blood through the gills.'}
        answer = self.run_answer('How many hearts does an octopus have?', results, pages)
        self.assertEqual(answer['route'], 'chat/web-search')
        self.assertIn('**three**', answer['response'])
        self.assertIn('2 different websites agree', answer['response'])
        self.assertIn('[Octopus facts (a.example)](https://a.example/octopus)', answer['response'])
        self.assertIn('[Octopus anatomy (b.example)](https://b.example/octopus)', answer['response'])

    def test_page_text_cleanup(self):
        text = ('Look up sommelier in Wiktionary, the free dictionary.\nFor the knife, see Sommelier knife.\n'
                'A sommelier (UK: /ˈsɒməljeɪ/), chef de vin or wine steward, is a trained wine professional who works in restaurants.')
        found = [s for _, s in W.sentences(text)]
        self.assertEqual(found, ['A sommelier, chef de vin or wine steward, is a trained wine professional who works in restaurants.'])

    def test_when_to_search(self):
        self.assertTrue(W.should_search('What does a barista do?'))
        self.assertTrue(W.should_search('Who designed the Sydney Opera House?'))
        self.assertFalse(W.should_search('What is my favourite colour?'))       # personal
        self.assertFalse(W.should_search('Who will win the 2099 World Cup?'))   # the future
        self.assertFalse(W.should_search('I had a long day'))                   # not a question

    def test_subjects_and_kinds(self):
        self.assertEqual(W.subject_of('Who designed the Eiffel Tower?'), 'Eiffel Tower')
        self.assertEqual(W.subject_of('When was the first iPhone released?'), 'iPhone')
        self.assertEqual(W.subject_of('How many hearts does an octopus have?'), 'octopus')
        self.assertEqual(W.subject_of('Who is the CEO of Nvidia?'), 'Nvidia')
        self.assertEqual(W.kind_of('Who is Hayao Miyazaki?'), 'other')
        self.assertEqual(W.kind_of('Who designed the Eiffel Tower?'), 'name')

    def test_private_addresses_are_never_fetched_directly(self):
        self.assertFalse(W.public_host('http://127.0.0.1/admin'))
        self.assertFalse(W.public_host('http://localhost:8766/api/health'))
        self.assertFalse(W.public_host('file:///etc/passwd'))

    def test_search_script_request(self):
        answer = W.script_reply('Write a python script that searches the web for the tallest building in Europe')
        self.assertEqual(answer['route'], 'chat/code-web-search')
        code = answer['response'].split('```python\n')[1].split('```')[0]
        compile(code, 'search.py', 'exec')
        self.assertIn("QUERY = 'the tallest building in Europe'", code)
        self.assertIsNone(W.script_reply('Write a python function that reverses a string'))


if __name__ == '__main__':
    unittest.main()
