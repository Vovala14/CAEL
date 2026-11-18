"""The Programmer: authored answers for everyday Python questions (no model, no web).

Three kinds of answer:
- how-to and concept questions ("How do I read a CSV file?", "list vs tuple"), each with follow-ups that
  stay on its subject ("And how do I skip the header row?");
- error messages ("TypeError: can only concatenate str (not "int") to str"): what it means and the usual fix;
- changes to the function CAEL just wrote ("Now make it recursive", "Add a docstring").

Every code block here was run when it was written (tests/test_python_answers.py runs them again).
"""
import ast
import re

PY = re.compile(r'(?i)\bpython\b|\bpy\b|\bpip\b|\bdef \w+\(|```|\bpandas\b|\bnumpy\b|\bjupyter\b|\bvenv\b|\.py\b')


def code(text):
    return '```python\n' + text.strip('\n') + '\n```'


# code blocks with backslashes, kept out of f-string expressions (Python 3.11 forbids them there)
_C = [
    code('''with open('notes.txt', encoding='utf-8') as f:
    text = f.read()            # the whole file as one string

with open('notes.txt', encoding='utf-8') as f:
    for line in f:             # one line at a time, good for big files
        print(line.rstrip('\\n'))'''),
    code('''with open('notes.txt', 'w', encoding='utf-8') as f:
    f.write('first line\\n')

with open('notes.txt', 'a', encoding='utf-8') as f:
    f.write('another line\\n')'''),
    code('''with open('output.txt', 'w', encoding='utf-8') as f:
    f.write('Hello\\n')
    f.write('Second line\\n')'''),
    code(r'''import re

text = 'Call 555-1234 or 555-9876'
print(re.findall(r'\d{3}-\d{4}', text))    # ['555-1234', '555-9876']
m = re.search(r'(\d{3})-(\d{4})', text)
print(m.group(1))                          # '555'
print(re.sub(r'\d', '#', text))'''),
]

# ---------------------------------------------------------------- topics
# id: (question patterns, needs a Python cue, answer, [(follow-up pattern, answer)])
T = {}


def topic(name, patterns, answer, follow=(), needs_python=True):
    T[name] = dict(patterns=[re.compile('(?i)' + p) for p in patterns], answer=answer.strip(),
                   follow=[(re.compile('(?i)' + p), a.strip()) for p, a in follow], needs_python=needs_python)


topic('csv', [r'\b(?:read|open|load|parse)\b.*\bcsv\b', r'\bcsv\b.*\b(?:read|open|load)'], f"""
Use the built-in `csv` module. Each row comes back as a list of strings:

{code('''import csv

with open('data.csv', newline='', encoding='utf-8') as f:
    for row in csv.reader(f):
        print(row)          # ['name', 'age'], then ['Ada', '36'], ...''')}

If the first row holds column names, `csv.DictReader` gives each row as a dictionary instead: `row['name']`.
With pandas installed, `pandas.read_csv('data.csv')` loads the whole file into a table.
""", [
    (r'\bskip\b.*\b(?:header|first (?:row|line))\b|\b(?:header|first row)\b.*\bskip', f"""
Call `next()` on the reader once before the loop; that reads and drops the first row:

{code('''import csv

with open('data.csv', newline='', encoding='utf-8') as f:
    reader = csv.reader(f)
    header = next(reader)   # the first row, kept in case you need the names
    for row in reader:
        print(row)''')}

`csv.DictReader` uses the header for the keys automatically, so you don't need to skip it there.
With pandas, the header is used by default; `pd.read_csv('data.csv', skiprows=1)` drops a row instead."""),
    (r'\bwrite\b|\bsave\b|\bexport\b', f"""
Use `csv.writer` (or `csv.DictWriter` for dictionaries):

{code('''import csv

rows = [['name', 'age'], ['Ada', 36], ['Alan', 41]]
with open('out.csv', 'w', newline='', encoding='utf-8') as f:
    csv.writer(f).writerows(rows)''')}

`newline=''` stops blank lines appearing between rows on Windows."""),
    (r'\bcolumn\b|\bone field\b|\bspecific\b', f"""
Pick the column by position in each row, or by name with `DictReader`:

{code('''import csv

with open('data.csv', newline='', encoding='utf-8') as f:
    ages = [row['age'] for row in csv.DictReader(f)]''')}"""),
])

topic('read_file', [r'\b(?:read|open|load)\b.{0,20}\b(?:text |txt )?file\b(?!.*\bcsv\b)', r'\bread\b.*\bline by line\b'], f"""
Open it with `with open(...)`, which closes the file for you:

{_C[0]}

`f.readlines()` gives a list of lines, each still ending in `\\n`.
""", [
    (r'\bwrite\b|\bsave\b', f"""
Open the file with mode `'w'` (replace) or `'a'` (add to the end):

{_C[1]}"""),
    (r'\bexist|\bnot found\b|\bmissing\b', f"""
Check first with `pathlib`, or catch the error:

{code('''from pathlib import Path

if Path('notes.txt').exists():
    text = Path('notes.txt').read_text(encoding='utf-8')''')}"""),
])

topic('write_file', [r'\b(?:write|save)\b.{0,30}\b(?:to |into |a )?(?:text |txt )?file\b'], f"""
Open the file with mode `'w'` to create or replace it, or `'a'` to add to the end:

{_C[2]}

`print('text', file=f)` also works and adds the newline for you.
""")

topic('json', [r'\bjson\b'], f"""
Use the built-in `json` module:

{code('''import json

data = json.loads('{"name": "Ada", "age": 36}')   # text -> dict
text = json.dumps(data, indent=2)                # dict -> text

with open('data.json', encoding='utf-8') as f:   # from a file
    data = json.load(f)
with open('out.json', 'w', encoding='utf-8') as f:   # to a file
    json.dump(data, f, indent=2)''')}

`loads`/`dumps` work on strings; `load`/`dump` (no s) work on files.
""", [
    (r'\bpretty\b|\bindent\b|\breadable\b', "Pass `indent=2` (and `sort_keys=True` if you like): `json.dumps(data, indent=2)`."),
    (r'\berror\b|\bdecode\b|\binvalid\b', "A `json.JSONDecodeError` means the text isn't valid JSON. Common causes are single quotes instead of double quotes, a trailing comma, or an empty file. Print the first characters (`print(repr(text[:200]))`) to see what you actually got."),
])

topic('list_tuple', [r'\blist\b.{0,20}\btuple\b|\btuple\b.{0,20}\blist\b'], f"""
Both hold an ordered sequence of items. The difference is that a **list can be changed** and a **tuple can't**:

{code('''items = [1, 2, 3]     # list: square brackets
items.append(4)       # fine
point = (3, 4)        # tuple: round brackets
# point[0] = 5        # TypeError: 'tuple' object does not support item assignment''')}

- Use a **list** for a collection that grows or changes (a shopping list, results you collect).
- Use a **tuple** for a fixed group of values that belong together (coordinates, a date, a row), or as a dictionary key: tuples can be keys and lists can't.
- Tuples are slightly smaller and faster, but that rarely matters.
""")

topic('list_set', [r'\blist\b.{0,20}\bset\b.{0,15}\b(?:difference|vs|versus|compare)|\bset\b.{0,20}\blist\b'], f"""
A **list** keeps order and allows duplicates; a **set** has no order and keeps each value once:

{code('''nums = [3, 1, 3, 2]
print(set(nums))        # {1, 2, 3}: duplicates gone
print(2 in set(nums))   # membership checks are fast in a set''')}

Use a set to remove duplicates or to test "is x in here?" many times; use a list when order or repeats matter.
""")

topic('dict_basics', [r'\b(?:what is|how do i use|explain)\b.{0,10}\b(?:a )?dict(?:ionary|ionaries)?\b', r'\bloop\b.*\bdict', r'\biterate\b.*\bdict'], f"""
A dictionary maps keys to values:

{code('''ages = {'Ada': 36, 'Alan': 41}
ages['Grace'] = 45                 # add or change
print(ages.get('Bob', 0))          # 0: a default instead of a KeyError
for name, age in ages.items():     # loop over pairs
    print(name, age)''')}

`ages.keys()` and `ages.values()` give just one side.
""")

topic('sort_dicts', [r'\bsort\b.*\b(?:list of )?dict(?:ionarie|ionary|s)?', r'\bsort\b.*\bby (?:a |the )?key\b'], f"""
Pass a `key` function to `sorted()` that picks the field to sort by:

{code('''people = [{'name': 'Ada', 'age': 36}, {'name': 'Alan', 'age': 41}, {'name': 'Grace', 'age': 29}]

by_age = sorted(people, key=lambda p: p['age'])
oldest_first = sorted(people, key=lambda p: p['age'], reverse=True)
print([p['name'] for p in by_age])     # ['Grace', 'Ada', 'Alan']''')}

`operator.itemgetter('age')` does the same as the lambda. `people.sort(key=...)` sorts the list in place instead of making a new one.
""", [
    (r'\btwo\b|\bmultiple\b|\bthen by\b|\bsecond key\b', "Return a tuple from the key: `sorted(people, key=lambda p: (p['age'], p['name']))` sorts by age, then by name for equal ages."),
    (r'\bmissing\b|\bnot all\b', "Use `.get` with a default so missing keys don't raise: `sorted(people, key=lambda p: p.get('age', 0))`."),
])

