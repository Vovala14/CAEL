"""Non-neural CA fixtures only; private photos are never read."""
import unittest
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch
import torch

from cael_image.general_detail_ca import DetailCA, neighbours
from cael_image.general_shape_ca import GeneralShapeCA
from cael_image.portrait_latent_ca import compile_latent_counts, sample_latent_ca
from cael_image.general_curriculum import curriculum, prompt_for
from cael_image.general_appearance import resolve_subject


class ShapeCATests(unittest.TestCase):
    def test_native_256_portrait_sampler_and_resolution_metadata(self):
        size = 256
        statistics = compile_latent_counts(torch.zeros(12, 4))
        prior = dict(image_size=size, rank=4, flow_limit=16., counts=torch.tensor([12]),
                     means=torch.zeros(1, size * size * 5), bases=torch.zeros(1, 4, size * size * 5),
                     scales=torch.zeros(1, 4), latent_statistics=[statistics])
        checkpoint = dict(format='cael-general-shape-ca-v2', image_size=size, aliases={'woman': ['woman']},
                          priors={'woman': prior}, detail_ca={'woman': {}},
                          guard_references=torch.full((1, size, size, 3), 255, dtype=torch.uint8),
                          settings=dict(warp_strength=.8, variation=1., sharpen=0., detail_strength=0.,
                                        joint_seed=True, guard_threshold=.04))
        images, info = GeneralShapeCA(checkpoint).generate('woman', n=1, seed=42)
        self.assertEqual(images.shape, (1, 256, 256, 3))
        self.assertIn('256x256', info['limitation'])
        checkpoint['subject_settings'] = {'woman': {'latent_ca': False}}
        _, info = GeneralShapeCA(checkpoint).generate('woman', n=1, seed=42)
        self.assertIn('Gaussian factor sampling', info['limitation'])

    def test_portrait_override_keeps_native_png_and_checks_checksum(self):
        from PIL import Image
        from cael_unified.assistant import Assistant
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'research').mkdir()
            candidate = root / 'candidate.pt'
            candidate.write_bytes(b'fixture checkpoint, never deserialized')
            config = dict(portrait_image=dict(path=str(candidate), sha256='0' * 64, enabled_subjects=['woman']))
            (root / 'research/active_models.json').write_text(json.dumps(config))
            assistant = Assistant.__new__(Assistant)
            assistant._image = SimpleNamespace(checkpoint={'priors': {'woman': {}}})
            assistant._portrait_synthetic = None
            assistant.output_root = root / 'output'
            with patch('cael_unified.assistant.ROOT', root):
                answer = assistant.image_reply('a portrait of a woman', 1, 42)
                self.assertEqual(answer['route'], 'image/unsupported')
                self.assertIn('checksum changed', answer['response'])
                pixels = torch.full((1, 256, 256, 3), 123, dtype=torch.uint8)
                info = dict(subject='woman', limitation='Synthetic software fixture only')
                assistant._portrait_synthetic = SimpleNamespace(generate=Mock(return_value=(pixels, info)))
                answer = assistant.image_reply('a portrait of a woman', 1, 42)
                self.assertEqual(answer['route'], 'image/generated')
                with Image.open(answer['paths'][0]) as image:
                    self.assertEqual(image.size, (256, 256))
                with Image.open(answer['grid']) as image:
                    self.assertEqual(image.size, (256, 256))

    def test_untrained_compound_topic_does_not_become_a_laptop(self):
        from cael_unified.assistant import Assistant
        assistant = Assistant.__new__(Assistant)
        assistant._image = SimpleNamespace(checkpoint={'priors': {'laptop': {}}}, generate=Mock())
        assistant._hybrid = False   # test the statistical model's route regardless of which models are live
        result = assistant.image_reply('make an image of a computer mouse', 1, 42)
        self.assertEqual(result['route'], 'image/unsupported')
        self.assertIn('has not finished training', result['response'])
        assistant._image.generate.assert_not_called()

    def test_expanded_curriculum_preserves_base_and_nested_aliases(self):
        base, expanded = curriculum(), curriculum('expanded')
        self.assertEqual(len(base), 32)
        self.assertEqual(len(expanded), 56)
        self.assertTrue(base.items() <= expanded.items())
        aliases = {key: values[1] for key, values in expanded.items()}
        for prompt, expected in [('make a computer mouse', 'computer_mouse'), ('make a computer monitor', 'monitor'),
                                 ('make a table lamp', 'lamp'), ('computer_mouse', 'computer_mouse')]:
            self.assertEqual(resolve_subject(prompt, aliases), expected)
        with self.assertRaisesRegex(ValueError, 'one supported'):
            resolve_subject('make a computer mouse and a dog', aliases)
        self.assertIn('waterfall', prompt_for('waterfall', 0, 'expanded'))
        self.assertEqual(set(curriculum('portraits')), {'woman', 'man'})
        self.assertIn('both eyes open', prompt_for('woman', 0, 'portraits'))

    def test_sixteen_factor_ca_counts_and_seeded_sampling(self):
        z = torch.randn(40, 16, generator=torch.Generator().manual_seed(4))
        state = compile_latent_counts(z)
        self.assertEqual(state['marginal'].shape, (16, 5))
        self.assertEqual(int(state['marginal'].sum()), 40 * 16)
        first = sample_latent_ca(state, 4, torch.Generator().manual_seed(9), joint_seed=True)
        second = sample_latent_ca(state, 4, torch.Generator().manual_seed(9), joint_seed=True)
        self.assertTrue(torch.equal(first, second))
        self.assertEqual(first.shape, (4, 16))

    def test_detail_cells_do_not_wrap_at_image_boundaries(self):
        grid = torch.arange(9).reshape(1, 3, 3)
        north, east, south, west = neighbours(grid, 99)
        self.assertEqual(int(north[0, 0, 1]), 99)
        self.assertEqual(int(west[0, 1, 0]), 99)
        self.assertEqual(int(east[0, 1, 2]), 99)
        self.assertEqual(int(south[0, 2, 1]), 99)

    def test_disabled_detail_preserves_the_sampled_field(self):
        field = torch.randn(2, 128, 128, 3)
        self.assertIs(DetailCA({}).apply(field, 1, strength=0), field)

    def test_new_sampler_never_returns_a_failed_similarity_guard(self):
        size = 16
        statistics = compile_latent_counts(torch.zeros(12, 4))
        prior = dict(image_size=size, rank=4, flow_limit=1., counts=torch.tensor([12]),
                     means=torch.zeros(1, size * size * 5), bases=torch.zeros(1, 4, size * size * 5),
                     scales=torch.zeros(1, 4), latent_statistics=[statistics])
        checkpoint = dict(format='cael-general-shape-ca-v2', aliases={'fixture': ['fixture']},
                          priors={'fixture': prior}, detail_ca={'fixture': {}},
                          guard_references=torch.zeros(1, size, size, 3, dtype=torch.uint8),
                          settings=dict(warp_strength=.8, variation=1., sharpen=0., detail_strength=0.,
                                        joint_seed=True, guard_threshold=.04))
        with self.assertRaisesRegex(RuntimeError, 'similarity guard'):
            GeneralShapeCA(checkpoint).generate('fixture', n=1, seed=42)


if __name__ == '__main__':
    unittest.main()
