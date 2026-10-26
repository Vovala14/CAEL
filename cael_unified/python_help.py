"""Everyday Python help: tested functions for common tasks, and short explanations of Python basics. Never a neural model.

`recipe(text)` answers "Write a Python function that ..." for common tasks from a hand-written library. Every recipe
has examples, and the examples are run before the code is shown (by CAEL's bounded interpreter when it can, otherwise by
plain evaluation in a restricted namespace), so a recipe that does not pass its own examples is never offered.
`concept(text)` answers questions such as "What is a dictionary in Python?" or "How do I read a file in Python?".
"""
import re

# (name, request pattern, code, examples [(call, expected repr)], one-line description)
RECIPES = [
    ('reverse_string', r'revers\w* (?:a |the )?(?:string|text|word)', 'def reverse_string(s):\n    return s[::-1]\n',
     [("reverse_string('hello')", "'olleh'")], 'reverses a string with slicing'),
    ('reverse_list', r'revers\w* (?:a |the )?list', 'def reverse_list(items):\n    return items[::-1]\n',
     [('reverse_list([1, 2, 3])', '[3, 2, 1]')], 'returns the list in reverse order (the original is unchanged)'),
    ('is_palindrome', r'palindrome', "def is_palindrome(text):\n    cleaned = ''.join(ch.lower() for ch in text if ch.isalnum())\n    return cleaned == cleaned[::-1]\n",
     [("is_palindrome('racecar')", 'True'), ("is_palindrome('hello')", 'False'), ("is_palindrome('A man, a plan, a canal: Panama')", 'True')],
     'ignores case, spaces and punctuation'),
    ('factorial', r'factorial', 'def factorial(n):\n    result = 1\n    for i in range(2, n + 1):\n        result *= i\n    return result\n',
     [('factorial(5)', '120'), ('factorial(0)', '1')], 'multiplies 1 x 2 x ... x n (0! is 1)'),
    ('fibonacci', r'fibonacci', 'def fibonacci(n):\n    a, b = 0, 1\n    for _ in range(n):\n        a, b = b, a + b\n    return a\n',
     [('fibonacci(10)', '55'), ('fibonacci(1)', '1'), ('fibonacci(0)', '0')], 'returns the nth Fibonacci number (0, 1, 1, 2, 3, 5, ...)'),
    ('is_prime', r'\bprime\b', 'def is_prime(n):\n    if n < 2:\n        return False\n    i = 2\n    while i * i <= n:\n        if n % i == 0:\n            return False\n        i += 1\n    return True\n',
     [('is_prime(7)', 'True'), ('is_prime(8)', 'False'), ('is_prime(2)', 'True'), ('is_prime(1)', 'False')], 'checks divisors up to the square root'),
    ('sum_list', r'\bsum\w*\b.*\blist|\btotal of (?:a |the )?list|\badd (?:up )?(?:all )?(?:the )?numbers in a list', 'def sum_list(numbers):\n    return sum(numbers)\n',
     [('sum_list([1, 2, 3])', '6'), ('sum_list([])', '0')], 'adds up all numbers in the list (an empty list gives 0)'),
    ('find_largest', r'(?<!second )(?<!2nd )(?:largest|biggest|maximum|max) (?:number|value|item|element)?\s*(?:in|of|from) (?:a |the )?list', 'def find_largest(numbers):\n    return max(numbers)\n',
     [('find_largest([3, 9, 2])', '9')], 'returns the largest number in a non-empty list'),
    ('find_smallest', r'(?:smallest|minimum|min) (?:number|value|item|element)?\s*(?:in|of|from) (?:a |the )?list', 'def find_smallest(numbers):\n    return min(numbers)\n',
     [('find_smallest([3, 9, 2])', '2')], 'returns the smallest number in a non-empty list'),
    ('second_largest', r'second (?:largest|biggest|highest)', 'def second_largest(numbers):\n    distinct = sorted(set(numbers))\n    return distinct[-2]\n',
     [('second_largest([4, 1, 9, 7])', '7'), ('second_largest([5, 5, 3])', '3')], 'uses distinct values, so duplicates of the largest are skipped'),
    ('count_vowels', r'vowel', "def count_vowels(text):\n    return sum(1 for ch in text.lower() if ch in 'aeiou')\n",
     [("count_vowels('hello world')", '3')], 'counts a, e, i, o and u (upper or lower case)'),
    ('remove_duplicates', r'(?:remove|delete|drop) (?:the )?duplicates?|unique (?:items|values|elements)', 'def remove_duplicates(items):\n    return list(dict.fromkeys(items))\n',
     [('remove_duplicates([1, 2, 2, 3, 1])', '[1, 2, 3]')], 'keeps the first copy of each item, in the original order'),
    ('celsius_to_fahrenheit', r'celsius to fahrenheit|c to f\b', 'def celsius_to_fahrenheit(celsius):\n    return celsius * 9 / 5 + 32\n',
     [('celsius_to_fahrenheit(100)', '212.0'), ('celsius_to_fahrenheit(0)', '32.0')], 'F = C x 9/5 + 32'),
    ('fahrenheit_to_celsius', r'fahrenheit to celsius|f to c\b', 'def fahrenheit_to_celsius(fahrenheit):\n    return (fahrenheit - 32) * 5 / 9\n',
     [('fahrenheit_to_celsius(212)', '100.0')], 'C = (F - 32) x 5/9'),
    ('count_words', r'count\w* (?:the )?(?:number of )?words(?! .*(?:each|frequen|appear|occur))|how many words', 'def count_words(sentence):\n    return len(sentence.split())\n',
     [("count_words('the cat sat')", '3')], 'splits on whitespace and counts the pieces'),
    ('word_frequencies', r'(?:each|every) word (?:appears|occurs)|word (?:frequenc|count)\w*|how (?:many times|often) each word', 'def word_frequencies(text):\n    counts = {}\n    for word in text.lower().split():\n        counts[word] = counts.get(word, 0) + 1\n    return counts\n',
     [("word_frequencies('a b a')", "{'a': 2, 'b': 1}")], 'returns a dictionary of word -> count (lower-cased)'),
    ('is_leap_year', r'leap year', 'def is_leap_year(year):\n    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)\n',
     [('is_leap_year(2024)', 'True'), ('is_leap_year(1900)', 'False'), ('is_leap_year(2000)', 'True')], 'divisible by 4, except centuries not divisible by 400'),
    ('average', r'\baverage\b|\bmean\b', 'def average(numbers):\n    return sum(numbers) / len(numbers)\n',
     [('average([2, 4, 6])', '4.0')], 'sum divided by count (for a non-empty list)'),
    ('are_anagrams', r'anagram', "def are_anagrams(a, b):\n    clean = lambda s: sorted(s.replace(' ', '').lower())\n    return clean(a) == clean(b)\n",
     [("are_anagrams('listen', 'silent')", 'True'), ("are_anagrams('abc', 'abd')", 'False')], 'compares the sorted letters, ignoring spaces and case'),
    ('gcd', r'\bgcd\b|greatest common (?:divisor|factor)|highest common factor', 'def gcd(a, b):\n    while b:\n        a, b = b, a % b\n    return a\n',
     [('gcd(12, 18)', '6')], "Euclid's algorithm"),
    ('lcm', r'\blcm\b|least common multiple|lowest common multiple', 'def lcm(a, b):\n    x, y = a, b\n    while y:\n        x, y = y, x % y\n    return a * b // x\n',
     [('lcm(4, 6)', '12')], 'a x b divided by their greatest common divisor'),
    ('even_numbers', r'(?:only |all |just )?(?:the )?even numbers (?:from|in|of)|filter\w* even', 'def even_numbers(numbers):\n    return [n for n in numbers if n % 2 == 0]\n',
     [('even_numbers([1, 2, 3, 4])', '[2, 4]')], 'keeps the numbers divisible by 2'),
    ('odd_numbers', r'(?:only |all |just )?(?:the )?odd numbers (?:from|in|of)|filter\w* odd', 'def odd_numbers(numbers):\n    return [n for n in numbers if n % 2 != 0]\n',
     [('odd_numbers([1, 2, 3, 4])', '[1, 3]')], 'keeps the numbers not divisible by 2'),
    ('is_even', r'(?:check\w*|tell\w*|test\w*|determin\w*) (?:if |whether )?(?:a |the )?number is even|is (?:a )?number even', 'def is_even(n):\n    return n % 2 == 0\n',
     [('is_even(4)', 'True'), ('is_even(7)', 'False')], 'a number is even when dividing by 2 leaves no remainder'),
    ('capitalize_words', r'capitali[sz]\w* (?:every|each|all|the first letter of each) word|title case', 'def capitalize_words(sentence):\n    return \' \'.join(word.capitalize() for word in sentence.split())\n',
     [("capitalize_words('hello big world')", "'Hello Big World'")], 'capitalizes the first letter of every word'),
    ('flatten', r'flatten', 'def flatten(list_of_lists):\n    return [item for sub in list_of_lists for item in sub]\n',
     [('flatten([[1, 2], [3], []])', '[1, 2, 3]')], 'joins the inner lists into one list (one level deep)'),
    ('sort_numbers', r'\bsort\w* (?:a |the )?(?:list|numbers)', 'def sort_numbers(numbers):\n    return sorted(numbers)\n',
     [('sort_numbers([3, 1, 2])', '[1, 2, 3]')], 'returns a new sorted list; use sorted(numbers, reverse=True) for descending'),
    ('squares', r'square (?:of )?(?:each|every|all) (?:number|item|element)|squares? of (?:a |the )?(?:list|numbers)', 'def squares(numbers):\n    return [n * n for n in numbers]\n',
     [('squares([1, 2, 3])', '[1, 4, 9]')], 'squares each number with a list comprehension'),
    ('merge_dicts', r'merg\w* (?:two )?(?:dict|dictionar)', 'def merge_dicts(a, b):\n    return {**a, **b}\n',
     [("merge_dicts({'a': 1}, {'b': 2})", "{'a': 1, 'b': 2}")], 'values from the second dictionary win when a key is in both'),
    ('count_characters', r'count\w* (?:the )?(?:characters|letters)|how many characters', 'def count_characters(text):\n    return len(text)\n',
     [("count_characters('hello')", '5')], 'counts every character, including spaces'),
    ('count_occurrences', r'(?:count|how many times)\w* (?:a |an |each )?(?:character|letter|item|element|value) (?:appears|occurs)', 'def count_occurrences(sequence, item):\n    return sequence.count(item)\n',
     [("count_occurrences('banana', 'a')", '3'), ('count_occurrences([1, 2, 1], 1)', '2')], 'works for strings and lists'),
    ('is_sorted', r'(?:check\w* )?(?:if |whether )?(?:a |the )?list is sorted', 'def is_sorted(items):\n    return all(items[i] <= items[i + 1] for i in range(len(items) - 1))\n',
     [('is_sorted([1, 2, 2, 5])', 'True'), ('is_sorted([3, 1])', 'False')], 'checks each neighbouring pair'),
    ('fizzbuzz', r'fizz ?buzz', "def fizzbuzz(n):\n    result = []\n    for i in range(1, n + 1):\n        if i % 15 == 0:\n            result.append('FizzBuzz')\n        elif i % 3 == 0:\n            result.append('Fizz')\n        elif i % 5 == 0:\n            result.append('Buzz')\n        else:\n            result.append(str(i))\n    return result\n",
     [('fizzbuzz(5)', "['1', '2', 'Fizz', '4', 'Buzz']")], 'Fizz for multiples of 3, Buzz for 5, FizzBuzz for both'),
    ('binary_search', r'binary search', 'def binary_search(items, target):\n    low, high = 0, len(items) - 1\n    while low <= high:\n        mid = (low + high) // 2\n        if items[mid] == target:\n            return mid\n        if items[mid] < target:\n            low = mid + 1\n        else:\n            high = mid - 1\n    return -1\n',
     [('binary_search([1, 3, 5, 7], 5)', '2'), ('binary_search([1, 3, 5], 4)', '-1')], 'returns the index in a sorted list, or -1 if absent'),
    ('bubble_sort', r'bubble sort', 'def bubble_sort(items):\n    items = list(items)\n    for end in range(len(items) - 1, 0, -1):\n        for i in range(end):\n            if items[i] > items[i + 1]:\n                items[i], items[i + 1] = items[i + 1], items[i]\n    return items\n',
     [('bubble_sort([3, 1, 2])', '[1, 2, 3]')], 'repeatedly swaps neighbours that are out of order'),
    ('digit_sum', r'sum of (?:the )?digits|add (?:up )?(?:the )?digits', 'def digit_sum(n):\n    return sum(int(d) for d in str(abs(n)))\n',
     [('digit_sum(1234)', '10')], 'adds the digits of a whole number'),
    ('count_uppercase', r'(?:count\w*|how many) (?:the )?(?:upper ?case|capital) letters', 'def count_uppercase(text):\n    return sum(1 for ch in text if ch.isupper())\n',
     [("count_uppercase('Hello World')", '2')], 'counts capital letters'),
    ('is_number_positive', r'(?:check\w* )?(?:if |whether )?(?:a )?number is positive', 'def is_positive(n):\n    return n > 0\n',
     [('is_positive(3)', 'True'), ('is_positive(-1)', 'False')], 'True for numbers greater than zero'),
    ('swap', r'swap (?:two )?(?:variables|values|numbers)', 'def swap(a, b):\n    return b, a\n',
     [('swap(1, 2)', '(2, 1)')], 'Python swaps with tuple unpacking: a, b = b, a'),
    ('list_intersection', r'common (?:elements|items|values)|intersection of (?:two )?lists', 'def common_items(a, b):\n    return [x for x in dict.fromkeys(a) if x in set(b)]\n',
     [('common_items([1, 2, 3], [2, 3, 4])', '[2, 3]')], 'items in both lists, in the order of the first'),
    ('char_frequencies', r'(?:frequency|count) of (?:each )?(?:character|letter)|each (?:character|letter) (?:appears|occurs)', 'def char_frequencies(text):\n    counts = {}\n    for ch in text:\n        counts[ch] = counts.get(ch, 0) + 1\n    return counts\n',
     [("char_frequencies('aab')", "{'a': 2, 'b': 1}")], 'a dictionary of character -> count'),
    ('power', r'(?:raise|power of|to the power|exponent)', 'def power(base, exponent):\n    return base ** exponent\n',
     [('power(2, 10)', '1024')], 'uses the ** operator'),
    ('km_to_miles', r'kilomet\w* to miles|km to miles', 'def km_to_miles(km):\n    return km * 0.621371\n',
     [('round(km_to_miles(10), 2)', '6.21')], '1 km is about 0.621371 miles'),
    ('is_empty', r'(?:check\w* )?(?:if |whether )?(?:a |the )?(?:string|list|text) is empty|empty (?:string|list)', 'def is_empty(value):\n    return len(value) == 0\n',
     [("is_empty('')", 'True'), ("is_empty('a')", 'False'), ('is_empty([])', 'True')], 'works for strings, lists and dictionaries'),
    ('list_length', r'(?:length|size) of (?:a |the )?(?:list|string)|how many (?:items|elements) (?:are )?in (?:a |the )?list', 'def list_length(items):\n    return len(items)\n',
     [('list_length([1, 2, 3])', '3')], 'uses the built-in len()'),
    ('product', r'(?:multipl\w*|product of) (?:all )?(?:the )?(?:numbers|items|elements|values)|product of (?:a |the )?list', 'def product(numbers):\n    result = 1\n    for n in numbers:\n        result *= n\n    return result\n',
     [('product([2, 3, 4])', '24'), ('product([])', '1')], 'multiplies all numbers together (an empty list gives 1)'),
    ('reverse_words', r'revers\w* (?:the )?(?:order of )?(?:the )?words', "def reverse_words(sentence):\n    return ' '.join(sentence.split()[::-1])\n",
     [("reverse_words('one two three')", "'three two one'")], 'reverses the order of the words, not the letters'),
    ('remove_spaces', r'remov\w* (?:all )?(?:the )?(?:spaces|whitespace)', "def remove_spaces(text):\n    return text.replace(' ', '')\n",
     [("remove_spaces('a b c')", "'abc'")], 'deletes every space'),
    ('count_consonants', r'consonant', "def count_consonants(text):\n    return sum(1 for ch in text.lower() if ch.isalpha() and ch not in 'aeiou')\n",
     [("count_consonants('hello')", '3')], 'letters that are not vowels'),
    ('contains_substring', r'(?:contains?|includes?) (?:a |another )?(?:substring|word|string)|substring', 'def contains(text, part):\n    return part in text\n',
     [("contains('hello world', 'world')", 'True'), ("contains('hello', 'xyz')", 'False')], 'uses the in operator'),
    ('to_uppercase', r'(?:convert\w*|turn\w*|change\w*|make\w*) (?:a |the )?(?:string|text) (?:to|into) upper ?case', 'def to_uppercase(text):\n    return text.upper()\n',
     [("to_uppercase('hi')", "'HI'")], 'uses str.upper()'),
    ('to_lowercase', r'(?:convert\w*|turn\w*|change\w*|make\w*) (?:a |the )?(?:string|text) (?:to|into) lower ?case', 'def to_lowercase(text):\n    return text.lower()\n',
     [("to_lowercase('HI')", "'hi'")], 'uses str.lower()'),
    ('circle_area', r'area of (?:a )?circle', 'def circle_area(radius):\n    return 3.141592653589793 * radius ** 2\n',
     [('round(circle_area(2), 2)', '12.57')], 'pi x r squared'),
    ('rectangle_area', r'area of (?:a )?rectangle', 'def rectangle_area(width, height):\n    return width * height\n',
     [('rectangle_area(3, 4)', '12')], 'width x height'),
    ('list_to_string', r'(?:convert\w*|join\w*|turn\w*) (?:a )?list (?:of \w+ )?(?:to|into) (?:a )?string', "def list_to_string(items, separator=' '):\n    return separator.join(str(x) for x in items)\n",
     [("list_to_string(['a', 'b'])", "'a b'")], 'joins the items with a separator'),
    ('all_equal', r'(?:all|every) (?:the )?(?:items|elements|values) (?:are )?(?:equal|the same)', 'def all_equal(items):\n    return len(set(items)) <= 1\n',
     [('all_equal([2, 2, 2])', 'True'), ('all_equal([1, 2])', 'False')], 'True when the list has at most one distinct value'),
    ('count_positive', r'count\w* (?:the )?positive numbers', 'def count_positive(numbers):\n    return sum(1 for n in numbers if n > 0)\n',
     [('count_positive([1, -2, 3])', '2')], 'counts numbers greater than zero'),
    ('sum_of_squares', r'sum of (?:the )?squares', 'def sum_of_squares(numbers):\n    return sum(n * n for n in numbers)\n',
     [('sum_of_squares([1, 2, 3])', '14')], 'adds up each number squared'),
    ('first_and_last', r'first and last (?:items?|elements?)', 'def first_and_last(items):\n    return items[0], items[-1]\n',
     [('first_and_last([1, 2, 3])', '(1, 3)')], 'index 0 and index -1'),
    ('string_length_list', r'length of each (?:word|string)', 'def word_lengths(words):\n    return [len(w) for w in words]\n',
     [("word_lengths(['a', 'abc'])", '[1, 3]')], 'a list of lengths'),
]
ASK_FUNCTION = re.compile(r"(?i)\b(?:write|create|make|give me|code|implement|show me|define)\b.*\b(?:function|program|script|code|def)\b|"
                          r"\b(?:python|py)\b.*\b(?:function|code|program|script)\b|\bfunction (?:that|to|which)\b")