topic('sort_list', [r'\bsort\b.{0,20}\b(?:a )?list\b(?!.*dict)', r'\breverse (?:sort|order)\b'], f"""
`sorted()` returns a new sorted list; `.sort()` sorts the list itself:

{code('''nums = [5, 2, 9, 1]
print(sorted(nums))                 # [1, 2, 5, 9]
print(sorted(nums, reverse=True))   # [9, 5, 2, 1]
words = ['banana', 'Apple', 'cherry']
print(sorted(words, key=str.lower)) # case-insensitive''')}
""")

topic('remove_duplicates', [r'\bremove\b.{0,15}\bduplicates?\b|\bunique\b.{0,15}\blist\b|\bdeduplicate\b'], f"""
`set()` removes duplicates but loses the order; `dict.fromkeys()` keeps the first of each in order:

{code('''items = [3, 1, 3, 2, 1]
print(list(set(items)))             # order not guaranteed
print(list(dict.fromkeys(items)))   # [3, 1, 2]: first-seen order''')}
""")

topic('list_comprehension', [r'\blist comprehension'], f"""
A list comprehension builds a list from a loop in one line:

{code('''squares = [n * n for n in range(5)]            # [0, 1, 4, 9, 16]
evens = [n for n in range(10) if n % 2 == 0]   # with a filter
names = [s.strip().title() for s in [' ada ', 'alan']]''')}

It reads as "this expression, for each item, if the condition holds". For anything longer than one line, an ordinary `for` loop is clearer.
""", needs_python=False)

topic('reverse_string', [r'\breverse\b.{0,12}\bstring\b'], f"""
Slice it with a step of -1:

{code('''text = 'hello'
print(text[::-1])               # 'olleh'
print(''.join(reversed(text)))  # the same''')}
""")

topic('string_format', [r'\bf-?strings?\b|\bformat\b.{0,15}\bstring|\bstring formatting\b|\bput (?:a )?variables? (?:in|into)\b'], f"""
An f-string puts values straight into the text:

{code('''name, total = 'Ada', 1234.5
print(f'Hello {name}, you owe ${total:,.2f}')   # Hello Ada, you owe $1,234.50
print(f'{0.256:.1%}')                           # 25.6%''')}

After the colon comes the format: `.2f` two decimals, `,` thousands separators, `%` percent, `>10` right-align in 10 characters.
""")

topic('round_decimals', [r'\bround\b.{0,20}\b(?:decimal|places|2 dp|two)', r'\b(?:2|two) decimal places\b'], f"""
`round(x, 2)` gives a number; an f-string gives text with exactly two decimals:

{code('''x = 3.14159
print(round(x, 2))    # 3.14
print(f'{x:.2f}')     # '3.14' (always two digits, e.g. 2.50)''')}

For money, `decimal.Decimal` avoids binary rounding surprises like `round(2.675, 2) == 2.67`.
""")

topic('input_number', [r'\binput\b.{0,30}\b(?:number|int|integer)\b|\bconvert\b.{0,20}\bstring\b.{0,10}\b(?:to )?(?:an? )?(?:int|number)'], f"""
`input()` always returns text, so convert it with `int()` or `float()`, and catch bad input:

{code('''while True:
    text = input('How old are you? ')
    try:
        age = int(text)
        break
    except ValueError:
        print('Please type a whole number.')''')}
""")

topic('random', [r'\brandom (?:number|choice|item|element)\b|\brandom\b.{0,15}\bfrom (?:a )?list\b|\bshuffle\b'], f"""
Use the `random` module:

{code('''import random

print(random.randint(1, 6))              # 1..6, both ends included
print(random.choice(['red', 'green']))   # one item
deck = list(range(10)); random.shuffle(deck)   # shuffle in place
print(random.sample(range(100), 3))      # 3 different values''')}

For passwords or tokens use the `secrets` module instead.
""")

topic('dates', [r'\b(?:current|today\'?s?) (?:date|time)\b|\bdatetime\b|\bformat (?:a |the )?(?:date|time)\b|\bdays between\b|\bget the time\b|\btime now\b'], f"""
Use `datetime`:

{code('''from datetime import date, datetime, timedelta

today = date.today()
print(today.strftime('%d %B %Y'))          # e.g. 18 November 2026
print(datetime.now().strftime('%H:%M'))    # current time
print((date(2026, 12, 25) - today).days)   # days until a date
print(today + timedelta(days=30))''')}

`datetime.strptime('18/11/2026', '%d/%m/%Y')` goes the other way, from text to a date.
""", [
    (r'\bhours?\b.{0,15}\bminutes?\b|\bhh:mm\b|\bformat (?:it|the time)\b|\b12[- ]hour\b|\bam/pm\b', f"""
Use `strftime` with the codes for hours and minutes:

{code('''from datetime import datetime

now = datetime.now()
print(now.strftime('%H:%M'))      # 24-hour, e.g. 14:05
print(now.strftime('%I:%M %p'))   # 12-hour, e.g. 02:05 PM
print(f'{now:%H:%M}')             # the same inside an f-string''')}

`%H` hours (00-23), `%I` hours (01-12), `%M` minutes, `%S` seconds, `%p` AM/PM."""),
    (r'\btime ?zone\b|\butc\b', f"""
Use `zoneinfo` (Python 3.9+):

{code('''from datetime import datetime, timezone

print(datetime.now(timezone.utc))          # current UTC time
# from zoneinfo import ZoneInfo            # named zones need the tzdata package on Windows
# print(datetime.now(ZoneInfo('Asia/Tokyo')))''')}"""),
])

topic('dict_key', [r'\b(?:check|test|see)\b.{0,25}\bkey\b.{0,25}\b(?:exists?|in)\b|\bkey exists?\b|\bif (?:a )?key (?:is )?in\b|\bhas_key\b'], f"""
Use `in`:

{code('''ages = {'Ada': 36, 'Alan': 41}
if 'Ada' in ages:
    print('found')
print('Bob' in ages)            # False''')}

`in` checks the keys; to check values use `36 in ages.values()`.
""", [
    (r'\bdefault\b|\bif (?:it )?(?:does ?n.t|is ?n.t|not)\b|\bmissing\b|\bwithout (?:an? )?error\b', f"""
Use `.get` with a default, or `setdefault` to also store it:

{code('''ages = {'Ada': 36}
print(ages.get('Bob', 0))          # 0, and ages is unchanged
ages.setdefault('Bob', 0)          # adds 'Bob': 0 if missing
from collections import defaultdict
counts = defaultdict(int)          # every missing key starts at 0
counts['x'] += 1''')}"""),
])

topic('append_extend', [r'\bappend\b.{0,25}\bextend\b|\bextend\b.{0,25}\bappend\b'], f"""
`append` adds **one** item (whatever it is) to the end; `extend` adds **each item** of another iterable:

{code('''a = [1, 2]
a.append([3, 4])     # [1, 2, [3, 4]]: one item, a list
b = [1, 2]
b.extend([3, 4])     # [1, 2, 3, 4]: two items
c = [1, 2]
c += [3, 4]          # the same as extend''')}
""", needs_python=False)

topic('merge_dicts', [r'\b(?:merge|combine|join|update)\b.{0,20}\bdict(?:ionar(?:y|ies)|s)?\b'], f"""
Make a new merged dictionary with `|` (Python 3.9+) or `{{**a, **b}}`; keys in the right-hand one win:

{code('''a = {'x': 1, 'y': 2}
b = {'y': 20, 'z': 3}
print(a | b)          # {'x': 1, 'y': 20, 'z': 3}
print({**a, **b})     # the same, older Pythons
a.update(b)           # changes a in place''')}
""")

topic('range_list', [r'\blist of (?:numbers|integers)\b.{0,20}\bfrom\b|\bnumbers from \d+ to \d+\b|\brange\b.{0,20}\b(?:list|numbers)\b|\b(?:make|create|generate)\b.{0,15}\blist\b.{0,15}\b\d+ to \d+\b'], f"""
`range` gives the numbers; wrap it in `list()` to get a list. The end value is not included:

{code('''numbers = list(range(1, 101))     # 1 to 100
print(numbers[:5], numbers[-1])   # [1, 2, 3, 4, 5] 100''')}
""", [
    (r'\beven\b', "Use a step of 2: `list(range(2, 101, 2))` gives 2, 4, ... 100. Or filter: `[n for n in range(1, 101) if n % 2 == 0]`."),
    (r'\bodd\b', "Start at 1 with a step of 2: `list(range(1, 101, 2))` gives 1, 3, ... 99."),
    (r'\breverse|\bbackwards?\b|\bcount ?down\b', "Use a negative step: `list(range(100, 0, -1))` gives 100 down to 1."),
    (r'\bsquares?\b', "`[n * n for n in range(1, 101)]` gives 1, 4, 9, ... 10000."),
])

topic('sum_average', [r'\b(?:average|mean|sum|total)\b.{0,20}\b(?:of )?(?:a )?list\b'], f"""
`sum()` adds them up; divide by `len()` for the average:

{code('''nums = [4, 8, 15, 16]
print(sum(nums))                  # 43
print(sum(nums) / len(nums))      # 10.75
import statistics
print(statistics.mean(nums), statistics.median(nums))''')}

Check the list isn't empty before dividing.
""")

