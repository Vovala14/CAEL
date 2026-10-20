import unittest

from cael_unified import advice_text, life_advice, thinking


@unittest.skipUnless(advice_text.dic.db(), 'dictionary not installed')
class AdviceReadingTests(unittest.TestCase):
    def test_reads_instructions_and_reasons(self):
        found = advice_text.advice_in('Make sure that you turn off your phone an hour before bedtime. '
                                      'You should keep your bedroom dark and cool, because light keeps you awake. '
                                      "Don't drink coffee after 2pm. Cast iron care is super-simple. I recommend reading before bed.")
        keys = {k for k, *_ in found}
        self.assertIn('turn|hour+phone', keys)
        self.assertIn('no:drink|coffee', keys)
        self.assertTrue(any(r == 'light keeps you awake' for _, _, r, _ in found))
        self.assertFalse(any(a.startswith('cast') for _, a, _, _ in found))        # a statement, not advice

    def test_situational_advice_is_dropped(self):
        self.assertEqual(advice_text.advice_in('Ask him firmly to stop. Tell your boss I said so.'), [])

    def test_nouns(self):
        self.assertEqual(advice_text.noun_stem('phones'), 'phone')
        self.assertEqual(advice_text.noun_stem('worries'), 'worry')


class ThinkingTests(unittest.TestCase):
    def test_understands_goals(self):
        self.assertEqual(thinking.understand('How do I keep my houseplants alive?'), ('how', 'keep your houseplants alive'))
        self.assertEqual(thinking.understand('what should I pack for a beach holiday?')[0], 'ideas')
        self.assertIsNone(thinking.understand('I like cats'))

    def test_life_topics(self):
        self.assertIsNotNone(life_advice.topic_for('stop procrastinating'))
        self.assertIn('sunscreen', life_advice.topic_for('pack for a beach holiday')[0][0])

    @unittest.skipUnless(thinking.db(), 'thinking knowledge not built')
    def test_writes_its_own_answer(self):
        answer = thinking.reply('how can I stop procrastinating?')
        self.assertEqual(answer['route'], 'chat/thinking')
        self.assertIn('1. **', answer['response'])
        self.assertTrue(answer['response'].rstrip().endswith('?'))
        self.assertIn('No neural model', answer['details'])
        self.assertIsNone(thinking.reply('how do I build a time machine out of cheese?'))

    @unittest.skipUnless(thinking.guides(), 'guides not built')
    def test_recipes_use_shared_ingredients(self):
        answer = thinking.recipe('how do I make pancakes?')
        self.assertIn('flour', answer['response'])
        self.assertIn('Wikibooks', answer['details'])
        self.assertIsNone(thinking.recipe('how do I make soup?'))            # too many different dishes to share a core


if __name__ == '__main__':
    unittest.main()