def verified(code, examples):
    """Run the recipe's examples; True only if every example gives the expected value."""
    space = {'__builtins__': {'sum': sum, 'max': max, 'min': min, 'len': len, 'sorted': sorted, 'set': set, 'list': list,
                              'dict': dict, 'range': range, 'str': str, 'int': int, 'abs': abs, 'all': all, 'round': round,
                              'enumerate': enumerate, 'zip': zip, 'repr': repr}}
    try:
        exec(compile(code, '<recipe>', 'exec'), space)
        return all(repr(eval(call, space)) == expected for call, expected in examples)
    except Exception:
        return False


# ---------------------------------------------------------------- composing simple functions from their description

NUMBER_TESTS = {'negative': ('is_negative', 'n < 0'), 'positive': ('is_positive', 'n > 0'), 'zero': ('is_zero', 'n == 0'),
                'even': ('is_even', 'n % 2 == 0'), 'odd': ('is_odd', 'n % 2 != 0'), 'a whole number': ('is_whole', 'n == int(n)'),
                'an integer': ('is_whole', 'n == int(n)')}
STRING_TESTS = {'digits': ('only_digits', 's.isdigit()'), 'numbers': ('only_digits', 's.isdigit()'), 'letters': ('only_letters', 's.isalpha()'),
                'alphabetic': ('only_letters', 's.isalpha()'), 'alphanumeric': ('is_alphanumeric', 's.isalnum()'),
                'lowercase': ('is_lowercase', 's.islower()'), 'lower case': ('is_lowercase', 's.islower()'),
                'uppercase': ('is_uppercase', 's.isupper()'), 'upper case': ('is_uppercase', 's.isupper()'),
                'spaces': ('only_spaces', 's.isspace()'), 'whitespace': ('only_spaces', 's.isspace()')}
