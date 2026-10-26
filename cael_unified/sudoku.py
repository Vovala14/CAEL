"""Sudoku: solve any 9x9 puzzle (including the hardest known ones), make new puzzles up to expert level with exactly
one solution, give a reasoned hint for the next move, and check a filled grid. Never a neural model.

Solving uses Knuth's Algorithm X (exact cover over the 324 Sudoku constraints), which finds every solution of any 9x9
grid in milliseconds; it counts solutions up to two, so it can tell a proper puzzle (one solution) from a broken one.
Difficulty is rated the way people experience it: a puzzle the two everyday rules alone can finish - a cell with one
candidate left (naked single), a digit with one possible place in a row, column or box (hidden single) - is easy or
medium; one that needs search is hard, and one that needs a long search is expert. Hints use the same two rules.
"""
import random
import re

ALL = 0x3FE                                         # bits 1..9
UNITS = ([[r * 9 + c for c in range(9)] for r in range(9)] + [[r * 9 + c for r in range(9)] for c in range(9)] +
         [[(br + r) * 9 + bc + c for r in range(3) for c in range(3)] for br in (0, 3, 6) for bc in (0, 3, 6)])
PEERS = [sorted({p for u in UNITS if i in u for p in u} - {i}) for i in range(81)]
UNIT_NAMES = [f'row {r + 1}' for r in range(9)] + [f'column {c + 1}' for c in range(9)] + \
             [f'box {b + 1}' for b in range(9)]


def bits(mask):
    return [d for d in range(1, 10) if mask >> d & 1]


def parse(text):
    """81 cells from a grid in the text: digits with 0 . _ or - for blanks, in one line or nine lines."""
    rows = [re.sub(r'[^0-9._-]', '', line) for line in text.splitlines()]
    rows = [r for r in rows if len(r) == 9]
    cells = ''.join(rows[:9]) if len(rows) >= 9 else ''
    if len(cells) != 81:
        flat = re.findall(r'[0-9._-]{81}', re.sub(r'[\s|+]', '', text))
        cells = flat[0] if flat else ''
    if len(cells) != 81:
        return None
    return [int(ch) if ch.isdigit() else 0 for ch in cells]


class Board:
    """Candidates per cell, filled in by the two everyday rules only (naked and hidden singles); no guessing."""

    def __init__(self, grid):
        self.cand = [ALL] * 81
        self._done = set()                              # cells already placed and propagated
        queue = [(i, v) for i, v in enumerate(grid) if v]
        self.ok = self.place(queue) and self.singles()

    def place(self, queue):
        while queue:
            i, d = queue.pop()
            if not self.cand[i] >> d & 1:
                return False
            if i in self._done:
                continue
            self.cand[i] = 1 << d
            self._done.add(i)
            for p in PEERS[i]:
                if self.cand[p] >> d & 1:
                    self.cand[p] &= ~(1 << d)
                    if not self.cand[p]:
                        return False
                    if self.cand[p] & (self.cand[p] - 1) == 0:
                        queue.append((p, self.cand[p].bit_length() - 1))
        return True

    def singles(self):
        """Hidden singles until nothing changes (naked singles are placed as they appear)."""
        changed = True
        while changed:
            changed = False
            for unit in UNITS:
                for d in range(1, 10):
                    places = [i for i in unit if self.cand[i] >> d & 1]
                    if not places:
                        return False
                    if len(places) == 1 and places[0] not in self._done:
                        if not self.place([(places[0], d)]):
                            return False
                        changed = True
        return True

    def solved(self):
        return all(c & (c - 1) == 0 for c in self.cand)