topic('string_contains', [r'\b(?:check|test|see|find)\b.{0,25}\bstring\b.{0,25}\b(?:contains?|in)\b|\bsubstring\b|\bstring contains\b'], f"""
Use `in`, or `.find()` to get the position:

{code('''text = 'Hello, world'
print('world' in text)            # True
print(text.find('world'))         # 7 (-1 if not found)
print('WORLD' in text.upper())    # case-insensitive check''')}
""")

topic('max_dict_value', [r'\b(?:key|item) with the (?:largest|highest|biggest|max(?:imum)?|smallest|lowest|min(?:imum)?) value\b|\bmax\b.{0,10}\bdict'], f"""
Pass the dictionary's own `get` as the key:

{code('''scores = {'Ada': 9, 'Alan': 7, 'Grace': 10}
print(max(scores, key=scores.get))   # 'Grace'
print(min(scores, key=scores.get))   # 'Alan' ''')}
""")

topic('count_items', [r'\bcount\b.{0,20}\b(?:occurrences|how many times|frequency|each (?:item|element|word|letter))\b|\bcounter\b'], f"""
`collections.Counter` counts everything at once:

{code('''from collections import Counter

c = Counter(['a', 'b', 'a', 'c', 'a'])
print(c['a'])              # 3
print(c.most_common(2))    # [('a', 3), ('b', 1)]
print('banana'.count('a')) # 3, for one item in a string or list''')}
""")

topic('global_var', [r'\bglobal\b.{0,15}\bvariable\b|\bchange a variable inside a function\b'], f"""
Inside a function, assigning to a name makes it local. To change a module-level variable, declare it `global`:

{code('''count = 0

def bump():
    global count
    count += 1

bump()
print(count)     # 1''')}

Usually it's cleaner to pass values in and `return` the new value.
""")

topic('import_module', [r'\b(?:import|use)\b.{0,20}\b(?:another|other|my own) (?:file|module|script)\b|\bhow (?:does|do) import\b'], f"""
Put the code in `helpers.py` next to your script, then import it by the file name without `.py`:

{code('''# helpers.py
def greet(name):
    return f'Hi {name}'

# main.py
# from helpers import greet
# print(greet('Ada'))''')}

Both files must be in the same folder (or the folder must be on `sys.path`).
""")

topic('while_loop_break', [r'\bbreak\b.{0,15}\b(?:loop|out)\b|\bexit (?:a|the) loop\b|\bstop (?:a|the) loop\b|\binfinite loop\b'], f"""
`break` leaves the loop immediately; `continue` skips to the next round:

{code('''while True:
    answer = 'quit'          # e.g. input('> ')
    if answer == 'quit':
        break
for n in range(10):
    if n % 2:
        continue             # skip odd numbers
    print(n)''')}
""")

topic('venv', [r'\bvirtual env(?:ironment)?\b|\bvenv\b'], f"""
A virtual environment keeps one project's packages separate from the others:

```bash
python -m venv .venv
# Windows:      .venv\\Scripts\\activate
# macOS/Linux:  source .venv/bin/activate
pip install requests
pip freeze > requirements.txt
```

`deactivate` leaves it. Anyone can then recreate it with `pip install -r requirements.txt`.
""", needs_python=False)

topic('pip_install', [r'\b(?:install|add)\b.{0,20}\b(?:package|library|module)\b', r'\bpip install\b', r'\bhow do i install\b.{0,30}\bpython\b'], f"""
Install packages with pip from a terminal (not inside Python):

```bash
python -m pip install requests
python -m pip install --upgrade requests
python -m pip list
```

`python -m pip` makes sure pip belongs to the same Python you run. If you use a virtual environment, activate it first.
""")

topic('exceptions', [r'\btry\b.{0,10}\bexcept\b|\bhandle\b.{0,20}\b(?:errors?|exceptions?)\b|\bcatch\b.{0,20}\b(?:errors?|exceptions?)'], f"""
Put the risky code in `try` and say which errors to catch:

{code('''try:
    value = int(text)
except ValueError:
    print('That was not a number')
else:
    print('Got', value)        # runs only if nothing failed
finally:
    print('Always runs')''')}

Catch specific errors (`ValueError`, `FileNotFoundError`) rather than a bare `except:`, which also hides real bugs.
""")

topic('classes', [r'\b(?:what is|how do i (?:make|create|write)|explain)\b.{0,10}\b(?:a )?class(?:es)?\b', r'\b__init__\b|\bself\b.{0,10}\bmean'], f"""
A class bundles data and the functions that work on it:

{code('''class Dog:
    def __init__(self, name):     # runs when you create a Dog
        self.name = name          # self is this particular dog

    def speak(self):
        return f'{self.name} says woof'

rex = Dog('Rex')
print(rex.speak())                # Rex says woof''')}

`self` is the object the method was called on; Python passes it for you.
""")

topic('functions', [r'\b(?:how do i|how to) (?:define|write|make) (?:a )?function\b|\bwhat is a function\b|\breturn\b.{0,10}\bvs\b.{0,10}\bprint\b|\bprint\b.{0,10}\bvs\b.{0,10}\breturn\b'], f"""
`def` defines a function; `return` hands a value back to whoever called it:

{code('''def area(width, height=1):    # height has a default
    return width * height

print(area(3, 4))             # 12
print(area(5))                # 5''')}

`print` only shows a value on screen; `return` gives it back so the program can use it.
""")

topic('loops', [r'\bfor loop\b|\bwhile loop\b|\bloop (?:through|over)\b(?!.*dict)', r'\benumerate\b|\bloop\b.{0,15}\bindex\b'], f"""
`for` walks over the items of anything iterable; `while` repeats while a condition holds:

{code('''for fruit in ['apple', 'pear']:
    print(fruit)

for i, fruit in enumerate(['apple', 'pear'], start=1):   # with a counter
    print(i, fruit)

n = 3
while n > 0:
    n -= 1''')}

`break` leaves the loop early; `continue` skips to the next item.
""")

topic('requests', [r'\b(?:http|api|web) request\b|\brequests\b.{0,10}\b(?:library|module|get)\b|\b(?:call|fetch|get data from)\b.{0,10}\b(?:an? )?(?:api|url|website)\b'], f"""
The `requests` package (`pip install requests`) is the usual way:

{code('''import requests

r = requests.get('https://api.github.com', timeout=10)
r.raise_for_status()           # an error for 4xx/5xx answers
data = r.json()                # parsed JSON''')}

Without extra packages, `urllib.request.urlopen(url)` does the same in the standard library.
""")

topic('main_guard', [r"__name__\s*==\s*['\"]__main__|if __name__"], f"""
`if __name__ == '__main__':` runs the block only when the file is run directly, not when it's imported:

{code('''def main():
    print('running as a script')

if __name__ == '__main__':
    main()''')}

That lets other files `import` your functions without starting the script.
""", needs_python=False)

topic('args_kwargs', [r'\*args\b|\*\*kwargs\b'], f"""
`*args` collects extra positional arguments into a tuple; `**kwargs` collects extra keyword arguments into a dict:

{code('''def show(*args, **kwargs):
    print(args, kwargs)

show(1, 2, colour='red')     # (1, 2) {'colour': 'red'}''')}
""", needs_python=False)

topic('lambda', [r'\blambda\b'], f"""
A `lambda` is a tiny unnamed function written in one expression:

{code('''square = lambda x: x * x
print(square(4))                                # 16
print(sorted(['bb', 'a', 'ccc'], key=lambda s: len(s)))''')}

They're handy as a `key=` for sorting; for anything longer, write a normal `def`.
""")

VS = r'(?:difference|differ|vs\.?|versus|instead of|rather than|compared? (?:to|with)|or (?:a|an)\b|when (?:should i|to|do i) use)'
DICT = r'\bdict(?:ionar(?:y|ies))?s?\b'

topic('list_vs_dict', [r'\blists?\b.{0,30}' + VS + r'.{0,30}' + DICT + r'|' + DICT + r'.{0,30}' + VS + r'.{0,30}\blists?\b',
                       VS + r'.{0,15}(?:\b(?:a )?lists?\b.{0,12}\b(?:and|or) (?:a )?' + DICT + r'|' + DICT + r'.{0,12}\b(?:and|or) (?:a )?lists?\b)'], f"""
A **list** is an ordered row of items you reach by position; a **dictionary** stores values under keys you choose:

{code('''fruits = ['apple', 'pear', 'plum']        # list: position 0, 1, 2
print(fruits[1])                           # pear

prices = {'apple': 0.5, 'pear': 0.8}         # dict: key -> value
print(prices['pear'])                      # 0.8''')}

- **Finding things:** a list is searched by position (`fruits[1]`), or item by item (`'pear' in fruits`, slow on long lists); a dict jumps straight to a key (`prices['pear']`, fast at any size).
- **Order and repeats:** a list keeps order and allows repeats; dict keys are unique (a second `'pear'` replaces the first) and keep the order they were added in (Python 3.7+).
- **Both can be changed** after you make them: `fruits.append('fig')`, `prices['fig'] = 1.2`.

Use a list for a sequence of things (a to-do list, scores in order), a dict when you look things up by name (a price list, settings, word counts).
""", needs_python=False)

