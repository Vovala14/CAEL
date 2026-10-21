"""Authored conversational controls; no photos, private chats or network."""
from pathlib import Path
import unittest
from unittest.mock import patch

from cael_unified.bundle import ROOT
from cael_unified.helper_chat import reply, arithmetic_steps
from cael_unified.reasoning import Reasoner
from cael_unified.text_repair import TextRepair, repair_messages


MODEL=ROOT/'models/cael-text-repair-0.4.4-r1/model.json'


def user(text):return dict(role='user',content=text)
def assistant(text):return dict(role='assistant',content=text)


class RepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.model=TextRepair(MODEL)

    def test_unseen_character_errors_and_transpositions(self):
        examples={
            'helo':'hello', 'hwo are you?':'how are you?',
            'whta is photosynthesis?':'what is photosynthesis?',
            'cna yuo caluclate 20 percnt of 50?':'can you calculate 20 percent of 50?',
            'please wrtie a pyhton fucntion':'please write a python function',
            'My naem is Maya':'My name is Maya',
            'Given: John wnet to the kitchen. Wher is John?':'Given: John went to the kitchen. Where is John?',
            'what year Metallica was starrted?':'what year Metallica was started?',
        }
        for text,expected in examples.items():
            with self.subTest(text=text):self.assertEqual(self.model.repair(text)[0],expected)

    def test_names_quantifiers_code_quotes_paths_and_numbers_are_preserved(self):
        controls=[
            'Where is Mary?', 'What is Helo?', 'My name is Helo',
            'All birds are animals. Nori is not a bird. Is Nori an animal?',
            'No, not more than 14.25 and never less than -3.',
            'I like fir trees.', 'I bought a can of beans.',
            'What do you know about Pyhton?', 'Tell me about helo',
            'Use `caluclate(20)`.', 'print("helo")',
            'def caluclate(x): return x + 1', '```python\nhelo = 3\n```',
            'Open C:\\private\\helo.txt', 'Visit https://example.com/helo',
            'Email helo@example.com', 'Repeat "whta is pyhton" exactly.',
            "Repeat 'whta is pyhton' exactly.",
            '2 + 4 = 6', 'what year was Metallica founded?', 'why?', 'How?',
            'I want to know the story.', 'I feel tried', 'hell',
        ]
        for text in controls:
            with self.subTest(text=text):self.assertEqual(self.model.repair(text),(text,[]))

    def test_history_copied_and_only_last_turn_corrections_reported(self):
        messages=[user('helo'),assistant('Hello.'),user('hwo are you?')]
        with patch('cael_unified.text_repair.active_repairer',return_value=self.model):
            output,changes=repair_messages(messages)
        self.assertEqual(messages[0]['content'],'helo')
        self.assertEqual(output[0]['content'],'hello')
        self.assertEqual(changes[0]['original'],'hwo')

    def test_disabled_and_bounded(self):
        with patch('cael_unified.text_repair.active_repairer',return_value=None):
            messages=[user('helo')]
            self.assertEqual(repair_messages(messages),(messages,[]))
        text='helo '*500
        self.assertEqual(self.model.repair(text),(text,[]))


