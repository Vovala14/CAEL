from datetime import datetime, timedelta, timezone
import unittest

from cael_unified import everyday, helper_quantities


class EverydayTests(unittest.TestCase):
    def test_clock(self):
        now = datetime(2026, 10, 19, 21, 5, tzinfo=timezone(timedelta(hours=3)))
        self.assertIn('21:05 (UTC+03:00)', everyday.clock('what time is it?', now)['response'])
        self.assertIn('Monday 19 October 2026', everyday.clock("what's the date today?", now)['response'])
        self.assertIsNone(everyday.clock('time flies when you have fun', now))

    def test_translation_only_from_the_list(self):
        self.assertIn('hola', everyday.reply('translate hello to spanish')['response'])
        self.assertIn('merci', everyday.reply('how do you say thank you in french?')['response'])
        self.assertEqual(everyday.reply('translate banana to german')['route'], 'chat/everyday-translate-unknown')
        self.assertIsNone(everyday.reply('what is 5 in binary?'))
        self.assertIsNone(everyday.reply('what is the capital in france'))

    def test_many_languages(self):
        from cael_unified import phrases
        self.assertGreaterEqual(len(phrases.TABLE), 50)
        self.assertTrue(all(set(t) <= set(phrases.PHRASES) for t in phrases.TABLE.values()))
        self.assertIn('konnichiwa', everyday.reply('translate hello to japanese')['response'])
        self.assertIn('asante', everyday.reply('how do you say thank you in swahili?')['response'])
        self.assertIn('Persian', everyday.reply('translate thanks to farsi')['response'])
        self.assertEqual(everyday.reply('translate hello to klingon')['route'], 'chat/everyday-translate-unknown')
        self.assertEqual(everyday.reply('translate please to hawaiian')['route'], 'chat/everyday-translate-unknown')

    def test_meaning_and_all_languages(self):
        self.assertIn('"thank you" in Japanese', everyday.reply('what does arigato mean?')['response'])
        self.assertIn('Spanish', everyday.reply('translate gracias to english')['response'])
        self.assertIsNone(everyday.reply('what does love mean?'))
        listing = everyday.reply('say cheers in all languages')['response']
        self.assertIn('Swedish', listing)
        self.assertIn('Japanese', everyday.reply('which languages do you know?')['response'])

    def test_plan_suggest_poem_figure(self):
        self.assertEqual(everyday.reply('can you help me plan my day?')['route'], 'chat/everyday-plan')
        planned = everyday.reply('help me plan my day, I need to email Bob, buy groceries and finish the report')['response']
        self.assertIn('email Bob', planned)
        self.assertIn('finish the report', planned)
        self.assertEqual(everyday.reply('what should I eat for dinner?')['route'], 'chat/everyday-suggest')
        self.assertEqual(everyday.reply('recommend a good book')['route'], 'chat/everyday-suggest')
        self.assertIn('Rain', everyday.reply('write me a short poem about rain')['response'])
        self.assertIn('384,400 km', everyday.reply('how far is the moon?')['response'])
        self.assertIsNone(everyday.reply('I recommend you stop'))

    def test_count_question_without_item(self):
        self.assertEqual(helper_quantities.reply('I have 3 apples and buy 5 more, how many do I have?')['response'], 'You have 8 apples.')


class WidgetTests(unittest.TestCase):
    """The vynly.co widget only uses chat and prompt modes."""

    @classmethod
    def setUpClass(cls):
        from cael_unified.assistant import Assistant
        cls.assistant = Assistant()
        cls.site = [dict(role='system', content='site: vynly.co')]

    def ask(self, text, site=True):
        return self.assistant.respond((self.site if site else []) + [dict(role='user', content=text)], n=1, seed=1, mode='chat')

    def test_picture_request_in_chat_gets_a_prompt(self):
        answer = self.ask('create an image of a dog')
        self.assertEqual(answer['route'], 'chat/picture-in-chat')
        self.assertIn('vynly.co/generate', answer['response'])
        self.assertIn('\n\na dog', answer['response'])
        self.assertNotIn('**', answer['response'])
        self.assertIn('Switch to Auto or Picture mode', self.ask('create an image of a dog', site=False)['response'])
        self.assertEqual(self.ask('how do I generate an image on vynly?')['route'], 'chat/vynly-faq')

    def test_greetings_in_other_languages(self):
        self.assertTrue(self.ask('היי')['response'].startswith('שלום (shalom)!'))
        self.assertTrue(self.ask('hola')['response'].startswith('Hola!'))
        self.assertEqual(self.ask('Как дела у тебя сегодня?')['route'], 'chat/everyday-foreign')
        self.assertEqual(self.ask('hi')['route'], 'chat/smalltalk-greeting')


class MemoryWriteTests(unittest.TestCase):
    def test_a_locked_file_never_breaks_a_reply(self):
        from unittest import mock
        from cael_unified import ltm
        memory = ltm.memory()
        with mock.patch('os.replace', side_effect=PermissionError('locked')):
            self.assertFalse(memory.save())
            memory.record('helper/arithmetic', 'answered')     # must not raise


if __name__ == '__main__':
    unittest.main()
