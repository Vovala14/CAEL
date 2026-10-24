"""0.3.1: exact quantities, world facts, Wikipedia answer finding, everyday writing, gap-fill, present-tense stories, text code."""
import unittest

from cael_unified import answer_finder, compose_text, dictionary, grammar, quantities, world_facts
from cael_unified.codegen.contracts import reply as compose_code
from cael_unified.codegen.python_vm import run_cases
from cael_unified.reasoning import present_story


def first(answer):
    return answer['response'].split('\n')[0]


class QuantityTests(unittest.TestCase):
    def test_powers_fractions_units(self):
        cases = {'What is 2 to the power of 10?': '**1024**', 'what is 6 squared?': '**36**', 'What is 7/8 as a decimal?': '**0.875**',
                 'convert 3/8 to a percentage': '**37.5%**', 'what is 0.35 as a fraction': '**7/20**',
                 'How many minutes are there in 3.5 hours?': '**210 minutes**', 'convert 5 miles to km': '**8.0467 km**',
                 'what is 100 F in celsius': '**37.78°C**', 'how many cups in a gallon': '**16 cups**'}
        for question, expected in cases.items():
            with self.subTest(question=question):
                self.assertIn(expected, first(quantities.reply(question)))

    def test_word_problems(self):
        self.assertIn('**30 km/h**', first(quantities.reply('A cyclist rides 45 km in 1.5 hours. What is her average speed?')))
        self.assertIn('**12**', first(quantities.reply('Tom has 3 times as many apples as Sam. Sam has 4 apples. How many apples does Tom have?')))
        self.assertIn('**$1.40**', first(quantities.reply('I buy 3 pens at $1.20 each and pay with a $5 note. How much change do I get?')))
        self.assertIn('**$30.00**', first(quantities.reply('A shirt costs $40 and is 25% off. What is the sale price?')))
        self.assertIsNone(quantities.reply('what is the capital of france'))
        self.assertIsNone(quantities.reply('I have 2 apples'))


class FactTests(unittest.TestCase):
    def test_table(self):
        self.assertIn('Jupiter', world_facts.reply('What is the largest planet in our solar system?')['response'])
        self.assertIn('Everest', world_facts.reply('What is the tallest mountain on Earth?')['response'])
        self.assertIn('Elbrus', world_facts.reply('what is the highest mountain in europe?')['response'])
        self.assertIn('206', world_facts.reply('how many bones are in the human body?')['response'])
        self.assertIsNone(world_facts.reply('what is the largest city in japan?'))

    def test_finder_reads_only_matching_sentences(self):
        class Net:
            def json(self, url, **kwargs):
                if 'list=search' in url:
                    return {'query': {'search': [{'title': 'Neptune'}, {'title': 'Jupiter'}]}}
                return {'query': {'pages': {
                    '1': {'title': 'Neptune', 'extract': 'Neptune is the eighth planet. It is the fourth-largest planet in the Solar System.', 'length': 9000},
                    '2': {'title': 'Jupiter', 'extract': 'Jupiter is the fifth planet from the Sun and the largest in the Solar System.', 'length': 5000}}}}
        answer = answer_finder.Finder(Net()).answer('What is the largest planet in the solar system?')
        self.assertTrue(answer['response'].startswith('**Jupiter**'))
        self.assertEqual(answer['sources'][0]['licence'], 'CC BY-SA 4.0')

    def test_finder_years_from_date_ranges(self):
        class Net:
            def json(self, url, **kwargs):
                if 'list=search' in url:
                    return {'query': {'search': [{'title': 'World War II'}]}}
                return {'query': {'pages': {'1': {'title': 'World War II', 'length': 1,
                                                  'extract': 'World War II (1 September 1939 – 2 September 1945) was a global conflict.'}}}}
        self.assertTrue(answer_finder.Finder(Net()).answer('In what year did World War II end?')['response'].startswith('**1945**'))
        self.assertTrue(answer_finder.Finder(Net()).answer('When did World War II begin?')['response'].startswith('**1939**'))


