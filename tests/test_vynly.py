"""CAEL as Vynly's helper chatbot: authored answers, retrieval, and when a message counts as a Vynly question."""
import json
import tempfile
import unittest
from pathlib import Path

from cael_unified.vynly import FAQ, VynlyHelp

CHUNKS = [
    dict(source='site', url='https://vynly.co/trails', title='Trails', heading='Trails are short videos.',
         text='Drop a clip, watch it loop. Up to 60 seconds. Any signed-in user can post to an open Trail.'),
    dict(source='site', url='https://vynly.co/privacy', title='Privacy Policy', heading='Your content, your control',
         text='Delete a post or spark: removes the record from our database immediately.'),
    dict(source='guide', url='https://vynly.co/about', title='Vynly guide', heading='Pages',
         text='The press kit and embeddable badge are at /embed. Explore is a discovery grid across the whole feed.'),
]


class VynlyHelpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        path = Path(cls.folder.name) / 'chunks.json'
        path.write_text(json.dumps(dict(chunks=CHUNKS)), encoding='utf-8')
        cls.help = VynlyHelp(path)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def ask(self, text, site=False, history=()):
        messages = ([dict(role='system', content='site: vynly.co')] if site else []) + list(history) + [dict(role='user', content=text)]
        if not self.help.about_vynly(text, messages):
            return None
        return self.help.answer(text, messages)

    def test_common_questions_get_authored_answers_with_links(self):
        cases = {'what is vynly?': 'what-is', 'why was my vynly upload rejected?': 'rejected', 'what are sparks?': 'sparks',
                 'how do I delete my vynly account?': 'delete-account', 'what is C2PA?': 'c2pa',
                 'can I post nsfw on vynly?': 'rules', 'how do I get a vynly demo token?': 'agents'}
        by_id = {f['id']: f for f in FAQ}
        for question, expected in cases.items():
            answer = self.ask(question)
            self.assertIsNotNone(answer, question)
            self.assertEqual(answer['route'], 'chat/vynly-faq', question)
            self.assertTrue(answer['response'].startswith(by_id[expected]['answer'][:40]), question)
            self.assertTrue(answer['sources'][0]['url'].startswith('https://vynly.co'), question)

    def test_general_how_to_counts_only_on_vynly(self):
        self.assertIsNone(self.ask('how do I post an image?'))                       # CAEL's own site: not a Vynly question
        self.assertEqual(self.ask('how do I post an image?', site=True)['route'], 'chat/vynly-faq')
        self.assertIsNone(self.ask('what is the capital of France?', site=True))    # not found on Vynly: normal chat answers

    def test_retrieval_answers_from_the_site_and_requires_most_words(self):
        answer = self.ask('is there a discovery grid across the whole feed?', site=True)
        self.assertEqual(answer['route'], 'chat/vynly-search')
        self.assertIn('Explore', answer['response'])
        self.assertIsNone(self.ask('how do I bake bread?', site=True))

    def test_follow_up_after_a_vynly_answer_stays_on_vynly(self):
        first = self.ask('what are sparks?')
        history = [dict(role='user', content='what are sparks?'), dict(role='assistant', content=first['response'])]
        self.assertTrue(self.help.follows_vynly_answer(history + [dict(role='user', content='how do I add one?')]))

    def test_unknown_vynly_question_is_honest(self):
        answer = self.ask('does vynly have a desktop app for linux?')
        self.assertEqual(answer['route'], 'chat/vynly-unknown')
        self.assertIn('support@vynly.co', answer['response'])


if __name__ == '__main__':
    unittest.main()
