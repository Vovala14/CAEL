"""Regressions from a real conversation on the shared worker (2026-10-17)."""
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from cael_unified.facts import FactLookup, describe_symbol
from cael_unified.memory import facts, recall
from cael_unified.smalltalk import reply


def chat(*user_turns):
    messages = []
    for text in user_turns:
        messages += [dict(role='user', content=text), dict(role='assistant', content='Okay.')]
    return messages[:-1]


class SmalltalkAndMemoryTests(unittest.TestCase):
    def test_contractions_without_apostrophes(self):
        self.assertEqual(reply(chat('whats your name?'))['route'], 'chat/smalltalk-identity')

    def test_what_else_can_you_do_lists_capabilities(self):
        self.assertIn('Python', reply(chat('what else can you do?'))['response'])

    def test_profanity_gets_a_calm_reply_not_an_empathy_reaction(self):
        self.assertEqual(reply(chat('fat fuck'))['route'], 'chat/smalltalk-profanity')
        self.assertIsNone(reply(chat('I got a new job!')))

    def test_place_is_the_name_not_the_description(self):
        self.assertEqual(facts(chat('i live in a shity country named israel'))['attributes']['home'], 'Israel')
        self.assertEqual(facts(chat('I live in New York'))['attributes']['home'], 'New York')

    def test_likes_recalled_for_other_phrasings(self):
        history = chat('i like black jack and hookers')
        for question in ('and what i like to do?', 'what are my hobbies?'):
            answer = recall(history + [dict(role='user', content=question)])
            self.assertEqual(answer['response'], 'You told me you like black jack and hookers.', question)

    def test_learning_requests_are_taught_not_deflected(self):
        # Requests the explainer can teach are left to it (None here), not answered with suggestions.
        self.assertIsNone(reply(chat('I want to learn how to play chess')))
        self.assertIsNone(reply(chat('teach me to cook pasta')))
        followup = reply(chat('I want to learn how to play chess', 'Can you help me?'))
        self.assertIn('about chess', followup['response'])
        self.assertEqual(reply(chat('Can you help me?'))['response'], 'Of course! What do you need help with?')
        explained = [dict(role='user', content='I want to learn how to play chess'),
                     dict(role='assistant', content='Chess rules.\n\nInitial setup:\nx\n\nCheck:\ny\n\nCheckmate:\nz'),
                     dict(role='user', content='Can you help me?')]
        self.assertIn('Check or Checkmate', reply(explained)['response'])

    def test_unknown_name_question_is_grammatical(self):
        self.assertIn("your dog's name", recall(chat('what is my dog name?'))['response'])


class Provider:
    """Wikipedia/MET fixture: records requests, answers from small canned payloads."""

    def __init__(self):
        self.calls = []

    def json(self, url, **kwargs):
        params = parse_qs(urlparse(url).query)
        self.calls.append(params)
        if 'met.no' in url:
            time = (datetime.now(timezone.utc) + timedelta(days=1, hours=1)).strftime('%Y-%m-%dT%H:00:00Z')
            return {'properties': {'timeseries': [{'time': time, 'data': {
                'instant': {'details': {'air_temperature': 24.0, 'wind_speed': 3.0}},
                'next_1_hours': {'summary': {'symbol_code': 'clearsky_day'}}}}]}}
        if params.get('list') == ['search']:
            return {'query': {'search': [{'title': 'Megadeth', 'snippet': 'American heavy metal band'},
                                         {'title': 'Alien Zombie Megadeath', 'snippet': 'video game'}],
                              'searchinfo': {'suggestion': 'megadeth'}}}
        raise AssertionError('unexpected request ' + url)


class LookupFixTests(unittest.TestCase):
    def test_close_spelling_with_matching_top_title_is_used(self):
        provider = Provider()
        lookup = FactLookup(provider)
        with patch.object(lookup.knowledge, 'remember'), patch.object(lookup.knowledge, 'lookup', return_value=None):
            try:
                lookup.wikipedia('what year megadeath was formed?')
            except AssertionError:
                pass  # the page fetch is outside this fixture; the chosen title is what matters
        self.assertTrue(any(c.get('titles') == ['Megadeth'] for c in provider.calls), provider.calls)

    def test_weather_without_a_place_uses_where_the_user_lives(self):
        lookup = FactLookup(Provider())
        with patch.object(lookup, 'place', return_value=('Israel', 31.4, 35.0, 'Q801')) as place:
            answer = lookup.weather('can you check the weather for tommorow?', chat('i live in a shity country named israel', 'x'))
        place.assert_called_once_with('Israel')
        self.assertIn('You told me you live in Israel', answer['response'])
        self.assertIn('clear sky', answer['response'])

    def test_weather_asks_for_a_city_instead_of_failing(self):
        lookup = FactLookup(Provider())
        self.assertEqual(lookup.weather('can you check the weather for tommorow?')['response'], 'Which city should I check the weather for?')
        with patch.object(lookup, 'place', side_effect=__import__('cael_unified.network', fromlist=['LookupUnavailable']).LookupUnavailable('none')):
            self.assertIn('Which city', lookup.weather('weather in Qwxyzville')['response'])

    def test_symbol_codes_are_readable(self):
        self.assertEqual(describe_symbol('lightrainshowers_day'), 'light rain showers')


if __name__ == '__main__':
    unittest.main()
