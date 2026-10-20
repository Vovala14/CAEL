import unittest

from cael_unified import chat_extra, dictionary, grammar, reasoning_extra


def first_line(answer):
    return answer['response'].split('\n')[0]


@unittest.skipUnless(dictionary.db(), 'dictionary model not installed')
class DictionaryTests(unittest.TestCase):
    def test_definitions_rank_the_everyday_meaning_first(self):
        self.assertIn('present everywhere', dictionary.reply('what does ubiquitous mean?')['response'])
        self.assertIn('(adjective) Lasting a very short time', dictionary.reply('define ephemeral')['response'])
        self.assertEqual(dictionary.reply('what does the idiom "break the ice" mean?')['route'], 'chat/dictionary-idiom')

    def test_synonyms_antonyms_and_forms(self):
        self.assertIn('glad', dictionary.reply('what is a synonym for happy?')['response'])
        self.assertIn('quick', dictionary.reply('synonyms for fast')['response'])
        self.assertIn('stingy', dictionary.reply('what is the opposite of generous?')['response'])
        self.assertIn('**mice**', dictionary.reply('what is the plural of mouse?')['response'])
        self.assertIn('**went**', dictionary.reply('what is the past tense of "go"?')['response'])
        self.assertIn('**swum**', dictionary.reply('past participle of swim')['response'])

    def test_spelling_rhymes_and_real_words(self):
        self.assertIn('definitely', dictionary.reply('how do you spell definately?')['response'])
        rhymes = dictionary.reply('what is a word that rhymes with cat?')['response']
        self.assertIn('hat', rhymes)
        self.assertNotIn('great', rhymes)
        self.assertIn('regardless', dictionary.reply('is "irregardless" a real word?')['response'])
        self.assertIsNone(dictionary.reply('what does it mean'))


@unittest.skipUnless(dictionary.db(), 'dictionary model not installed')
class GrammarTests(unittest.TestCase):
    def fixed(self, text):
        return first_line(grammar.reply(text))

    def test_corrections(self):
        cases = {
            'correct this sentence: she dont like apples': "She doesn't like apples.",
            'fix the grammar: me and him goes to school every day': 'He and I go to school every day.',
            'correct: I has two cat': 'I have two cats.',
            "fix: the dog wagged it's tail": 'The dog wagged its tail.',
            'correct the sentence: he runned fast yesterday': 'He ran fast yesterday.',
            'correct this: Me and my friend was late.': 'My friend and I were late.',
            'fix: their is a book on the table': 'There is a book on the table.',
            'correct: the childs plays in the park': 'The children play in the park.',
            'correct this: he go to school every day': 'He goes to school every day.',
            'fix: I seen him yesterday': 'I saw him yesterday.',
            'correct: i dont know were he is': "I don't know where he is.",
            'fix: a elephant is big': 'An elephant is big.',
        }
        for request, expected in cases.items():
            self.assertIn(f'**{expected}**', self.fixed(request), request)

    def test_correct_sentences_are_left_alone(self):
        for sentence in ('She is a good singer.', 'The news is good.', 'The cats are sleeping.', 'I have seen it.'):
            self.assertEqual(grammar.reply('correct: ' + sentence)['route'], 'chat/grammar-ok', sentence)

    def test_transformations_and_explanations(self):
        self.assertIn('The mouse was chased by the cat.', grammar.reply('put this in passive voice: The cat chased the mouse')['response'])
        self.assertIn('I walked to school.', grammar.reply('make this sentence past tense: I walk to school')['response'])
        self.assertIn('The tall man', grammar.reply('what is the subject in "The tall man sang loudly"?')['response'])
        self.assertIn("Let's eat, Grandma!", grammar.reply('add punctuation: lets eat grandma')['response'])
        self.assertIn('fewer', grammar.reply('should I say "fewer" or "less" people?')['response'])
        self.assertIn('Between you and **me**', grammar.reply('is "between you and I" correct?')['response'])
        self.assertIsNone(grammar.reply('fix this code: def add(a, b) return a + b'))


