import pytest

from cael_unified import chess_skill as C

pytestmark = pytest.mark.skipif(not C.available(), reason='numba and python-chess are needed for chess')


def talk(lines):
    msgs, replies = [], []
    for t in lines:
        msgs.append({'role': 'user', 'content': t})
        r = C.reply(t, msgs)
        replies.append(r)
        msgs.append({'role': 'assistant', 'content': r['response'] if r else ''})
    return replies


def record(r):
    return [l for l in r['response'].split('\n') if l.startswith('Game record')][0]


def test_game_flow_white():
    r = talk(["let's play chess", 'e4', 'Nf3'])
    assert r[0]['route'] == 'chat/chess-start'
    assert record(r[1]).startswith('Game record (you are White): 1. e4 ')
    assert '2. Nf3' in record(r[2])


def test_play_as_black_cael_moves_first():
    r = talk(['play chess as black'])
    assert 'you are Black' in r[0]['response']
    assert record(r[0]).startswith('Game record (you are Black): 1. ')


def test_illegal_move_is_refused_with_list():
    r = talk(["let's play chess", 'Ke5'])
    assert r[1]['route'] == 'chat/chess-illegal'


def test_take_back_and_resign():
    r = talk(["let's play chess", 'e4', 'take back', 'resign'])
    assert record(r[2]).strip().endswith('):')
    assert 'CAEL wins' in r[3]['response']


def test_best_move_for_fen_finds_mate():
    r = C.reply('best move: 6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1', [])
    assert 'Rd8' in r['response'] and 'mate' in r['response']


def test_review_finds_the_blunder():
    r = C.reply('review this game: 1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7#', [])
    assert '3... Nf6' in r['response']


def test_not_chess_stays_silent():
    assert C.reply("what's the weather today", []) is None
    assert C.reply('I moved to e4 street last year', []) is None
