"""Conversation-scoped public subjects; current answers still need evidence."""
import unittest
from unittest.mock import patch

from cael_unified.factual_context import resolve,topic_from_history
from cael_unified.knowledge_query import KnowledgeQuery,static_allowed
from cael_unified.facts import FactLookup
from cael_unified.knowledge_time import temporal_excerpt


def user(text):return dict(role='user',content=text)
def bot(text='A sourced answer.'):return dict(role='assistant',content=text)


class ContextTests(unittest.TestCase):
    def setUp(self):self.policy=KnowledgeQuery()

    def test_chain_keeps_the_original_subject(self):
        messages=[user('Tell me about Metallica'),bot(),user('When was it formed?'),bot(),user('Who formed it?')]
        question,context=resolve(messages[-1]['content'],messages,self.policy)
        self.assertEqual(context['subject'],'Metallica')
        self.assertEqual(question,'Who formed Metallica?')
        self.assertEqual(self.policy.parse(question)['focus'],'agent')

    def test_topic_switch_ack_and_personal_turn_breaks(self):
        messages=[user('What is photosynthesis?'),bot(),user('Tell me about Metallica'),bot(),user('Thanks!'),bot(),user('When was it formed?')]
        self.assertEqual(resolve(messages[-1]['content'],messages,self.policy)[1]['subject'],'Metallica')
        for interruption in ('I live in Paris','My password is not public','Facts: Mira went to the kitchen.',
                             'Hello','Write a Python function','What is my name?','Who are you?'):
            history=messages[:-1]+[user(interruption),bot(),user('When was it formed?')]
            with self.subTest(interruption=interruption):self.assertIsNone(resolve(history[-1]['content'],history,self.policy)[1])

    def test_no_session_state_comparison_binding_or_deictic_noun_rewrite(self):
        self.assertIsNone(resolve('When was it formed?',[user('When was it formed?')],self.policy)[1])
        history=[user('Compare Venus and Mars'),bot(),user('How big is it?')]
        self.assertIsNone(resolve(history[-1]['content'],history,self.policy)[1])
        history=[user('What is photosynthesis?'),bot(),user('What is this book about?')]
        self.assertEqual(resolve(history[-1]['content'],history,self.policy),(history[-1]['content'],None))

    def test_possessive_does_not_disable_freshness(self):
        history=[user('Tell me about Acme'),bot(),user('Who is its current CEO?')]
        question,context=resolve(history[-1]['content'],history,self.policy)
        self.assertEqual(context['subject'],'Acme')
        self.assertEqual(question,"Who is Acme's current CEO?")
        self.assertFalse(static_allowed(question))

    def test_weather_news_and_explicit_new_subject_are_not_rewritten(self):
        for question in ('What about Paris?','What is the weather in Paris?','Who formed Megadeth?',
                         'What is this year’s forecast?','Tell me a story about it',
                         'What does the word it mean?', 'Who wrote "It"?', 'What is `it`?',
                         'What is IT?', 'Who wrote It?'):
            history=[user('Tell me about Metallica'),bot(),user(question)]
            self.assertEqual(resolve(question,history,self.policy),(question,None))


class LookupTests(unittest.TestCase):
    def test_unbound_pronoun_asks_for_a_topic_without_network(self):
        lookup=FactLookup()
        with patch.object(lookup,'_respond',side_effect=AssertionError('Unbound subject lookup')):
            self.assertEqual(lookup.respond('What is it?')['route'],'chat/factual-clarify')

    def test_who_question_needs_an_agent_not_only_an_event_date(self):
        parsed=dict(kind='time',event='formed',focus='agent',original='Who formed Acme?')
        def paragraph(body):return dict(body=body,heading='Introduction',position=0)
        self.assertIsNone(temporal_excerpt([paragraph('Acme was formed in 1981.')],parsed,'Acme'))
        self.assertIsNotNone(temporal_excerpt([paragraph('Acme was formed in 1981 by Nori and Mira.')],parsed,'Acme'))
        self.assertIsNotNone(temporal_excerpt([paragraph('Nori and Mira formed Acme in 1981.')],parsed,'Acme'))

    def test_resolved_question_reaches_current_lookup_with_disclosure(self):
        lookup=FactLookup()
        history=[user('Tell me about Metallica'),bot(),user('When was it formed?'),bot(),user('Who formed it?')]
        with patch.object(lookup.knowledge,'lookup',return_value=None),patch.object(lookup,'_respond',return_value=dict(route='chat/local-knowledge',response='Fixture evidence.',details='Source fixture.',sources=[])) as call:
            answer=lookup.respond(history[-1]['content'],history)
        self.assertEqual(call.call_args[0][0],'Who formed Metallica?')
        self.assertIn('Follow-up topic from this chat: Metallica',answer['details'])

    def test_mechanism_request_is_resolved_before_explainer_fetch(self):
        lookup=FactLookup();history=[user('What is photosynthesis?'),bot(),user('How does it work?')]
        with patch.object(lookup.knowledge,'lookup',return_value=None),patch.object(lookup,'explain',return_value=dict(route='chat/web-explain',response='Fixture explanation.',sources=[])) as explain:
            answer=lookup.respond(history[-1]['content'],history)
        self.assertEqual(explain.call_args[0][0]['subject'],'photosynthesis')
        self.assertEqual(answer['route'],'chat/web-explain')

    def test_dynamic_followup_skips_static_local_snapshot(self):
        lookup=FactLookup();history=[user('Tell me about Acme'),bot(),user('Who is its current CEO?')]
        with patch.object(lookup.knowledge,'lookup',side_effect=AssertionError('Stale local lookup')),patch.object(lookup,'structured_faq',return_value=None),patch.object(lookup,'leader',return_value=None),patch.object(lookup,'wikipedia',return_value=dict(route='chat/web-unavailable',response='Could not verify the current answer.',sources=[])) as remote:
            answer=lookup.respond(history[-1]['content'],history)
        self.assertIn('Acme',remote.call_args[0][0])
        self.assertEqual(answer['route'],'chat/web-unavailable')


if __name__=='__main__':unittest.main()