class WritingTests(unittest.TestCase):
    def test_summary_resolves_pronouns(self):
        text = ('Summarise in one sentence: The city council met on Tuesday to discuss the new park. After a long debate, they voted '
                '7 to 2 to fund it, and construction will start in spring. Some residents worried about the cost.')
        self.assertIn('The city council voted 7 to 2 to fund the new park', compose_text.reply(text)['response'])

    def test_emails(self):
        decline = compose_text.reply('Write a short, polite email declining a meeting invitation for Friday.')['response']
        self.assertIn('the meeting on Friday', decline)
        self.assertIn("won't be able to attend", decline)
        self.assertIn('thank you for watching my cat', compose_text.reply('write a short email thanking my neighbour for watching my cat')['response'])
        self.assertIn('ask for a day off next week', compose_text.reply('write an email to my boss asking for a day off next week')['response'])

    def test_names(self):
        answer = compose_text.reply('Suggest three names for a coffee shop.', seed=1)['response']
        self.assertEqual(len([l for l in answer.split('\n') if l[:2] in ('1.', '2.', '3.')]), 3)

    @unittest.skipUnless(dictionary.db(), 'dictionary model not installed')
    def test_compare_from_definitions(self):
        answer = compose_text.reply('What is the difference between weather and climate?')['response']
        self.assertIn('**Climate**: the weather in some location averaged over some long period of time.', answer)


@unittest.skipUnless(dictionary.db(), 'dictionary model not installed')
class LanguageTests(unittest.TestCase):
    def test_gap_fill(self):
        cases = {'Fill the gap with "its" or "it\'s": ___ a lovely day.': "It's a lovely day.",
                 'Fill the gap with "its" or "it\'s": The dog wagged ___ tail.': 'The dog wagged its tail.',
                 'Choose "then" or "than": She is taller ___ her brother.': 'She is taller than her brother.',
                 'Choose their, there or they\'re: Put it over ___.': 'Put it over there.',
                 'Choose to, too or two: I have ___ cats.': 'I have two cats.'}
        for question, expected in cases.items():
            with self.subTest(question=question):
                self.assertIn(f'**{expected}**', grammar.reply(question)['response'])

    def test_passive_phrasing_and_antonyms(self):
        self.assertIn('The man was bitten by the dog.', grammar.reply('Put this sentence in the passive voice: The dog bit the man.')['response'])
        self.assertIn('new', dictionary.reply('What is the opposite of "ancient"?')['response'])


class StoryAndCodeTests(unittest.TestCase):
    def test_present_tense_story(self):
        self.assertEqual(present_story('Mary is in the kitchen. Mary goes to the bedroom. Where is Mary?'),
                         'Mary went to the kitchen. Mary went to the bedroom. Where is Mary?')
        self.assertEqual(present_story('Ben has the keys. Ben gives the keys to Lucy. Who has the keys?'),
                         'Ben got the keys. Ben gave the keys to Lucy. Who has the keys?')
        self.assertEqual(present_story('I like tea. Do you?'), 'I like tea. Do you?')

    def test_text_operations_run(self):
        for request, name, args, expected in [
                ('Write a Python function that reverses the order of words in a sentence.', 'reverse_words', ['hello big world'], 'world big hello'),
                ('write a function that returns the longest word in a sentence', 'longest_word', ['a bb ccc'], 'ccc'),
                ('write a python function that removes all punctuation from a string', 'remove_punctuation', ['hi, you!'], 'hi you'),
                ('write a function that makes an acronym from a phrase', 'acronym', ['portable network graphics'], 'PNG'),
                ('write a function that returns the smallest number in a list', 'smallest', [[4, 1, 9]], 1)]:
            with self.subTest(request=request):
                code = compose_code(request)['response'].split('```python\n')[1].split('```')[0]
                self.assertEqual(run_cases(code, [dict(name=name, args=args)])['cases'][0]['value'], expected)


if __name__ == '__main__':
    unittest.main()
