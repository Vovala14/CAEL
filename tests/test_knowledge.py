"""Offline local-memory, freshness and persistent public-text fixtures."""
from datetime import datetime, timedelta, timezone
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from cael_unified.facts import FactLookup
from cael_unified.knowledge import KnowledgeStore, SCHEMA, add_document
from cael_unified.knowledge_html import ArticleText
from cael_unified.knowledge_query import KnowledgeQuery, static_allowed
from cael_unified.network import LookupUnavailable


class NoInternet:
    def __init__(self):
        self.calls = 0

    def json(self, *args, **kwargs):
        self.calls += 1
        raise LookupUnavailable('offline fixture')


def record(title, pageid, paragraphs, heading='Introduction'):
    return dict(title=title, pageid=pageid, revision=1000 + pageid, revision_time='2020-01-01T00:00:00Z',
                retrieved_at=datetime.now(timezone.utc).isoformat(), url='https://en.wikipedia.org/w/index.php?oldid=' + str(1000 + pageid),
                sections=[dict(heading=heading, paragraphs=paragraphs)], licence='CC BY-SA 4.0')


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / 'knowledge.sqlite'
        with sqlite3.connect(self.path) as connection:
            connection.executescript(SCHEMA)
            add_document(connection, record('Photosynthesis', 1, [
                'Photosynthesis converts light energy into chemical energy in plants. This process uses sunlight to produce food for the plant.',
                'Some plants grow in deserts and some plants grow in forests. Their environments vary between different regions of the world.']))
            add_document(connection, record('Mercury (planet)', 2, ['Mercury is a planet in the Solar System and orbits closest to the Sun. It has a rocky surface and almost no atmosphere.']))
            add_document(connection, record('Mercury (element)', 3, ['Mercury is a chemical element that is liquid near room temperature. It is a metal with a silvery appearance.']))
            add_document(connection, record('Bicycle', 4, ['Bicycles can be categorized by function and construction. Examples include racing bikes, mountain bikes and utility bicycles.']))
        connection.close()
        self.store = KnowledgeStore(self.path, self.root / 'online.sqlite')
        self.policy = KnowledgeQuery()

    def tearDown(self):
        for connection in getattr(self.store.local, 'connections', {}).values():
            connection.close()
        self.temp.cleanup()

    def test_stable_answers_need_no_network_and_keep_credits(self):
        network = NoInternet()
        lookup = FactLookup(network)
        lookup.knowledge = self.store
        answer = lookup.respond('What is photosynthesis?')
        self.assertEqual(answer['route'], 'chat/local-knowledge')
        self.assertEqual(network.calls, 0)
        self.assertIn('converts light', answer['response'])
        self.assertEqual(answer['sources'][0]['licence'], 'CC BY-SA 4.0')
        self.assertIn('oldid=', answer['sources'][0]['url'])

    def test_polite_factual_requests_use_local_evidence_before_the_web(self):
        network = NoInternet()
        lookup = FactLookup(network)
        lookup.knowledge = self.store
        for question in ('Could you explain photosynthesis?', 'Can you tell me about photosynthesis?',
                         'Do you know what photosynthesis is?', 'Tell me what photosynthesis is.',
                         "I'd like to know what photosynthesis is.", 'Please define photosynthesis.'):
            with self.subTest(question=question):
                answer = lookup.respond(question)
                self.assertIsNotNone(answer)
                self.assertEqual(answer['route'], 'chat/local-knowledge')
                self.assertIn('converts light', answer['response'])
        self.assertEqual(network.calls, 0)

    def test_polite_unknown_requests_fetch_and_do_not_guess_when_offline(self):
        network = NoInternet()
        lookup = FactLookup(network)
        lookup.knowledge = self.store
        for question in ('Could you explain a pangolin?', 'Do you know what a pangolin is?',
                         'Tell me about pangolins.'):
            with self.subTest(question=question):
                answer = lookup.respond(question)
                self.assertEqual(answer['route'], 'chat/web-unavailable')
                self.assertFalse(answer['sources'])
        self.assertEqual(network.calls, 3)

    def test_request_frames_do_not_send_personal_or_creative_queries_to_lookup(self):
        network = NoInternet()
        lookup = FactLookup(network)
        lookup.knowledge = self.store
        for question in ('Could you explain my account?', 'Do you know where I live?',
                         'Who are you?', 'Please write a story about photosynthesis.'):
            self.assertIsNone(lookup.respond(question), question)
        self.assertEqual(network.calls, 0)

    def test_general_why_question_is_not_reported_as_live_sports(self):
        lookup = FactLookup(NoInternet())
        lookup.knowledge = self.store
        answer = lookup.respond('Why is the sky blue?')
        self.assertNotEqual(answer['route'], 'chat/web-unsupported-sports')

    def test_unknown_subject_does_not_return_nearby_topic(self):
        self.assertIsNone(self.store.lookup(self.policy.parse('What is flarblequux photosynthesis?')))

    def test_ambiguous_alias_requests_clarification(self):
        answer = self.store.lookup(self.policy.parse('What is Mercury?'))
        self.assertEqual(answer['route'], 'chat/local-knowledge-ambiguous')
        self.assertIn('Mercury (planet)', answer['response'])
        self.assertIn('Mercury (element)', answer['response'])

    def test_category_list_is_not_a_mechanism(self):
        self.assertIsNone(self.store.lookup(self.policy.parse('How does a bicycle work?')))

    def test_current_explicit_web_and_guidance_bypass_snapshot(self):
        for question in ['What is the latest Python version?', 'Who is the current president of France?',
                         'Search the web for photosynthesis', 'What medicine treats a fever?']:
            self.assertFalse(static_allowed(question), question)
            parsed = self.policy.parse(question)
            self.assertIsNone(self.store.lookup(parsed))
        self.assertTrue(static_allowed('How does the internet work?'))

    def test_followup_uses_only_this_conversation(self):
        network = NoInternet()
        lookup = FactLookup(network)
        lookup.knowledge = self.store
        messages = [dict(role='user', content='What is photosynthesis?'), dict(role='assistant', content='A fixture response'),
                    dict(role='user', content='How does it work?')]
        answer = lookup.respond(messages[-1]['content'], messages)
        self.assertEqual(answer['route'], 'chat/local-knowledge')
        self.assertEqual(answer['knowledge']['title'], 'Photosynthesis')
        self.assertEqual(network.calls, 0)

    def test_public_reference_persists_and_expired_reference_is_ignored(self):
        item = record('An obscure reference', 15, ['An obscure reference is an invented public reference for testing the persistent knowledge store. It contains no private information.'])
        self.store.remember(item)
        self.assertIsNotNone(self.store.lookup(self.policy.parse('What is an obscure reference?')))
        item['retrieved_at'] = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        self.store.remember(item)
        self.assertIsNone(self.store.lookup(self.policy.parse('What is an obscure reference?')))

    def test_refresh_prefers_new_public_text_over_frozen_snapshot(self):
        item = record('Photosynthesis', 1, ['Photosynthesis converts light into stored chemical energy. This refreshed public-source fixture replaces the earlier frozen reference text.'])
        self.store.remember(item)
        answer = self.store.lookup(self.policy.parse('What is photosynthesis?'))
        self.assertIn('refreshed public-source fixture', answer['response'])

    def test_article_parser_ignores_scripts_images_and_references(self):
        parser = ArticleText()
        parser.feed('<p>A public fixture definition describes a process that turns sunlight into stored energy for plants.<sup>SECRET REF</sup>'
                    '<img src="https://invalid.test/photo.jpg"></p><script>SECRET SCRIPT</script>'
                    '<h2>Mechanism</h2><p>The process converts one type of energy into another using a chemical reaction within the organism.</p>')
        text = json.dumps(parser.sections)
        self.assertNotIn('SECRET', text)
        self.assertNotIn('photo.jpg', text)
        self.assertEqual(parser.sections[1]['heading'], 'Mechanism')

    def test_causal_question_rejects_incidental_historical_cause(self):
        with sqlite3.connect(self.path) as connection:
            add_document(connection, record('Earthquake', 25, [
                'The earthquake was a historical disaster that destroyed many settlements and changed the history of an entire region for generations. Years later many residents died due to famine.',
                'Earthquakes are caused by a sudden release of energy in the lithosphere. This release creates seismic waves that shake the ground.']))
        connection.close()
        answer = self.store.lookup(self.policy.parse('Why do earthquakes happen?'))
        self.assertIn('release of energy', answer['response'])
        self.assertNotIn('famine', answer['response'])

    def test_damaged_source_excerpt_is_not_presented_as_an_answer(self):
        with sqlite3.connect(self.path) as connection:
            add_document(connection, record('Damaged reference', 26, [
                'A damaged reference (with missing markup is a public test passage that lost part of its source formatting and should be rejected.']))
        connection.close()
        self.assertIsNone(self.store.lookup(self.policy.parse('What is a damaged reference?')))

    def add_invention_fixtures(self):
        with closing(sqlite3.connect(self.path)) as connection, connection:
            add_document(connection, record('Incandescent light bulb', 30, [
                'Earlier inventors of incandescent lamps contributed prior to Joseph Swan and Thomas Edison.',
                'Thomas Edison studied a practical incandescent lamp in 1878. The first successful test was in 1879, and it lasted over thirteen hours.'], 'History'))
            add_document(connection, record('Telephone', 31, [
                'In 1876, Alexander Graham Bell was the first to be granted a patent for a device that reproduced intelligible speech.']))
            add_document(connection, record('Bicycle', 4, [
                'The bicycle was invented in Europe in the 19th century. Later generations developed numerous specialized designs for racing and everyday transport.']))

    def test_declarative_invention_question_and_real_word_typo_stay_on_subject(self):
        self.add_invention_fixtures()
        network = NoInternet()
        lookup = FactLookup(network)
        lookup.knowledge = self.store
        answer = lookup.respond('When the light blob was invented?')
        self.assertEqual(answer['route'], 'chat/local-knowledge')
        self.assertEqual(answer['knowledge']['title'], 'Incandescent light bulb')
        self.assertIn('If you mean "light bulb"', answer['response'])
        self.assertIn('1879', answer['response'])
        self.assertIn('Earlier inventors', answer['response'])
        self.assertEqual(network.calls, 0)

    def test_temporal_frames_do_not_become_subject_terms(self):
        for text in ['When was the light bulb invented?', 'When the light bulb was invented?',
                     'When light bulb was invented?', 'Who invented the light bulb?']:
            parsed = self.policy.parse(text)
            self.assertEqual(parsed['subject'], 'light bulb', text)
            self.assertEqual(parsed['terms'], ['light', 'bulb'], text)
            self.assertEqual(parsed['event'], 'invented', text)

    def test_conversational_overviews_keep_only_the_requested_topic(self):
        for text, subject in [
            ('Metallica band , what do you know about it', 'Metallica band'),
            ('Saturn, what can you tell me about it?', 'Saturn'),
            ('What do you know about photosynthesis?', 'photosynthesis'),
            ('What can you tell me about a pangolin?', 'pangolin'),
            ('Tell me something about photosynthesis.', 'photosynthesis')]:
            parsed = self.policy.parse(text)
            self.assertIsNotNone(parsed, text)
            self.assertEqual(parsed['subject'], subject, text)
            self.assertEqual(parsed['kind'], 'definition', text)

    def test_formation_year_frames_work_across_different_subjects(self):
        for text, subject, event in [
            ('What year metralica was started', 'metralica', 'started'),
            ('What year was Nintendo founded?', 'Nintendo', 'founded'),
            ('In which year was the Red Cross established?', 'Red Cross', 'founded'),
            ('When did Radiohead start?', 'Radiohead', 'started'),
            ('When was Metallica formed?', 'Metallica', 'formed'),
            ('When did the festival begin?', 'festival', 'started')]:
            parsed = self.policy.parse(text)
            self.assertEqual(parsed['subject'], subject, text)
            self.assertEqual(parsed['kind'], 'time', text)
            self.assertEqual(parsed['event'], event, text)

    def test_conversational_factual_requests_do_not_fall_through_to_smalltalk(self):
        lookup = FactLookup(NoInternet())
        lookup.knowledge = self.store
        for text in ('What do you know about photosynthesis?', 'Photosynthesis, what do you know about it?'):
            self.assertEqual(lookup.respond(text)['route'], 'chat/local-knowledge', text)
        for text in ('Metallica band , what do you know about it', 'What can you tell me about a pangolin?'):
            self.assertEqual(lookup.respond(text)['route'], 'chat/web-unavailable', text)
        self.assertIsNone(lookup.respond('My account, what do you know about it?'))

    def test_formation_date_extraction_is_anchored_to_the_requested_entity(self):
        with closing(sqlite3.connect(self.path)) as connection, connection:
            add_document(connection, record('Example Ensemble', 70, [
                'Example Ensemble is a fictional musical group that was formed in 1981 in a coastal city.',
                'Members of Example Ensemble founded Another Ensemble in 1970 during their early careers.']))
        answer = self.store.lookup(self.policy.parse('What year was Example Ensemble started?'))
        self.assertIn('1981', answer['response'])
        self.assertNotIn('1970', answer['response'])

    def test_web_followup_keeps_resolved_subject_after_a_local_miss(self):
        lookup = FactLookup(NoInternet())
        lookup.knowledge = self.store
        messages = [dict(role='user',content='What is Example Ensemble?'),
                    dict(role='assistant',content='A fictional musical group.'),
                    dict(role='user',content='When was it formed?')]
        with patch.object(lookup, 'wikipedia', return_value={'route':'fixture'}) as wiki:
            self.assertEqual(lookup.respond(messages[-1]['content'], messages)['route'], 'fixture')
            self.assertEqual(wiki.call_args.kwargs['parsed_question']['subject'], 'Example Ensemble')

    def test_invention_dates_use_overview_and_preserve_century_precision(self):
        self.add_invention_fixtures()
        with closing(sqlite3.connect(self.path)) as connection, connection:
            add_document(connection, dict(record('Telephone', 31, [
                'In 1876, Alexander Graham Bell was the first to be granted a patent for a device that reproduced intelligible speech.']),
                sections=[dict(heading='Introduction', paragraphs=[
                    'In 1876, Alexander Graham Bell was the first to be granted a patent for a device that reproduced intelligible speech.']),
                    dict(heading='Early history', paragraphs=[
                    'A different instrument called telephone was invented for sailing vessels in 1844. This device used air horns to communicate in fog.'])]))
        answer = self.store.lookup(self.policy.parse('When was the telephone invented?'))
        self.assertIn('1876', answer['response'])
        self.assertNotIn('1844', answer['response'])
        answer = self.store.lookup(self.policy.parse('When was the bicycle invented?'))
        self.assertIn('19th century', answer['response'])

    def test_history_heading_and_unrelated_date_are_not_event_evidence(self):
        for body in ['The widget is a historic mechanical object. Its inventor became famous in 1900 after travelling around Europe.',
                     'A famous historian attributed the success of the widget to its development as a complete system.']:
            with closing(sqlite3.connect(self.path)) as connection, connection:
                add_document(connection, record('Widget', 33, [body], 'History'))
            self.assertIsNone(self.store.lookup(self.policy.parse('When was the widget invented?')))

    def test_bare_word_and_ambiguous_typos_are_not_corrected(self):
        self.assertIsNone(self.store.subject_suggestion(['flarblequux']))
        with closing(sqlite3.connect(self.path)) as connection, connection:
            add_document(connection, record('Quartz mold', 34, ['Quartz mold is a fictional named reference created solely to exercise conservative source-title matching in a test fixture.']))
            add_document(connection, record('Quartz mode', 35, ['Quartz mode is another fictional reference created solely to exercise conservative source-title matching in a test fixture.']))
        self.assertIsNone(self.store.subject_suggestion(['quartz', 'mole']))

    def test_inventor_question_preserves_multiple_contributors(self):
        self.add_invention_fixtures()
        answer = self.store.lookup(self.policy.parse('Who invented the light bulb?'))
        self.assertIn('Earlier inventors', answer['response'])
        self.assertIn('Joseph Swan', answer['response'])
        self.assertNotIn('first successful test', answer['response'])

    def test_event_date_must_belong_to_requested_entity_and_event(self):
        fixtures = [
            ('University of Northvale', 'founded', 'Introduction',
             'Northvale academics moved to a different city, where they established the University of Southvale in 1209.'),
            ('University of Northvale', 'founded', 'Colleges',
             "Northvale's graduate colleges were founded as coeducational establishments in the 20th century."),
            ('Television', 'invented', 'History',
             'Television had already developed considerably before this period. In the mid-1960s, color broadcasting was introduced in several countries.'),
            ('Ada Example', 'born', 'Introduction',
             'Ada Example (1879-1955) was a German-born fictional scientist who worked on inventions in the early twentieth century.'),
        ]
        for title, event, heading, body in fixtures:
            with closing(sqlite3.connect(self.path)) as connection, connection:
                add_document(connection, record(title, 40, [body], heading))
            self.assertIsNone(self.store.lookup(self.policy.parse(f'When was {title} {event}?')), title)


if __name__ == '__main__':
    unittest.main()
