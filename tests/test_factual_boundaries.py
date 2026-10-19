"""Authored ambiguous topic boundaries, checked through actual unified replies."""
import unittest
from unittest.mock import patch
from cael_unified.assistant import Assistant
from cael_unified.factual_context import resolve
from cael_unified.knowledge_query import KnowledgeQuery


def user(text): return dict(role='user', content=text)
def bot(text='Authored placeholder; no source assertion.'): return dict(role='assistant', content=text)


class FactualBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = Assistant()
        cls.policy = KnowledgeQuery()

    def history(self, interruption, ack=False):
        messages = [user('Tell me about Metallica'), bot(), user(interruption), bot()]
        if ack:
            messages += [user('Thanks!'), bot()]
        return messages + [user('Who formed it?')]

    def test_comparisons_with_pronouns_clear_the_next_topic(self):
        for text in ('How does it compare with Megadeth?', 'Compare it and Megadeth.',
                     'What is the difference between it and Megadeth?', 'Explain its differences versus Megadeth.'):
            messages = self.history(text)
            self.assertEqual(resolve(messages[-1]['content'], messages, self.policy), ('Who formed it?', None), text)

    def test_literal_quoted_pronouns_clear_old_subject(self):
        for text in ('What does the word it mean?', 'Who wrote "it"?', 'Define `its`.', 'What is the pronoun that?'):
            messages = self.history(text)
            self.assertIsNone(resolve(messages[-1]['content'], messages, self.policy)[1], text)

    def test_acknowledgements_do_not_restore_cleared_subject(self):
        messages = self.history('How does it compare with Megadeth?', ack=True)
        self.assertIsNone(resolve(messages[-1]['content'], messages, self.policy)[1])

    def test_explicit_subject_after_boundary_establishes_new_topic(self):
        messages = self.history('How does it compare with Megadeth?')[:-1]
        messages += [user('Tell me about photosynthesis'), bot(), user('How does it work?')]
        question, context = resolve(messages[-1]['content'], messages, self.policy)
        self.assertEqual(question, 'How does photosynthesis work?')
        self.assertEqual(context['subject'], 'photosynthesis')

    def test_unified_ambiguous_followups_never_fetch_or_reuse_old_source(self):
        for text in ('How does it compare with Megadeth?', 'What does the word it mean?', 'Who wrote "it"?'):
            messages = self.history(text)
            with patch.object(self.engine._facts, '_respond', side_effect=AssertionError('Ambiguous topic cannot fetch or guess')), patch.object(self.engine._facts.knowledge, 'lookup', side_effect=AssertionError('Old topic lookup forbidden')):
                answer = self.engine.respond(messages, n=1, seed=413)
            self.assertEqual(answer['route'], 'chat/factual-clarify')
            self.assertEqual(answer['sources'], [])
            self.assertNotIn('Metallica', answer['response'])

    def test_unambiguous_actual_licensed_source_chain_still_works(self):
        messages = [user('Tell me about Metallica'), bot(), user('Thanks!'), bot(), user('Who formed it?')]
        with patch.object(self.engine._facts.net, 'json', side_effect=AssertionError('Local source should suffice')):
            answer = self.engine.respond(messages, n=1, seed=413)
        self.assertEqual(answer['route'], 'chat/local-knowledge')
        self.assertIn('Hetfield', answer['response'])
        self.assertEqual(answer['sources'][0]['licence'], 'CC BY-SA 4.0')

    def test_current_comparison_can_still_resolve_original_subject(self):
        messages = [user('Tell me about Metallica'), bot(), user('How does it compare with Megadeth?')]
        question, context = resolve(messages[-1]['content'], messages, self.policy)
        self.assertEqual(question, 'How does Metallica compare with Megadeth?')
        self.assertEqual(context['subject'], 'Metallica')


if __name__ == '__main__':
    unittest.main()
