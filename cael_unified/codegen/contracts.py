"""Compose ordinary Python from explicit typed operation contracts.

An authored symbolic adapter, not a language model or stored benchmark answers.
The example-driven counted program search remains available in chat.py.
"""
import ast
import keyword
import re


def emit(name, params, body, note):
    code = f'def {name}({params}):\n' + '\n'.join('    ' + line if line else '' for line in body.splitlines()) + '\n'
    ast.parse(code)
    return dict(route='chat/code-composed', response=f'```python\n{code}```\n{note}', sources=[],
                details='Authored non-neural semantic contracts composed into Python statements. '
                        'No neural model, internet, benchmark answer lookup, or execution of user code. '
                        'This is algorithm composition, not a newly trained language checkpoint.')


def reply(text):
    if len(text) > 1800 or '```' in text:
        return None
    t = ' '.join(text.lower().split())
    # Inflections map to the same operation, not separate per-prompt rules.
    t = re.sub(r'\b(?:adds?|adding|add up|total(?:s|ing)?)\b', 'sum', t)
    t = re.sub(r'\b(?:counts|counting)\b', 'count', t)
    if not re.search(r'\b(?:write|implement|create|make|build|generate|give me|how (?:do|can) i|how to)\b', t) or not re.search(r'\b(?:python|function|code|program)\b', t):
        return None
    if re.search(r'\b(?:without using|do not use|in[- ]place|numpy|pandas|async|yield|generator|files?|threads?)\b', t):
        return None
    chosen = re.search(r'\b(?:named|called)\s+`?([a-zA-Z_]\w*)', text, re.I)
    custom = chosen[1] if chosen and not keyword.iskeyword(chosen[1]) else None
    make = lambda name, params, body, note: emit(custom or name, params, body, note)

    if re.search(r'\bfibonacci\b', t) and not re.search(r'\bsum|even|odd|prime\b', t):
        sequence = bool(re.search(r'\bfirst|terms|sequence|list\b', t))
        body = "if not isinstance(n, int) or isinstance(n, bool) or n < 0:\n    raise ValueError('n must be a nonnegative integer')\na, b = 0, 1\n"
        if sequence:
            body += 'result = []\nfor _ in range(n):\n    result.append(a)\n    a, b = b, a + b\nreturn result'
        else:
            body += 'for _ in range(n):\n    a, b = b, a + b\nreturn a'
        return make('fibonacci', 'n', body, 'Uses F(0)=0 and F(1)=1. ' + ('Returns the first n terms.' if sequence else 'Returns F(n), using constant auxiliary space.'))
    if re.search(r'\bcount\w*\b', t) and re.search(r'\bvowels?\b', t) and not re.search(r'\blist|array|each word\b', t):
        letters = 'aeiou' if 'lowercase only' in t else 'AEIOU' if 'uppercase only' in t else 'aeiouAEIOU'
        return make('count_vowels', 'text', "return sum(char in '" + letters + "' for char in text)", 'Counts English A/E/I/O/U; y is not counted as a vowel. Case policy follows the request, defaulting to both cases.')
    if re.search(r'\bmerge\b', t) and re.search(r'\btwo sorted (?:lists|arrays)\b', t):
        return make('merge_sorted', 'a, b', 'i = j = 0\nresult = []\nwhile i < len(a) and j < len(b):\n    if a[i] <= b[j]:\n        result.append(a[i])\n        i += 1\n    else:\n        result.append(b[j])\n        j += 1\nreturn result + list(a[i:]) + list(b[j:])', 'Assumes both inputs are ascending sorted. Keeps duplicates and runs in O(len(a)+len(b)).')
    if re.search(r'\bsort\b', t) and re.search(r'\bdictionary|dict\b', t) and re.search(r'\bkeys?\b', t):
        reverse = bool(re.search(r'\bdescending|reverse\b', t))
        return make('sort_by_key', 'mapping', 'return dict(sorted(mapping.items(), reverse=' + str(reverse) + '))', 'Returns a new dictionary ordered by its keys.')

    if re.search(r'\b(?:odd|even)\b', t) and re.search(r'\b(?:check|test|determine|whether)\b', t) and not re.search(r'\blist|array|sum|product|count\b', t):
        odd = bool(re.search(r'\bodd\b', t))
        if odd and 'even' in t:
            return None
        return make('is_odd' if odd else 'is_even', 'n', 'return n % 2 ' + ('!=' if odd else '==') + ' 0', 'Tests the requested parity of an integer.')
    if re.search(r'\bprime\b', t) and re.search(r'\b(?:check|test|determine|whether)\b', t) and not re.search(r'\blist|array|sum|product|count\b', t):
        return make('is_prime', 'n', 'from math import isqrt\nif n < 2:\n    return False\nfor divisor in range(2, isqrt(n) + 1):\n    if n % divisor == 0:\n        return False\nreturn True', 'Trial division through the exact integer square root; integers below 2 are not prime.')

    if re.search(r'\bbalanced\b|\bmatching (?:brackets|parentheses)\b', t) and re.search(r'\b(?:brackets|parentheses|parenthesis)\b', t):
        pairs = "{')': '('}" if 'parenthes' in t and 'bracket' not in t else "{')': '(', ']': '[', '}': '{'}"
        return make('balanced_brackets', 'text', f"pairs = {pairs}\nstack = []\nfor char in text:\n    if char in pairs.values():\n        stack.append(char)\n    elif char in pairs:\n        if not stack or stack.pop() != pairs[char]:\n            return False\nreturn not stack", 'Checks nesting and matching; ignores non-bracket characters.')
    if 'binary search' in t:
        return make('binary_search', 'items, target', 'from bisect import bisect_left\nindex = bisect_left(items, target)\nreturn index if index < len(items) and items[index] == target else -1', 'Assumes ascending sorted input. Returns the first matching index, or -1.')
    if re.search(r'\btwo[- ]sum\b', t):
        if re.search(r'\bvalues\b', t) and not re.search(r'\bindices|indexes\b', t):
            return None
        return make('two_sum', 'numbers, target', 'seen = {}\nfor index, value in enumerate(numbers):\n    complement = target - value\n    if complement in seen:\n        return [seen[complement], index]\n    seen[value] = index\nreturn None', 'Returns two distinct indices, or None when no pair exists. Runs in O(n) expected time.')
    if re.search(r'\b(?:frequenc\w*|count (?:each|every)|occurrences of each)\b', t):
        words = bool(re.search(r'\bwords?\b', t))
        chars = bool(re.search(r'\bcharacters?|letters?\b', t))
        if words or chars or re.search(r'\b(?:list|items|elements)\b', t):
            prep = 'items.split()' if words else 'items'
            if re.search(r'\b(?:ignor(?:e|ing) case|case[- ]insensitive|lowercase)\b', t):
                if not (words or chars):
                    return None
                prep = 'items.lower().split()' if words else 'items.lower()'
            if words and re.search(r'\bignor(?:e|ing) punctuation\b', t):
                prep = "re.findall(r'\\b\\w+\\b', " + ('items.lower()' if 'lower()' in prep else 'items') + ')'
                imports = 'from collections import Counter\nimport re\n'
                note = 'Word tokens contain letters, digits and underscores; punctuation separates tokens.'
            else:
                imports = 'from collections import Counter\n'
                note = 'Words are separated by whitespace; punctuation is retained.' if words else ''
            return make('frequencies', 'items', imports + 'return dict(Counter(' + prep + '))', 'Returns an item-to-count dictionary. ' + note)
    if 'palindrome' in t and re.search(r'\b(?:ignore|ignoring|case[- ]insensitive|alphanumeric)\b', t):
        prep = 'text.casefold()' if re.search(r'\bcase|case[- ]insensitive\b', t) else 'text'
        lines = ['value = ' + prep]
        if re.search(r'\b(?:punctuation|alphanumeric|non[- ]alphanumeric)\b', t):
            lines.append("value = ''.join(char for char in value if char.isalnum())")
        elif re.search(r'\bspaces?|whitespace\b', t):
            lines.append("value = ''.join(value.split())")
        lines.append('return value == value[::-1]')
        return make('is_palindrome', 'text', '\n'.join(lines), 'Applies the requested normalization, then compares against the reversed text.')
    if 'flatten' in t and re.search(r'\b(?:recursively|recursive|arbitrarily|deeply|any depth)\b', t):
        return make('flatten', 'items', 'result = []\nstack = list(reversed(items))\nwhile stack:\n    item = stack.pop()\n    if isinstance(item, (list, tuple)):\n        stack.extend(reversed(item))\n    else:\n        result.append(item)\nreturn result', 'Flattens finite nested lists/tuples, preserves order, and leaves strings intact.')
    if re.search(r'\bchunks?|batches\b', t) and re.search(r'\blist|array|sequence\b', t):
        size = re.search(r'\b(?:of|size)\s+(\d{1,5})\b', t)
        param = 'items, size' + ('=' + size[1] if size else '')
        return make('chunks', param, "if not isinstance(size, int) or isinstance(size, bool) or size <= 0:\n    raise ValueError('size must be a positive integer')\nreturn [items[i:i + size] for i in range(0, len(items), size)]", 'Includes the final shorter chunk; empty input returns an empty list.')
    if 'rotate' in t and re.search(r'\blist|array|sequence\b', t):
        side = 'left' if 'left' in t else 'right' if 'right' in t else None
        if side is None:
            return None
        step = re.search(r'\bby\s+(\d{1,5})\b', t)
        param = 'items, k' + ('=' + step[1] if step else '')
        expression = 'items[k:] + items[:k]' if side == 'left' else 'items[-k:] + items[:-k]'
        return make('rotate_' + side, param, 'items = list(items)\nif not items:\n    return []\nk %= len(items)\nreturn ' + expression, 'Returns a new list; rotation wraps and supports negative k.')
    if re.search(r'\bsort\b', t) and re.search(r'\bdict|dictionary\b', t) and 'value' in t and re.search(r'\bdescending|reverse|largest first\b', t):
        return make('sort_by_value', 'mapping', 'return dict(sorted(mapping.items(), key=lambda pair: pair[1], reverse=True))', 'Sorts by value descending, preserving input order on ties.')
    if re.search(r'\bsecond (?:largest|biggest|highest)\b', t):
        distinct = bool(re.search(r'\bdistinct|unique|ignore duplicates\b', t))
        if not distinct and not re.search(r'\b(?:count|include|including) duplicates\b', t):
            return dict(route='chat/code-clarify', response='Should duplicate values count when finding the second largest, or do you want the second distinct value?', sources=[])
        return make('second_largest', 'numbers', 'values = sorted(' + ('set(numbers)' if distinct else 'numbers') + ")\nif len(values) < 2:\n    raise ValueError('Need at least two " + ('distinct ' if distinct else '') + "values')\nreturn values[-2]", 'Uses the requested duplicate policy; raises ValueError if there are fewer than two eligible values.')

    # Common text operations on words and characters (each is a standard one-line Python idiom).
    texty = re.search(r'\b(?:string|sentence|text|word|words|phrase|name)\b', t) and not re.search(r'\b(?:list of (?:numbers|integers)|numbers|integers)\b', t)
    if texty:
        word_ops = [
            (r'\breverse\w*\b.*\b(?:order of (?:the )?words|words? order|each word.s position)\b|\breverse\w* (?:the )?words\b', 'reverse_words', 'text',
             "return ' '.join(text.split()[::-1])", 'Splits on whitespace and joins the words in reverse order with single spaces.'),
            (r'\breverse\w* each word\b|\breverse\w* (?:the )?letters (?:of|in) each word\b', 'reverse_each_word', 'text',
             "return ' '.join(word[::-1] for word in text.split())", 'Reverses the letters of every word and keeps the word order.'),
            (r'\bcapitali[sz]\w* (?:the )?first (?:letter|character) of (?:every|each|all) words?\b|\btitle case\b|\bcapitali[sz]\w* (?:every|each|all) words?\b', 'capitalize_words', 'text',
             "return ' '.join(word[:1].upper() + word[1:] for word in text.split(' '))", 'Uppercases the first letter of every word and leaves the rest of each word unchanged.'),
            (r'\bcount\w* (?:the )?(?:number of )?words\b|\bhow many words\b|\bnumber of words\b|\bword count\b', 'count_words', 'text',
             'return len(text.split())', 'Counts whitespace-separated words; an empty string has 0 words.'),
            (r'\blongest word\b', 'longest_word', 'text',
             "words = text.split()\nif not words:\n    return ''\nreturn max(words, key=len)", 'Returns the first longest word; an empty string returns an empty string.'),
            (r'\bshortest word\b', 'shortest_word', 'text',
             "words = text.split()\nif not words:\n    return ''\nreturn min(words, key=len)", 'Returns the first shortest word; an empty string returns an empty string.'),
            (r'\bremove\w* (?:all )?(?:the )?(?:spaces|whitespace)\b', 'remove_spaces', 'text', "return ''.join(text.split())", 'Removes spaces, tabs and new lines.'),
            (r'\bremove\w* (?:all )?(?:the )?punctuation\b', 'remove_punctuation', 'text',
             "punctuation = '!\"#$%&\\'()*+,-./:;<=>?@[\\\\]^_`{|}~'\nreturn ''.join(char for char in text if char not in punctuation)",
             'Removes the ASCII punctuation characters and keeps everything else.'),
            (r'\bremove\w* (?:all )?(?:the )?vowels\b', 'remove_vowels', 'text', "return ''.join(char for char in text if char not in 'aeiouAEIOU')", 'Removes A, E, I, O and U in both cases.'),
            (r'\bacronym\b', 'acronym', 'text', "return ''.join(word[0].upper() for word in text.split())", 'Takes the first letter of every word, in upper case.'),
            (r'\b(?:upper ?case|uppercase|capital letters)\b(?!.*\bfirst\b)', 'to_upper', 'text', 'return text.upper()', 'Returns the text in upper case.'),
            (r'\b(?:lower ?case|lowercase)\b', 'to_lower', 'text', 'return text.lower()', 'Returns the text in lower case.'),
            (r'\bcount\w* (?:how many times|the occurrences of|occurrences of) (?:a )?word\b', 'count_word', 'text, word',
             'return text.lower().split().count(word.lower())', 'Counts whole words, ignoring case.'),
            (r'\breverse\w* (?:a |the )?(?:string|text)\b', 'reverse_string', 'text', 'return text[::-1]', 'Returns the characters in reverse order.'),
        ]
        for pattern, name, params, body, note in word_ops:
            if re.search(pattern, t):
                return make(name, params, body, note)
    if re.search(r'\b(?:list|array|numbers|integers)\b', t):
        list_ops = [
            (r'\b(?:largest|biggest|maximum|max|highest|greatest) (?:number|value|element|item|integer)?\b(?!.*\bsecond\b)', 'largest', 'numbers',
             "if not numbers:\n    raise ValueError('The list is empty')\nreturn max(numbers)", 'Raises ValueError for an empty list.'),
            (r'\b(?:smallest|minimum|min|lowest|least) (?:number|value|element|item|integer)?\b(?!.*\bsecond\b)', 'smallest', 'numbers',
             "if not numbers:\n    raise ValueError('The list is empty')\nreturn min(numbers)", 'Raises ValueError for an empty list.'),
            (r'\bproduct of (?:all )?(?:the )?(?:numbers|elements|items|values)\b|\bmultipl\w* (?:all )?(?:the )?(?:numbers|elements|values)\b', 'product', 'numbers',
             'result = 1\nfor value in numbers:\n    result *= value\nreturn result', 'The product of an empty list is 1.'),
            (r'\breverse\w* (?:a |the )?(?:list|array)\b', 'reverse_list', 'items', 'return list(items)[::-1]', 'Returns a new reversed list.'),
            (r'\blast (?:element|item|value)\b', 'last_item', 'items', "if not items:\n    raise ValueError('The list is empty')\nreturn items[-1]", 'Raises ValueError for an empty list.'),
            (r'\bfirst (?:element|item|value)\b', 'first_item', 'items', "if not items:\n    raise ValueError('The list is empty')\nreturn items[0]", 'Raises ValueError for an empty list.'),
        ]
        if not re.search(r'\b(?:even|odd|positive|negative|greater than|less than|above|below|squares?|sorted?)\b', t):
            for pattern, name, params, body, note in list_ops:
                if re.search(pattern, t):
                    return make(name, params, body, note)

    # A small compositional list algebra: filter -> map -> unique -> sort -> reduce.
    if not re.search(r'\b(?:list|array|numbers|integers|iterable)\b', t):
        return None
    if re.search(r'\b(?:nested|recursive|except|alternating|every other|pairwise|cumulative|adjacent)\b', t):
        return None
    predicates = []
    for cue, expression in [('even', 'x % 2 == 0'), ('odd', 'x % 2 != 0'),
                            ('positive', 'x > 0'), ('negative', 'x < 0'),
                            ('nonnegative', 'x >= 0'), ('nonzero', 'x != 0')]:
        match = re.search(r'\b' + cue + r'(?:s)?\b', t)
        if match:
            prefix = t[max(0, match.start()-35):match.start()]
            excluded = bool(re.search(r'\b(?:remove|drop|exclude|without|discard)\s+(?:all |the )?$', prefix))
            predicates.append('not (' + expression + ')' if excluded else expression)
    threshold = re.search(r'\b(greater than|above|less than|below|at least|at most)\s+(-?\d{1,7}(?:\.\d{1,5})?)\b', t)
    if threshold:
        operator = {'greater than': '>', 'above': '>', 'less than': '<', 'below': '<', 'at least': '>=', 'at most': '<='}[threshold[1]]
        predicates.append('x ' + operator + ' ' + threshold[2])
    if 'even' in t and 'odd' in t and 'or' not in t:
        return None
    mapping = 'x * x' if re.search(r'\bsquares?|squared\b', t) else 'x ** 3' if re.search(r'\bcubes?|cubed\b', t) else 'abs(x)' if 'absolute' in t else None
    unique = bool(re.search(r'\bunique|distinct|duplicates\b', t))
    sorting = bool(re.search(r'\bsort\w*|ascending|descending\b', t))
    operation = 'sum' if re.search(r'\bsum|total|add up\b', t) else 'len' if re.search(r'\bcount|how many|number of\b', t) else 'mean' if re.search(r'\baverage|mean\b', t) else None
    # Delegate ordinary existing tasks to the existing example-driven search.
    if not predicates and not (unique and sorting) and not (mapping and operation):
        return None
    if operation is None and not (mapping or unique or sorting or re.search(r'\b(?:filter|keep|remove|exclude|return|select|drop|discard)\b', t)):
        return None
    lines = ['values = list(numbers)']
    if predicates:
        connector = ' or ' if re.search(r'\beven or odd\b|\bpositive or negative\b', t) else ' and '
        lines.append('values = [x for x in values if ' + connector.join('(' + p + ')' for p in predicates) + ']')
    if mapping:
        lines.append('values = [' + mapping + ' for x in values]')
    if unique:
        lines += ['unique = []', 'for value in values:', '    if value not in unique:', '        unique.append(value)', 'values = unique']
    if sorting:
        lines.append('values = sorted(values, reverse=' + str(bool(re.search(r'\bdescending|reverse|largest first\b', t))) + ')')
    if operation == 'mean':
        lines += ["if not values:", "    raise ValueError('Mean of an empty selection is undefined')", 'return sum(values) / len(values)']
    else:
        lines.append('return ' + (operation + '(values)' if operation else 'values'))
    return make('process_numbers', 'numbers', '\n'.join(lines), 'Composes the requested filter, transformation, ordering and reduction. Returns a new value without modifying the input.')