@unittest.skipUnless(dictionary.db(), 'dictionary model not installed')
class ReasoningTests(unittest.TestCase):
    def answer(self, text):
        return first_line(reasoning_extra.reply(text))

    def test_logic(self):
        self.assertEqual(self.answer('If it rains, the ground gets wet. It is raining. Is the ground wet?'), 'Yes.')
        self.assertEqual(self.answer('If it rains, the ground gets wet. The ground is not wet. Is it raining?'), 'No.')
        self.assertTrue(self.answer('If it rains, the ground gets wet. The ground is wet. Is it raining?').startswith('Not necessarily'))
        self.assertEqual(self.answer('No birds are mammals. A penguin is a bird. Is a penguin a mammal?'), 'No.')
        self.assertEqual(self.answer('If all bloops are razzies and all razzies are lazzies, are all bloops lazzies?'), 'Yes.')
        self.assertTrue(self.answer('Is the following true: some cats are black, so all cats are black?').startswith('No'))

    def test_comparisons(self):
        self.assertIn('**Bob** is the shortest', self.answer('Tom is taller than Ann. Ann is taller than Bob. Who is the shortest?'))
        self.assertEqual(self.answer('John is older than Mike. Mike is older than Sue. Is Sue older than John?'), 'No.')
        self.assertEqual(self.answer('Kate is older than Jim. Who is younger, Kate or Jim?'), '**Jim**.')

    def test_word_problems_and_time(self):
        self.assertIn('**8**', self.answer('Sam has twice as many sweets as Lee. Lee has 4. How many does Sam have?'))
        self.assertIn('**3**', self.answer('There are 5 birds on a tree. 2 fly away. How many are left?'))
        self.assertIn('**0.05**', self.answer('A bat and a ball cost 1.10 in total. The bat costs 1.00 more than the ball. How much is the ball?'))
        self.assertIn('5:00 PM', self.answer('A train leaves at 3 pm and the trip takes 2 hours. When does it arrive?'))
        self.assertIn('Thursday', self.answer('If today is Monday, what day is it in 3 days?'))
        self.assertIn('Wednesday', self.answer('If today is Friday, what day was it 2 days ago?'))
        self.assertIn('x = 4', reasoning_extra.reply('If 3x = 12, what is x?')['response'])

    def test_analogies_and_common_sense(self):
        self.assertIn('**down**', self.answer('Hot is to cold as up is to what?'))
        self.assertIn('**cat**', self.answer('Puppy is to dog as kitten is to what?'))
        self.assertIn('**hive**', self.answer('Bird is to nest as bee is to what?'))
        self.assertTrue(self.answer('Can a fish climb a tree?').startswith('No'))
        self.assertIn('same', self.answer('Which is heavier, a kilo of feathers or a kilo of steel?'))


class ChatTests(unittest.TestCase):
    def test_follow_up_rewrites(self):
        topic = [dict(role='user', content='what is the capital of France?'), dict(role='assistant', content='The capital of France is Paris.'),
                 dict(role='user', content='and what about Germany?')]
        self.assertEqual(chat_extra.rewrite(topic), 'what is the capital of Germany?')
        person = [dict(role='user', content='who wrote Hamlet?'), dict(role='assistant', content='Hamlet was written by William Shakespeare.'),
                  dict(role='user', content='when was he born?')]
        self.assertEqual(chat_extra.rewrite(person), 'when was William Shakespeare born?')
        self.assertIsNone(chat_extra.rewrite([dict(role='user', content='hi')]))

    def test_statements_tips_and_facts(self):
        self.assertEqual(chat_extra.reply('I got the job!')['route'], 'chat/talk-good-news')
        self.assertEqual(chat_extra.reply('I had a long day at work')['route'], 'chat/talk-sympathy')
        history = [dict(role='user', content='I am learning to cook'), dict(role='assistant', content='Great!'), dict(role='user', content='any tips?')]
        self.assertIn('recipes', chat_extra.reply('any tips?', history)['response'])
        self.assertEqual(chat_extra.reply('tell me something interesting')['route'], 'chat/talk-fact')
        self.assertIsNone(chat_extra.reply('I did not get the job'))


if __name__ == '__main__':
    unittest.main()
