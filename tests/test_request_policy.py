"""Public request fixtures; no images or private data."""
import unittest
from unittest.mock import patch
from cael_unified.facts import FactLookup
from cael_unified.request_policy import RequestPolicy


class RequestPolicyTests(unittest.TestCase):
    def test_weather_locations_and_definition_separation(self):
        policy = RequestPolicy()
        for text, city in [('Paris weather', 'paris'), ('will it rain in Cape Town tonight', 'cape town'),
                           ('Tel Aviv forecast please', 'tel aviv'), ('wind in Sydney today', 'sydney')]:
            actual = policy.parse(text)
            self.assertEqual((actual['intent'], actual['subject']), ('weather', city))
        self.assertNotEqual(policy.parse('what does weather mean')['intent'], 'weather')

    def test_live_sports_never_falls_back_to_encyclopedia(self):
        lookup = FactLookup()
        with patch.object(lookup, 'wikipedia') as encyclopedia, patch.object(lookup, 'news') as news:
            for text in ['Liverpool fixtures tomorrow', 'who won the Celtics game', 'what was the Chelsea score', 'hockey league standings']:
                self.assertEqual(lookup.respond(text)['route'], 'chat/web-unsupported-sports')
            encyclopedia.assert_not_called()
            news.assert_not_called()

    def test_sports_topic_is_preserved_in_news(self):
        lookup = FactLookup()
        with patch.object(lookup, 'news', return_value={'response': 'fixture'}) as news:
            lookup.respond('show me recent hockey updates')
            self.assertEqual(news.call_args.args[1]['topic'], 'hockey')

    def test_capital_discards_ended_and_deprecated_claims(self):
        lookup = FactLookup()
        claim = lambda qid, **extra: dict(mainsnak={'datavalue': {'value': {'id': qid}}}, **extra)
        entity = {'labels': {'en': {'value': 'Fixture Republic'}}, 'claims': {'P36': [
            claim('Q2', rank='normal', qualifiers={'P582': [{}]}), claim('Q3', rank='deprecated'), claim('Q4', rank='preferred')]}}
        with patch.object(lookup, 'entity_search', return_value=[{'id': 'Q1'}]), \
             patch.object(lookup, 'entities', side_effect=[{'Q1': entity}, {'Q4': {'labels': {'en': {'value': 'Fixture City'}}}}]):
            answer = lookup.respond('What is the capital of Fixture Republic?')
        self.assertEqual(answer['response'], 'The capital of Fixture Republic is Fixture City.')
        self.assertEqual(answer['sources'][0]['licence'], 'CC0 1.0')

    def test_population_requires_date_and_reports_it(self):
        lookup = FactLookup()
        claim = {'rank': 'normal', 'mainsnak': {'datavalue': {'value': {'amount': '+12345'}}}}
        entity = {'labels': {'en': {'value': 'Fixture Republic'}}, 'claims': {'P1082': [claim]}}
        with patch.object(lookup, 'entity_search', return_value=[{'id': 'Q1'}]), patch.object(lookup, 'entities', return_value={'Q1': entity}):
            self.assertIsNone(lookup.structured_faq('population of Fixture Republic'))
            claim['qualifiers'] = {'P585': [{'datavalue': {'value': {'time': '+2020-01-01T00:00:00Z', 'precision': 11}}}]}
            answer = lookup.structured_faq('population of Fixture Republic')
            self.assertIn('12,345', answer['response'])
            self.assertIn('2020-01-01', answer['response'])


if __name__ == '__main__':
    unittest.main()