class HelperTests(unittest.TestCase):
    def test_exact_arithmetic_and_polite_phrasing(self):
        for text,end in [('Could you calculate (12 + 3) * 4?','60'),
                         ('Please compute 0.1 + 0.2','3/10'),
                         ("What's 16 divided by 4?",'4'),
                         ('How much is 9 minus 2?','7')]:
            with self.subTest(text=text):
                answer=reply(text)
                self.assertEqual(answer['response'].split(' = ')[-1],end)
                self.assertTrue(answer['helper_reasoning']['exact'])

    def test_operations_explained_in_dependency_order(self):
        steps=arithmetic_steps('(123 + 456) * (2 + 3)')
        self.assertEqual(steps[-1],'(123 + 456) * (2 + 3) = 2895')
        self.assertIn('123 + 456 = 579',steps[:-1])
        self.assertIn('2 + 3 = 5',steps[:-1])

    def test_percentages_conversions_and_zero_bases(self):
        self.assertEqual(reply('What percentage is 15 of 60?')['response'],'15 is 25% of 60.')
        self.assertEqual(reply('20% off 80')['response'].split(' = ')[-1],'64')
        self.assertEqual(reply('increase 80 by 25 percent')['response'].split(' = ')[-1],'100')
        self.assertEqual(reply('percentage change from 80 to 100')['response'],'Percentage change: 25%.')
        self.assertEqual(reply('How many centimeters in 2 meters?')['response'],'2 meters = 200 centimeters')
        for text in ('what percentage is 3 of 0?','percentage change from 0 to 50','1 / 0'):
            self.assertEqual(reply(text)['route'],'helper/undefined')

    def test_linear_equations_no_unique_solution_and_refusal(self):
        for text,expected in [('Solve 2x + 3 = 11','x = 4'),
                              ('Solve 2(x + 1) = 8','x = 3'),
                              ('Solve 3*x - 2 = x + 8','x = 5'),
                              ('Solve x + 1 = x + 2','This equation has no solution.'),
                              ('Solve x + 1 = x + 1','Every value of x satisfies this equation.')]:
            with self.subTest(text=text):self.assertEqual(reply(text)['response'],expected)
        self.assertEqual(reply('Solve x*x = 4')['route'],'helper/equation')
        self.assertIn('x = -2',reply('Solve x*x = 4')['response'])
        self.assertIn('x = 2',reply('Solve x*x = 4')['response'])
        self.assertIn('Collect terms',reply('Explain 3*x - 2 = x + 8')['response'])
        self.assertIsNone(reply('__import__("os").system("bad")'))
        self.assertEqual(reply('9 ** 99999999')['route'],'helper/undefined')

    def test_chained_calculation_explanation_and_session_isolation(self):
        messages=[user('12 + 3')]
        first=reply(messages[-1]['content'],messages)
        messages += [assistant(first['response']),user('multiply that by 4')]
        second=reply(messages[-1]['content'],messages)
        self.assertTrue(second['response'].endswith(' = 60'))
        messages += [assistant(second['response']),user('why?')]
        self.assertIn('Steps:',reply(messages[-1]['content'],messages)['response'])
        self.assertEqual(reply('multiply that by 4',[user('multiply that by 4')])['route'],'helper/clarify')
        unrelated=[user('Who was born in 1920?'),assistant('A person was born in 1920.'),user('add 4')]
        self.assertEqual(reply('add 4',unrelated)['route'],'helper/clarify')