TRANSFORMS = {'cube': ('cube', 'n ** 3'), 'square': ('square', 'n ** 2'), 'double': ('double', 'n * 2'), 'triple': ('triple', 'n * 3'),
              'half': ('half', 'n / 2'), 'absolute value': ('absolute_value', 'abs(n)'), 'negative': ('negate', '-n'),
              'opposite': ('negate', '-n'), 'square root': ('square_root', 'n ** 0.5'), 'reciprocal': ('reciprocal', '1 / n')}
AGGREGATES = {'sum': ('sum({x})', 'sum'), 'total': ('sum({x})', 'sum'), 'average': ('sum({x}) / len({x})', 'average'),
              'mean': ('sum({x}) / len({x})', 'average'), 'count': ('len({x})', 'count'), 'number': ('len({x})', 'count'),
              'maximum': ('max({x})', 'max'), 'max': ('max({x})', 'max'), 'largest': ('max({x})', 'max'), 'biggest': ('max({x})', 'max'),
              'minimum': ('min({x})', 'min'), 'min': ('min({x})', 'min'), 'smallest': ('min({x})', 'min')}
FILTERS = {'even': 'n % 2 == 0', 'odd': 'n % 2 != 0', 'positive': 'n > 0', 'negative': 'n < 0'}
POSITIONS = {'first': ('first', 'items[0]'), 'last': ('last', 'items[-1]'), 'second': ('second', 'items[1]'),
             'middle': ('middle', 'items[len(items) // 2]')}
