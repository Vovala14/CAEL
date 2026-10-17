"""Probability mass, independent alternatives and checkpoint integrity controls."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    import joblib
    import numpy as np
    from scipy import sparse
    from sklearn.feature_extraction.text import TfidfVectorizer
except ImportError as error:
    raise unittest.SkipTest('Optional non-neural count-language dependencies are not installed') from error
from cael_unified.count_language import CountLanguage
from cael_unified.assistant import Assistant,choice_problem,route_request


class CountLanguageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        retriever=TfidfVectorizer()
        contexts=retriever.fit_transform(['red case','blue case'])
        joblib.dump(retriever,self.root/'retriever.joblib')
        sparse.save_npz(self.root/'contexts.npz',contexts)
        sparse.save_npz(self.root/'answers.npz',sparse.csr_matrix([[0,3,0],[0,0,3]]))
        sparse.save_npz(self.root/'prefix.npz',sparse.csr_matrix([[0,1,1],[0,3,1],[0,1,3]]))
        np.save(self.root/'global.npy',np.array([1,3,3]),allow_pickle=False)
        (self.root/'vocab.json').write_text(json.dumps(['<unk>','red','blue']))
        manifest=dict(format='cael-conditional-count-v1',
            settings=dict(neighbours=2,recall_power=3,recall_weight=.8,prefix_weight=.25),
            files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.iterdir()})
        (self.root/'model.json').write_text(json.dumps(manifest))
        self.model=CountLanguage(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_complete_next_token_distribution_sums_to_one(self):
        for context in ('red case','blue case','unseen context','red'):
            probabilities=[np.exp(self.model.score_ending(context,word)['sum_lnp']) for word in ('zzzz','red','blue')]
            self.assertAlmostEqual(sum(probabilities),1.,places=12)
            self.assertTrue(all(0<p<1 for p in probabilities))

    def test_training_context_changes_distribution(self):
        red=self.model.score_ending('red case','red')['sum_lnp']
        blue=self.model.score_ending('red case','blue')['sum_lnp']
        self.assertGreater(red,blue)

    def test_entity_bound_likelihood_is_invariant_to_consistent_names(self):
        self.model.manifest['entity_binding']=True
        first=self.model.score_endings('Vera holds the red case.',['red','blue'])
        second=self.model.score_endings('Neri holds the red case.',['red','blue'])
        self.assertEqual(first,second)

    def test_unrelated_alternatives_do_not_change_likelihood(self):
        first=self.model.score_endings('red case',['red','blue'])
        second=self.model.score_endings('red case',['blue','zzzz','red'])
        self.assertEqual(first[0],second[2])
        self.assertEqual(first[1],second[0])

    def test_empty_or_oversized_endings_are_rejected(self):
        for endings in (['red',' '],['red',''],['red','x'*2001]):
            with self.assertRaises(ValueError):
                self.model.score_endings('red case',endings)

    def test_corruption_fails_before_loading_serialized_objects(self):
        (self.root/'vocab.json').write_text('corrupt')
        with patch('joblib.load',side_effect=AssertionError('Should not deserialize')),self.assertRaisesRegex(ValueError,'checksum mismatch'):
            CountLanguage(self.root)

    def test_unknown_token_has_finite_probability(self):
        self.assertTrue(np.isfinite(self.model.score_ending('unseen','unseenword')['sum_lnp']))

    def test_extreme_associations_still_have_normalized_finite_mass(self):
        self.model.association=sparse.csr_matrix(np.tile([0.,1000.,-1000.],(self.model.contexts.shape[1],1)))
        self.model.settings['association_strength']=10.
        probabilities=[np.exp(self.model.score_ending('red case',word)['sum_lnp']) for word in ('zzzz','red','blue')]
        self.assertAlmostEqual(sum(probabilities),1.,places=12)
        self.assertTrue(all(p>0 for p in probabilities))

    def test_lexical_probability_transfer_preserves_mass(self):
        # One new observed word shares red's mass; no probabilities are duplicated.
        self.model.transfer=sparse.csc_matrix([[1,0,0,0],[0,.5,0,.5],[0,0,1,0]])
        self.model.output_vocab=['<unk>','red','blue','crimson']
        self.model.output_index={word:i for i,word in enumerate(self.model.output_vocab)}
        self.model.settings['lexical_weight']=.3
        values=[np.exp(self.model.score_ending('red case',word)['sum_lnp']) for word in ('zzzz','red','blue','crimson')]
        self.assertAlmostEqual(sum(values),1.,places=12)
        self.assertTrue(all(p>0 for p in values))

    def test_unified_assistant_scores_with_the_same_component(self):
        assistant=Assistant(output_root=self.root/'outputs',language_checkpoint=self.root/'model.json')
        scores=assistant.score_endings('red case',['red','blue'])
        self.assertEqual(scores,self.model.score_endings('red case',['red','blue']))
        # This checks the language-model path itself, independent of whichever chooser is live.
        with patch.object(assistant._facts,'respond',side_effect=AssertionError('No web lookup')), \
                patch.object(assistant,'choice_settings',return_value=None):
            result=assistant.respond([dict(role='user',content='Choose a colour for the red case.\nA. red\nB. blue')],mode='chat')
        self.assertEqual(result['route'],'chat/choice-count')
        self.assertEqual(result['choice'],0)

    def test_multiple_choices_do_not_trigger_image_creation(self):
        prompt='Which picture best matches the story?\nA. paint a car\nB. draw a cat\nC. make a house\nD. none'
        self.assertEqual(route_request(prompt),'chat')
        self.assertIsNotNone(choice_problem(prompt))
        self.assertIsNone(choice_problem('Draw these:\nA. car\nB. cat'))

    def test_incomplete_or_duplicate_choice_labels_are_rejected(self):
        self.assertIsNone(choice_problem('Choose:\nA. red\nA. blue'))
        self.assertIsNone(choice_problem('Choose:\nA. red\nC. blue'))

    def test_public_sources_retain_language_training_credits(self):
        from cael_unified.public_worker import sources_page
        (self.root/'research').mkdir()
        (self.root/'research/active_models.json').write_text(json.dumps(dict(language=dict(path='fixture',wordnet=True))))
        with patch('cael_unified.public_worker.ROOT',self.root):
            page=sources_page()
        self.assertIn('Social IQa',page)
        self.assertIn('Princeton University',page)
        self.assertIn('CC BY 4.0',page)


if __name__=='__main__':
    unittest.main()
