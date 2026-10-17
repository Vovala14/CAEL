import unittest

from cael_image.request import parse

WORDS = {'car': ['car', 'cars'], 'cat': ['cat', 'cats'], 'orange': ['orange', 'oranges'], 'apple': ['apple', 'apples'],
         'beach': ['beach'], 'bicycle': ['bicycle', 'bicycles']}


class PictureRequestTests(unittest.TestCase):
    def test_attributes_are_understood(self):
        request = parse('draw two red cars on a beach', WORDS)
        self.assertEqual((request['subject'], request['count'], request['colour'], request['background']), ('car', 2, 'red', 'beach'))
        self.assertEqual(parse('a cartoon cat', WORDS)['style'], 2)
        self.assertEqual(parse('a car, side view', WORDS)['style'], 1)
        self.assertEqual(parse('photo of a green apple', WORDS)['colour'], 'green')

    def test_orange_is_a_colour_before_another_subject(self):
        self.assertEqual(parse('an orange cat', WORDS)[('subject')], 'cat')
        self.assertEqual(parse('an orange cat', WORDS)['colour'], 'orange')
        self.assertEqual(parse('an orange', WORDS)['subject'], 'orange')

    def test_unsupported_parts_are_reported_not_dropped(self):
        self.assertTrue(parse('draw 5 cats', WORDS)['notes'])
        with self.assertRaises(ValueError):
            parse('draw a dragon', WORDS)


if __name__ == '__main__':
    unittest.main()