STRING_COUNTS = {'characters': ('len(s)', 'characters'), 'letters': ('sum(1 for ch in s if ch.isalpha())', 'letters'),
                 'digits': ('sum(1 for ch in s if ch.isdigit())', 'digits'), 'spaces': ("s.count(' ')", 'spaces'),
                 'words': ('len(s.split())', 'words'), 'vowels': ("sum(1 for ch in s.lower() if ch in 'aeiou')", 'vowels'),
                 'uppercase letters': ('sum(1 for ch in s if ch.isupper())', 'uppercase'), 'lowercase letters': ('sum(1 for ch in s if ch.islower())', 'lowercase'),
                 'sentences': ("sum(s.count(p) for p in '.!?')", 'sentences')}


def compose(text):
    """Build a small function from the request's own wording; None when it is not one of these shapes."""
    t = re.sub(r'\s+', ' ', text.lower())
    sample_numbers, sample_text = '[3, -2, 8, 5, -7, 10]', "'Hello World 42'"
    m = re.search(r'(?:check\w*|test\w*|tell\w*|determin\w*|return\w*|see) (?:if|whether) (?:a |the |an )?(?:given )?number is (?:a )?'
                  r'(negative|positive|zero|even|odd|a whole number|an integer|divisible by (\d+)|greater than (-?\d+)|less than (-?\d+)|'
                  r'between (-?\d+) and (-?\d+))', t)
    if m:
        kind = m.group(1)
        if kind in NUMBER_TESTS:
            name, body = NUMBER_TESTS[kind]
        elif kind.startswith('divisible'):
            name, body = f'is_divisible_by_{m.group(2)}', f'n % {m.group(2)} == 0'
        elif kind.startswith('greater'):
            name, body = 'is_greater', f'n > {m.group(3)}'
        elif kind.startswith('less'):
            name, body = 'is_less', f'n < {m.group(4)}'
        else:
            name, body = 'is_between', f'{m.group(5)} <= n <= {m.group(6)}'
        return f'def {name}(n):\n    return {body}\n', [f'{name}(5)', f'{name}(-4)', f'{name}(0)']
    m = re.search(r'(?:check\w*|test\w*|return\w*) (?:if|whether) (?:a |the )?(?:string|text|word) (?:contains only|is all|has only|consists of(?: only)?|is (?:made of|only)|is) '
                  r'(digits|numbers|letters|alphabetic|alphanumeric|lowercase|lower case|uppercase|upper case|spaces|whitespace)', t)
    if m:
        name, body = STRING_TESTS[m.group(1)]
        return f'def {name}(s):\n    return {body}\n', [f"{name}('12345')", f"{name}('abc')", f"{name}('ABC')"]
    m = re.search(r'(?:check\w*|test\w*) (?:if|whether) (?:a |the )?(?:string|text|word) (starts|begins|ends) with', t)
    if m:
        name = 'starts_with' if m.group(1) in ('starts', 'begins') else 'ends_with'
        method = 'startswith' if name == 'starts_with' else 'endswith'
        return f'def {name}(s, part):\n    return s.{method}(part)\n', [f"{name}('python', 'py')", f"{name}('python', 'on')"]
    m = re.search(r'(?:return\w*|calculat\w*|comput\w*|find\w*|get\w*) (?:the )?(cube|square root|square|double|triple|half|absolute value|negative|opposite|reciprocal) of (?:a |the |any )?(?:given )?number', t)
    if m:
        name, body = TRANSFORMS[m.group(1)]
        return f'def {name}(n):\n    return {body}\n', [f'{name}(3)', f'{name}(-4)']
    m = re.search(r'(sum|total|average|mean|count|number|maximum|max|largest|biggest|minimum|min|smallest) of (?:all )?(?:the )?'
                  r'(even|odd|positive|negative) (?:numbers|values|items|elements|integers)(?: in| of| from) (?:a |the )?list', t)
    if m:
        template, label = AGGREGATES[m.group(1)]
        condition = FILTERS[m.group(2)]
        name = f'{label}_of_{m.group(2)}'
        picked = f'[n for n in numbers if {condition}]'
        return f'def {name}(numbers):\n    chosen = {picked}\n    return {template.format(x="chosen")}\n', [f'{name}({sample_numbers})']
    m = re.search(r'(?:return\w*|get\w*|find\w*) (?:the )?(first|last|second|middle) (?:element|item|value|number) (?:of|in|from) (?:a |the )?list', t)
    if m:
        label, body = POSITIONS[m.group(1)]
        return f'def {label}_item(items):\n    return {body}\n', [f'{label}_item([10, 20, 30, 40, 50])']
    m = re.search(r'(?:count\w*|how many|number of) (?:the )?(?:number of )?(characters|letters|digits|spaces|words|vowels|uppercase letters|lowercase letters|sentences) '
                  r'(?:are )?(?:in|of) (?:a |the )?(?:string|text|sentence|word)', t)
    if m:
        body, label = STRING_COUNTS[m.group(1)]
        return f'def count_{label}(s):\n    return {body}\n', [f'count_{label}({sample_text})']
    return None


