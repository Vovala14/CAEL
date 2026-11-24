"""Chess in chat: play a game against CAEL's own engine, ask for the best move in a position (FEN), rank every legal
move, or review a pasted game. The engine (chess_engine/) is non-neural: alpha-beta search with a hand-written
evaluation, and an opening book from master games.

The game state lives in the conversation: every reply during a game ends with a "Game record" line, and the next
turn rebuilds the position from it, so nothing is stored outside the chat.
"""
import re

ENGINE = None
THINK_MS = 1500
RECORD = re.compile(r'Game record \(you are (White|Black)\):[ \t]*([^\n]*)')
START = re.compile(r"(?i)\b(?:let'?s|lets|wanna|want to|can we|shall we|play|start|new)\b[^.?!\n]{0,40}\bchess\b|"
                   r"\bchess\b[^.?!\n]{0,30}\b(?:game|match)\b[^.?!\n]{0,20}\b(?:with|against|vs)\b")
FEN = re.compile(r'([rnbqkpRNBQKP1-8]{1,8}(?:/[rnbqkpRNBQKP1-8]{1,8}){7})\s+([wb])(?:\s+([KQkq-]{1,4})\s+([a-h][36]|-)'
                 r'(?:\s+(\d+)\s+(\d+))?)?')
PGN_MOVES = re.compile(r'\b1\.\s*(?:[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8]|O-O)')


def available():
    try:
        import chess  # noqa: F401
        import numba  # noqa: F401
        return True
    except Exception:
        return False


def engine():
    global ENGINE
    if ENGINE is None:
        from .chess_engine.engine import Engine
        ENGINE = Engine(hash_mb=64, use_book=True, threads=2)
        ENGINE.go(moves=['e2e4', 'e7e5'], movetime=200, use_book=False)   # compile the search once
    return ENGINE


def out(text, kind):
    return {'response': text, 'route': f'chat/chess-{kind}', 'confidence': 0.9}


def board_text(board, white_bottom=True):
    rows = []
    ranks = range(7, -1, -1) if white_bottom else range(8)
    files = range(8) if white_bottom else range(7, -1, -1)
    for r in ranks:
        cells = []
        for f in files:
            p = board.piece_at(r * 8 + f)
            cells.append(p.symbol() if p else '.')
        rows.append(f'{r + 1}  ' + ' '.join(cells))
    rows.append('   ' + ' '.join('abcdefgh'[f] for f in files))
    return '```\n' + '\n'.join(rows) + '\n```\n(Capital letters are White, small letters Black.)'


def san_record(board):
    import chess
    b = chess.Board()
    parts = []
    for i, m in enumerate(board.move_stack):
        if i % 2 == 0:
            parts.append(f'{i // 2 + 1}.')
        parts.append(b.san(m))
        b.push(m)
    return ' '.join(parts)


def from_record(moves_text):
    import chess
    b = chess.Board()
    for tok in moves_text.split():
        if re.fullmatch(r'\d+\.+', tok) or tok in ('*', '1-0', '0-1', '1/2-1/2'):
            continue
        b.push_san(tok)
    return b


def current_game(messages):
    """(board, human_colour) from the last game record in the chat, or None."""
    for m in reversed(messages or []):
        if m.get('role') != 'assistant':
            continue
        c = m.get('content') or ''
        if 'Game over' in c or 'game is over' in c:
            return None
        g = RECORD.search(c)
        if g:
            try:
                return from_record(g.group(2)), g.group(1)
            except Exception:
                return None
    return None


def score_text(res, board):
    if res.get('mate') is not None:
        n = res['mate']
        side = board.turn if n > 0 else not board.turn
        return f"mate in {abs(n)} for {'White' if side else 'Black'}"
    s = res.get('score')
    if s is None:
        return 'from the opening book'
    pov = s if board.turn else -s
    return f'{pov / 100:+.2f} for White'


def parse_move(text, board):
    """A legal move named in the user's message (SAN like Nf3, exd5, O-O, or coordinates like e2e4)."""
    import chess
    t = text.strip().replace('0-0-0', 'O-O-O').replace('0-0', 'O-O')
    for tok in re.findall(r'[KQRBNkqrbn]?[a-h]?[1-8]?x?[a-h][1-8](?:=?[QRBNqrbn])?[+#]?|O-O(?:-O)?|[a-h][1-8][a-h][1-8][qrbn]?', t):
        for cand in (tok, tok[0].upper() + tok[1:] if tok[0] in 'kqrbn' and len(tok) > 2 else tok):
            try:
                return board.parse_san(cand)
            except Exception:
                pass
            try:
                m = chess.Move.from_uci(cand.lower())
                if m in board.legal_moves:
                    return m
            except Exception:
                pass
    return None


