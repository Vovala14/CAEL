"""Reasoning about picture requests: several objects, placements, sizes, described subjects and follow-up edits."""
import tempfile
import unittest
from pathlib import Path

import numpy as np

from cael_image import concepts
from cael_image.hybrid import HybridModel, fit
from cael_image.scene import SceneError, edit, is_edit, layout, parse, simple, summary
from cael_unified.assistant import picture_follow_up

NEW_040 = ('mouse', 'fox', 'wolf', 'deer', 'dolphin', 'desert', 'snow', 'sky', 'ocean', 'park', 'field', 'room')
TOPICS = [t for t in concepts.FACTS if t not in ('city',) + NEW_040]     # the 0.3.9 subjects
TOPICS_040 = TOPICS + list(NEW_040)
ALIASES = {'cat': ['cat', 'cats', 'kitten'], 'dog': ['dog', 'dogs', 'puppy'], 'car': ['car', 'cars'],
           'computer_mouse': ['computer mouse'], 'flower': ['flower', 'flowers']}


def scene(text, seed=0):
    return parse(text, ALIASES, TOPICS, seed)


class ParseTests(unittest.TestCase):
    def test_several_objects_and_relation(self):
        s = scene('draw a red car to the left of a tree')
        self.assertEqual([o['topic'] for o in s['objects']], ['car', 'tree'])
        self.assertEqual(s['objects'][0]['colour'], 'red')
        self.assertEqual(s['relations'], [(0, 'left', 1)])

    def test_kind_of_and_closest_stand_in_are_explained(self):
        self.assertEqual(scene('draw a poodle')['objects'][0]['topic'], 'dog')
        self.assertIn('kind of dog', scene('draw a poodle')['objects'][0]['why'])
        self.assertIn('closest', scene('draw a dolphin')['objects'][0]['why'])

    def test_described_subjects(self):
        self.assertEqual(scene('draw the animal that says moo')['objects'][0]['topic'], 'cow')
        self.assertEqual(scene('draw a yellow fruit')['objects'][0]['topic'], 'banana')
        self.assertEqual(scene('draw an animal with a long neck')['objects'][0]['topic'], 'giraffe')
        self.assertEqual(scene('draw the biggest animal')['objects'][0]['topic'], 'whale')

    def test_impossible_description_says_why(self):
        with self.assertRaises(SceneError):
            scene('draw a fruit that can fly')

    def test_definite_reference_reuses_the_object_and_contradiction_is_reported(self):
        s = scene('draw a cat to the left of a dog and the dog to the left of the cat')
        self.assertEqual(len(s['objects']), 2)
        layout(s, 128)
        self.assertTrue(any('contradict' in n for n in s['notes']))

    def test_anchors_are_not_read_as_on_top_of(self):
        s = scene('draw a car on the left and a tree on the right')
        self.assertEqual(s['relations'], [])
        self.assertEqual([o['anchor'] for o in s['objects']], ['left', 'right'])

    def test_counts_are_capped_and_unknown_background_reported(self):
        s = scene('draw five apples in the desert')
        self.assertEqual(s['objects'][0]['count'], 3)
        self.assertTrue(any('desert' in n for n in s['notes']))

    def test_new_subjects_and_backgrounds_are_used_when_available(self):
        s = parse('draw a fox in the snow', ALIASES, TOPICS_040)
        self.assertEqual((s['objects'][0]['topic'], s['background']), ('fox', 'snow'))
        s = parse('draw a penguin in the desert', ALIASES, TOPICS_040)
        self.assertEqual(s['background'], 'desert')
        self.assertEqual(parse('draw a mouse', ALIASES, TOPICS_040)['objects'][0]['topic'], 'mouse')
        self.assertEqual(parse('draw a dolphin', ALIASES, TOPICS_040)['objects'][0]['why'], None)
        self.assertEqual(parse('draw a boat on the sea', ALIASES, TOPICS_040)['background'], 'ocean')
        self.assertEqual(scene('draw a boat on the sea')['background'], 'beach')     # older models: nearest background

    def test_excluded_colour_and_simple_path(self):
        self.assertEqual(scene('draw a car that is not red')['objects'][0]['not_colours'], ['red'])
        self.assertTrue(simple(scene('draw a blue cat on a beach')))
        self.assertFalse(simple(scene('draw a cat on a sofa')))