def composed(text):
    built = compose(text)
    if not built:
        return None
    code, calls = built
    space = {'__builtins__': {'sum': sum, 'max': max, 'min': min, 'len': len, 'abs': abs, 'int': int}}
    try:
        exec(compile(code, '<composed>', 'exec'), space)
        shown = '\n'.join(f'{call}  # {eval(call, space)!r}' for call in calls)
    except Exception:
        return None
    return dict(route='chat/code-composed', sources=[],
                response=f'```python\n{code}```\nExamples (run):\n```python\n{shown}\n```',
                details='Built from the wording of the request by CAEL\'s Python templates and run on the examples shown. No neural model.')


def recipe(text):
    if not ASK_FUNCTION.search(text) or re.search(r'(?i)\b(?:javascript|java\b|c\+\+|rust|go\b|ruby|php|sql)\b', text):
        return None
    if re.search(r'(?i)```|\bdef \w+\(|\bexamples?:', text):
        return None                                    # the user's own code or examples: the synthesizer handles it
    answer = composed(text)
    if answer is not None:
        return answer
    low = text.lower()
    hits = [(len(m.group(0)), r) for r in RECIPES for m in [re.search(r[1], low)] if m]
    if not hits:
        return None
    hits.sort(key=lambda h: -h[0])
    name, _, code, examples, note = hits[0][1]
    if not verified(code, examples):
        return None
    shown = '\n'.join(f'{call}  # {expected}' for call, expected in examples)
    return dict(route='chat/code-recipe', sources=[],
                response=f'```python\n{code}```\nIt {note}.\n\nExamples (checked):\n```python\n{shown}\n```',
                details='A tested function from CAEL\'s hand-written Python library; its examples were run before showing it. '
                        'No neural model.')


