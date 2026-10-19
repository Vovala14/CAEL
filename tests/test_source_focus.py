"""Authored source clauses test focus without silently dropping uncertainty."""
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from cael_unified.assistant import Assistant
from cael_unified.knowledge import KnowledgeStore, SCHEMA, add_document
from cael_unified.knowledge_query import KnowledgeQuery
from tests.test_knowledge import NoInternet, record


class SourceFocusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / 'knowledge.sqlite'
        with sqlite3.connect(self.path) as connection:
            connection.executescript(SCHEMA)
        connection.close()
        self.store = KnowledgeStore(self.path, self.root / 'online.sqlite')
        self.net = NoInternet()
        self.engine = Assistant(output_root=self.root / 'outputs')
        self.engine._facts.knowledge = self.store
        self.engine._facts.net = self.net
        self.policy = KnowledgeQuery()

    def tearDown(self):
        for connection in getattr(self.store.local, 'connections', {}).values():
            connection.close()
        self.temp.cleanup()

    def put(self, body, title='Aster Ensemble', sections=None):
        item = record(title, 601, [body])
        if sections:
            item['sections'] = sections
        with sqlite3.connect(self.path) as connection:
            add_document(connection, item)
        connection.close()

    def ask(self, text, history=None):
        return self.engine.respond((history or []) + [dict(role='user', content=text)], n=1, seed=49)

    def test_explicit_undated_founders_do_not_require_an_invented_year(self):
        for body in ('Aster Ensemble was founded by Nori and Mira.', 'Nori founded Aster Ensemble.',
                     'Nori and Mira formed Aster Ensemble as a joint venture.'):
            self.put(body)
            answer = self.ask('Who founded Aster Ensemble?')
            self.assertEqual(answer['route'], 'chat/local-knowledge')
            self.assertEqual(answer['response'], body)
            self.assertEqual(answer['sources'][0]['licence'], 'CC BY-SA 4.0')
        self.assertEqual(self.net.calls, 0)

    def test_short_explicit_founding_dates_are_valid_source_answers(self):
        for body in ('Aster Ensemble was founded in 1927.', 'In 1927, Nori founded Aster Ensemble.'):
            self.put(body)
            answer = self.ask('When was Aster Ensemble founded?')
            self.assertEqual(answer['route'], 'chat/local-knowledge')
            self.assertEqual(answer['response'], body)
        self.assertEqual(self.net.calls, 0)

    def test_founding_dates_do_not_identify_founders(self):
        self.put('Aster Ensemble was formed in 1927.')
        self.assertIsNone(self.store.lookup(self.policy.parse('Who formed Aster Ensemble?')))

    def test_actor_dates_and_later_events_do_not_date_the_founding(self):
        for body in ('Nori (1900-1980) founded Aster Ensemble.',
                     'Aster Ensemble was founded by Nori (1900-1980).',
                     'Aster Ensemble was founded by Nori, born in 1900.',
                     'Aster Ensemble was founded by Nori after leaving a different group in 1927.',
                     'In Nori’s lifetime (1900-1980), Nori founded Aster Ensemble.'):
            self.put(body)
            self.assertIsNone(self.store.lookup(self.policy.parse('When was Aster Ensemble founded?')), body)

    def test_negated_events_and_mechanisms_are_not_founder_answers(self):
        for body in ('Aster Ensemble was not founded by Nori in 1927.',
                     'Aster Ensemble wasn’t founded by Nori in 1927.',
                     'Aster Ensemble was formed by merging two groups in 1927.',
                     'Aster Ensemble was formed by a merger of two groups.',
                     'Aster Ensemble was formed by decree in 1927.',
                     'Aster Ensemble was formed by royal decree in 1927.',
                     'Aster Ensemble was formed by an act of parliament in 1927.',
                     'He founded Aster Ensemble.'):
            self.put(body)
            self.assertIsNone(self.store.lookup(self.policy.parse('Who founded Aster Ensemble?')), body)

    def test_plain_adjacent_definition_can_be_removed_with_disclosed_subject(self):
        self.put('Aster Ensemble is a chamber music group. It was formed in 1927 by Nori and Mira.')
        answer = self.ask('When was Aster Ensemble formed?')
        self.assertEqual(answer['response'], 'Aster Ensemble was formed in 1927 by Nori and Mira.')
        self.assertIn('Source subject pronoun expanded', answer['details'])

    def test_qualifiers_in_the_context_and_event_are_retained(self):
        for qualifier in ('uncertain', 'unknown', 'disputed', 'fictional'):
            body = f'Aster Ensemble is a group with {qualifier} origins. It was probably formed around 1927 by Nori and Mira.'
            self.put(body)
            answer = self.ask('When was Aster Ensemble formed?')
            self.assertEqual(answer['route'], 'chat/local-knowledge')
            self.assertIn(qualifier, answer['response'])
            self.assertIn('probably', answer['response'])
            self.assertIn('around 1927', answer['response'])

    def test_intervening_entity_does_not_license_old_antecedent(self):
        for body in ('Aster Ensemble is a chamber music group. Beta Ensemble is a rock group. It was formed in 1927 by Nori.',
                     'Aster Ensemble is a chamber music group with a subsidiary called Beta. It was formed in 1927 by Nori.',
                     'Aster Ensemble is a chamber music group and Beta Group is a rock band. It was formed in 1927 by Nori.'):
            self.put(body)
            self.assertIsNone(self.store.lookup(self.policy.parse('When was Aster Ensemble formed?')))

    def test_explicit_mechanism_forms_keep_only_the_subject(self):
        for text in ('How does Vela Device work?', 'How does Vela Device operate?',
                     'How does Vela Device function?', 'How does Vela Device work in simple terms?',
                     'Please explain how Vela Device works.', 'Explain how Vela Device functions briefly.'):
            parsed = self.policy.parse(text)
            self.assertEqual((parsed['kind'], parsed['subject']), ('mechanism', 'Vela Device'), text)

    def test_local_mechanism_answers_precede_remote_article_requests(self):
        self.put('', title='Vela Device', sections=[
            dict(heading='Introduction', paragraphs=['Vela Device is a classroom apparatus with a wheel and a pump.']),
            dict(heading='Mechanism', paragraphs=['Vela Device operates by passing water through a wheel. The wheel rotates and transmits power to an attached pump.'])])
        with patch.object(self.engine._facts, 'explain', side_effect=AssertionError('Unneeded remote article')):
            for text in ('How does Vela Device work?', 'Explain how Vela Device works.', 'How does Vela Device operate?'):
                answer = self.ask(text)
                self.assertEqual(answer['route'], 'chat/local-knowledge')
                self.assertIn('passing water through a wheel', answer['response'])
                self.assertNotIn('classroom apparatus', answer['response'])
        self.assertEqual(self.net.calls, 0)

    def test_founder_initials_and_honorifics_are_not_dropped(self):
        for body in ('Dr. Nori founded Aster Ensemble.', 'J. Smith and R. Smith founded Aster Ensemble.',
                     'Aster Ensemble was founded by Dr. Nori and J. Smith.'):
            self.put(body)
            answer = self.ask('Who founded Aster Ensemble?')
            self.assertEqual(answer['route'], 'chat/local-knowledge')
            self.assertEqual(answer['response'], body)

    def test_mechanism_frame_does_not_override_freshness_or_guidance_controls(self):
        for text in ('How does the current tax system work?', 'How does medication work?',
                     'How does the latest software version function?'):
            self.assertFalse(self.policy.parse(text)['static'], text)

    def test_definition_alone_is_not_a_mechanism_or_a_followup_answer(self):
        self.put('Vela Device is a classroom apparatus found in schools around the country.', title='Vela Device')
        first = self.ask('What is Vela Device?')
        history = [dict(role='user', content='What is Vela Device?'), dict(role='assistant', content=first['response'])]
        answer = self.ask('Explain how it works.', history)
        self.assertEqual(answer['route'], 'chat/web-unavailable')
        self.assertFalse(answer['sources'])
        self.assertNotIn('classroom apparatus', answer['response'])

    def test_mechanism_section_precedes_definition_and_incidental_later_use(self):
        self.put('', title='Vela Device', sections=[
            dict(heading='Introduction', paragraphs=['Vela Device converts water flow into motion. It is a classroom apparatus.']),
            dict(heading='Mechanism', paragraphs=['Vela Device operates by passing water through a wheel. The wheel rotates and transmits power to an attached pump.']),
            dict(heading='Later applications', paragraphs=['Vela Device uses a different mechanism in an experimental variant that powers a light.'])])
        first = self.ask('What is Vela Device?')
        self.assertIn('classroom apparatus', first['response'])
        history = [dict(role='user', content='What is Vela Device?'), dict(role='assistant', content=first['response'])]
        answer = self.ask('How does it work?', history)
        self.assertEqual(answer['knowledge']['heading'], 'Mechanism')
        self.assertIn('passing water through a wheel', answer['response'])
        self.assertNotIn('experimental variant', answer['response'])
        self.assertNotIn('classroom apparatus', answer['response'])
        self.assertEqual(self.net.calls, 0)


if __name__ == '__main__':
    unittest.main()