def finish(board):
    if board.is_checkmate():
        return 'Checkmate: ' + ('Black' if board.turn else 'White') + ' wins.'
    if board.is_stalemate():
        return 'Stalemate: a draw.'
    if board.is_insufficient_material():
        return 'Draw: not enough material to checkmate.'
    if board.can_claim_threefold_repetition() or board.is_fifty_moves():
        return 'Draw by repetition or the fifty-move rule.'
    return None


def cael_turn(board, human):
    res = engine().go(moves=[m.uci() for m in board.move_stack], movetime=THINK_MS)
    import chess
    mv = chess.Move.from_uci(res['move'])
    san = board.san(mv)
    num = board.fullmove_number
    label = f'{num}. {san}' if board.turn else f'{num}... {san}'
    how = 'opening book' if res.get('source') == 'book' else f"search, depth {res.get('depth')}, eval {score_text(res, board)}"
    board.push(mv)
    return f'**CAEL plays {label}** ({how}).'


def show_game(board, human, head):
    end = finish(board)
    lines = [head, '', board_text(board, human == 'White'), '']
    lines.append(f'Game record (you are {human}): {san_record(board)}')
    if end:
        lines += ['', f'**Game over.** {end} Say "new chess game" to play again.']
    else:
        lines += ['', 'Your move' + (' (you are in check)' if board.is_check() else '') + '. Type it like e4, Nf3, exd5, O-O or e2e4.']
    return '\n'.join(lines)


def play(text, low, board, human):
    import chess
    if re.search(r'\b(resign|i give up|i quit)\b', low):
        return out(f'You resigned. **CAEL wins.** Game over.\n\nGame record: {san_record(board)}', 'end')
    if re.search(r'\b(take ?back|undo)\b', low):
        if len(board.move_stack) >= 2:
            board.pop()
            board.pop()
        return out(show_game(board, human, 'Took back the last move pair.'), 'undo')
    if re.search(r'\b(hint|what should i play|best move here|help)\b', low):
        res = engine().go(moves=[m.uci() for m in board.move_stack], movetime=THINK_MS, use_book=False)
        mv = chess.Move.from_uci(res['move'])
        return out(show_game(board, human, f'**Hint:** {board.san(mv)} (eval {score_text(res, board)}).'), 'hint')
    if re.search(r'\b(show|see)\b.*\bboard\b|\bwhere are we\b', low):
        return out(show_game(board, human, 'The current position:'), 'board')
    mv = parse_move(text, board)
    if mv is None:
        if re.search(r'[a-h][1-8]|O-O', text):
            legal = ', '.join(sorted(board.san(m) for m in board.legal_moves)[:40])
            return out(show_game(board, human, f"That isn't a legal move here. Legal moves: {legal}."), 'illegal')
        return None
    you = board.san(mv)
    board.push(mv)
    head = f'You played {you}.'
    if finish(board) is None:
        head += ' ' + cael_turn(board, human)
    return out(show_game(board, human, head), 'move')


def analyse_fen(text, low):
    import chess
    g = FEN.search(text)
    fen = ' '.join(x for x in (g.group(1), g.group(2), g.group(3) or '-', g.group(4) or '-', g.group(5) or '0', g.group(6) or '1'))
    try:
        board = chess.Board(fen)
    except Exception:
        return out("That FEN isn't a valid chess position.", 'fen')
    if board.is_game_over():
        return out(f'This position is already over: {finish(board) or board.result()}.', 'fen')
    eng = engine()
    if re.search(r'\b(rank|all (?:the )?(?:legal )?moves|every move)\b', low):
        from .chess_engine.engine import rank_moves
        rk = rank_moves(eng, fen, [], movetime=4000)
        rows = [f"{i + 1}. {r['san']}: {r['score'] / 100:+.2f}" for i, r in enumerate(rk['ranked'][:15])]
        return out(f"All {rk['legal_moves']} legal moves ranked by CAEL (depth {rk['depth']}, score for the side to move):\n"
                   + '\n'.join(rows) + ('\n...' if len(rk['ranked']) > 15 else ''), 'rank')
    res = eng.go(fen, [], movetime=3000, use_book=False)
    mv = chess.Move.from_uci(res['move'])
    pv = []
    b = board.copy()
    for u in res.get('pv', [])[:8]:
        try:
            m = chess.Move.from_uci(u)
            pv.append(b.san(m))
            b.push(m)
        except Exception:
            break
    side = 'White' if board.turn else 'Black'
    return out(f"**Best move for {side}: {board.san(mv)}** (eval {score_text(res, board)}, depth {res.get('depth')}).\n"
               f"Expected line: {' '.join(pv)}\n\n{board_text(board, board.turn)}", 'best')