topic('list_vs_tuple', [r'\blists?\b.{0,30}' + VS + r'.{0,30}\btuples?\b|\btuples?\b.{0,30}' + VS + r'.{0,30}\blists?\b',
                        VS + r'.{0,15}\b(?:a )?(?:lists?|tuples?)\b.{0,12}\b(?:and|or) (?:a )?(?:lists?|tuples?)\b'], f"""
Both are ordered sequences; the difference is that a **list can be changed** and a **tuple can't**:

{code('''point = (3, 4)          # tuple: fixed
items = [3, 4]          # list: can grow and change
items.append(5)         # fine
# point.append(5)       # AttributeError: tuples have no append
x, y = point            # unpacking works on both''')}

Use a tuple for a fixed group of values that belong together (coordinates, a date, a row from a database), and because it can't change it can be a dict key or a set member. Use a list when you will add, remove or reorder items.
""", needs_python=False)

topic('list_vs_set', [r'\blists?\b.{0,30}' + VS + r'.{0,30}\bsets?\b|\bsets?\b.{0,30}' + VS + r'.{0,30}\blists?\b'], f"""
A **list** keeps order and repeats; a **set** keeps each value once, has no positions, and checks membership very fast:

{code('''nums = [3, 1, 3, 2]
print(set(nums))        # {1, 2, 3}: the repeat is gone
print(2 in set(nums))   # True, fast even for millions of items
# set(nums)[0]          # TypeError: a set has no positions''')}

Use a list for things in order (with repeats); use a set to remove duplicates, or when you often ask "is this value in here?".
""", needs_python=False)

topic('is_vs_eq', [r'\bis\b.{0,6}\bvs\b.{0,6}==|==.{0,10}\bvs\b.{0,6}\bis\b|difference between (?:==|is) and (?:==|is)'], f"""
`==` asks "equal value?"; `is` asks "the very same object?":

{code('''a = [1, 2]
b = [1, 2]
print(a == b)     # True: same contents
print(a is b)     # False: two separate lists
print(a is a)     # True''')}

Use `is` only for `None` (`if x is None:`); use `==` for everything else.
""", needs_python=False)

topic('copy_list', [r'\bcopy\b.{0,10}\b(?:a )?list\b|\bshallow\b|\bdeep ?copy\b'], f"""
`b = a` doesn't copy: both names point at the same list. Make a real copy:

{code('''import copy

a = [[1, 2], [3]]
b = a.copy()            # new outer list, same inner lists (shallow)
c = copy.deepcopy(a)    # everything copied
a[0].append(9)
print(b[0], c[0])       # [1, 2, 9] [1, 2]''')}
""")

topic('string_methods', [r'\bsplit\b.{0,15}\bstring\b|\bstring\b.{0,15}\bsplit\b|\bjoin\b.{0,15}\blist\b|\bstrip\b|\breplace\b.{0,15}\b(?:in|a) string\b'], f"""
The everyday string methods:

{code('''s = '  Hello, World  '
print(s.strip())                  # 'Hello, World'
print(s.lower(), s.upper())
print('a,b,c'.split(','))         # ['a', 'b', 'c']
print('-'.join(['a', 'b', 'c']))  # 'a-b-c'
print(s.replace('World', 'Ada'))
print('ell' in s, s.count('l'))''')}

Strings can't be changed in place; each method returns a new string.
""")

topic('timing', [r'\b(?:time|measure)\b.{0,20}\b(?:how long|code|function|runs?)\b|\btimeit\b'], f"""
For a quick measure, `time.perf_counter()` before and after:

{code('''import time

start = time.perf_counter()
total = sum(range(1_000_000))
print(f'{time.perf_counter() - start:.3f} s')''')}

For small snippets, `python -m timeit "sum(range(1000))"` repeats it and gives a fair average.
""")

topic('env_vars', [r'\benvironment variables?\b|\bos\.environ\b|\bgetenv\b'], f"""
Read them with `os.environ`:

{code('''import os

home = os.environ.get('HOME', 'not set')   # a default instead of KeyError
debug = os.getenv('DEBUG') == '1' ''')}

Keep secrets like API keys in environment variables rather than in your code.
""")

topic('args_cli', [r'\bcommand[- ]line arguments?\b|\bsys\.argv\b|\bargparse\b'], f"""
`sys.argv` holds the raw arguments; `argparse` gives you named options and `--help` for free:

{code('''import argparse

parser = argparse.ArgumentParser(description='Greet someone')
parser.add_argument('name')
parser.add_argument('--times', type=int, default=1)
args = parser.parse_args()
for _ in range(args.times):
    print('Hello', args.name)''')}

Run it as `python greet.py Ada --times 2`.
""")

topic('files_in_folder', [r'\b(?:list|all|every)\b.{0,20}\bfiles\b.{0,20}\b(?:folder|directory|dir)\b|\bos\.listdir\b|\bglob\b'], f"""
`pathlib` is the modern way:

{code('''from pathlib import Path

for path in Path('.').iterdir():          # everything in the folder
    print(path.name)
for path in Path('.').rglob('*.txt'):     # every .txt, including subfolders
    print(path)''')}
""")

topic('regex', [r'\bregex\b|\bregular expressions?\b|\bre\.(?:search|match|findall|sub)\b'], f"""
Use the `re` module:

{_C[3]}

Write patterns as raw strings (`r'...'`) so backslashes reach `re` unchanged.
""", needs_python=False)

topic('generators', [r'\byield\b|\bgenerator (?:function|expression|object)s?\b|\bwhat (?:is|are) (?:a )?generators?\b|\bhow do generators\b'], f"""
A function with `yield` is a generator: it hands back values one at a time instead of building a whole list:

{code('''def countdown(n):
    while n > 0:
        yield n
        n -= 1

print(list(countdown(3)))   # [3, 2, 1]''')}

Good for big or endless sequences, since only one value exists at a time.
""")

topic('decorators', [r'\bdecorators?\b|@\w+ (?:mean|do)'], f"""
A decorator wraps a function to add behaviour around it:

{code('''import functools

def shout(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs).upper()
    return wrapper

@shout
def greet(name):
    return f'hello {name}'

print(greet('ada'))    # HELLO ADA''')}

`@shout` above `def greet` is the same as writing `greet = shout(greet)` afterwards.
""")

topic('none_check', [r'\bcheck\b.{0,15}\bnone\b|\bwhat is none\b|\bnull in python\b'], f"""
`None` means "no value". Test for it with `is`:

{code('''result = None
if result is None:
    print('nothing yet')''')}

A function without a `return` gives back `None`, which is a common source of `'NoneType' object ...` errors.
""")

topic('learn_python', [r'\b(?:learn|start(?:ing)?|begin(?:ner)?)\b.{0,30}\bpython\b|\bpython\b.{0,20}\bbeginner'], """
A path that works for most people:

1. **Install Python** from python.org and use an editor such as VS Code or Thonny.
2. **The basics** (a week or two): variables, strings, lists, `if`, `for`, functions. The official tutorial at docs.python.org is free and good.
3. **Small programs straight away**: a number-guessing game, a tip calculator, a word counter for a text file. Writing code teaches far more than reading about it.
4. **Then** dictionaries, files, error handling, and installing a package with pip.
5. **A project you care about**: automate something boring, analyse your own data, or a small website.

Ask me for any of those programs and I'll write and check one with you.
""")


# ---------------------------------------------------------------- everyday operations (short reference)
def op(name, patterns, text, example, follow=()):
    topic('op_' + name, patterns, text + '\n\n' + code(example), follow)


op('remove_item', [r'\b(?:remove|delete|take out|take (?:\w+ ){0,3}out|get rid of|drop)\b.{0,25}\b(?:item|element|value|entry|number|word)?.{0,10}\b(?:from|in|out of|of) (?:a |the |my )?list\b'],
   "Use `.remove(value)` to delete the first matching item, or a list comprehension to drop every match:",
   "fruits = ['apple', 'pear', 'apple']\nfruits.remove('apple')                          # ['pear', 'apple']\nfruits = [f for f in fruits if f != 'apple']    # ['pear']",
   [(r'\bposition\b|\bindex\b|\bplace\b|\bnumber\b|\bfirst\b|\blast\b', "Use `del items[i]`, or `items.pop(i)` if you also want the removed item back:\n\n" +
     code("items = ['a', 'b', 'c', 'd']\ndel items[1]          # ['a', 'c', 'd']\nlast = items.pop()    # 'd', items is ['a', 'c']\nfirst = items.pop(0)  # 'a'")),
    (r'\bnot (?:there|in)\b|\berror\b|\bmissing\b|\bdoes ?n.t exist\b', "`.remove` raises `ValueError` if the item isn't there. Check first: `if x in items: items.remove(x)`.")])
op('lower_upper', [r'\b(?:lower ?case|upper ?case|capitali[sz]e|title case|small letters|capital letters)\b'],
   "Strings have methods for case; each returns a new string:",
   "s = 'Hello World'\nprint(s.lower())       # 'hello world'\nprint(s.upper())       # 'HELLO WORLD'\nprint(s.title())       # 'Hello World'\nprint(s.capitalize())  # 'Hello world'\nprint(s.casefold())    # like lower(), best for comparing",
   [(r'\bcompare\b|\bcase[- ]insensitive\b|\bignore case\b', "Compare lower-cased (or `casefold()`-ed) copies: `a.casefold() == b.casefold()`.")])
