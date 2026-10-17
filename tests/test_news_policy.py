"""Topic routing, short factual replies and source fallback regression checks."""
from datetime import datetime, timedelta, timezone
import unittest
from urllib.parse import parse_qs, urlparse

from cael_unified.facts import FactLookup, NewsItems
from cael_unified.network import LookupUnavailable
from cael_unified.news_policy import NewsPolicy, shorten, topical


class NewsPolicyTests(unittest.TestCase):
    def test_topic_before_after_and_without_news_keyword(self):
        policy = NewsPolicy()
        for text, topic in [('Israel news', 'israel'), ('news about Israel', 'israel'),
                            ('latest news on quantum computers', 'quantum computers'),
                            ('what is happening in Canada', 'canada'), ('New York news', 'new york')]:
            self.assertEqual(policy.parse(text)['topic'], topic, text)
        self.assertEqual(policy.parse('world news')['topic'], '')

    def test_creative_code_and_definition_requests_do_not_fetch_news(self):
        policy = NewsPolicy()
        for text in ('write a news article about France', 'write python code to fetch news for Israel',
                     'create a newsletter about Canada', 'what does news mean', 'who are you'):
            self.assertIsNone(policy.parse(text), text)

    def test_shortening_preserves_complete_sentences_when_possible(self):
        self.assertEqual(shorten('A short first sentence. A much longer second sentence that does not fit.', words=6), 'A short first sentence.')
        self.assertLessEqual(len(shorten('word ' * 100, words=55).split()), 55)
        self.assertEqual(shorten('Dr. Smith finds an object from c. 8000 BC. Another sentence.', sentences=1),
                         'Dr. Smith finds an object from c. 8000 BC.')

    def test_topic_matching_does_not_use_substrings(self):
        self.assertFalse(topical('A chair factory announces new furniture', 'ai'))
        self.assertTrue(topical('Artificial intelligence chip announced', 'ai'))
        self.assertFalse(topical('Football result announced in Brazil', 'quantum computers'))
        self.assertTrue(topical('A new quantum computer was unveiled today', 'quantum computers'))
        self.assertTrue(topical("Canada's parliament announces a vote", 'Canada'))

    def test_parser_returns_leaf_stories_not_unrelated_group_headings(self):
        parser = NewsItems()
        parser.feed('<div id="2026_October_16"><ul><li>Group heading<ul><li>First complete leaf story.</li><li>Second leaf.</li></ul></li></ul></div>')
        self.assertEqual(parser.items, ['First complete leaf story.', 'Second leaf.'])
        self.assertEqual(parser.dated_items[0][0].isoformat(), '2026-10-16')

    def test_failed_topic_feed_falls_back_only_to_matching_recent_dated_items(self):
        today = datetime.now(timezone.utc).date()
        stale = today - timedelta(days=20)
        marker = today.strftime('%Y_%B_') + str(today.day)
        old_marker = stale.strftime('%Y_%B_') + str(stale.day)
        markup = (f'<div id="{old_marker}"><ul><li>Israel announces an old unrelated policy that should never appear as recent news.</li></ul></div>'
                  f'<div id="{marker}"><ul><li>Space group<ul>'
                  '<li>Canadian researchers launch a new telescope to study distant galaxies and stars.</li>'
                  '<li>Israel announces a new public research programme for universities across the country.</li>'
                  '</ul></li></ul></div>')
        class FeedFixture:
            def json(self, url, **kwargs):
                if urlparse(url).hostname == 'api.gdeltproject.org':
                    raise LookupUnavailable('fixture outage')
                return {'parse': {'text': {'*': markup}}}
        reply = FactLookup(FeedFixture()).respond('Israel news')
        self.assertEqual(reply['route'], 'chat/web-news-wikipedia-topic')
        self.assertIn('public research', reply['response'])
        self.assertNotIn('telescope', reply['response'])
        self.assertNotIn('old unrelated policy', reply['response'])
        self.assertLessEqual(len(reply['response'].split()), 75)

    def test_followup_uses_only_this_conversations_news_context(self):
        class FeedFixture:
            def json(self, url, **kwargs):
                params = parse_qs(urlparse(url).query)
                if urlparse(url).hostname == 'api.gdeltproject.org':
                    self_outer.assertEqual(params['query'], ['canada sourcelang:english'])
                    return {'articles': [{'title': 'Canada announces a research grant', 'url': 'https://example.com/fixture'}]}
                raise AssertionError('Unexpected provider')
        self_outer = self
        messages = [dict(role='user', content='Israel news'), dict(role='assistant', content='Fixture reply'),
                    dict(role='user', content='What about Canada?')]
        reply = FactLookup(FeedFixture()).respond(messages[-1]['content'], messages=messages)
        self.assertIn('Canada announces', reply['response'])