def exact_cover(grid, limit=2, rng=None, stats=None):
    """Knuth's Algorithm X on the 324 Sudoku constraints: up to `limit` solutions (lists of 81 digits)."""
    X = {}
    for r in range(9):
        for c in range(9):
            for n in range(1, 10):
                b = (r // 3) * 3 + c // 3
                for key in (('rc', r, c), ('rn', r, n), ('cn', c, n), ('bn', b, n)):
                    X.setdefault(key, set()).add((r, c, n))
    Y = {(r, c, n): [('rc', r, c), ('rn', r, n), ('cn', c, n), ('bn', (r // 3) * 3 + c // 3, n)]
         for r in range(9) for c in range(9) for n in range(1, 10)}

    def select(row):
        cols = []
        for j in Y[row]:
            for i in X[j]:
                for k in Y[i]:
                    if k != j:
                        X[k].remove(i)
            cols.append(X.pop(j))
        return cols

    def deselect(row, cols):
        for j in reversed(Y[row]):
            X[j] = cols.pop()
            for i in X[j]:
                for k in Y[i]:
                    if k != j:
                        X[k].add(i)

    chosen = []
    for i, v in enumerate(grid):
        if v:
            row = (i // 9, i % 9, v)
            if any(j not in X or row not in X[j] for j in Y[row]):
                return []                               # two givens clash
            select(row)
            chosen.append(row)
    found = []

    def search():
        if not X:
            g = [0] * 81
            for r, c, n in chosen:
                g[r * 9 + c] = n
            found.append(g)
            return len(found) >= limit
        col = min(X, key=lambda j: len(X[j]))
        options = list(X[col])
        if rng:
            rng.shuffle(options)
        if stats is not None and len(options) > 1:
            stats['branches'] = stats.get('branches', 0) + len(options) - 1   # real choices, not forced moves
        for row in options:
            if stats is not None:
                stats['nodes'] = stats.get('nodes', 0) + 1
                if stats['nodes'] > stats.get('cap', 200000):
                    raise TimeoutError('search limit')
            chosen.append(row)
            cols = select(row)
            done = search()
            deselect(row, cols)
            chosen.pop()
            if done:
                return True
        return False

    search()
    return found


def solve(grid, limit=2):
    """(solutions, search nodes, solved by singles alone)."""
    stats = {'nodes': 0, 'branches': 0}
    solutions = exact_cover(grid, limit, stats=stats)
    logic = Board(grid)
    return solutions, stats['branches'], logic.ok and logic.solved()


def rate(grid):
    solutions, nodes, logic_only = solve(grid, limit=2)
    if len(solutions) != 1:
        return None, nodes
    if logic_only:
        clues = sum(1 for v in grid if v)
        return ('easy' if clues >= 34 else 'medium'), nodes
    return ('hard' if nodes <= 12 else 'expert'), nodes


def generate(level='expert', seed=None, tries=30, budget=6.0):
    """A new puzzle with exactly one solution at the requested level (easy, medium, hard, expert).
    Expert puzzles are minimal: no given can be removed without losing the unique solution."""
    import time
    rng = random.Random(seed)
    started = time.time()
    order = {'easy': 0, 'medium': 1, 'hard': 2, 'expert': 3}
    want = order.get(level, 3)
    best = None
    for _ in range(tries):
        puzzle = exact_cover([0] * 81, limit=1, rng=rng)[0]         # a random complete grid
        cells = list(range(81))
        rng.shuffle(cells)
        floor = {0: 36, 1: 28, 2: 0, 3: 0}[want]
        for i in cells:                                # remove givens while the solution stays unique
            if sum(1 for v in puzzle if v) <= floor:
                break
            keep, puzzle[i] = puzzle[i], 0
            if len(exact_cover(puzzle, limit=2)) != 1:
                puzzle[i] = keep
        got, nodes = rate(puzzle)
        if got is None:
            continue
        if order[got] == want and want < 3:
            return puzzle, got
        score = (order[got] == want, nodes if want == 3 else -abs(order[got] - want))
        if best is None or score > best[2]:
            best = (puzzle, got, score)
        # Expert: keep the hardest puzzle found (most search needed) within the time budget.
        if want == 3 and time.time() - started > budget and best and best[1] == 'expert':
            break
    return best[0], best[1]


# Famous hardest puzzles (widely published grids). A random symmetry of one keeps its exact difficulty.
FAMOUS = {
    'Arto Inkala, 2012 ("world\'s hardest Sudoku")': '8..........36......7..9.2...5...7.......457.....1...3...1....68..85...1..9....4..',
    'AI Escargot (Arto Inkala, 2006)': '1....7.9..3..2...8..96..5....53..9...1..8...26....4...3......1..4......7..7...3..',
    'top95 #1': '4.....8.5.3..........7......2.....6.....8.4......1.......6.3.7.5..2.....1.4......',
    'top95 #2': '52...6.........7.13...........4..8..6......5...........418.........3..2...87.....',
    'top95 #3': '6.....8.3.4.7.................5.4.7.3..2.....1.6.......2.....5.....8.6......1....',
    'top95 #4': '48.3............71.2.......7.5....6....2..8.............1.76...3.....4......5....',
}


def transform(grid, rng):
    """A random symmetry of a Sudoku: relabel digits, shuffle rows within bands and bands, columns within stacks and
    stacks, and maybe transpose. The result is a different-looking puzzle with exactly the same difficulty."""
    digits = list(range(1, 10))
    rng.shuffle(digits)
    relabel = {0: 0, **{d: digits[d - 1] for d in range(1, 10)}}
    def order():
        bands = [0, 1, 2]
        rng.shuffle(bands)
        out = []
        for b in bands:
            rows = [0, 1, 2]
            rng.shuffle(rows)
            out += [b * 3 + r for r in rows]
        return out
    rows, cols = order(), order()
    new = [relabel[grid[rows[r] * 9 + cols[c]]] for r in range(9) for c in range(9)]
    if rng.random() < 0.5:
        new = [new[c * 9 + r] for r in range(9) for c in range(9)]
    return new


def hardest(seed=None):
    rng = random.Random(seed)
    name = rng.choice(sorted(FAMOUS))
    base = [int(ch) if ch.isdigit() else 0 for ch in FAMOUS[name]]
    return transform(base, rng), name


def show(grid):
    lines = []
    for r in range(9):
        if r in (3, 6):
            lines.append('------+-------+------')
        row = ''
        for c in range(9):
            if c in (3, 6):
                row += '| '
            v = grid[r * 9 + c]
            row += (str(v) if v else '.') + ' '
        lines.append(row.rstrip())
    return '\n'.join(lines)


def hint(grid):
    """The next logical move with its reason: a naked or hidden single, or None if guessing is needed."""
    board = Board([0] * 81)
    for i, v in enumerate(grid):
        if v:
            board.cand[i] = 1 << v
    for i, v in enumerate(grid):                      # plain elimination from the givens, without propagation
        if v:
            for p in PEERS[i]:
                board.cand[p] &= ~(1 << v)
    for i in range(81):
        if not grid[i] and board.cand[i] and board.cand[i] & (board.cand[i] - 1) == 0:
            d = board.cand[i].bit_length() - 1
            return i, d, f'row {i // 9 + 1}, column {i % 9 + 1} can only be **{d}**: every other digit already appears in its row, column or box.'
    for u, unit in enumerate(UNITS):
        for d in range(1, 10):
            if any(grid[i] == d for i in unit):
                continue
            places = [i for i in unit if not grid[i] and board.cand[i] >> d & 1]
            if len(places) == 1:
                i = places[0]
                return i, d, f'in {UNIT_NAMES[u]}, **{d}** fits only at row {i // 9 + 1}, column {i % 9 + 1}.'
    return None


def valid_complete(grid):
    return all(sorted(grid[i] for i in unit) == list(range(1, 10)) for unit in UNITS)


# ---------------------------------------------------------------- chat

ASK_NEW = re.compile(r'(?i)\b(?:give|make|generate|create|show|send)\b.*\bsudoku\b|\b(?:play|start|new)\b.*\bsudoku\b|\bsudoku\b.*\b(?:puzzle )?(?:for me|please)\b')
LEVEL = re.compile(r'(?i)\b(easy|simple|beginner|medium|normal|hard|expert|hardest|highest|evil|extreme|diabolical|insane|'
                   r'difficult|maximum|max|toughest|impossible|master|ultimate)\b')
TOP = {'hardest', 'highest', 'evil', 'extreme', 'diabolical', 'insane', 'maximum', 'max', 'toughest', 'impossible', 'master', 'ultimate'}


def last_puzzle(messages):
    """The puzzle CAEL gave earlier in this conversation (its one-line form), or None."""
    for m in reversed(messages or []):
        if m.get('role') == 'assistant':
            found = re.search(r'Puzzle in one line: `([0-9.]{81})`', m.get('content', ''))
            if found:
                return [int(ch) if ch.isdigit() else 0 for ch in found.group(1)]
    return None


def reply(text, messages=None):
    low = text.lower()
    earlier = last_puzzle(messages)
    follow_up = earlier is not None and re.fullmatch(
        r"\s*(?:(?:give me |can i (?:have|get) |i need |any )?(?:a |another )?hint|i'?m stuck|help(?: me)?|next (?:move|step)|"
        r"(?:please )?solve it|show (?:me )?the (?:solution|answer)|(?:i )?give up|what'?s the (?:solution|answer))\s*[.!?]*\s*", low)
    if 'sudoku' not in low and not follow_up and not re.search(r'(?i)\bsolve (?:this|the) (?:puzzle|grid)\b', text) \
            and not (earlier is not None and parse(text) is not None):
        return None
    grid = parse(text)
    if grid is None and follow_up:
        grid = list(earlier)
        if re.search(r'hint|stuck|help|next', low):
            low += ' hint'
    if grid is not None:
        clues = sum(1 for v in grid if v)
        if clues == 81:
            if earlier is not None and any(g and g != v for g, v in zip(earlier, grid)):
                changed = [f'row {i // 9 + 1}, column {i % 9 + 1}' for i, (g, v) in enumerate(zip(earlier, grid)) if g and g != v]
                return out('**Not quite:** some of the original givens were changed (' + ', '.join(changed[:4]) + ').', 'check')
            if valid_complete(grid):
                return out('**Correct!** Every row, column and box has the digits 1 to 9 exactly once.', 'check')
            bad = [UNIT_NAMES[u] for u, unit in enumerate(UNITS) if sorted(grid[i] for i in unit) != list(range(1, 10))]
            return out('**Not quite.** These have a repeated or missing digit: ' + ', '.join(bad[:6]) + '.', 'check')
        if re.search(r'\bhint\b|next (?:move|step)|help me|stuck', low):
            found = hint(grid)
            if found:
                return out('**Hint:** ' + found[2], 'hint')
            return out('No single forced move is left from the givens alone; the next step needs a pair or a guess. '
                       'Ask me to solve it if you want the answer.', 'hint')
        try:
            solutions, guesses, logic_only = solve(grid, limit=2)
        except TimeoutError:   # pragma: no cover - only for grids with almost no givens
            return out('This grid has so few givens that it has a huge number of solutions, so it is not a proper Sudoku. '
                       'A proper puzzle needs at least 17 givens and exactly one solution.', 'none')
        if not solutions:
            return out('This Sudoku has **no solution**: the givens contradict each other (check for a repeated digit).', 'none')
        level, _ = rate(grid)
        extra = '' if len(solutions) == 1 else '\n\nNote: this puzzle has **more than one solution**, so it is not a proper Sudoku; this is one of them.'
        how = ('it can be solved by logic alone (naked and hidden singles)' if logic_only else
               f'logic alone gets stuck, so it needed a search of {guesses} steps with backtracking')
        return out(f'Solved ({clues} givens, {how}; difficulty: {level or "not unique"}):\n```text\n{show(solutions[0])}\n```' + extra, 'solve')
    if ASK_NEW.search(text) or re.search(r'(?i)\bsudoku\b', text):
        word = (LEVEL.search(text) or [None, 'expert'])[1].lower()
        note = ''
        if word in TOP or re.search(r'(?i)most difficult|world.?s hardest|inkala', text):
            puzzle, name = hardest()
            level = 'highest-level'
            note = (f'\n\nThis is a reshuffled version of a famous hardest puzzle ({name}): digits relabelled and rows, columns '
                    'and boxes swapped, so it looks new but is exactly as hard. Logic rules alone cannot finish it.')
        else:
            level = {'simple': 'easy', 'beginner': 'easy', 'normal': 'medium', 'difficult': 'hard'}.get(word, word)
            puzzle, level = generate(level)
        clues = sum(1 for v in puzzle if v)
        article = 'an' if level[0] in 'aeiou' else 'a'
        return out(f'Here is {article} **{level}** Sudoku ({clues} givens, exactly one solution):{note}\n```text\n{show(puzzle)}\n```\n'
                   'Fill each row, column and 3x3 box with 1 to 9. Send it back with your digits to check it, ask for a '
                   '**hint** with the grid, or ask me to **solve** it.\n\nPuzzle in one line: `'
                   + ''.join(str(v) if v else '.' for v in puzzle) + '`', 'new')
    return None


def out(response, kind):
    return dict(route='chat/sudoku-' + kind, response=response, sources=[],
                details='CAEL\'s Sudoku tools: Knuth\'s Algorithm X (exact cover) for solving and counting solutions, the '
                        'naked- and hidden-single rules for hints and difficulty, and difficulty-preserving symmetries for the '
                        'hardest puzzles. No neural model.')