op('length', [r'\b(?:length|size|how many (?:items|elements|keys|characters|entries))\b.{0,25}\b(?:of )?(?:a |the |my )?(?:list|string|dict(?:ionary)?|set|tuple|array)\b|\blen\(\)'],
   "`len()` works on lists, strings, dictionaries, sets and tuples:",
   "print(len([1, 2, 3]))            # 3 items\nprint(len('hello'))              # 5 characters\nprint(len({'a': 1, 'b': 2}))     # 2 keys")
op('insert', [r'\b(?:insert|add)\b.{0,25}\b(?:at|to) (?:a |the )?(?:position|index|start|beginning|front|middle)\b'],
   "`.insert(position, value)` puts an item before that position; `.append` adds to the end:",
   "items = ['b', 'c']\nitems.insert(0, 'a')      # ['a', 'b', 'c']\nitems.insert(2, 'x')      # ['a', 'b', 'x', 'c']\nitems.append('z')         # at the end")
op('index_of', [r'\b(?:find|get)\b.{0,15}\b(?:index|position)\b.{0,20}\b(?:of|in)\b|\bwhere (?:is|does) .{1,20} (?:appear|in the list)\b'],
   "`.index(value)` gives the first position; it raises `ValueError` if the item isn't there:",
   "items = ['a', 'b', 'c', 'b']\nprint(items.index('b'))                                # 1\nprint([i for i, v in enumerate(items) if v == 'b'])    # every position: [1, 3]")
op('join_list', [r'\b(?:join|combine|turn|convert)\b.{0,20}\blist\b.{0,20}\b(?:into |to )?(?:a |one )?string\b|\blist to (?:a )?string\b'],
   "`'separator'.join(list)` glues strings together; convert numbers with `map(str, ...)` first:",
   "words = ['red', 'green', 'blue']\nprint(', '.join(words))              # 'red, green, blue'\nprint(''.join(['a', 'b']))           # 'ab'\nprint(' '.join(map(str, [1, 2, 3])))  # '1 2 3'")
op('split_string', [r'\b(?:split|break|turn|convert)\b.{0,20}\bstring\b.{0,20}\b(?:into |to )?(?:a )?(?:list|words|parts|characters)\b|\bstring to (?:a )?list\b'],
   "`.split()` breaks on whitespace, or on the separator you give; `list()` splits into characters:",
   "print('a b  c'.split())          # ['a', 'b', 'c']\nprint('a,b,c'.split(','))        # ['a', 'b', 'c']\nprint(list('abc'))               # ['a', 'b', 'c']")
op('slicing', [r'\bslic(?:e|ing)\b|\bfirst (?:\d+|few|three|five|n) (?:items|elements|characters|letters)\b|\blast (?:\d+|few|three|five|n) (?:items|elements|characters|letters)\b|\bsub ?string\b'],
   "Slices take `[start:stop:step]`; the stop position isn't included, and negative numbers count from the end:",
   "s = 'abcdefg'\nprint(s[:3])     # 'abc' first three\nprint(s[-2:])    # 'fg' last two\nprint(s[2:5])    # 'cde'\nprint(s[::2])    # 'aceg' every second\nprint(s[::-1])   # reversed")
op('first_last', [r'\b(?:first|last|final|end) (?:item|element|value|character|letter|entry)\b'],
   "Index 0 is the first item and -1 is the last:",
   "items = [10, 20, 30]\nprint(items[0], items[-1])    # 10 30\nprint('word'[0], 'word'[-1])  # w d\nprint(items[-2:])             # [20, 30] the last two\nlast = items.pop()            # 30, and removes it from the list\n\nempty = []\nprint(empty[-1] if empty else None)   # empty[-1] alone raises IndexError")
op('empty_check', [r'\b(?:check|test|see)\b.{0,15}\b(?:if|whether)\b.{0,15}\b(?:list|string|dict(?:ionary)?)\b.{0,10}\bempty\b|\bis empty\b'],
   "Empty containers count as False, so test them directly:",
   "items = []\nif not items:\n    print('empty')\nname = ''\nprint(bool(name))   # False")
op('dict_delete', [r'\b(?:remove|delete)\b.{0,20}\b(?:key|entry|item)\b.{0,15}\b(?:from )?(?:a |the )?dict(?:ionary)?\b'],
   "`del d[key]` removes it (KeyError if missing); `d.pop(key, None)` removes it safely and returns the value:",
   "ages = {'Ada': 36, 'Alan': 41}\ndel ages['Ada']\nprint(ages.pop('Bob', None))   # None, no error\nprint(ages)                    # {'Alan': 41}")
op('dict_keys_values', [r'\b(?:get|list|all)\b.{0,15}\b(?:the )?(?:keys|values)\b.{0,15}\b(?:of |from |in )?(?:a |the )?dict'],
   "`.keys()`, `.values()` and `.items()` give views; wrap them in `list()` for a list:",
   "ages = {'Ada': 36, 'Alan': 41}\nprint(list(ages.keys()))      # ['Ada', 'Alan']\nprint(list(ages.values()))    # [36, 41]\nfor name, age in ages.items():\n    print(name, age)")
op('concat_lists', [r'\b(?:combine|join|merge|concatenate|add)\b.{0,15}\b(?:two |2 )?lists\b'],
   "`+` makes a new list; `.extend()` adds to an existing one:",
   "a = [1, 2]\nb = [3, 4]\nprint(a + b)      # [1, 2, 3, 4]\na.extend(b)       # a is now [1, 2, 3, 4]\nprint([*a, *b])   # unpacking works too")
op('convert_types', [r'\b(?:convert|turn|change|cast)\b.{0,20}\b(?:to|into) (?:an? )?(?:int|integer|float|string|str|number|list|tuple|set)\b'],
   "Call the type you want: `int()`, `float()`, `str()`, `list()`, `tuple()`, `set()`:",
   "print(int('42') + 1)        # 43\nprint(float('3.5'))         # 3.5\nprint(str(7) + ' days')     # '7 days'\nprint(list('abc'))          # ['a', 'b', 'c']\nprint(int(3.9))             # 3: int() cuts off the decimals")
op('type_check', [r'\b(?:check|find out|know|get)\b.{0,15}\b(?:the )?type of\b|\bisinstance\b|\bwhat type is\b'],
   "`type(x)` tells you the type; `isinstance(x, int)` checks it (and accepts subclasses):",
   "x = 3.0\nprint(type(x))                  # <class 'float'>\nprint(isinstance(x, (int, float)))   # True")
op('math_ops', [r'\b(?:square root|power|exponent|absolute value|modulo|remainder|integer division|floor division|round up|round down)\b'],
   "The operators and the `math` module cover these:",
   "import math\nprint(2 ** 10)         # 1024 power\nprint(math.sqrt(16))   # 4.0\nprint(abs(-5))         # 5\nprint(17 // 5, 17 % 5) # 3 2: whole part and remainder\nprint(math.ceil(2.1), math.floor(2.9))  # 3 2")
op('strip_spaces', [r'\b(?:remove|strip|trim|get rid of)\b.{0,15}\b(?:spaces|whitespace|newlines?|blank)\b'],
   "`.strip()` removes whitespace (and newlines) from both ends; `lstrip`/`rstrip` from one end; `replace` removes it everywhere:",
   "s = '  hello world \\n'\nprint(s.strip())             # 'hello world'\nprint(s.replace(' ', ''))     # 'helloworld\\n'\nprint(' '.join(s.split()))   # collapses runs of spaces")
op('replace_text', [r'\breplace\b.{0,20}\b(?:in )?(?:a |the )?string\b|\breplace (?:a |every |all )?(?:word|character|letter)\b'],
   "`.replace(old, new)` returns a new string with every match replaced (pass a count to limit it):",
   "s = 'cat hat cat'\nprint(s.replace('cat', 'dog'))      # 'dog hat dog'\nprint(s.replace('cat', 'dog', 1))   # 'dog hat cat'")
op('enumerate', [r'\benumerate\b'],
   "`enumerate` gives you each item together with its position, so you don't need a counter:",
   "for i, fruit in enumerate(['apple', 'pear']):\n    print(i, fruit)              # 0 apple, 1 pear\nfor n, fruit in enumerate(['apple', 'pear'], start=1):\n    print(n, fruit)              # 1 apple, 2 pear")
op('zip', [r'\bzip\(?\)?\b(?!.*\b(?:file|archive|folder)\b)'],
   "`zip` walks several sequences side by side and stops at the shortest:",
   "names = ['Ada', 'Alan']\nages = [36, 41]\nfor name, age in zip(names, ages):\n    print(name, age)\nprint(dict(zip(names, ages)))    # {'Ada': 36, 'Alan': 41}")
op('write_lines', [r'\b(?:write|save)\b.{0,20}\blist\b.{0,25}\b(?:file|text file)\b|\bone (?:item|element|value|word) per line\b'],
   "Join the items with newlines, or write them one by one:",
   "items = ['apple', 'pear', 'plum']\nwith open('items.txt', 'w', encoding='utf-8') as f:\n    f.write('\\n'.join(items) + '\\n')\n# or: for item in items: print(item, file=f)")
op('read_lines', [r'\bread\b.{0,25}\b(?:lines|file)\b.{0,20}\binto (?:a )?list\b|\bfile\b.{0,15}\binto (?:a )?list\b|\blist of lines\b'],
   "`read().splitlines()` gives the lines without their newline characters:",
   "open('items.txt', 'w').write('a\\nb\\n')\nwith open('items.txt', encoding='utf-8') as f:\n    lines = f.read().splitlines()\nprint(lines)     # ['a', 'b']")
