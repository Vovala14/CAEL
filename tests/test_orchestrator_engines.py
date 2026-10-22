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


class CodexEngineChainTests(unittest.TestCase):
    """Results from the exact-maths helper and the bounded Python interpreter pass between steps."""

    def test_decimal_of_an_exact_result_and_several_solutions(self):
        self.assertEqual(orchestrator.classify('helper/geometry', 'Area = 9*pi (approximately 28.27433388)'), ('number', '28.27433388'))
        answers = {'Solve x*x = 4': dict(route='helper/equation', response='x = -2 or x = 2'),
                   '(2) + (3)': dict(route='helper/arithmetic', response='(2) + (3) = 5')}
        board = orchestrator.run(['Solve x*x = 4', 'add 3 to it'], lambda text, history: answers[text])
        self.assertIsNone(board.entries[1].value)
        self.assertEqual(board.entries[1].route, 'chat/plan-skipped')
        self.assertIn('multiple solutions; no single value selected', board.entries[0].notes)

    def test_code_runs_in_the_bounded_interpreter(self):
        code = '```python\ndef count_vowels(text):\n    return sum(char in "aeiou" for char in text)\n```'
        board = orchestrator.run(['write a function that counts vowels', 'run it on "banana"'],
                                 lambda text, history: dict(route='chat/code-composed', response=code))
        self.assertEqual(board.entries[1].value, 3)
        self.assertIn("bounded Python interpreter", board.entries[1].response)

    def test_yes_no_rewrites_and_steps_without_a_result(self):
        self.assertEqual(orchestrator.normalise('tell me if the result is a prime number'), 'is the result a prime number?')
        answers = {'How much change do I get?': dict(route='helper/quantity-clarify', response='I cannot reliably parse every event.')}
        board = orchestrator.run(['How much change do I get?', 'double it'], lambda text, history: answers[text])
        self.assertEqual(board.entries[1].route, 'chat/plan-skipped')


class PromptKindTests(unittest.TestCase):
    """'Make prompt for a dog image' is a picture prompt, not an assistant task (seen on vynly.co)."""

    def test_picture_prompts_in_any_word_order(self):
        from cael_unified.promptgen import is_prompt_request, parse
        for text, brief in [('Make prompt for a dog image', 'a dog'), ('prompt for a dragon picture', 'a dragon'),
                            ('Make a prompt for a dragon picture.', 'a dragon'), ('make me a midjourney prompt for a robot', 'a robot'),
                            ('improve this prompt: a dog on a beach', 'a dog on a beach'),
                            ('write a prompt for an image of a cat', 'an image of a cat')]:
            with self.subTest(text=text):
                self.assertTrue(is_prompt_request(text))
                request = parse(text)
                self.assertEqual(request['kind'], 'image')
                self.assertEqual(request['brief'], brief)
        self.assertEqual(parse('write a prompt for a chatbot that summarises emails')['kind'], 'task')
        self.assertEqual(parse('write a story prompt about a lost key')['kind'], 'story')

    def test_another_prompt_keeps_the_subject(self):
        seen = []

        def answer(text, history):
            seen.append(text)
            return dict(route='chat/prompt-image', response='Image prompt:\na dog, ...')
        orchestrator.run(['write a prompt for a dog image', 'make another one', 'make one for a cat image'], answer)
        self.assertEqual(seen[1], 'make a prompt for a dog image')
        self.assertEqual(seen[2], 'make a prompt for a cat image')


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
