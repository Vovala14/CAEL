"""Synthetic inference regression tests; never access private image data."""
import unittest
from types import SimpleNamespace
from pathlib import Path
import tempfile
from unittest.mock import patch

try:
    import torch
except ModuleNotFoundError as error:
    if error.name != 'torch':
        raise
    torch = None

if torch is not None:
    from cael_image.portrait_sampling import CompactRows, downsample_lab, luminance_weights
    from cael_assistant import imagegen as ig


@unittest.skipIf(torch is None, 'Optional portrait inference requires PyTorch')
class PortraitSamplingTests(unittest.TestCase):
    def test_alignment_flip_round_trip_preserves_eye_order(self):
        from cael_image.portrait_alignment_geometry import mirror_pair
        pair = ((12., 15.), (28., 17.))
        flipped = mirror_pair(pair, 64)
        self.assertLess(flipped[0][0], flipped[1][0])
        self.assertEqual(mirror_pair(flipped, 64), pair)

    def test_added_alignment_requires_plausible_native_geometry(self):
        from cael_image.portrait_alignment_geometry import plausible_pair
        face = (0., 0., 40., 40.)
        self.assertTrue(plausible_pair(((12., 16.), (28., 16.)), face))
        self.assertFalse(plausible_pair(((18., 16.), (22., 16.)), face))
        self.assertFalse(plausible_pair(((28., 16.), (12., 16.)), face))
        self.assertFalse(plausible_pair(((12., 10.), (28., 22.)), face))
        self.assertFalse(plausible_pair(((12., 35.), (28., 35.)), face))

    def test_detector_agreement_is_scaled_by_eye_span(self):
        from cael_image.portrait_alignment_geometry import pair_agreement
        pair = ((12., 16.), (28., 16.))
        self.assertTrue(pair_agreement(pair, ((13., 16.), (29., 16.))))
        self.assertFalse(pair_agreement(pair, ((16., 16.), (32., 16.))))

    def test_eye_similarity_alignment_identity_and_translation(self):
        import numpy as np
        from cael_image.portrait_appearance import align_similarity
        rgb = np.zeros((64, 64, 3), dtype=np.uint8)
        rgb[25, 24] = 255
        original = rgb.copy()
        unchanged = align_similarity(rgb, [24, 25], [40, 25], [24, 25], [40, 25])
        np.testing.assert_array_equal(unchanged.numpy(), rgb)
        moved = align_similarity(rgb, [24, 25], [40, 25], [30, 25], [46, 25])
        self.assertEqual(int(moved[25, 30, 0]), 255)
        self.assertEqual(int(moved[25, 24, 0]), 0)
        np.testing.assert_array_equal(rgb, original)
        with self.assertRaises(ValueError):
            align_similarity(rgb, [24, 25], [24, 25], [24, 25], [40, 25])

    def test_inverse_deformation_zero_field_preserves_image(self):
        from cael_image.portrait_deformation import invert_deformation
        generator = torch.Generator().manual_seed(9)
        field = torch.rand((2, 64, 64, 3), generator=generator)
        restored = invert_deformation(field, torch.zeros(2, 64, 64, 2))
        torch.testing.assert_close(restored, field, atol=1e-5, rtol=1e-5)

    def test_latent_integer_counts_and_seeded_local_sampling(self):
        from cael_image.portrait_latent_ca import compile_latent_counts, sample_latent_ca
        z = torch.cat([-torch.ones(20, 8), torch.ones(20, 8)])
        statistics = compile_latent_counts(z)
        self.assertEqual(statistics['marginal'].dtype, torch.int32)
        self.assertTrue(bool((statistics['marginal'].sum(-1) == 40).all()))
        self.assertTrue(bool((statistics['pairs'].sum((-1, -2)) == 40).all()))
        self.assertFalse(statistics['source_vectors_stored'])
        a = sample_latent_ca(statistics, 200, torch.Generator().manual_seed(9))
        b = sample_latent_ca(statistics, 200, torch.Generator().manual_seed(9))
        torch.testing.assert_close(a, b, rtol=0, atol=0)
        self.assertTrue(bool(torch.isfinite(a).all()))
        self.assertGreater(float(((a[:, 0] > 0) == (a[:, 1] > 0)).float().mean()), .6)

    def test_appearance_guard_fails_without_returning_source_like_batch(self):
        from cael_image.portrait_appearance import sample_guarded_appearance
        prior = SimpleNamespace(sample=lambda count, seed, variation: (torch.zeros(count, 64, 64, 3), None))
        with self.assertRaisesRegex(RuntimeError, 'exhausted its retries'):
            sample_guarded_appearance(prior, 2, 7, torch.zeros(1, 64, 64, 3, dtype=torch.uint8), max_attempts=1)

    def test_joint_shape_appearance_sampler_round_trip_and_seed(self):
        from cael_image.portrait_deformation import DeformationPrior
        dim = 64 * 64 * 5
        means = torch.zeros(1, dim)
        means[0, :64 * 64 * 3:3] = 1.25
        bases = torch.zeros(1, 8, dim)
        bases[0, 0, :64 * 64 * 3:3] = .01
        state = dict(means=means, bases=bases, scales=torch.ones(1, 8), counts=torch.tensor([20]), rank=8)
        prior = DeformationPrior(state)
        a, _ = prior.sample(4, 7)
        b, _ = prior.sample(4, 7)
        c, _ = prior.sample(4, 8)
        torch.testing.assert_close(a, b, rtol=0, atol=0)
        self.assertFalse(torch.equal(a, c))
        self.assertTrue(bool(torch.isfinite(a).all()))
        self.assertEqual(a.shape, (4, 64, 64, 3))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'prior.pt'
            torch.save(state, path)
            loaded = DeformationPrior(torch.load(path, weights_only=True))
            torch.testing.assert_close(loaded.sample(4, 7)[0], a, rtol=0, atol=0)

    def test_whole_face_prior_samples_are_seeded_aggregate_variations(self):
        from cael_image.portrait_structure import StructurePrior
        images = torch.zeros(12, 64, 64, 3, dtype=torch.uint8)
        for i in range(12):
            images[i, :, :, :] = 30 + i * 12
            images[i, 8 + i:24 + i, 12:40] = 180
        prior = StructurePrior.fit(images, clusters=2, rank=3, min_members=4)
        self.assertGreaterEqual(int(prior.state['counts'].min()), 4)
        self.assertEqual(int(prior.state['counts'].sum()), 12)
        self.assertFalse(prior.state['source_images_stored'])
        self.assertNotIn('source_coefficients', prior.state)
        a, population_a = prior.sample(4, 7)
        b, population_b = prior.sample(4, 7)
        c, _ = prior.sample(4, 8)
        torch.testing.assert_close(a, b, rtol=0, atol=0)
        torch.testing.assert_close(population_a, population_b)
        self.assertFalse(torch.equal(a, c))
        self.assertEqual(a.shape, (4, 64, 64, 3))
        self.assertTrue(bool(torch.isfinite(a).all()))

    def test_structure_probability_is_finite_for_distant_palette(self):
        from cael_image.portrait_structure import shape_probabilities
        palette = torch.tensor([[0., 0, 0], [100., 0, 0]])
        field = torch.full((2, 4, 4, 3), 1000.)
        p = shape_probabilities(palette, field, .1)
        self.assertTrue(bool(torch.isfinite(p).all()))
        torch.testing.assert_close(p.sum(-1), torch.ones(2, 4, 4))
        with self.assertRaises(ValueError):
            shape_probabilities(palette, field, 0)

    def test_similarity_guard_rejects_and_resamples_without_using_refs_to_synthesise(self):
        from cael_image.portrait_structure import generate_guarded
        references = torch.zeros(1, 64, 64, 3, dtype=torch.uint8)
        bad = references.repeat(2, 1, 1, 1)
        accepted = torch.full_like(bad, 100)
        populations = torch.zeros(2, dtype=torch.long)
        with patch('cael_image.portrait_structure.generate_structured',
                   side_effect=[(bad.clone(), populations.clone()), (accepted, populations.clone())]) as synth:
            result, check = generate_guarded(None, None, 2, 7, references, threshold=.12)
        self.assertTrue(torch.equal(result, accepted))
        self.assertEqual(check['replacements'], 2)
        self.assertEqual(check['rounds'], 1)
        self.assertNotIn('references', synth.call_args.kwargs)
        self.assertTrue(all(d >= .12 for d in check['nearest_RMS']))

    def test_similarity_guard_never_returns_failed_batch(self):
        from cael_image.portrait_structure import generate_guarded
        references = torch.zeros(1, 64, 64, 3, dtype=torch.uint8)
        with patch('cael_image.portrait_structure.generate_structured',
                   side_effect=lambda *a, **k: (references.clone(), torch.zeros(1, dtype=torch.long))):
            with self.assertRaisesRegex(RuntimeError, 'exhausted its retries'):
                generate_guarded(None, None, 1, 7, references, threshold=.12, max_attempts=2)

    def test_continuation_preserves_holdout_and_skips_prior_training_pixels(self):
        from cael_image.train_portrait_update import continuation_split
        def record(name, pixel):
            return dict(image=name, pixel_sha256=pixel, image_file_sha256=pixel, caption_sha256=None)
        trained, reserved = record('trained.png', 'A'), record('reserved.png', 'B')
        previous = dict(train=[trained], heldout=[reserved])
        records = [trained, reserved, record('renamed_training.png', 'A'),
                   record('renamed_holdout.png', 'B'), record('new1.png', 'C'), record('new2.png', 'D')]
        delta, heldout, cumulative, old_heldout, fresh = continuation_split(records, previous, .5, 42)
        self.assertEqual(len(delta), 1)
        self.assertEqual(len(fresh), 1)
        self.assertEqual(len(old_heldout), 2)
        self.assertEqual(len(cumulative), 2)
        self.assertFalse({r['pixel_sha256'] for r in delta} & {'A', 'B'})
        self.assertFalse({r['pixel_sha256'] for r in cumulative} & {r['pixel_sha256'] for r in heldout})
        with self.assertRaisesRegex(ValueError, 'changed or disappeared'):
            continuation_split([record('trained.png', 'changed')] + records[1:], previous, .5, 42)

    def test_snapshot_accepts_missing_caption_but_rejects_late_changes(self):
        from PIL import Image
        from cael_image.data import discover
        from cael_image.train_portrait_update import load_snapshot, caption_keys
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            Image.new('RGB', (64, 64), 'red').save(root / 'photo.png')
            records = discover(root, require_captions=False)
            self.assertEqual(load_snapshot(root, records).shape, (1, 64, 64, 3))
            self.assertEqual(caption_keys(records[0]['caption']), set())
            (root / 'photo.txt').write_text('added after manifest freeze', encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError, 'Source changed after manifest freeze'):
                load_snapshot(root, records)

    def test_compact_rows_preserve_empty_and_duplicate_lookups(self):
        dense = torch.tensor([[0, 0, 0], [3, 0, 8], [0, 0, 0], [0, 2, 0]])
        keys = torch.tensor([[3, 0, 1], [2, 1, 3]])
        compact = CompactRows(dense.to_sparse(), 'cpu')
        self.assertEqual(compact.shape, dense.shape)
        torch.testing.assert_close(compact[keys], dense[keys])
        empty = CompactRows(torch.zeros_like(dense).to_sparse(), 'cpu')
        torch.testing.assert_close(empty[keys], torch.zeros_like(dense[keys]))

    def test_caption_pooling_preserves_spatial_blocks(self):
        blocks = torch.arange(256).reshape(1, 16, 16, 1).expand(2, 16, 16, 3).float()
        lab = blocks.repeat_interleave(4, 1).repeat_interleave(4, 2)
        torch.testing.assert_close(downsample_lab(lab, 16), blocks)
        # The old layout averaged distant rows, rather than each 4x4 block.
        self.assertFalse(torch.equal(lab.reshape(-1, 4, 16, 4, 16, 3).mean((2, 4)), blocks))

    def test_incremental_sparse_counts_match_dense_accumulation(self):
        dense = torch.tensor([[0, 0, 0], [3, 0, 8], [0, 0, 0], [0, 2, 0]], dtype=torch.int32)
        compact = CompactRows(dense.to_sparse(), 'cpu')
        for keys, colours in [(torch.tensor([0, 1, 0, 2]), torch.tensor([1, 2, 1, 0])),
                              (torch.tensor([3, 2, 2]), torch.tensor([1, 0, 1]))]:
            compact.add_(keys, colours)
            dense.view(-1).index_add_(0, keys * 3 + colours, torch.ones_like(colours, dtype=torch.int32))
        torch.testing.assert_close(compact[torch.arange(4)], dense)
        torch.testing.assert_close(compact.to_sparse().to_dense(), dense)
        empty = CompactRows(torch.zeros_like(dense).to_sparse(), 'cpu')
        empty.add_(torch.tensor([2, 2]), torch.tensor([0, 1]))
        self.assertEqual(int(empty[torch.tensor([2])].sum()), 2)

    def test_luminance_tilt_is_bounded_and_temperature_consistent(self):
        pal = torch.tensor([[0., 0, 0], [50, 0, 0], [100, 0, 0]])
        torch.testing.assert_close(luminance_weights(pal, 0, 1), torch.ones(3))
        cold = luminance_weights(pal, 0.4, 0.5) ** 2
        warm = luminance_weights(pal, 0.4, 1)
        torch.testing.assert_close(cold, warm)
        self.assertTrue(bool((warm[1:] > warm[:-1]).all()))

    def test_compact_full_sampler_is_pixel_identical_to_dense(self):
        rng = torch.Generator().manual_seed(83)
        def counts(rows):
            t = torch.randint(0, 5, (rows, 4), generator=rng, dtype=torch.int32)
            t[::3] = 0
            return t
        dense = ig.v10.GCA10(torch.device('cpu'), 4, 2, 2, 2)
        dense.pal = torch.tensor([[20., 0, 0], [40, 10, 10], [65, 5, 10], [85, 0, 0]])
        dense.coarse = torch.tensor([0, 0, 1, 1])
        dense.seed = {'sf': counts(16 * 2 ** 4), 'sp': counts(16)}
        dense.t = {L: {k: counts(rows) for k, rows in
                      [('gf', 128), ('gn', 64), ('gp', 16), ('rf', 128), ('rn', 64), ('rp', 4)]}
                   for L in ig.v9.LEVELS[1:]}
        dense.prior = {L: counts(L * L) for L in ig.v9.LEVELS}
        dense.sym = {L: counts(L * L * 2) for L in ig.v9.LEVELS}
        compact = ig.v10.GCA10(torch.device('cpu'), 4, 2, 2, 2)
        for name in ('pal', 'coarse', 'seed', 'prior', 'sym'):
            setattr(compact, name, getattr(dense, name))
        compact.t = {L: {k: CompactRows(t.to_sparse(), 'cpu') for k, t in tables.items()}
                     for L, tables in dense.t.items()}
        settings = dict(sweeps=(1, 1, 1, 1, 1), temps=(1., 1., .9, .6, .4))
        compact.luminance_bias = 0.0
        a = dense.generate(2, 19, **settings)
        b = compact.generate(2, 19, **settings)
        torch.testing.assert_close(a, b, rtol=0, atol=0)


if __name__ == '__main__':
    if torch is not None:
        torch.set_num_threads(2)
    unittest.main()