op('file_exists', [r'\b(?:check|test|see)\b.{0,15}\b(?:if|whether)\b.{0,15}\b(?:a )?(?:file|folder|directory|path)\b.{0,10}\bexists?\b|\bfile exists?\b'],
   "`pathlib.Path(...).exists()` (or `.is_file()` / `.is_dir()`):",
   "from pathlib import Path\np = Path('notes.txt')\nprint(p.exists(), p.is_file())")
op('make_folder', [r'\b(?:create|make)\b.{0,10}\b(?:a )?(?:folder|directory|dir)\b'],
   "`Path(...).mkdir(parents=True, exist_ok=True)` creates it, with any missing parent folders, and doesn't fail if it already exists:",
   "from pathlib import Path\nPath('output/reports').mkdir(parents=True, exist_ok=True)")
op('sleep_wait', [r'\b(?:wait|pause|sleep|delay)\b.{0,20}\b(?:seconds?|a second|for a while|before)\b|\btime\.sleep\b'],
   "`time.sleep(seconds)` pauses the program:",
   "import time\nprint('start')\ntime.sleep(0.5)    # half a second\nprint('done')")
op('print_no_newline', [r'\bprint\b.{0,20}\b(?:without (?:a )?new ?line|on the same line|no new ?line)\b'],
   "Pass `end=''` (or another ending) to `print`:",
   "for i in range(3):\n    print(i, end=' ')    # 0 1 2 on one line\nprint()                  # finish the line")
op('comments', [r'\b(?:write|make|add)\b.{0,10}\bcomments?\b(?!.*\bto (?:my|this|the) (?:code|function))|\bmulti[- ]?line comment\b|\bcomment out\b'],
   "`#` starts a comment to the end of the line; for several lines, put `#` on each (editors do it with Ctrl+/):",
   "# this is a comment\nx = 5  # so is this\ndef f():\n    \"\"\"A docstring describes the function.\"\"\"\n    return x")
op('exit_program', [r'\b(?:exit|quit|stop|end)\b.{0,10}\b(?:the |a |my )?(?:program|script)\b'],
   "`sys.exit()` ends the program (optionally with an exit code or message):",
   "import sys\nif False:\n    sys.exit('Something went wrong')   # prints the message and stops")
op('list_contains', [r'\b(?:check|test|see)\b.{0,20}\b(?:if|whether)\b.{0,20}\b(?:in|is in) (?:a |the )?list\b|\bitem (?:is )?in (?:a |the )?list\b|\blist contains\b'],
   "Use `in`:",
   "items = ['a', 'b']\nprint('a' in items)       # True\nprint('z' not in items)   # True")
op('sort_desc', [r'\bsort\b.{0,35}\b(?:descending|reverse|largest first|highest first|biggest first)\b'],
   "Pass `reverse=True`:",
   "nums = [3, 1, 2]\nprint(sorted(nums, reverse=True))   # [3, 2, 1]\nnums.sort(reverse=True)             # in place")


# ---------------------------------------------------------------- error messages
E = []


def error(pattern, meaning, fix, example=None):
    E.append((re.compile(pattern, re.I), meaning.strip(), fix.strip(), example))


error(r'can only concatenate str \(not "(\w+)"\) to str', 'You tried to join text and a value of type `{0}` with `+`. Python won\'t mix them automatically.',
      'Convert the `{0}` to text first with `str()`, or use an f-string:', "age = 36\nprint('Age: ' + str(age))\nprint(f'Age: {age}')")
error(r"unsupported operand type\(s\) for ([^:]+): '(\w+)' and '(\w+)'", "The `{0}` operator doesn't work between a `{1}` and a `{2}`.",
      'Check where each value comes from. Text read from `input()` or a file is a `str` and needs `int()` or `float()` first; a function that forgot to `return` gives `NoneType`.',
      "total = int('5') + 3   # 8, not an error")
error(r"'NoneType' object is not subscriptable", 'You used `[...]` on something that is `None`.',
      'Usually a function that forgot to `return`, or a method like `.sort()` or `.append()` that changes a list in place and returns `None`. Check the line that set the variable.',
      "nums = [3, 1, 2]\nnums.sort()        # don't write nums = nums.sort()\nprint(nums[0])")
error(r"'NoneType' object has no attribute '(\w+)'", 'You called `.{0}` on something that is `None`.',
      'The variable was never given a real value: a function without `return`, a lookup that found nothing (`re.search`, `dict.get`), or an in-place method whose result you saved. Check for `None` before using it.',
      "import re\nm = re.search(r'\\d+', 'abc')\nif m is not None:\n    print(m.group())")
error(r"'(\w+)' object has no attribute '(\w+)'", 'A `{0}` doesn\'t have anything called `{1}`.',
      'Check the spelling and the type: `print(type(x))` shows what you actually have. A common case is a list where you expected one item, or a string where you expected a number or a dict.', None)
error(r"'(\w+)' object is not callable", 'You put `(...)` after something that is a `{0}`, not a function.',
      'Usually a variable that has the same name as a function (for example `list = [1, 2]` and later `list(...)`), or a missing operator such as `2(3)` instead of `2 * (3)`. Rename the variable.',
      "items = [1, 2]       # not: list = [1, 2]\nprint(list(range(3)))")
error(r"'(\w+)' object is not iterable", 'You looped over (or unpacked) a `{0}`, which isn\'t a collection.',
      'For a number of repetitions use `range(n)`; if you meant a list, check what the variable really holds.', "n = 3\nfor i in range(n):\n    print(i)")
error(r"'(\w+)' object is not subscriptable", 'You used `[...]` on a `{0}`, which can\'t be indexed.',
      'Check the variable: you probably meant a list, string or dict. `print(type(x), x)` shows what it is.', None)
error(r"'(\w+)' object does not support item assignment", 'A `{0}` can\'t be changed in place.',
      'Strings and tuples are immutable. Build a new one instead, or convert to a list first.', "s = 'cat'\ns = 'b' + s[1:]      # 'bat'")
error(r"unhashable type: '(\w+)'", 'A `{0}` can\'t be a dictionary key or a set member, because it can change.',
      'Convert it to a tuple first.', "seen = set()\nseen.add(tuple([1, 2]))")
error(r'missing (\d+) required positional arguments?: (.+)', 'The function was called with {0} argument(s) too few: {1}.',
      'Pass the missing value(s). With methods, the usual cause is calling it on the class instead of an object (`Dog.speak()` instead of `Dog().speak()`).', None)
error(r'takes (\d+) positional arguments? but (\d+) (?:were|was) given', 'The function expects {0} argument(s) but got {1}.',
      'Check the call. For a method defined in a class, remember the first parameter is `self`: `def speak(self):`.', "class Dog:\n    def speak(self):\n        return 'woof'")
error(r"name '(\w+)' is not defined", 'Python doesn\'t know anything called `{0}` at that point.',
      'Check the spelling and capitals, that it\'s assigned (or imported) before this line, and that text is in quotes: `print(hello)` looks for a variable, `print(\'hello\')` prints the word.', None)
error(r'list index out of range', 'You asked for a position the list doesn\'t have.',
      'A list of length n has positions 0 to n-1, so `items[len(items)]` is one too far. Check `len(items)`, and that the list isn\'t empty.', "items = ['a', 'b']\nprint(items[-1])     # last item, safe if not empty")
error(r'string index out of range', 'You asked for a character position the string doesn\'t have.',
      'Valid positions are 0 to len(s) - 1. Check for an empty string before `s[0]`.', None)
error(r'^KeyError|\bKeyError\b', 'The dictionary has no such key.',
      'Use `d.get(key)` (gives `None` or a default) or check `if key in d:` first. Check the spelling and capitals, and for stray spaces.', "ages = {'Ada': 36}\nprint(ages.get('Bob', 0))")
error(r"invalid literal for int\(\) with base 10: '([^']*)'", "`int()` can't turn `'{0}'` into a whole number.",
      'Strip spaces and newlines with `.strip()`, use `float()` for decimals, and catch `ValueError` for anything a user types.', "text = ' 42\\n'\nprint(int(text.strip()))")
error(r'could not convert string to float', '`float()` got text that isn\'t a number.',
      'Look for commas as decimal points or thousands separators (`"1,5"`), currency signs, or empty strings. Clean the text first: `float(s.replace(",", ""))`.', None)
error(r'division by zero|ZeroDivisionError', 'You divided by zero.',
      'Check the divisor before dividing, for example when averaging an empty list.', "nums = []\navg = sum(nums) / len(nums) if nums else 0")
error(r"No module named '([\w.]+)'", 'Python can\'t find the module `{0}`.',
      'Install it with `python -m pip install {0}` (the package name is sometimes different, e.g. `pip install pillow` for `PIL`). If it is installed, you are probably running a different Python or virtual environment from the one you installed it into.', None)
error(r'expected an indented block', 'A line that ends with `:` (`if`, `for`, `def`, ...) must be followed by an indented block.',
      'Indent the body by 4 spaces. If it should be empty for now, write `pass`.', "def todo():\n    pass")