# ---------------------------------------------------------------- explanations

CONCEPTS = [
    (r'what (?:is|are) (?:a )?lists?\b', 'A **list** is an ordered, changeable collection of items: `fruits = ["apple", "banana", "cherry"]`. '
     'Access items by position (`fruits[0]` is "apple"), add with `fruits.append("kiwi")`, and get the length with `len(fruits)`.'),
    (r'what (?:is|are) (?:a )?dict(?:ionary|ionaries)?\b', 'A **dictionary** stores key-value pairs: `ages = {"Ann": 30, "Bob": 25}`. '
     'Look up a value by its key (`ages["Ann"]` is 30), add or change one with `ages["Cid"] = 40`, and loop with `for name, age in ages.items():`.'),
    (r'what (?:is|are) (?:a )?tuples?\b', 'A **tuple** is an ordered collection that cannot be changed after it is made (immutable): `point = (3, 4)`. '
     'Use it for fixed groups of values; `point[0]` is 3.'),
    (r'(?:difference|differences) between (?:a )?(?:list|tuple)s? and (?:a )?(?:list|tuple)s?|list vs\.? tuple|tuple vs\.? list',
     'A **list** is mutable (you can change, add or remove items: `[1, 2, 3]`); a **tuple** is immutable (fixed once created: `(1, 2, 3)`). '
     'Tuples are slightly faster and can be dictionary keys; lists are better when the contents change.'),
    (r'what (?:is|are) (?:a )?sets?\b', 'A **set** is an unordered collection with no duplicates: `colors = {"red", "blue"}`. '
     '`set([1, 1, 2])` gives `{1, 2}`; check membership with `"red" in colors`.'),
    (r'what (?:is|are) (?:a )?(?:for )?loops?\b|what does a for loop do', 'A **for loop** repeats code for each item in a sequence:\n```python\nfor i in range(3):\n    print(i)   # prints 0, 1, 2\n```\nA **while loop** repeats as long as a condition is true.'),
    (r'what (?:is|are) (?:a )?while loops?\b', 'A **while loop** repeats while a condition is true:\n```python\nn = 3\nwhile n > 0:\n    print(n)\n    n -= 1\n```'),
    (r'what (?:is|are) (?:a )?functions?\b', 'A **function** is a reusable block of code that you define once and call by name:\n```python\ndef greet(name):\n    return "Hello, " + name\n\nprint(greet("Ann"))   # Hello, Ann\n```'),
    (r'what (?:is|are) (?:a )?class(?:es)?\b', 'A **class** is a blueprint for objects that bundle data and behaviour:\n```python\nclass Dog:\n    def __init__(self, name):\n        self.name = name\n    def bark(self):\n        return self.name + " says woof"\n\nprint(Dog("Rex").bark())\n```'),
    (r'what (?:is|are) (?:a )?(?:variable)s?\b', 'A **variable** is a name that refers to a value: `age = 30`. Python works out the type itself, and you can reassign it later.'),
    (r'what (?:is|are) (?:a )?strings?\b', 'A **string** is text in quotes: `"hello"` or `\'hello\'`. Strings can be joined with `+`, sliced with `s[0:3]`, and changed with methods like `s.upper()`.'),
    (r'what (?:is|are) (?:an? )?(?:if statement|conditional)s?\b', 'An **if statement** runs code only when a condition is true:\n```python\nif age >= 18:\n    print("adult")\nelif age >= 13:\n    print("teen")\nelse:\n    print("child")\n```'),
    (r'what (?:is|are) (?:an? )?(?:modules?|librar(?:y|ies)|packages?)\b', 'A **module** is a Python file you can import; a **package** is a collection of modules. Import with `import math` and use `math.sqrt(16)`; install third-party packages with `pip install name`.'),
    (r'what (?:is|are) (?:an? )?exceptions?\b|what is try except', 'An **exception** is an error raised while the program runs. Handle it with try/except:\n```python\ntry:\n    x = int("abc")\nexcept ValueError:\n    print("not a number")\n```'),
    (r'what does (?:the )?len(?:\(\))? (?:function )?do|what is len\b', '`len()` returns the **length** of something: the number of items in a list, characters in a string or keys in a dictionary. `len([1, 2, 3])` is 3 and `len("hi")` is 2.'),
    (r'what does (?:the )?range(?:\(\))? (?:function )?do|what is range\b', '`range()` makes a sequence of numbers: `range(5)` is 0 to 4, `range(1, 11)` is 1 to 10, and `range(0, 10, 2)` counts by twos. Use `list(range(5))` to see them.'),
    (r'what does (?:the )?print(?:\(\))? (?:function )?do', '`print()` shows values on the screen: `print("Hello")` or `print("Total:", 5)`.'),
    (r'what (?:is|does) (?:a )?return\b|what does return do', '`return` ends a function and sends a value back to the caller: `def double(x): return x * 2` then `double(4)` gives 8.'),
    (r'how (?:do|can|to) (?:i |you )?read (?:a |from a |the )?(?:text )?file', 'Read a file with `open()` inside a `with` block, which closes it for you:\n```python\nwith open("notes.txt", encoding="utf-8") as f:\n    text = f.read()          # the whole file\n# or line by line:\nwith open("notes.txt", encoding="utf-8") as f:\n    for line in f:\n        print(line.strip())\n```'),
    (r'how (?:do|can|to) (?:i |you )?write (?:to )?(?:a |the )?(?:text )?file|save (?:text )?to a file', 'Write a file with `open(..., "w")` (or `"a"` to append):\n```python\nwith open("notes.txt", "w", encoding="utf-8") as f:\n    f.write("Hello\\n")\n```'),
    (r'how (?:do|can|to) (?:i |you )?install (?:a )?(?:python )?(?:package|library|module)|\bpip install\b|what is pip',
     'Install a package with **pip** from a terminal: `pip install requests` (or `python -m pip install requests`). Then `import requests` in your code.'),
    (r'how (?:do|can|to) (?:i |you )?(?:get|read|ask for|take) (?:the )?(?:user )?input', 'Use `input()`, which always returns text:\n```python\nname = input("What is your name? ")\nage = int(input("Your age: "))   # convert to a number\nprint("Hello,", name)\n```'),
    (r'how (?:do|can|to) (?:i |you )?(?:make|create|get) a list of numbers from (\d+) to (\d+)', None),
    (r'how (?:do|can|to) (?:i |you )?print hello world|hello world (?:in|program)', '```python\nprint("Hello, World!")\n```'),
    (r'how (?:do|can|to) (?:i |you )?(?:convert|turn|change) (?:a )?string (?:in)?to (?:an? )?(?:int|integer|number)', 'Use `int()`: `int("42")` gives 42; `float("3.5")` gives 3.5. Wrap it in try/except ValueError if the text might not be a number.'),
    (r'how (?:do|can|to) (?:i |you )?(?:add|append) (?:an? )?(?:item|element|value)s? to (?:a )?list', 'Use `append` for one item and `extend` for several: `items.append(4)`, `items.extend([5, 6])`, or insert at a position with `items.insert(0, "first")`.'),
    (r'how (?:do|can|to) (?:i |you )?(?:loop|iterate) (?:over|through) (?:a )?dict', '```python\nfor key, value in ages.items():\n    print(key, value)\n```\nUse `.keys()` for keys only and `.values()` for values only.'),
    (r'how (?:do|can|to) (?:i |you )?(?:sort) (?:a )?list', 'Use `sorted(items)` for a new sorted list or `items.sort()` to sort in place; add `reverse=True` for descending order or `key=len` to sort by length.'),
    (r'how (?:do|can|to) (?:i |you )?(?:import)', 'Use `import math` (then `math.pi`), `from math import sqrt` (then `sqrt(9)`), or `import numpy as np` for a shorter name.'),
    (r'how (?:do|can|to) (?:i |you )?(?:comment)', 'Start a comment with `#`: everything after it on that line is ignored. For longer notes, use several `#` lines or a docstring `"""..."""` at the top of a function.'),
    (r'how (?:do|can|to) (?:i |you )?(?:run|start) (?:a )?python (?:file|script|program)', 'Save the code as `script.py` and run `python script.py` in a terminal (on some systems `python3 script.py`).'),
    (r'what is python\b', '**Python** is a popular, easy-to-read programming language used for web development, data analysis, automation, AI and teaching. Programs are plain text files ending in `.py`.'),
]


