"""Fixtures exercise network/licence boundaries; never open private photos."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import urllib.error
from urllib.parse import parse_qs, urlparse

from cael_unified.facts import FactLookup
from cael_unified.licensing import commercial_image_licence
from cael_unified.network import Cached, LookupUnavailable, Network, ReviewedRedirect, allowed_url


class LookupTests(unittest.TestCase):
    def test_reject_noncommercial_unknown_and_misleading_image_licences(self):
        for licence in ('CC BY-NC 4.0', 'CC BY-ND 4.0', 'CC BY 4.0 non-commercial', 'free', 'PD-Art', '', None):
            self.assertFalse(commercial_image_licence(licence), licence)
        for licence in ('MIT', 'Apache-2.0', 'CC0 1.0', 'Public domain', 'CC BY 4.0', 'CC BY-SA 4.0'):
            self.assertTrue(commercial_image_licence(licence), licence)

    def test_nonreviewed_hosts_and_redirects_cannot_be_fetched(self):
        for url in ('https://api.open-meteo.com/v1/forecast', 'https://api.coingecko.com/api/v3/simple/price',
                    'https://www.thesportsdb.com/api/v1/json/123/searchteams.php', 'https://api.jolpi.ca/ergast/f1/',
                    'https://feeds.bbci.co.uk/news/rss.xml', 'https://api.duckduckgo.com/',
                    'http://en.wikipedia.org/', 'https://en.wikipedia.org.evil.test/',
                    'https://raw.githubusercontent.com/unknown/repo/main/image.png', 'https://en.wikipedia.org:bad/'):
            self.assertFalse(allowed_url(url), url)
        with self.assertRaises(LookupUnavailable):
            ReviewedRedirect().redirect_request(None, None, 302, '', {}, 'https://example.com/private')

    def test_rate_limited_provider_is_not_repeatedly_called(self):
        net = Network()
        error = urllib.error.HTTPError('https://api.met.no/test', 429, 'busy', {'Retry-After': '120'}, io.BytesIO())
        with patch.object(net.opener, 'open', side_effect=error) as open_request:
            for _ in range(2):
                with self.assertRaises(LookupUnavailable):
                    net.get('https://api.met.no/test')
            self.assertEqual(open_request.call_count, 1)

    def test_conditional_cache_reuses_not_modified_body(self):
        net = Network()
        url = 'https://api.met.no/test'
        net.cache[url] = Cached(b'cached-data', 0, 'Fri, 16 Oct 2026 00:00:00 GMT')
        error = urllib.error.HTTPError(url, 304, 'not modified', {}, io.BytesIO())
        with patch.object(net.opener, 'open', side_effect=error) as call:
            self.assertEqual(net.get(url), b'cached-data')
            request = call.call_args.args[0]
            self.assertEqual(request.get_header('If-modified-since'), net.cache[url].last_modified)
            self.assertEqual(net.get(url), b'cached-data')
            self.assertEqual(call.call_count, 1)

    def test_provider_failure_never_becomes_old_local_answer(self):
        class Offline:
            def json(self, *args, **kwargs):
                raise LookupUnavailable('offline')
        with patch('cael_unified.knowledge.KnowledgeStore.lookup', return_value=None):
            answer = FactLookup(Offline()).respond('What is a capybara?')
        self.assertEqual(answer['route'], 'chat/web-unavailable')
        self.assertFalse(answer['sources'])
        self.assertIsNone(FactLookup(Offline()).respond('hello'))
        self.assertIsNone(FactLookup(Offline()).respond('Who are you?'))

    def test_explicit_reference_search_does_not_become_weather_or_news(self):
        lookup = FactLookup()
        with patch.object(lookup.request_policy, 'parse', return_value={'intent':'weather','subject':'web fixture'}), \
             patch.object(lookup.news_policy, 'parse', return_value={'topic':'web fixture'}), \
             patch.object(lookup, 'wikipedia', return_value={'route':'chat/web-wikipedia','response':'fixture'}) as wiki, \
             patch.object(lookup, 'weather') as weather, patch.object(lookup, 'news') as news:
            for question in ('Could you search the web for a fixture animal?', 'Check the web for a fixture animal.'):
                self.assertEqual(lookup.respond(question)['route'], 'chat/web-wikipedia')
            self.assertEqual(wiki.call_count, 2)
            weather.assert_not_called()
            news.assert_not_called()

    def test_wikipedia_result_includes_source_and_sharealike_notice(self):
        class WikiFixture:
            def json(self, url, **kwargs):
                params = parse_qs(urlparse(url).query)
                if 'list' in params:
                    return {'query': {'search': [{'title': 'Fixture animal'}]}}
                return {'query': {'pages': {'1': {'title': 'Fixture animal', 'extract': 'A fictional animal for a software fixture.',
                        'fullurl': 'https://en.wikipedia.org/wiki/Fixture_animal'}}}}
        answer = FactLookup(WikiFixture()).respond('What is a fixture animal?')
        self.assertEqual(answer['route'], 'chat/web-wikipedia')
        self.assertEqual(answer['sources'][0]['licence'], 'CC BY-SA 4.0')
        self.assertIn('excerpt', answer['details'])

    def test_unrelated_top_search_hit_is_not_downloaded_or_cited(self):
        calls = []
        class WrongTopic:
            def json(self, url, **kwargs):
                calls.append(parse_qs(urlparse(url).query))
                return {'query': {'search': [{'title': 'Lava lamp', 'snippet': 'A decorative lamp with blobs of wax.'}]}}
        answer = FactLookup(WrongTopic()).wikipedia('When the light blob was invented?')
        self.assertEqual(answer['route'], 'chat/web-not-found')
        self.assertFalse(answer['sources'])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['srsearch'], ['light blob'])

    def test_search_uses_subject_and_skips_unrelated_first_hit(self):
        calls = []
        class SearchFixture:
            def json(self, url, **kwargs):
                params = parse_qs(urlparse(url).query)
                calls.append(params)
                if 'list' in params:
                    return {'query': {'search': [{'title': 'Wrong subject'}, {'title': 'Fixture animal'}]}}
                return {'query': {'pages': {'1': {'title': 'Fixture animal', 'extract': 'A fictional animal for a software fixture.'}}}}
        answer = FactLookup(SearchFixture()).wikipedia('What are fixture animals?')
        self.assertEqual(answer['route'], 'chat/web-wikipedia')
        self.assertEqual(calls[0]['srsearch'], ['fixture animals'])
        self.assertEqual(calls[1]['titles'], ['Fixture animal'])

    def test_provider_spelling_suggestion_is_checked_and_disclosed(self):
        calls = []
        class SuggestionFixture:
            def json(self, url, **kwargs):
                params = parse_qs(urlparse(url).query)
                calls.append(params)
                if params.get('srsearch') == ['pengwin']:
                    return {'query': {'search': [], 'searchinfo': {'suggestion':'penguin'}}}
                if 'list' in params:
                    return {'query': {'search': [{'title':'Penguin', 'snippet':'Penguins are flightless birds.'}]}}
                return {'query': {'pages': {'1': {'title':'Penguin', 'extract':'Penguins are flightless birds that live mainly in the Southern Hemisphere.'}}}}
        answer = FactLookup(SuggestionFixture()).wikipedia('What is a pengwin?')
        self.assertEqual(answer['route'], 'chat/web-wikipedia')
        self.assertIn('If you mean "Penguin"', answer['response'])
        self.assertEqual(calls[1]['srsearch'], ['penguin'])
        self.assertEqual(calls[2]['titles'], ['Penguin'])

    def test_far_or_multiword_provider_suggestions_are_not_assumed(self):
        for subject, suggestion in [('light blob','lava lamp'), ('planet','platinum'), ('cat','car')]:
            calls = []
            class SuggestionFixture:
                def json(self, url, **kwargs):
                    calls.append(url)
                    return {'query': {'search': [], 'searchinfo': {'suggestion':suggestion}}}
            answer = FactLookup(SuggestionFixture()).wikipedia('What is '+subject+'?')
            self.assertEqual(answer['route'], 'chat/web-not-found')
            self.assertEqual(len(calls), 1)

    def test_incumbent_lookup_discards_ended_terms_and_uses_label_fallback(self):
        def claim(person, end=None):
            return dict(rank='preferred', mainsnak={'datavalue': {'value': {'id': person}}},
                        qualifiers={'P582': [{'datavalue': {'value': {'time': end}}}]} if end else {})
        class LeaderFixture:
            def json(self, url, **kwargs):
                params = parse_qs(urlparse(url).query)
                if params.get('action') == ['wbsearchentities']:
                    return {'search': [{'id': 'Q1', 'label': 'Fixture Republic'}]}
                if params.get('ids') == ['Q1']:
                    return {'entities': {'Q1': {'labels': {'en': {'value': 'Fixture Republic'}},
                            'claims': {'P35': [claim('Q2', '+2001-01-01T00:00:00Z'), claim('Q3')]}}}}
                self_outer.assertEqual(params['languagefallback'], ['1'])
                return {'entities': {'Q3': {'labels': {'en': {'value': 'Current Fixture Leader'}}}}}
        self_outer = self
        answer = FactLookup(LeaderFixture()).respond('Who is the current president of Fixture Republic?')
        self.assertEqual(answer['route'], 'chat/web-wikidata')
        self.assertIn('Current Fixture Leader', answer['response'])

    def test_weather_uses_wikidata_and_met_with_rounded_coordinates(self):
        urls = []
        class WeatherFixture:
            def json(self, url, **kwargs):
                urls.append(url)
                params = parse_qs(urlparse(url).query)
                if params.get('action') == ['wbsearchentities']:
                    return {'search': [{'id': 'Q1', 'label': 'Fixture City'}]}
                if params.get('action') == ['wbgetentities']:
                    return {'entities': {'Q1': {'labels': {'en': {'value': 'Fixture City'}}, 'claims': {'P625': [
                        {'mainsnak': {'datavalue': {'value': {'latitude': 12.123456, 'longitude': 23.123456, 'globe': 'http://www.wikidata.org/entity/Q2'}}}}]}}}}
                return {'properties': {'timeseries': [{'time': '2099-01-01T00:00:00Z', 'data': {
                    'instant': {'details': {'air_temperature': 25, 'wind_speed': 2}},
                    'next_1_hours': {'summary': {'symbol_code': 'clearsky_day'}}}}]}}
        answer = FactLookup(WeatherFixture()).respond('Weather in Fixture City?')
        self.assertEqual(answer['route'], 'chat/web-weather')
        self.assertIn('lat=12.1235', urls[-1])
        self.assertIn('lon=23.1235', urls[-1])
        self.assertEqual([s['source'] for s in answer['sources']], ['MET Norway', 'Wikidata'])

    def test_rejected_emoji_candidates_are_never_downloaded(self):
        from cael_assistant import emoji_fetch
        rejected = dict(url='https://raw.githubusercontent.com/hfg-gmuend/openmoji/master/test.png',
                        source='fixture', licence='CC BY-NC 4.0')
        with tempfile.TemporaryDirectory() as temp, patch.object(emoji_fetch, 'ROOT', Path(temp)), \
             patch.object(emoji_fetch, 'openmoji', return_value=[rejected]), \
             patch.object(emoji_fetch, 'fluent', return_value=[]), patch.object(emoji_fetch, '_get') as download:
            self.assertEqual(emoji_fetch.fetch('fixture'), [])
            download.assert_not_called()


if __name__ == '__main__':
    unittest.main()
