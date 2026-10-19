"""Loss-aware source extraction/cache tests; valid Unicode stays intact."""
import sqlite3
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from cael_unified.assistant import Assistant
from cael_unified.bundle import digest
from cael_unified.facts import FactLookup
from cael_unified.knowledge import KnowledgeStore, SCHEMA, add_document, readable_excerpt
from cael_unified.knowledge_html import ArticleText
from cael_unified.source_quality import intact_text
from tests.test_knowledge import NoInternet, record


class QualityTests(unittest.TestCase):
    def test_known_loss_markers_reject_without_guessing_the_character(self):
        for value in ('2 \ufffd 4 volts', 'A \x00 B', 'A \x0b B', 'A \ud800 B', 'A \x7f B'):
            self.assertFalse(intact_text(value))
            self.assertFalse(readable_excerpt(value))

    def test_legitimate_unicode_punctuation_names_and_operators_are_kept(self):
        for value in ('Energy\u2014typically sunlight\u2014is converted.', 'Schr\u00f6dinger and S\u00e3o Paulo.',
                      '\u03b1 \u2264 \u03b2; 2 \u00d7 3 = 6; 4 \u2212 2 = 2; 20 \u00b0C.', 'A line.\nAnother line.\tA tab.'):
            self.assertTrue(intact_text(value), ascii(value))
        self.assertTrue(readable_excerpt('Light energy\u2014typically from sunlight\u2014is stored as chemical energy.'))

    def test_inline_math_omission_drops_the_entire_affected_paragraph(self):
        parser = ArticleText()
        parser.feed('<p>Aster Device uses the <math><mi>r</mi></math> to convert the input into a regulated output for the apparatus.</p>'
                    '<p>Aster Device is a mechanical apparatus used in authored tests to demonstrate careful source extraction.</p>')
        self.assertEqual(parser.omitted_math_blocks, 1)
        text = str(parser.sections)
        self.assertNotIn('uses the', text)
        self.assertIn('mechanical apparatus', text)

    def test_math_image_fallback_and_list_item_are_not_silently_removed(self):
        parser = ArticleText()
        parser.feed('<h2>Mechanism</h2><p>Aster Device uses the <span class="mwe-math-element"><img class="mwe-math-fallback-image-inline" alt="r"></span> to regulate the output of the apparatus.</p>'
                    '<ul><li>The ratio <math><mi>a</mi><mo>/</mo><mi>b</mi></math> determines the output of this authored example.</li>'
                    '<li>A clean text-only item remains available for source extraction in this authored example.</li></ul>')
        self.assertEqual(parser.omitted_math_blocks, 2)
        self.assertNotIn('determines the output', str(parser.sections))
        self.assertIn('clean text-only item', str(parser.sections))

    def test_reference_math_does_not_poison_unrelated_healthy_text(self):
        parser = ArticleText()
        parser.feed('<p>Aster Device is a mechanical apparatus for authored tests with intact text and a source reference.<sup><math><mi>x</mi></math></sup></p>')
        self.assertEqual(parser.omitted_math_blocks, 0)
        self.assertIn('mechanical apparatus', str(parser.sections))


class SourceCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / 'knowledge.sqlite'
        with sqlite3.connect(self.path) as connection:
            connection.executescript(SCHEMA)
        connection.close()
        self.store = KnowledgeStore(self.path, self.root / 'online.sqlite')
        self.engine = Assistant(output_root=self.root / 'outputs')
        self.engine._facts.knowledge = self.store

    def tearDown(self):
        for connection in getattr(self.store.local, 'connections', {}).values():
            connection.close()
        self.temp.cleanup()

    def put(self, paragraphs, heading='Introduction'):
        with sqlite3.connect(self.path) as connection:
            add_document(connection, record('Aster Device', 801, paragraphs, heading))
        connection.close()

    def ask(self, text):
        return self.engine.respond([dict(role='user', content=text)], n=1, seed=411)

    def test_unified_corrupt_local_source_refuses_when_provider_is_unavailable(self):
        self.put(['Aster Device is a mechanical apparatus that operates at 2 \ufffd 4 volts according to this authored test source.'])
        self.engine._facts.net = NoInternet()
        answer = self.ask('What is Aster Device?')
        self.assertEqual(answer['route'], 'chat/web-unavailable')
        self.assertFalse(answer['sources'])
        self.assertNotIn('\ufffd', answer['response'])

    def test_damaged_later_context_is_not_shortened_away_into_a_clean_claim(self):
        self.put(['Aster Device is a mechanical apparatus used in authored tests. It has a wheel and a pump. The safety limit is 2 \ufffd 4 units.'])
        parsed = self.engine._facts.knowledge_query.parse('What is Aster Device?')
        self.assertIsNone(self.store.lookup(parsed))

    def test_clean_mechanism_sibling_can_be_used_without_copying_damaged_text(self):
        self.put(['Aster Device operates with an unknown \ufffd component that should not be guessed.',
                  'Aster Device operates by passing water through a wheel. The wheel rotates and transmits power to a pump.'], 'Mechanism')
        self.engine._facts.net = NoInternet()
        answer = self.ask('How does Aster Device work?')
        self.assertEqual(answer['route'], 'chat/local-knowledge')
        self.assertIn('passing water through a wheel', answer['response'])
        self.assertEqual(self.engine._facts.net.calls, 0)

    def fixture(self, extract):
        class Provider:
            def __init__(self): self.calls = 0
            def json(self, url, **kwargs):
                self.calls += 1
                params = parse_qs(urlparse(url).query)
                if 'list' in params:
                    return {'query': {'search': [{'title': 'Aster Device'}]}}
                return {'query': {'pages': {'801': dict(pageid=801, title='Aster Device', extract=extract,
                         fullurl='https://en.wikipedia.org/wiki/Aster_Device', revisions=[dict(revid=9911, timestamp='2026-01-01T00:00:00Z')])}}}
        return Provider()

    def test_clean_provider_refreshes_only_public_cache_then_answers_offline(self):
        self.put(['Aster Device is a mechanical apparatus with a missing \ufffd expression in this authored fixture.'])
        before = digest(self.path)
        clean = 'Aster Device is a mechanical apparatus used in authored tests to demonstrate careful source extraction.'
        net = self.fixture(clean)
        self.engine._facts.net = net
        answer = self.ask('What is Aster Device?')
        self.assertEqual(answer['route'], 'chat/web-wikipedia-extractive')
        self.assertEqual(answer['response'], clean)
        self.assertIn('oldid=9911', answer['sources'][0]['url'])
        self.assertTrue(answer['knowledge']['internet_used'])
        calls = net.calls
        second = self.ask('What is Aster Device?')
        self.assertEqual(second['route'], 'chat/local-knowledge')
        self.assertEqual(net.calls, calls)
        self.assertEqual(digest(self.path), before)

    def test_damaged_provider_body_is_not_returned_or_cached(self):
        for marker in ('\ufffd', '\x0b'):
            net = self.fixture('Aster Device is a mechanical apparatus whose critical limit is 2 ' + marker + ' 4 units.')
            self.engine._facts.net = net
            answer = self.ask('What is Aster Device?')
            self.assertEqual(answer['route'], 'chat/web-unreadable')
            self.assertFalse(answer['sources'])
            self.assertFalse(self.store.online_path.exists())

    def test_damaged_record_cannot_overwrite_a_clean_public_cache_record(self):
        good = record('Aster Device', 801, ['Aster Device is a mechanical apparatus used only in authored source-quality tests.'])
        self.assertTrue(self.store.remember(good))
        before = digest(self.store.online_path)
        bad = dict(good, revision=9911, sections=[dict(heading='Introduction', paragraphs=['Aster Device has a missing \ufffd operator in this authored fixture.'])])
        self.assertFalse(self.store.remember(bad))
        self.assertEqual(digest(self.store.online_path), before)
        answer = self.store.lookup(self.engine._facts.knowledge_query.parse('What is Aster Device?'))
        self.assertEqual(answer['response'], good['sections'][0]['paragraphs'][0])

    def test_failed_cache_write_does_not_relabel_an_old_answer_as_fresh(self):
        self.engine._facts.net = self.fixture('Aster Device is a mechanical apparatus described in this authored source fixture.')
        parsed = self.engine._facts.knowledge_query.parse('How does Aster Device work?')
        with patch.object(self.store, 'remember', return_value=False), patch.object(self.store, 'lookup', side_effect=AssertionError('Old cache must not be labelled fresh')):
            answer = self.engine._facts.wikipedia('How does Aster Device work?', parsed)
        self.assertEqual(answer['route'], 'chat/web-answer-not-found')

    def test_mismatched_cached_revision_is_not_labelled_as_fetched_evidence(self):
        self.engine._facts.net = self.fixture('Aster Device is a mechanical apparatus described in this authored source fixture.')
        parsed = self.engine._facts.knowledge_query.parse('How does Aster Device work?')
        old = dict(route='chat/local-knowledge', response='OLD CACHE SENTINEL', knowledge=dict(title='Aster Device'), sources=[dict(url='https://en.wikipedia.org/w/index.php?oldid=1')])
        with patch.object(self.store, 'remember', return_value=True), patch.object(self.store, 'lookup', return_value=old):
            answer = self.engine._facts.wikipedia('How does Aster Device work?', parsed)
        self.assertEqual(answer['route'], 'chat/web-answer-not-found')
        self.assertNotIn('OLD CACHE', answer['response'])

    def test_unified_formula_omission_cannot_become_a_mechanism_answer(self):
        html = ('<p>Aster Device is a mechanical apparatus used only in authored source-extraction tests.</p>'
                '<h2>Mechanism</h2><p>Aster Device uses the <math><mi>r</mi></math> to convert the input into a regulated output for the apparatus.</p>')
        plain = 'Aster Device is a mechanical apparatus used only in authored source-extraction tests.'
        base = self.fixture(plain)
        original = base.json
        def provider(url, **kwargs):
            params = parse_qs(urlparse(url).query)
            if params.get('action') == ['parse']:
                return {'parse': dict(title='Aster Device', revid=9911, text={'*': html})}
            return original(url, **kwargs)
        base.json = provider
        self.engine._facts.net = base
        answer = self.ask('How does Aster Device work?')
        self.assertEqual(answer['route'], 'chat/web-answer-not-found')
        self.assertNotIn('uses the to convert', answer['response'])


if __name__ == '__main__':
    unittest.main()
