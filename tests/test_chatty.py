import unittest

from cael_unified import chat_corpus, chat_extra


def chat(*turns, replies=None):
    messages = []
    for i, text in enumerate(turns):
        messages.append(dict(role='user', content=text))
        if i < len(turns) - 1:
            messages.append(dict(role='assistant', content=(replies or {}).get(i, 'Okay.')))
    return messages


@unittest.skipUnless(chat_corpus.db(), 'chat corpus not installed')
class CorpusTests(unittest.TestCase):
    def test_close_matches_only(self):
        sleep = chat_corpus.reply('how can I sleep better?')
        self.assertEqual(sleep['route'], 'chat/corpus')
        self.assertRegex(sleep['details'], r'Apache 2\.0|CC BY-SA 3\.0')      # every reply names its source licence
        self.assertIsNone(chat_corpus.reply('how do I make pancakes?'))          # "Pancakes or waffles?" is not a recipe
        self.assertIsNone(chat_corpus.reply('how was your day?'))                # one shared word is not a match
        self.assertIsNone(chat_corpus.reply('Explain how it works.'))            # a follow-up about the conversation's topic

    def test_similar_requests_are_named(self):
        answer = chat_corpus.reply('give me ideas for a date night')
        self.assertTrue(answer['response'].startswith('I found a similar request'))

    def test_kinds_must_agree(self):
        self.assertEqual(chat_corpus.kind('how do I make pancakes?'), 'how')
        self.assertEqual(chat_corpus.kind('Pancakes or waffles?'), 'preference')
        self.assertEqual(chat_corpus.kind('why do people procrastinate?'), 'why')

    def test_shortening_keeps_list_items(self):
        text = 'Intro line.\n\n' + '\n'.join(f'{i}. ' + 'tip ' * 30 for i in range(1, 9))
        short = chat_corpus.shorten(text, limit=500)
        self.assertIn('1. tip', short)
        self.assertTrue(short.endswith('(Shortened; ask me for more.)'))


class ConversationTests(unittest.TestCase):
    def test_reacts_and_asks_back(self):
        answer = chat_extra.converse('I watched Dune last night')
        self.assertEqual(answer['route'], 'chat/talk-converse')
        self.assertTrue(answer['response'].endswith('?'))
        self.assertIn('sorry', chat_extra.reply('My cat is sick')['response'].lower())
        self.assertEqual(chat_extra.reply('tell me about yourself')['route'], 'chat/talk-persona')
        self.assertEqual(chat_extra.reply('can you help me plan a trip to Japan?')['route'], 'chat/talk-trip')

    def test_context(self):
        tips = chat_extra.reply('yes', chat('I am learning to cook', 'yes', replies={0: "That's great! Learning to cook is a good thing to spend time on. Want a few tips?"}))
        self.assertEqual(tips['route'], 'chat/talk-tips')
        answered = chat_extra.reply('It was great, we saw a waterfall', chat('I went hiking', 'It was great, we saw a waterfall',
                                                                              replies={0: 'Oh nice, hiking! How was it?'}))
        self.assertEqual(answered['route'], 'chat/talk-converse')
        # A functional question is not CAEL's small talk: "London" goes to the weather instead.
        weather = chat('what is the weather like?', 'London', replies={0: 'Which city should I check the weather for?'})
        self.assertIsNone(chat_extra.reply('London', weather))
        self.assertEqual(chat_extra.rewrite(weather), 'what is the weather in London?')


if __name__ == '__main__':
    unittest.main()