error(r'unexpected indent', 'A line is indented when it shouldn\'t be.', 'Line it up with the lines around it. Mixing tabs and spaces also causes this: use spaces only.', None)
error(r'unindent does not match', 'The indentation goes back to a level that doesn\'t match any earlier block.', 'Make the blocks line up exactly, using spaces only (4 per level).', None)
error(r'invalid syntax|SyntaxError', 'Python couldn\'t read the line as code.',
      'Look at the line shown and the one before it: a missing `:` after `if`/`for`/`def`, an unclosed bracket or quote, `=` where you meant `==`. Paste the code and I\'ll point at the exact spot.', None)
error(r"No such file or directory: '([^']+)'", "Python can't find `{0}`.",
      'A relative path is looked up from the folder you run the script in, not where the script lives. Print `os.getcwd()` to see it, or build the path from the script: `Path(__file__).parent / "{0}"`.', None)
error(r'maximum recursion depth exceeded', 'A function called itself too many times (about 1000 levels).',
      'Usually the stopping case (base case) is missing or never reached. Check that each call moves towards it; for very deep inputs, use a loop instead.', None)
error(r"local variable '(\w+)' referenced before assignment|cannot access local variable '(\w+)'", 'Inside the function, `{0}` is assigned somewhere, so Python treats it as local, but you read it before that happens.',
      'Pass the value in as an argument and return the new one, or (for a module-level counter) declare `global {0}` at the top of the function.', None)
error(r'JSONDecodeError|Expecting value: line', 'The text isn\'t valid JSON.',
      'Print what you received (`print(repr(text[:200]))`). Common causes: an empty response, an HTML error page, single quotes, or a trailing comma.', None)
error(r"'(\w+)' codec can't decode", 'The file isn\'t in the text encoding Python tried.',
      "Open it with the right encoding, usually `open(path, encoding='utf-8')`; for unknown files `errors='replace'` keeps going.", None)
error(r'Permission denied', 'The operating system refused access to that file or folder.',
      'The file may be open in another program (Excel locks files on Windows), you may be writing to a folder that needs admin rights, or the path is a folder, not a file.', None)
error(r'too many values to unpack|not enough values to unpack', 'The number of names on the left doesn\'t match the number of values on the right.',
      'Check how many items the right side really has. When looping over a dict, use `.items()` to get pairs.', "for name, age in {'Ada': 36}.items():\n    print(name, age)")


def explain_error(text):
    for pattern, meaning, fix, example in E:
        m = pattern.search(text)
        if not m:
            continue
        groups = [g for g in m.groups() if g is not None] if m.groups() else []
        fill = lambda s: s.format(*groups) if groups else s
        kind = re.search(r'\b(\w+(?:Error|Exception))\b', text)
        head = f"**{kind[1]}:** " if kind else ''
        parts = [head + fill(meaning), fill(fix)]
        if example:
            parts.append(code(example))
        parts.append('If it still happens, paste the full traceback and the line it points to.')
        return '\n\n'.join(parts)
    return None


# ---------------------------------------------------------------- changes to the function just written
RECURSIVE = {
    'factorial': ('n', "def factorial(n):\n    if n <= 1:\n        return 1\n    return n * factorial(n - 1)",
                  'The base case `n <= 1` stops the recursion; each call works on a smaller `n`.'),
    'fibonacci': ('n', "def fibonacci(n):\n    if n < 2:\n        return n\n    return fibonacci(n - 1) + fibonacci(n - 2)",
                  'Simple but slow for large n (it repeats work); `functools.lru_cache` on top makes it fast.'),
    'fib': ('n', "def fib(n):\n    if n < 2:\n        return n\n    return fib(n - 1) + fib(n - 2)", 'Add `@functools.lru_cache` above it for large n.'),
    'sum_list': ('items', "def sum_list(items):\n    if not items:\n        return 0\n    return items[0] + sum_list(items[1:])", 'The empty list is the base case.'),
    'reverse_string': ('text', "def reverse_string(text):\n    if len(text) <= 1:\n        return text\n    return reverse_string(text[1:]) + text[0]", 'Strings of length 0 or 1 are their own reverse.'),
    'power': ('base, exp', "def power(base, exp):\n    if exp == 0:\n        return 1\n    return base * power(base, exp - 1)", 'Works for whole-number exponents of 0 or more.'),
    'gcd': ('a, b', "def gcd(a, b):\n    if b == 0:\n        return a\n    return gcd(b, a % b)", "Euclid's algorithm: gcd(a, b) = gcd(b, a mod b)."),
    'count_down': ('n', "def count_down(n):\n    if n < 0:\n        return\n    print(n)\n    count_down(n - 1)", 'Stops once n goes below 0.'),
    'is_palindrome': ('text', "def is_palindrome(text):\n    cleaned = ''.join(ch.lower() for ch in text if ch.isalnum())\n    if len(cleaned) <= 1:\n        return True\n    return cleaned[0] == cleaned[-1] and is_palindrome(cleaned[1:-1])",
                      'Compares the outer pair, then the rest.'),
    'binary_search': ('items, target, lo=0, hi=None', "def binary_search(items, target, lo=0, hi=None):\n    if hi is None:\n        hi = len(items) - 1\n    if lo > hi:\n        return -1\n    mid = (lo + hi) // 2\n    if items[mid] == target:\n        return mid\n    if items[mid] < target:\n        return binary_search(items, target, mid + 1, hi)\n    return binary_search(items, target, lo, mid - 1)",
                      'Each call halves the search range; -1 means not found.'),
}

FOLLOW_CHANGE = re.compile(r'(?i)^(?:now |ok,? |okay,? |and |can you |could you |please )*(?:make|rewrite|write|change|turn|do|convert)\b.{0,20}\b(recursive(?:ly)?|recursion|iterative(?:ly)?|(?:with |using )?a loop|type hints?|typed|docstring|comments?|one[- ]liner)\b'
                         r'|^(?:now |and |ok,? |okay,? |please )*(?:(?:can|could|would|will) you (?:please )?)?add (?:some |a |the )?(?:type hints?|docstrings?|comments?)\b')


def last_code(messages):
    for m in reversed(messages[:-1]):
        if m.get('role') == 'assistant':
            blocks = re.findall(r'```python\n(.*?)```', m.get('content') or '', re.S)
            if blocks:
                return blocks[0]
    return None