def review_pgn(text):
    import chess
    import chess.pgn
    import io
    game = chess.pgn.read_game(io.StringIO(text))
    if game is None or not list(game.mainline_moves()):
        return None
    eng = engine()
    board = game.board()
    moves = list(game.mainline_moves())[:120]
    evals = []
    for i in range(len(moves) + 1):
        if i:
            board.push(moves[i - 1])
        if board.is_game_over():
            evals.append(None)
            continue
        r = eng.go(board.fen(), [], movetime=250, use_book=False)
        s = r.get('score') or 0
        if r.get('mate') is not None:
            s = 3000 if r['mate'] > 0 else -3000
        evals.append(s if board.turn else -s)   # White's view
    board = game.board()
    notes = []
    for i, m in enumerate(moves):
        a, b = evals[i], evals[i + 1]
        san = board.san(m)
        mover_white = board.turn
        board.push(m)
        if a is None or b is None:
            continue
        drop = (a - b) if mover_white else (b - a)
        if drop >= 150:
            tag = 'blunder' if drop >= 300 else 'mistake'
            num = f'{i // 2 + 1}.' if mover_white else f'{i // 2 + 1}...'
            fmt = lambda v: ('mate for White' if v > 0 else 'mate for Black') if abs(v) >= 3000 else f'{v / 100:+.1f}'
            notes.append((drop, f"{num} {san}: {tag} ({fmt(a)} -> {fmt(b)}, White's view)"))
    notes.sort(key=lambda x: -x[0])
    head = f"CAEL reviewed {len(moves)} moves at a quick depth (scores are for White)."
    if not notes:
        return out(head + ' No move lost more than 1.5 pawns of evaluation.', 'review')
    return out(head + ' Biggest errors:\n' + '\n'.join(f'- {n}' for _, n in notes[:8]), 'review')


def reply(text, messages=None):
    low = text.lower()
    has_chess_words = 'chess' in low or FEN.search(text) or (PGN_MOVES.search(text) and re.search(r'\b(review|analy[sz]e|mistakes?|check)\b', low))
    state = current_game(messages)
    if not has_chess_words and state is None:
        return None
    if not available():
        if has_chess_words:
            return out('Chess needs two extra packages that are not installed here: `pip install numba chess`.', 'unavailable')
        return None
    try:
        if FEN.search(text) and re.search(r'\b(best|analy[sz]e|evaluate|rank|move|what)\b', low):
            return analyse_fen(text, low)
        if PGN_MOVES.search(text) and re.search(r'\b(review|analy[sz]e|mistakes?|check)\b', low):
            r = review_pgn(text)
            if r:
                return r
        if START.search(text) or re.search(r'\bnew (?:chess )?game\b', low) and 'chess' in (low + ' '.join(
                (m.get('content') or '') for m in (messages or [])[-4:])).lower():
            import chess
            human = 'Black' if re.search(r"\b(as black|i(?:'ll| will)? (?:be|play) black|with black|you (?:be|play|take) white)\b", low) else 'White'
            board = chess.Board()
            head = f"New game: you are {human}, CAEL is {'Black' if human == 'White' else 'White'}. CAEL thinks about {THINK_MS / 1000:g} s per move."
            if human == 'Black':
                head += ' ' + cael_turn(board, human)
            return out(show_game(board, human, head), 'start')
        if state is not None:
            board, human = state
            return play(text, low, board, human)
    except Exception as exc:   # never break the chat over a chess problem
        return out(f'Something went wrong with the chess engine ({type(exc).__name__}).', 'error')
    return None
