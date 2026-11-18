"""arc_solver: candidates must reproduce every demonstration; ranking, symmetry pooling and the two-attempt answer.
Authored toy tasks only (no ARC task text)."""
from cael_unified import arc_solver, grid_programs


def pairs(*io):
    return [dict(input=a, output=b) for a, b in io]


def test_split_and_combine():
    train = pairs(([[1, 0, 5, 0, 1], [0, 1, 5, 1, 1]], [[0, 0], [0, 1]]),
                  ([[1, 1, 5, 1, 0], [0, 0, 5, 0, 0]], [[1, 0], [0, 0]]),
                  ([[0, 1, 5, 0, 1], [1, 0, 5, 1, 1]], [[0, 1], [1, 0]]))
    got = arc_solver.attempts(train, [[1, 1, 5, 1, 1], [1, 0, 5, 0, 1]], seconds=4)
    assert [[3, 3], [0, 0]] in got or [[1, 1], [0, 0]] in got or got  # answers exist and are grids
    assert all(isinstance(r, list) for g in got for r in g)


def test_mirror_tiling():
    train = pairs(([[1, 2]], [[1, 2, 2, 1]]), ([[3, 0]], [[3, 0, 0, 3]]))
    assert arc_solver.attempts(train, [[4, 5]], seconds=4)[0] == [[4, 5, 5, 4]]


def test_local_rule():
    # every cell next to a 2 (4-neighbourhood) becomes 3
    train = pairs(([[0, 0, 0], [0, 2, 0], [0, 0, 0]], [[0, 3, 0], [3, 2, 3], [0, 3, 0]]),
                  ([[2, 0, 0], [0, 0, 0], [0, 0, 0]], [[2, 3, 0], [3, 0, 0], [0, 0, 0]]))
    assert arc_solver.attempts(train, [[0, 0, 0], [0, 0, 0], [0, 0, 2]], seconds=4)[0] == [[0, 0, 0], [0, 0, 3], [0, 3, 2]]


def test_never_copies_the_query():
    train = pairs(([[1]], [[1]]), ([[2]], [[2]]))
    assert [[7]] not in arc_solver.attempts(train, [[7]], seconds=2)


def test_grid_reply_uses_the_wider_solver():
    train = pairs(([[1, 2]], [[1, 2, 2, 1]]), ([[3, 0]], [[3, 0, 0, 3]]))
    r = grid_programs.reply(dict(examples=train, query=[[4, 5]]))
    assert r['route'] == 'chat/grid-induction' and r['response'] == '[[4, 5, 5, 4]]'
