"""Everyday Python help (tested function library, Python basics) and everyday reasoning solvers. Offline."""
import unittest

from cael_unified import python_help, everyday_reasoning as er


class PythonHelpTests(unittest.TestCase):
    def test_every_recipe_passes_its_own_examples(self):
        for name, _, code, examples, _ in python_help.RECIPES:
            with self.subTest(name=name):
                self.assertTrue(python_help.verified(code, examples))

    def test_requests_pick_the_right_recipe(self):
        for text, name in (('Write a Python function to reverse a string.', 'def reverse_string'),
                           ('Write a Python function to find the second largest number in a list.', 'def second_largest'),
                           ('Write a Python function to find the largest number in a list.', 'def find_largest'),
                           ('Write a Python function that merges two dictionaries.', 'def merge_dicts'),
                           ('Write a Python function that counts how many times each word appears in a text.', 'def word_frequencies'),
                           ('Write a Python function that counts the words in a sentence.', 'def count_words'),
                           ('Write a Python function that multiplies all numbers in a list.', 'def product')):
            with self.subTest(text=text):
                self.assertIn(name, python_help.recipe(text)['response'])

    def test_simple_functions_are_composed_from_the_description(self):
        for text, code in (('Write a Python function to check if a string contains only digits.', 's.isdigit()'),
                           ('Write a Python function that returns the sum of the even numbers in a list.', 'n % 2 == 0'),
                           ('Write a Python function that checks if a number is negative.', 'n < 0'),
                           ('Write a python function that returns the cube of a number.', 'n ** 3'),
                           ('Write a Python function that checks if a number is divisible by 3.', 'n % 3 == 0'),
                           ('Write a Python function to count the number of vowels in a string.', 'aeiou')):
            with self.subTest(text=text):
                answer = python_help.recipe(text)
                self.assertEqual(answer['route'], 'chat/code-composed')
                self.assertIn(code, answer['response'])

    def test_user_code_and_other_languages_are_left_to_other_tools(self):
        self.assertIsNone(python_help.recipe('Write a JavaScript function to reverse a string.'))
        self.assertIsNone(python_help.recipe('Write a function with examples: f(1) = 2, f(2) = 4'))
        self.assertIsNone(python_help.recipe('What is the capital of France?'))

    def test_python_basics(self):
        for text, word in (('What is a dictionary in Python?', 'key'), ('How do I read a file in Python?', 'open('),
                           ('How do I install a package in Python?', 'pip install'), ('How do I get user input in Python?', 'input('),
                           ('How do I make a list of numbers from 1 to 10 in Python?', 'range(1, 11)'),
                           ('What is the difference between a list and a tuple in Python?', 'immutable')):
            with self.subTest(text=text):
                self.assertIn(word, python_help.concept(text)['response'])
        self.assertIsNone(python_help.concept('What is a list of famous painters?'))


class ReasoningTests(unittest.TestCase):
    def check(self, text, expected):
        answer = er.reply(text)
        self.assertIsNotNone(answer, text)
        self.assertIn(expected, answer['response'], text)

    def test_word_problems(self):
        self.check('If I have 5 apples and eat 2, how many apples do I have left?', '**3**')
        self.check('If a ticket costs 7 dollars, how much do 3 tickets cost?', '**21**')
        self.check('I have 20 dollars and spend 7 dollars on lunch. How much money do I have left?', '**13**')
        self.check('Emma is three times as old as Leo. Leo is 4. How old is Emma?', '**12**')
        self.check('A car goes 50 km/h for 3 hours. How far does it travel?', '**150 km**')
        self.check('If y - 4 = 6, what is y?', 'y = 10')
        self.check('A bag has 4 green apples and 5 red apples. How many apples are in the bag?', '**9**')
        self.check('It takes 2 hours to dry one towel outside. How long do 4 towels take to dry together outside?', '2 hours')

    def test_days_time_and_numbers(self):
        self.check('What day comes before Thursday?', 'Wednesday')
        self.check('If today is Sunday, what day will it be in 2 days?', 'Tuesday')
        self.check('What time will it be 3 hours after 10:30 am?', '1:30 pm')
        self.check('How long is it from 2:30 to 4:15?', '1 hour and 45 minutes')
        self.check('Which is smaller, 0.7 or 0.65?', '**0.65**')
        self.check("How many s's are in the word mississippi?", '**4**')

    def test_sequences_and_puzzles(self):
        self.check('What comes next: 3, 6, 12, 24?', '**48**')
        self.check('What comes next in the sequence 1, 1, 2, 3, 5, 8?', '**13**')
        self.check('What is the next letter: B, D, F, H?', '**J**')
        self.check('Which number is the odd one out: 3, 5, 8, 7?', '**8**')
        self.check('Maria is the mother of Pedro. Pedro is the father of Lucas. Who is the grandmother of Lucas?', '**Maria**')
        self.check('Jake put the ball in the box. Then he moved it to the shelf. Where is the ball?', 'shelf')
        self.check('The book is on the desk. The desk is in the bedroom. Where is the book?', 'bedroom')

    def test_other_questions_are_left_alone(self):
        for text in ('The pump pumps at a constant rate of 25 milliliters per sec for 2 mins. How many L does the pump pump?',
                     'What is the capital of France?', 'How are you?', 'Where is Paris?'):
            with self.subTest(text=text):
                self.assertIsNone(er.reply(text))


if __name__ == '__main__':
    unittest.main()