def concept(text):
    t = re.sub(r'\s+', ' ', text.lower().strip().rstrip('?.!'))
    if not re.search(r'\bpython\b|\bpip\b|\blen\b|\brange\b|\bprint\b|\bfor loop|\bwhile loop|\bdictionar|\btuple|\blist\b|\bclass\b|'
                     r'\bfunction\b|\bmodule|\bexception|\bstring\b|\bvariable|\bif statement|\binput\b|\bhello world|\bimport\b|\bfile\b', t):
        return None
    python_context = bool(re.search(r'\bpython\b|\bpip\b|\bcode\b|\bprogramming\b', t))
    for pattern, answer in CONCEPTS:
        m = re.search(pattern, t)
        if not m:
            continue
        # A bare "what is a list" without Python context could be about anything: only coding-specific patterns.
        if not python_context and not re.search(r'len|range|print|pip|for loop|while loop|dictionar|tuple|hello world|try except|exception', pattern):
            continue
        if answer is None:                             # "a list of numbers from 1 to 10"
            start, end = int(m.group(1)), int(m.group(2))
            answer = f'Use `range`, which stops before its end value:\n```python\nnumbers = list(range({start}, {end + 1}))\nprint(numbers)\n```'
        return dict(route='chat/python-help', sources=[], response=answer,
                    details='From CAEL\'s hand-written Python guide. No neural model.')
    return None


def reply(text):
    return recipe(text) or concept(text)
