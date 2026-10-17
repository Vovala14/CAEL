import unittest
from fractions import Fraction

from cael_unified import wordmath
from cael_unified.choice import choose, short_answers, standardise


def lm(*sums, chars=10):
    return [dict(sum_lnp=s, tokens=3, chars=chars) for s in sums]


class WordMathTests(unittest.TestCase):
    def test_common_one_and_two_step_problems(self):
        cases = {
            'Ava had 30 shells. Ben gave Ava 12 more. Now Ava had': 42,
            'Ava had 30 shells. Ava lost 7. Then Ava had': 23,
            'Ava put 6 stamps in each of 4 boxes. Altogether there were': 24,
            'Ava shared 24 beads equally among 4 friends. Each friend got': 6,
            'Ava had 30 cards. Ben had 8 fewer than Ava. So Ben had': 22,
            'Ava has 9 coins. Ben has twice as many coins as Ava. Ben has': 18,
            'Ava bought 20 pencils, then sold 4 and later received 9 more. Ava ended with': 25,
        }
        for text, expected in cases.items():
            answer = wordmath.solve_with_multiplier(text)
            if answer is None:
                answer = wordmath.solve(text)
            self.assertEqual(answer, Fraction(expected), text)

    def test_unclear_wording_abstains_instead_of_guessing(self):
        for text in ('The sky was blue and the grass was green.', 'Ava had 30 shells.', 'Ava had 30 shells and 5 friends liked them.'):
            self.assertIsNone(wordmath.match(text, [' 30 shells.', ' 35 shells.']), text)

    def test_match_needs_exactly_one_option(self):
        text = 'Ava had 30 shells. Ava found 5 more. Ava had'
        self.assertEqual(wordmath.match(text, [' 34 shells.', ' 35 shells.', ' 36 shells.']), 1)
        self.assertIsNone(wordmath.match(text, [' 35 shells.', ' 35 big shells.']))


class ChooserTests(unittest.TestCase):
    def test_arithmetic_overrides_the_language_model(self):
        index, details = choose('Sam had 10 marbles. Sam found 5 more. Sam had', [' 15 marbles.', ' 14 marbles.'], lm(-50, -1))
        self.assertEqual((index, details['route']), (0, 'exact-arithmetic'))

    def test_language_model_alone_without_evidence(self):
        index, details = choose('Question: Which is warm?\nAnswer:', [' ice', ' fire'], lm(-30, -10))
        self.assertEqual((index, details['route']), (1, 'language'))

    def test_evidence_is_weighted_in_for_short_answers_only(self):
        class Fixed:
            def scores(self, context, endings):
                return [5.0, 0.0]
        index, details = choose('Question: q\nAnswer:', [' a', ' b'], lm(-20, -10), Fixed(), weight=3.0)
        self.assertEqual((index, details['route']), (0, 'language+evidence'))
        long = [' ' + 'word ' * 20, ' ' + 'other ' * 20]
        self.assertFalse(short_answers(long))
        self.assertEqual(choose('Question: q\nAnswer:', long, lm(-20, -10), Fixed(), weight=3.0)[1]['route'], 'language')

    def test_standardise(self):
        self.assertEqual(standardise([1.0, 1.0]), [0.0, 0.0])
        values = standardise([1.0, 3.0])
        self.assertAlmostEqual(values[0], -1.0)
        self.assertAlmostEqual(values[1], 1.0)


if __name__ == '__main__':
    unittest.main()