class LayoutTests(unittest.TestCase):
    def test_left_right_between_and_real_sizes(self):
        s = scene('draw a dog between a cat and an elephant')
        boxes, order, _ = layout(s, 128)
        x = {s['objects'][i]['topic']: boxes[i][0] for i in boxes}
        self.assertLess(x['cat'], x['dog'])
        self.assertLess(x['dog'], x['elephant'])
        heights = {s['objects'][i]['topic']: boxes[i][2] for i in boxes}
        self.assertGreater(heights['elephant'], heights['cat'] * 1.5)

    def test_on_stacks_in_one_column(self):
        s = scene('draw a cat on a sofa')
        boxes, _, _ = layout(s, 128)
        cat, sofa = boxes[0], boxes[1]
        self.assertAlmostEqual(cat[0], sofa[0])
        self.assertLess(cat[1], sofa[1])
        self.assertEqual(summary(s), 'a cat on a sofa')


class EditTests(unittest.TestCase):
    def test_follow_up_edits(self):
        s = scene('draw a cat')
        s, _ = edit(s, 'make it blue', ALIASES, TOPICS)
        self.assertEqual(s['objects'][0]['colour'], 'blue')
        s, _ = edit(s, 'add a dog next to the cat', ALIASES, TOPICS)
        self.assertEqual([o['topic'] for o in s['objects']], ['cat', 'dog'])
        s, _ = edit(s, 'now put them in a forest', ALIASES, TOPICS)
        self.assertEqual(s['background'], 'forest')
        s, _ = edit(s, 'replace the cat with a horse', ALIASES, TOPICS)
        self.assertEqual(s['objects'][0]['topic'], 'horse')
        s, _ = edit(s, 'remove the dog', ALIASES, TOPICS)
        self.assertEqual([o['topic'] for o in s['objects']], ['horse'])
        with self.assertRaises(SceneError):
            edit(s, 'remove the horse', ALIASES, TOPICS)

    def test_background_edit_does_not_move_objects(self):
        s = scene('draw a cow next to a red car')
        s, _ = edit(s, 'now put them on a beach', ALIASES, TOPICS)
        self.assertEqual((s['background'], s['relations']), ('beach', []))
        s, _ = edit(s, 'put the cow on the car', ALIASES, TOPICS)
        self.assertEqual(s['relations'], [(0, 'on', 1)])

    def test_follow_up_detection_needs_a_picture_before(self):
        picture = dict(role='assistant', content='Created 2 small images of a cat.')
        self.assertTrue(picture_follow_up([dict(role='user', content='draw a cat'), picture, dict(role='user', content='make it blue')]))
        chat = dict(role='assistant', content='Hello!')
        self.assertFalse(picture_follow_up([dict(role='user', content='hi'), chat, dict(role='user', content='make it blue')]))
        self.assertFalse(is_edit('what is the capital of France?'))


class RenderTests(unittest.TestCase):
    def test_scene_is_drawn_with_both_objects(self):
        from cael_image.scene import render
        rng = np.random.default_rng(0)

        def boxes(colour):
            images = np.full((8, 64, 64, 3), 230, np.uint8)
            for i in range(8):
                y, x = rng.integers(16, 24, 2)
                images[i, y:y + 24, x:x + 24] = colour
            return images
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'model.npz'
            np.savez(path, **fit({'cat': boxes((200, 30, 30)), 'elephant': boxes((30, 30, 200))}, {'cat': ['cat'], 'elephant': ['elephant']}))
            model = HybridModel(path)
            s = parse('draw a cat to the left of an elephant', {'cat': ['cat'], 'elephant': ['elephant']}, model.topics)
            images, info = render(model, s, n=1, seed=1)
            model.data.close()
        picture = images[0].astype(int)
        red = (picture[..., 0] - picture[..., 2]) > 80
        blue = (picture[..., 2] - picture[..., 0]) > 80
        self.assertTrue(red.any() and blue.any())
        self.assertLess(np.where(red)[1].mean(), np.where(blue)[1].mean())      # cat on the left
        self.assertLess(red.sum(), blue.sum())                                   # elephant drawn larger
        self.assertIn('left to right', info['subject'])


if __name__ == '__main__':
    unittest.main()
