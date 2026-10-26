"""Sudoku: solving the hardest known puzzles, unique-solution generation at each level, hardest-level puzzles, hints,
checking, and playing across a conversation."""
import random
import re
import unittest

from cael_unified import sudoku

INKALA = '8..........36......7..9.2...5...7.......457.....1...3...1....68..85...1..9....4..'


def cells(text):
    return [int(ch) if ch.isdigit() else 0 for ch in text]


class SudokuTests(unittest.TestCase):
    def test_hardest_known_puzzles_are_solved_uniquely(self):
        for name, puzzle in sudoku.FAMOUS.items():
            with self.subTest(name=name):
                grid = cells(puzzle)
                solutions = sudoku.exact_cover(grid, limit=2)
                self.assertEqual(len(solutions), 1)
                self.assertTrue(sudoku.valid_complete(solutions[0]))
                self.assertTrue(all(g in (0, s) for g, s in zip(grid, solutions[0])))
                self.assertEqual(sudoku.rate(grid)[0], 'expert')

    def test_generated_puzzles_have_one_solution_at_their_level(self):
        for level in ('easy', 'medium', 'hard'):
            with self.subTest(level=level):
                puzzle, got = sudoku.generate(level, seed=5)
                self.assertEqual(len(sudoku.exact_cover(puzzle, limit=2)), 1)
                self.assertEqual(got, level)

    def test_hardest_level_keeps_the_difficulty(self):
        puzzle, name = sudoku.hardest(seed=3)
        self.assertIn(name, sudoku.FAMOUS)
        self.assertEqual(len(sudoku.exact_cover(puzzle, limit=2)), 1)
        self.assertEqual(sum(1 for v in puzzle if v), sum(1 for ch in sudoku.FAMOUS[name] if ch.isdigit()))
        answer = sudoku.reply('lets play sudoku at the highest difficulty')
        self.assertEqual(answer['route'], 'chat/sudoku-new')
        self.assertIn('highest-level', answer['response'])

    def test_solve_hint_and_check(self):
        solved = sudoku.reply('solve this sudoku: ' + INKALA)
        self.assertIn('8 1 2 | 7 5 3 | 6 4 9', solved['response'])
        grid9 = '\n'.join(INKALA[i:i + 9].replace('.', '0') for i in range(0, 81, 9))
        self.assertEqual(sudoku.reply('Solve this sudoku:\n' + grid9)['route'], 'chat/sudoku-solve')
        hint = sudoku.reply('sudoku hint: 53..7....6..195....98....6.8...6...34..8.3..17...2...6.6....28....419..5....8..79')
        self.assertIn('**5**', hint['response'])
        solution = ''.join(map(str, sudoku.exact_cover(cells(INKALA))[0]))
        self.assertIn('Correct', sudoku.reply('is my sudoku right? ' + solution)['response'])
        wrong = solution[:-1] + ('1' if solution[-1] != '1' else '2')
        self.assertIn('Not quite', sudoku.reply('check my sudoku ' + wrong)['response'])
        self.assertIn('no solution', sudoku.reply('solve this sudoku ' + '11' + INKALA[2:])['response'])

    def test_playing_across_a_conversation(self):
        first = sudoku.reply('play sudoku, medium')
        history = [dict(role='user', content='play sudoku, medium'), dict(role='assistant', content=first['response'])]
        self.assertEqual(sudoku.reply('give me a hint', history)['route'], 'chat/sudoku-hint')
        self.assertEqual(sudoku.reply('solve it', history)['route'], 'chat/sudoku-solve')
        self.assertIsNone(sudoku.reply('Hello, how are you?', history))
        self.assertIsNone(sudoku.reply('What is the capital of France?'))


if __name__ == '__main__':
    unittest.main()