def function_name(source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    return funcs[0] if funcs else None


def docstring_for(fn):
    words = fn.name.replace('_', ' ')
    params = ', '.join(a.arg for a in fn.args.args)
    return f'"""Return the {words} of {params}."""' if params else f'"""{words.capitalize()}."""'


EMPTY_GUARD = re.compile(r"(?i)\b(?:handle|deal with|cope with|work (?:with|for)|support|check for|guard against)\b.{0,15}\b(?:an? |the )?(?:empty|blank)\b"
                         r"|\bwhat (?:if|happens if|about if) (?:the |my )?(?:list|string|input|it) is empty\b|\bempty (?:list|string|input)s?\b.{0,20}\b(?:crash|error|fail|break)")
EMPTY_RESULT = {'max': 'None', 'min': 'None', 'largest': 'None', 'smallest': 'None', 'sum': '0', 'total': '0', 'count': '0',
                'average': 'None', 'mean': 'None', 'first': 'None', 'last': 'None', 'second': 'None', 'join': "''", 'reverse': "''"}


def empty_guard(messages):
    """'Now make it handle an empty list' after a function CAEL wrote: a guard at the top that returns a sensible value."""
    text = messages[-1].get('content') or ''
    if not EMPTY_GUARD.search(text):
        return None
    source = last_code(messages)
    fn = function_name(source) if source else None
    if fn is None or not fn.args.args:
        return None
    arg = fn.args.args[0].arg
    value = next((v for k, v in EMPTY_RESULT.items() if k in fn.name), 'None')
    lines = source.rstrip('\n').split('\n')
    head = next(i for i, l in enumerate(lines) if l.lstrip().startswith('def '))
    indent = ' ' * (len(lines[head]) - len(lines[head].lstrip()) + 4)
    body = head + 1
    if body < len(lines) and lines[body].strip().startswith(('"""', "'''")):
        body += 1
    lines[body:body] = [f'{indent}if not {arg}:', f'{indent}    return {value}']
    new = '\n'.join(lines)
    try:
        space = {}
        exec(compile(new, '<guard>', 'exec'), space)
        got = space[fn.name]('' if 'str' in fn.name or arg in ('s', 'text', 'word') else [])
    except Exception:
        return None
    return reply(code(new) + f"\n\nIt now returns `{value}` for an empty input instead of failing (checked: `{fn.name}([])` gives `{got!r}`). "
                 "If you'd rather it raised a clear error, use `raise ValueError('empty input')` there instead.", 'python-empty-guard')


def change(messages):
    text = messages[-1].get('content') or ''
    guarded = empty_guard(messages)
    if guarded:
        return guarded
    m = FOLLOW_CHANGE.search(text.strip())
    if not m:
        return None
    source = last_code(messages)
    if not source:
        return None
    fn = function_name(source)
    if fn is None:
        return None
    want = m.group(0).lower()
    if 'recurs' in want:
        known = RECURSIVE.get(fn.name)
        if not known:
            return reply(f"I don't have a checked recursive version of `{fn.name}`. The pattern is: handle the smallest input directly "
                         '(the base case), and otherwise call the function on a smaller piece and combine the result. '
                         'Tell me what the smallest case should return and I can help write it.', 'python-change-unknown')
        _, src, note = known
        return reply(code(src) + f'\n\nThis is the recursive version of `{fn.name}`. {note}', 'python-recursive')
    if 'docstring' in want or 'comment' in want:
        lines = source.rstrip('\n').split('\n')
        head = next(i for i, l in enumerate(lines) if l.lstrip().startswith('def '))
        indent = ' ' * (len(lines[head]) - len(lines[head].lstrip()) + 4)
        lines.insert(head + 1, indent + docstring_for(fn))
        return reply(code('\n'.join(lines)) + '\n\nI added a docstring; `help(' + fn.name + ')` now shows it. Edit the wording to say exactly what it promises.',
                     'python-docstring')
    if 'type hint' in want or 'typed' in want:
        hints = {'n': 'int', 'items': 'list', 'numbers': 'list[int]', 'text': 'str', 's': 'str', 'a': 'int', 'b': 'int', 'base': 'int', 'exp': 'int'}
        params = ', '.join(f"{a.arg}: {hints.get(a.arg, 'object')}" for a in fn.args.args)
        new = re.sub(r'def ' + re.escape(fn.name) + r'\([^)]*\):', f'def {fn.name}({params}):', source, count=1)
        return reply(code(new) + '\n\nType hints document what each argument should be; Python doesn\'t enforce them, but editors and `mypy` check them. '
                     'Adjust any I guessed as `object`.', 'python-type-hints')
    return None


# ---------------------------------------------------------------- entry
def reply(text, kind):
    return dict(route='chat/python-' + kind if not kind.startswith('python') else 'chat/' + kind, response=text, sources=[],
                details="The Programmer (python_answers.py): authored Python answers whose code was run when written; not a web lookup.")


def python_context(messages, k=4):
    users = [m.get('content') or '' for m in messages if m.get('role') in ('user', 'assistant')][-k:]
    return any(PY.search(u) for u in users)


def find_topic(text, python_here):
    """First match, with the short operation entries (op_*) checked before the broad topics: 'write my list to a file one
    per line' is the specific write-lines answer, not the general write-a-file one."""
    order = [n for n in T if n.startswith('op_')] + [n for n in T if not n.startswith('op_')]
    for name in order:
        t = T[name]
        if (python_here or not t['needs_python']) and any(p.search(text) for p in t['patterns']):
            return name
    return None


def last_topic(messages):
    """The topic of the previous answer, recognised by its opening words (no hidden markers in replies)."""
    for m in reversed(messages[:-1]):
        if m.get('role') == 'assistant':
            said = (m.get('content') or '').strip()
            for name, t in T.items():
                if said[:60] and said[:60] == t['answer'][:60]:
                    return name
                if any(said[:60] == a[:60] for _, a in t['follow']):
                    return name
            return None
    return None


WRITE_ME = re.compile(r'(?i)\b(?:write|create|make|give me|code|implement|build)\b.{0,40}\b(?:function|program|script|class|def|generator|app|game|bot|tool|calculator|website|scraper)s?\b')
CAPABILITY = re.compile(r'(?i)\bwhat (?:can|could) you (?:help|do)\b|\bwhat (?:are you|do you) (?:able|good) (?:to|at)\b|\bwhat can i ask you\b|\bhow can you help\b')
CAPABILITIES = ("Quite a lot of everyday things. For example, I can:\n\n"
                "- **Work things out:** percentages, splitting bills, budgets, unit conversions, dates and times.\n"
                "- **Write:** emails, thank-you notes, messages, short stories, summaries and name ideas.\n"
                "- **Python:** write and check small functions, explain code and error messages, and fix simple bugs.\n"
                "- **Everyday problems:** a slow drain, a squeaky door, a car that won't start, what to try first and when to call someone.\n"
                "- **Talk things through:** nerves before an interview, a hard day, worries about family.\n"
                "- **Look things up** on the web and tell you where the answer came from.\n\n"
                "What would you like to start with?")


def respond(messages):
    text = (messages[-1].get('content') or '').strip()
    if not text:
        return None
    if CAPABILITY.search(text) and len(text) < 80:
        return dict(route='chat/capabilities', response=CAPABILITIES, sources=[], details='Authored overview of what CAEL can do.')
    changed = change(messages)
    if changed:
        return changed
    if re.search(r'\b\w*(?:Error|Exception)\b', text) and (re.search(r'(?i)\b(?:mean|error|why|fix|help|get|getting|got|what)\b', text)
                                                           or text.count('\n') > 1 or re.match(r'\s*(?:\w+\.)*\w+(?:Error|Exception)\b', text)):
        explained = explain_error(text)
        if explained:
            return reply(explained, 'error')
    here = python_context(messages)
    previous = last_topic(messages)
    if previous and len(text.split()) <= 20:
        for pattern, answer in T[previous]['follow']:
            if pattern.search(text):
                return reply(answer, 'followup')
    if len(text) > 400 or '```' in text:
        return None                     # pasted code goes to the code workbench (codegen)
    if WRITE_ME.search(text) and not re.search(r'(?i)\bhow (?:do|can|would|should) (?:i|you|we)\b|\bhow to\b|\bexplain\b|\bwhat is\b', text):
        return None                     # "Write a function that ..." is the code writer's (python_help, codegen)
    name = find_topic(text, here)
    if name:
        # an exact pattern can fire on the wrong topic ("get rid of duplicate words" hits remove-an-item); when the word
        # overlap clearly prefers another topic, that one wins
        ranked = dict((i, s) for s, i in index().scores(text))
        top = max(ranked, key=ranked.get)
        if top != name and ranked[top] >= LEAST and ranked[top] > 1.5 * max(ranked.get(name, 0), 0.1):
            name = top
        return reply(T[name]['answer'], 'topic')
    # rewordings: word overlap with each topic's own text (phrase_match), only in a Python conversation and for a question
    if here and ASKING.search(text):
        idx = index()
        if previous and len(text.split()) <= 14:
            # a short follow-up ("And how do I write them back?", "Show me one used for sorting"): the previous question gives
            # it its subject; the answer is another topic than the one just given
            asked = next((m.get('content') or '' for m in reversed(messages[:-1]) if m.get('role') == 'user'), '')
            got = idx.best(text + ' ' + asked, least=LEAST, allowed=set(T) - {previous})
            if got:
                return reply(T[got]['answer'], 'followup-match')
        got = idx.best(text, least=LEAST)
        if got:
            return reply(T[got]['answer'], 'topic-match')
    return None


ASKING = re.compile(r"(?i)\?\s*$|\b(?:how|what|why|which|can|could|is there|show me|example|explain|difference)\b|^\s*(?:in )?python\b\s*[:,-]?")
LEAST = 5.0
_index = None


ALSO = {   # the other words people use for the same thing (searched, never shown)
    'op_lower_upper': 'every letter small capital letters case change uppercase lowercase',
    'op_insert': 'put add element item beginning front start middle position place before',
    'op_index_of': 'where position place find locate sits which index item element',
    'op_join_list': 'glue words together into one sentence string join list separator commas',
    'op_empty_check': 'nothing in it no items empty check list has none blank',
    'op_replace_text': 'swap substitute change one word another replace characters',
    'op_enumerate': 'index and item at the same time counter position loop number each',
    'op_zip': 'two lists together side by side pair loop parallel at once',
    'op_sleep_wait': 'pause wait delay seconds program stop for a while sleep',
    'op_print_no_newline': 'same line one line no line break newline end print',
    'op_list_contains': 'inside contains member present in my list value there',
    'op_sort_desc': 'biggest to smallest highest to lowest descending reverse order sort',
    'sort_dicts': 'order sort dictionaries by one field key value list of dicts',
    'string_format': 'variable inside string insert value text f-string format placeholder',
    'op_file_exists': 'file there exists present before opening check path',
    'op_length': 'how many characters items elements size length count',
    'remove_duplicates': 'repeated values duplicates unique keep order drop dedupe',
    'op_type_check': 'kind type of variable what type is it check type',
    'op_remove_item': 'remove take out delete item element value from list',
    'op_dict_delete': 'remove delete key entry from dictionary',
    'op_read_lines': 'load lines of a file into a list read lines',
    'op_write_lines': 'write save list items to a file each on its own line',
    'op_make_folder': 'create new folder directory make',
    'op_exit_program': 'stop end quit exit script program early',
    'op_strip_spaces': 'trim remove spaces whitespace ends newline',
    'op_slicing': 'part of a string first last characters piece slice',
    'op_convert_types': 'turn text into number int float string convert change type',
    'merge_dicts': 'join combine two dictionaries together merge',
}


def doc_of(name):
    """Searchable text of a topic: its name, answer prose, identifiers in its code, the literal words of its patterns, and a
    short line of the other words people use for it."""
    t = T[name]
    words = [name.replace('op_', '').replace('_', ' '), ALSO.get(name, '')]
    words.append(re.sub(r'```.*?```', ' ', t['answer'], flags=re.S))
    words += re.findall(r'\.?([a-z_]{3,})\(', t['answer'])
    for p in t['patterns']:
        words.append(re.sub(r'\\[bswdBSWD]|\(\?[:!=<i]+|[\\()\[\]{}|?*+^$.,0-9]', ' ', p.pattern))
    return ' '.join(words)


def index():
    global _index
    if _index is None:
        from .phrase_match import Index
        _index = Index({n: doc_of(n) for n in T})
    return _index
