"""Authored temporal routing/evidence cases, including whole unified replies."""
from datetime import datetime, timezone
import sqlite3
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from cael_unified.assistant import Assistant
from cael_unified.facts import FactLookup
from cael_unified.knowledge import KnowledgeStore, SCHEMA, add_document
from cael_unified.news_policy import NewsPolicy
from cael_unified.news_time import historical_question, historical_excerpt, unsupported_period
from tests.test_knowledge import NoInternet, record


class NewsTimeTests(unittest.TestCase):
    def test_explicit_unsupported_dates_are_not_recent(self):
        policy = NewsPolicy()
        for scope in ('in 1867', 'on 2020-01-03', 'last year', 'last month', 'last week',
                      'next week', 'tomorrow', 'in January', 'on Monday', 'two years ago',
                      'last 24 hours', 'past 30 days', 'during the 19th century', 'this year'):
            with self.subTest(scope=scope):
                parsed = policy.parse('Canada news ' + scope)
                self.assertEqual(parsed['period'], 'unsupported')
                self.assertTrue(parsed['requested_period'])

    def test_recent_requests_and_numeric_topic_names_stay_eligible(self):
        policy = NewsPolicy()
        for text in ('Recent COVID-19 news', 'Latest news on Windows 2000', 'Boeing 747 news',
                     'News about the 2024 election', 'What is happening in Canada?',
                     'Canada news this week', 'Canada news past week', 'Canada news past 7 days'):
            with self.subTest(text=text):
                parsed = policy.parse(text)
                self.assertIsNotNone(parsed)
                self.assertEqual(parsed['period'], 'recent')
        self.assertEqual(policy.parse('Canada news yesterday')['period'], 'yesterday')
        self.assertEqual(policy.parse('Canada news today')['period'], 'today')
        self.assertEqual(policy.parse('Canada news past 7 days')['topic'], 'canada')
        self.assertEqual(policy.parse('Canada news past week and next month')['period'], 'unsupported')
        self.assertEqual(policy.parse('Explain the news in Canada')['period'], 'recent')
        self.assertEqual(policy.parse('What is the news in Canada today?')['period'], 'today')

    def test_creative_personal_and_definition_frames_are_not_date_news(self):
        policy = NewsPolicy()
        for text in ('Write a news article set in 1867', 'Create headlines for my story in 1867',
                     'What does news mean in 1867?', 'Explain the news in my story', 'My news tomorrow'):
            with self.subTest(text=text):
                self.assertIsNone(policy.parse(text))

    def test_history_parser_does_not_make_current_or_future_years_static(self):
        now = datetime(2026, 10, 18, tzinfo=timezone.utc)
        self.assertEqual(historical_question('What happened in Canada in 1867?', now)['subject'], 'Canada')
        self.assertEqual(historical_question('What happened in 1867 in Canada?', now)['year'], '1867')
        for text in ('What happened in Canada in 2026?', 'What happened in Canada in 2030?',
                     'What happened in my story in 1867?', 'What happened in Canada in 1867 and 1868?'):
            self.assertIsNone(historical_question(text, now))
        self.assertIsNone(historical_question('What happened in stock prices in 2025?', now))

    def test_historical_excerpt_needs_event_time_and_topic(self):
        parsed = historical_question('What happened in Asteria in 1847?')
        def row(body): return dict(body=body, heading='History', position=1)
        for body in ('Asteria has a wide river and many towns. Its history began long ago.',
                     'A book about Asteria was published in 1847 by a local author.',
                     'Asteria had a bridge by 1847, but the year of its construction is unknown.',
                     'Asteria had a settlement in 1847 BC that was later abandoned.',
                     'Belora built a bridge in 1847, long after a treaty with Asteria in 1832.',
                     'Asteria fought a war from 1845 to 1847 with a neighboring state.'):
            with self.subTest(body=body):
                # A sentence can mention both a different dated event and the
                # topic. Multiple-year sentences need conservative refusal too.
                self.assertIsNone(historical_excerpt([row(body)], parsed, 'Asteria'))
        body = 'Asteria built a stone bridge in 1847 to connect its two river districts.'
        self.assertEqual(historical_excerpt([row(body)], parsed, 'Asteria')[0], body)
        body = 'Asteria signed a peace treaty in 1847 and remained under occupation until 1852.'
        self.assertEqual(historical_excerpt([row(body)], parsed, 'Asteria')[0], body)


class UnifiedHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.path = root / 'knowledge.sqlite'
        with sqlite3.connect(self.path) as connection:
            connection.executescript(SCHEMA)
            add_document(connection, record('Asteria', 101, [
                'Asteria is a fictional country used only in authored software tests. It has several river towns.',
                'Asteria built a stone bridge in 1847 to connect its two river districts.',
                'Asteria opened its library in 1861 with books donated by local residents.']))
        connection.close()
        self.net = NoInternet()
        self.store = KnowledgeStore(self.path, root / 'online.sqlite')
        self.lookup = FactLookup(self.net)
        self.lookup.knowledge = self.store
        self.assistant = Assistant(output_root=root / 'outputs')
        self.assistant._facts = self.lookup

    def tearDown(self):
        for connection in getattr(self.store.local, 'connections', {}).values():
            connection.close()
        self.temp.cleanup()

    def ask(self, text, history=None):
        return self.assistant.respond((history or []) + [dict(role='user', content=text)], n=1, seed=48)

    def test_unified_historical_answer_has_the_requested_year_and_source(self):
        with patch.object(self.lookup, 'news', side_effect=AssertionError('Recent news for historical question')), \
             patch.object(self.lookup, 'weather', side_effect=AssertionError('Weather for historical question')):
            for text in ('What happened in Asteria in 1847?', 'What happened in 1847 in Asteria?'):
                answer = self.ask(text)
                self.assertEqual(answer['route'], 'chat/local-knowledge')
                self.assertIn('stone bridge in 1847', answer['response'])
                self.assertNotIn('fictional country', answer['response'])
                self.assertEqual(answer['sources'][0]['licence'], 'CC BY-SA 4.0')
                self.assertIn('not a complete history', answer['details'])
        self.assertEqual(self.net.calls, 0)

    def test_unverified_year_does_not_return_intro_weather_or_current_news(self):
        with patch.object(self.lookup, 'news', side_effect=AssertionError('Recent news')), \
             patch.object(self.lookup, 'weather', side_effect=AssertionError('Weather')):
            answer = self.ask('What happened in Asteria in 1849?')
        self.assertEqual(answer['route'], 'chat/web-unavailable')
        self.assertIn('historical event', answer['response'])
        self.assertFalse(answer['sources'])
        self.assertEqual(self.net.calls, 1)

    def test_unsupported_news_range_precedes_wrong_classifier_predictions(self):
        for intent in ('weather', 'faq', 'sports', 'other'):
            with patch.object(self.lookup.request_policy, 'parse', return_value=dict(intent=intent, subject='fixture')), \
                 patch.object(self.lookup, 'weather', side_effect=AssertionError('Wrong weather')):
                for text in ('Canada news in 1867', 'What happened in Canada last year?',
                             'News about Canada last month', 'Canada news tomorrow'):
                    answer = self.ask(text)
                    self.assertEqual(answer['route'], 'chat/web-unsupported-news-period')
                    self.assertIn('cannot verify news', answer['response'])
                    self.assertFalse(answer['sources'])
                    self.assertNotIn('news for in', answer['response'])
                    self.assertNotIn('Retrieved', answer['details'])
        self.assertEqual(self.net.calls, 0)

    def test_news_topic_followup_preserves_date_scope(self):
        history = [dict(role='user', content='Canada news yesterday'), dict(role='assistant', content='A dated fixture digest.')]
        with patch.object(self.lookup, 'news', return_value=dict(route='chat/web-news', response='Fixture.', sources=[])) as news:
            self.ask('What about Japan?', history)
            self.assertEqual(news.call_args.args[1]['period'], 'yesterday')
            self.ask('What about Japan today?', history)
            self.assertEqual(news.call_args.args[1]['period'], 'today')
            self.assertEqual(news.call_args.args[1]['topic'], 'japan')
            self.ask('What about today?', history)
            self.assertEqual(news.call_args.args[1]['topic'], 'canada')
        answer = self.ask('What about Japan in 1945?', history)
        self.assertEqual(answer['route'], 'chat/web-unsupported-news-period')
        history[0]['content'] = 'Canada news last year'
        answer = self.ask('What about Japan?', history)
        self.assertEqual(answer['route'], 'chat/web-unsupported-news-period')
        self.assertEqual(self.net.calls, 0)

    def test_direct_news_call_cannot_replace_an_explicit_date_with_recent(self):
        answer = self.lookup.news('Canada news in 1867', dict(topic='Canada', period='recent'))
        self.assertEqual(answer['route'], 'chat/web-unsupported-news-period')
        self.assertEqual(self.net.calls, 0)


if __name__ == '__main__':
    unittest.main()