class ReasoningConversationTests(unittest.TestCase):
    def setUp(self):self.engine=Reasoner()

    def exchange(self,messages,text):
        messages.append(user(text))
        answer=self.engine.respond(text,messages)
        if answer:messages.append(assistant(answer['response']))
        return answer

    def test_incremental_premises_queries_and_why(self):
        messages=[]
        with patch('cael_unified.network.NETWORK.json',side_effect=AssertionError('Network forbidden')):
            self.assertEqual(self.exchange(messages,'Facts: Zora is a rover.')['route'],'chat/reasoning-context')
            self.exchange(messages,'Add: All rovers are machines.')
            self.exchange(messages,'Add: All machines are physical.')
            answer=self.exchange(messages,'Is Zora physical?')
            self.assertEqual(answer['reasoning']['answer'],'true')
            self.assertEqual(answer['reasoning']['support'],[1,2,3])
            why=self.exchange(messages,'why?')
            self.assertEqual(why['reasoning']['answer'],'true')
            self.assertIn('All machines are physical',why['response'])

    def test_event_updates_replace_location(self):
        messages=[]
        self.exchange(messages,'Facts: Zora went to the kitchen.')
        self.exchange(messages,'Add: Zora moved to the office.')
        answer=self.exchange(messages,'Where is Zora?')
        self.assertEqual(answer['reasoning']['answer'],'office')

    def test_context_does_not_leak_to_new_scenario_session_or_unrelated_topic(self):
        messages=[]
        self.exchange(messages,'Facts: Zora is a rover. All rovers are machines.')
        self.assertIsNone(self.engine.respond('Is Zora a machine?',[user('Is Zora a machine?')]))
        self.assertIsNone(self.engine.respond('What is photosynthesis?',messages+[user('What is photosynthesis?')]))
        self.exchange(messages,'Is Zora a machine?')
        self.exchange(messages,'Facts: Zora is curious.')
        self.assertEqual(self.exchange(messages,'why?')['route'],'chat/reasoning-clarify')
        self.assertEqual(self.exchange(messages,'Is Zora a machine?')['reasoning']['answer'],'unknown')
        self.exchange(messages,'Clear premises')
        self.assertIsNone(self.exchange(messages,'Is Zora a machine?'))

    def test_contradiction_add_and_why_without_query(self):
        messages=[]
        self.assertEqual(self.exchange(messages,'Add: Zora is a bird.')['route'],'chat/reasoning-clarify')
        self.exchange(messages,'Facts: Zora is a bird.')
        self.assertEqual(self.exchange(messages,'why?')['route'],'chat/reasoning-clarify')
        answer=self.exchange(messages,'Add: Zora is not a bird. Question: Is Zora a bird?')
        self.assertEqual(answer['reasoning']['answer'],'conflicting')


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from cael_unified.assistant import Assistant
        cls.engine=Assistant()
        cls.model=TextRepair(MODEL)

    def test_repaired_helper_and_greeting_use_the_unified_entrypoint(self):
        with patch('cael_unified.text_repair.active_repairer',return_value=self.model),patch.object(self.engine._facts,'respond',side_effect=AssertionError('Lookup forbidden')):
            answer=self.engine.respond([user('cna yuo caluclate 20 percnt of 50?')],seed=1)
            self.assertTrue(answer['response'].endswith(' = 10'))
            self.assertIn('Spelling interpretation:',answer['details'])
            self.assertEqual(self.engine.respond([user('helo')],seed=1)['route'],'chat/smalltalk-greeting')

    def test_unified_multiturn_repaired_reasoning(self):
        messages=[]
        with patch('cael_unified.text_repair.active_repairer',return_value=self.model),patch.object(self.engine._facts,'respond',side_effect=AssertionError('Lookup forbidden')):
            for text in ('Facts: John wnet to the kitchen.','Add: John moved to the office.','Wher is John?','why?'):
                messages.append(user(text))
                answer=self.engine.respond(messages,seed=1)
                messages.append(assistant(answer['response']))
            self.assertEqual(answer['reasoning']['answer'],'office')

    def test_malformed_earlier_messages_are_rejected(self):
        for messages in ([None,user('hello')],[dict(role='invalid',content='bad'),user('hello')]):
            with self.assertRaises(ValueError):self.engine.respond(messages)

    def test_image_and_emoji_requests_do_not_use_the_new_repair_model(self):
        with patch('cael_unified.text_repair.repair_messages',side_effect=AssertionError('Image repair forbidden')),patch.object(self.engine,'image_reply',return_value={'route':'image/test'}),patch.object(self.engine,'emoji_reply',return_value={'route':'emoji/test'}):
            self.assertEqual(self.engine.respond([user('Make a picture of a car')],seed=1)['route'],'image/test')
            self.assertEqual(self.engine.respond([user('Make a pizza emoji')],seed=1)['route'],'emoji/test')

    def test_choice_questions_keep_their_original_wording(self):
        with patch('cael_unified.text_repair.repair_messages',side_effect=AssertionError('Choice repair forbidden')),patch.object(self.engine,'score_endings',return_value=[dict(sum_lnp=-4,tokens=2),dict(sum_lnp=-1,tokens=2)]),patch.object(self.engine,'choice_settings',return_value=None):
            answer=self.engine.respond([user('Whta follows? A) Nori is not a bird B) Nori is a bird')],seed=1)
            self.assertEqual(answer['choice'],1)


if __name__=='__main__':unittest.main()
