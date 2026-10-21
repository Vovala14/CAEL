"""Multi-part requests that pass results between the newer engines (dictionary, grammar, reasoning, translation)."""
import unittest

from cael_unified import dictionary, grammar, orchestrator, reasoning_extra


class PlanShapeTests(unittest.TestCase):
    def test_new_splits(self):
        self.assertEqual(orchestrator.plan('Correct this sentence: she go to school yesterday. Then explain the rule'),
                         ['Correct this sentence: she go to school yesterday', 'explain the rule'])
        self.assertEqual(orchestrator.plan('How can I sleep better? Also give me a tip for stress'),
                         ['How can I sleep better?', 'give me a tip for stress'])
        self.assertEqual(orchestrator.plan('1. What is 7 times 8\n2. Divide it by 4'), ['What is 7 times 8', 'Divide it by 4'])
        self.assertEqual(len(orchestrator.plan('If all cats are animals and Tom is a cat, is Tom an animal? Then explain why')), 2)
        self.assertIsNone(orchestrator.plan('Is it raining? No idea'))

    def test_normalise(self):
        self.assertEqual(orchestrator.normalise('tell me how many eggs I need'), 'how many eggs I need')
        self.assertEqual(orchestrator.normalise('tell me the capital of Japan'), 'what is the capital of Japan?')
        self.assertEqual(orchestrator.normalise('tell me a joke'), 'tell me a joke')
        self.assertEqual(orchestrator.normalise('say thank you in French'), 'how do you say thank you in French?')

    def test_word_values(self):
        self.assertEqual(orchestrator.classify('chat/dictionary-synonyms', 'Synonyms of **happy** (adjective): glad, bright.'), ('short', 'glad'))
        self.assertEqual(orchestrator.classify('chat/dictionary-antonyms', 'The opposite of **brave** is **cowardly, timid**.'), ('short', 'cowardly'))
        self.assertEqual(orchestrator.classify('chat/everyday-translate-meaning', '"arigato" means "thank you" in Japanese.'), ('short', 'thank you'))
        self.assertEqual(orchestrator.classify('chat/web-wikidata-faq', 'Hamlet was written by William Shakespeare.'), ('short', 'William Shakespeare'))

    def test_there_and_quoted_sentences(self):
        board = orchestrator.Board()
        board.add(orchestrator.Entry(1, 'capital of France', 'chat/web-wikidata-faq', 'The capital of France is Paris.', 'short', 'Paris'))
        self.assertEqual(orchestrator.resolve('what is the weather there?', board)[0], 'what is the weather in Paris?')
        board.add(orchestrator.Entry(2, 'fix it', 'chat/grammar-fixed', '', 'short', "They're going home."))
        self.assertEqual(orchestrator.resolve('put it in the past tense', board)[0], 'put "They\'re going home." in the past tense')

    def test_explain_uses_the_previous_steps_reasoning(self):
        answers = {'If all cats are animals and Tom is a cat, is Tom an animal?':
                   dict(route='chat/reasoning-categories', response='Yes.\n\nSteps:\n1. Tom is a cat, and every cat is an animal.')}
        board = orchestrator.run(['If all cats are animals and Tom is a cat, is Tom an animal', 'explain why'],
                                 lambda text, history: answers[text])
        self.assertEqual(board.entries[1].route, 'chat/plan-explain')
        self.assertIn('every cat is an animal', board.entries[1].response)


class EngineAdditionsTests(unittest.TestCase):
    def test_numbers_and_words(self):
        self.assertIn('not prime: 14 = 2 × 7', reasoning_extra.reply('is 14 a prime number?')['response'])
        self.assertIn('**97** is prime', reasoning_extra.reply('is 97 prime?')['response'])
        self.assertIn('1, 2, 3, 4, 6, 9, 12, 18, 36', reasoning_extra.reply('what are the factors of 36?')['response'])
        self.assertIn('yrassecen', reasoning_extra.reply('spell necessary backwards')['response'])
        self.assertIn('**9** letters', reasoning_extra.reply('how many letters are in necessary?')['response'])
        self.assertIn('**6** eggs', reasoning_extra.reply('how many eggs do I need for 3 batches if one batch uses 2 eggs?')['response'])
        self.assertIn('**24** eggs', reasoning_extra.reply('each box holds 6 eggs. how many eggs are in 4 boxes?')['response'])
        self.assertTrue(reasoning_extra.reply('If all dogs are mammals and Rex is a dog, is Rex a mammal?')['response'].startswith('Yes'))

    @unittest.skipUnless(dictionary.db(), 'dictionary model not installed')
    def test_grammar_past_time_and_contractions(self):
        self.assertIn('She went to school yesterday.', grammar.reply('Correct this sentence: she go to school yesterday')['response'])
        self.assertIn('They played football last week.', grammar.reply('fix: they plays football last week')['response'])
        self.assertIn('He goes to school every day.', grammar.reply('correct this: he go to school every day')['response'])
        self.assertIn('They were going home.', grammar.reply('put "They\'re going home." in the past tense')['response'])
        self.assertIn('She walked home.', grammar.reply('put "she walks home" in the past tense')['response'])


if __name__ == '__main__':
    unittest.main()
