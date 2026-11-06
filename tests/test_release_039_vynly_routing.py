"""The site proxy marker must not turn general tasks into site-help retrieval."""
import tempfile
import unittest
from cael_unified import Assistant
from cael_unified.vynly import VynlyHelp

SITE = {'role':'system','content':'site: vynly.co'}

class VynlyScopeTests(unittest.TestCase):
    def test_unrelated_questions_are_not_site_help(self):
        helper=VynlyHelp()
        for text in ['Can you work out 74 * 5?', 'How do I iterate over dictionary values?',
                     'Which editor did I say I prefer?', 'Who invented the telephone?',
                     'Can you check that calculation again?', 'How do I sort a list in Python?']:
            with self.subTest(text=text):
                self.assertFalse(helper.about_vynly(text,[SITE,{'role':'user','content':text}]))

    def test_site_faq_and_explicit_site_retrieval_remain(self):
        helper=VynlyHelp()
        for text in ['What is Vynly?', 'How do I post?', 'How do I delete my account?',
                     'How do I report a post?', 'What are Sparks?']:
            with self.subTest(text=text):
                self.assertTrue(helper.about_vynly(text,[SITE,{'role':'user','content':text}]))
                self.assertIsNotNone(helper.answer(text,[SITE,{'role':'user','content':text}]))

    def test_new_task_after_help_is_not_captured(self):
        helper=VynlyHelp()
        messages=[{'role':'assistant','content':'Site help.\n\nMore: vynly.co/faq'},
                  {'role':'user','content':'Can you work out 74 * 5?'}]
        self.assertFalse(helper.about_vynly(messages[-1]['content'],messages))

    def test_actual_arithmetic_under_proxy_context(self):
        with tempfile.TemporaryDirectory() as temp:
            assistant=Assistant(output_root=temp)
            result=assistant.respond([SITE,{'role':'user','content':'Can you work out 74 * 5?'}],mode='chat',n=1,seed=137)
            self.assertEqual(result['route'],'helper/arithmetic')
            self.assertIn('370',result['response'])

if __name__=='__main__':
    unittest.main()
