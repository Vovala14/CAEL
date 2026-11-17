"""Index v2 (cael_unified/retrieval.py): query model, fielded search, and the numpy tree evaluator."""
import json

import numpy as np
import pytest

from cael_unified import retrieval as rv

needs_index = pytest.mark.skipif(rv.db() is None, reason='fielded.sqlite not built')


def conv(*turns):
    m = []
    for t in turns:
        m += [dict(role='user', content=t), dict(role='assistant', content='ok')]
    return m[:-1]


@needs_index
def test_query_model_weights_last_question_and_learns_associations():
    q = rv.Query(['Our shower has really low pressure. It is more of a trickle.', 'Could the shower head be blocked?'])
    assert rv._stem('shower') in q.orig and 'really' not in q.orig
    assert q.orig[rv._stem('blocked')] > 0
    assert rv._stem('pressure') in q.w                    # said, and also what "trickle" is titled as


@needs_index
@pytest.mark.parametrize('turns,word', [
    (('My kitchen knives are really blunt.', "What's the easiest way to sharpen them at home?"), 'sharpen'),
    (('The window in our bedroom is really draughty and the room is freezing.', 'What can I do about it cheaply?'), 'draft'),
    (('Our smoke alarm keeps chirping every minute or so.', 'I already changed the battery. What else could it be?'), 'smoke'),
])
def test_search_finds_the_same_problem_first(turns, word):
    hits = rv.search(conv(*turns), k=5)
    assert hits and word in hits[0].doc['title'].lower().replace('draught', 'draft')


def test_tree_evaluator_matches_hand_computation(tmp_path, monkeypatch):
    # one tree: x0 <= 1 ? (x1 <= 0 ? 1.0 : 2.0) : 3.0 ; one constant tree 0.5
    trees = [dict(feature=[0, 1], threshold=[1.0, 0.0], left=[1, -1], right=[-3, -2], value=[1.0, 2.0, 3.0], default_left=[1, 1]),
             dict(feature=[0], threshold=[float('inf')], left=[-1], right=[-1], value=[0.5], default_left=[1])]
    p = tmp_path / 'm.json'
    p.write_text(json.dumps(dict(names=['a', 'b'], trees=trees)))
    monkeypatch.setattr(rv, 'LTR', p)
    rv.model.cache_clear()
    try:
        out = rv.tree_scores(np.array([[0, -1], [0, 5], [2, 0]]))
        assert out.tolist() == [1.5, 2.5, 3.5]
    finally:
        rv.model.cache_clear()
