"""Python side of the CAEL chess engine: positions, time control, opening book,
optional online endgame tablebase, and principal variations."""
import json
import os
import threading
import time
import urllib.parse
import urllib.request

import chess
import chess.polyglot
import numpy as np

from . import core
from .core import MAXMOVES, MAXPLY, HISTLEN, MATE, MATE_BOUND, INF

HERE = os.path.dirname(os.path.abspath(__file__))
PARAMS_FILE = os.path.join(HERE, "data", "params.json")
BOOK_FILE = os.path.join(HERE, "data", "book.json")

MAX_TURN_MS = 29500  # hard ceiling: no CAEL turn takes longer than 30 seconds
PROMO = {2: "n", 3: "b", 4: "r", 5: "q"}
PROMO_INV = {v: k for k, v in PROMO.items()}
FILES = "abcdefgh"


def sq_name(s):
    s64 = core.SQ64[s]
    return FILES[s64 & 7] + str((s64 >> 3) + 1)


def move_uci(m):
    u = sq_name(core.mfrom(m)) + sq_name(core.mto(m))
    pr = core.mpromo(m)
    return u + PROMO[pr] if pr else u


def load_params():
    if os.path.exists(PARAMS_FILE):
        with open(PARAMS_FILE) as f:
            return np.array(json.load(f)["params"], dtype=np.int64)
    from .pesto import initial_params
    return initial_params()


def book_key(board):
    """FEN without move counters; en passant only when capturable (as python-chess does)."""
    return " ".join(board.fen(en_passant="legal").split()[:4])


class Position:
    """Engine-side arrays for one game state."""

    def __init__(self, fen=chess.STARTING_FEN, moves=()):
        self.b = np.full(120, core.OFF, dtype=np.int64)
        self.st = np.zeros(16, dtype=np.int64)
        self.hist = np.zeros(HISTLEN + MAXPLY + 8, dtype=np.uint64)
        self.und = np.zeros((HISTLEN + MAXPLY + 8, 6), dtype=np.int64)
        self.set_fen(fen)
        for u in moves:
            self.push_uci(u)

    def set_fen(self, fen):
        board = chess.Board(fen)
        self.b[:] = core.OFF
        for s64 in range(64):
            self.b[core.SQ120[s64]] = 0
        for s64, pc in board.piece_map().items():
            v = pc.piece_type if pc.color == chess.WHITE else -pc.piece_type
            self.b[core.SQ120[s64]] = v
            if pc.piece_type == chess.KING:
                self.st[4 if pc.color == chess.WHITE else 5] = core.SQ120[s64]
        st = self.st
        st[0] = 1 if board.turn == chess.WHITE else -1
        cr = 0
        if board.has_kingside_castling_rights(chess.WHITE):
            cr |= 1
        if board.has_queenside_castling_rights(chess.WHITE):
            cr |= 2
        if board.has_kingside_castling_rights(chess.BLACK):
            cr |= 4
        if board.has_queenside_castling_rights(chess.BLACK):
            cr |= 8
        st[1] = cr
        st[2] = core.SQ120[board.ep_square] if board.ep_square is not None else 0
        st[3] = board.halfmove_clock
        st[6] = 0
        st[7] = core.compute_pawn_key(self.b)
        self.hist[0] = core.compute_hash(self.b, st)

    def legal(self):
        out = np.zeros(MAXMOVES, dtype=np.int64)
        n = core.legal_moves(self.b, self.st, self.hist, self.und, out)
        return [int(x) for x in out[:n]]

    def push_uci(self, u):
        for m in self.legal():
            if move_uci(m) == u:
                if self.st[6] >= HISTLEN - 2:
                    raise ValueError("game too long")
                core.make_move(self.b, self.st, self.hist, self.und, m)
                return m
        raise ValueError(f"illegal move {u}")


class _Worker:
    """Search state for one helper thread (Lazy SMP): everything except the shared hash table."""

    def __init__(self):
        self.mvs = np.zeros((MAXPLY + 2, MAXMOVES), dtype=np.int64)
        self.scs = np.zeros((MAXPLY + 2, MAXMOVES), dtype=np.int64)
        self.kil = np.zeros((MAXPLY + 2, 2), dtype=np.int64)
        self.hh = np.zeros(core.HH_LEN, dtype=np.int64)
        self.info = np.zeros(8, dtype=np.int64)
        self.tm = np.zeros(2, dtype=np.float64)
        self.scr = np.zeros(core.SCR_LEN, dtype=np.int64)


def _helper_loop(eng, w, fen, moves, max_depth, k):
    """Iterative deepening on a private copy of the position; results only reach the main
    search through the shared hash table."""
    pos = Position(fen, moves)
    w.kil[:] = 0
    reset_plies(w)
    for d in range(1 + (k % 2), max_depth + 1):
        core.search(pos.b, pos.st, pos.hist, pos.und, w.mvs, w.scs, w.kil, w.hh,
                    eng.ttk, eng.ttm, eng.ttd, eng.ttf, eng.tts, w.info, w.tm,
                    eng.P, w.scr, d, -INF, INF, 0, True, eng.cfg)
        if w.info[1]:
            break


class Engine:
    # search feature switches (index: meaning); a candidate build turns them on
    # SEE prune+order (+28), razoring (+16), improving (+11), qsearch TT (+26), eval cache (same search, ~11% faster)
    # history 2: countermove + continuation history + malus (+26), singular extensions (+22), ProbCut (+10)
    DEFAULT_CFG = (1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 1)

    def __init__(self, hash_mb=64, use_book=True, use_tablebase=False, params=None, style=None, cfg=None,
                 threads=1):
        """style: a player key from players.PLAYERS (e.g. "carlsen"): that
        player's own opening repertoire first, and their trained weights."""
        n = 1
        while n * 2 * 24 <= hash_mb * 1024 * 1024:
            n *= 2
        self.ttk = np.zeros(n, dtype=np.uint64)
        self.ttm = np.zeros(n, dtype=np.int64)
        self.ttd = np.zeros(n, dtype=np.int32)
        self.ttf = np.zeros(n, dtype=np.int8)
        self.tts = np.zeros(n, dtype=np.int32)
        self.mvs = np.zeros((MAXPLY + 2, MAXMOVES), dtype=np.int64)
        self.scs = np.zeros((MAXPLY + 2, MAXMOVES), dtype=np.int64)
        self.kil = np.zeros((MAXPLY + 2, 2), dtype=np.int64)
        self.hh = np.zeros(core.HH_LEN, dtype=np.int64)
        self.info = np.zeros(8, dtype=np.int64)
        self.tm = np.zeros(2, dtype=np.float64)
        self.scr = np.zeros(core.SCR_LEN, dtype=np.int64)
        c = list(cfg if cfg is not None else self.DEFAULT_CFG)
        self.cfg = np.array(c + [0] * (core.NCFG - len(c)), dtype=np.int64)
        self.style = style
        self.threads = max(1, int(threads))
        self.workers = []
        style_w = os.path.join(HERE, "data", f"params_{style}.json") if style else None
        if params is not None:
            self.P = params
        elif style_w and os.path.exists(style_w):
            with open(style_w) as f:
                self.P = np.array(json.load(f)["params"], dtype=np.int64)
        else:
            self.P = load_params()
        from .pesto import pad
        self.P = pad(self.P)
        self.use_book = use_book
        self.use_tablebase = use_tablebase
        self.book = None
        self.style_book = None
        if use_book and os.path.exists(BOOK_FILE):
            with open(BOOK_FILE) as f:
                self.book = json.load(f)
        style_b = os.path.join(HERE, "data", f"book_{style}.json") if style else None
        if use_book and style_b and os.path.exists(style_b):
            with open(style_b) as f:
                self.style_book = json.load(f)

    def new_game(self):
        self.ttk[:] = 0
        self.hh[:] = 0
        for w in self.workers:
            w.hh[:] = 0

    def evaluate(self, pos):
        return int(core.evaluate(pos.b, pos.st[0], self.P, self.scr, False))

    # ---------------------------------------------------------------- helpers
    def _book_move(self, fen, moves):
        board = chess.Board(fen)
        for u in moves:
            board.push_uci(u)
        h = str(chess.polyglot.zobrist_hash(board))
        for bk in (self.style_book, self.book):
            if bk and h in bk:
                mv = self._pick_book(board, bk[h])
                if mv:
                    return mv
        return None

    def _pick_book(self, board, entry):
        # entry: [[uci, games, score_for_mover], ...]; keep sound, popular moves
        best = max(e[1] for e in entry)
        good = [e for e in entry if e[1] >= max(3, best * 0.15) and e[2] >= 0.40]
        if not good:
            return None
        rng = np.random.default_rng()
        w = np.array([e[1] * (0.5 + e[2]) for e in good], dtype=float)
        pick = good[int(rng.choice(len(good), p=w / w.sum()))]
        if pick[0] not in {m.uci() for m in board.legal_moves}:
            return None
        return pick[0]

    def _tablebase(self, fen, moves):
        board = chess.Board(fen)
        for u in moves:
            board.push_uci(u)
        if len(board.piece_map()) > 7:
            return None
        url = "https://tablebase.lichess.ovh/standard?fen=" + urllib.parse.quote(board.fen())
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "cael-chess"})
            with urllib.request.urlopen(req, timeout=3) as r:
                data = json.load(r)
        except Exception:
            return None
        if not data.get("moves"):
            return None
        mv = data["moves"][0]
        cat = data.get("category", "")
        return mv["uci"], cat

    def pv_line(self, pos, first, maxlen=12):
        line = [first]
        made = 0
        try:
            core.make_move(pos.b, pos.st, pos.hist, pos.und, first)
            made = 1
            seen = {int(pos.hist[pos.st[6]])}
            mask = np.uint64(self.ttk.shape[0] - 1)
            while len(line) < maxlen:
                key = pos.hist[pos.st[6]]
                idx = int(key & mask)
                if self.ttk[idx] != key or self.ttm[idx] == 0:
                    break
                m = int(self.ttm[idx])
                if m not in pos.legal():
                    break
                core.make_move(pos.b, pos.st, pos.hist, pos.und, m)
                made += 1
                line.append(m)
                h = int(pos.hist[pos.st[6]])
                if h in seen:
                    break
                seen.add(h)
        finally:
            for _ in range(made):
                core.unmake_move(pos.b, pos.st, pos.hist, pos.und)
        return [move_uci(m) for m in line]

    # ---------------------------------------------------------------- search
    def go(self, fen=chess.STARTING_FEN, moves=(), movetime=None, depth=None, nodes=None,
           wtime=None, btime=None, winc=0, binc=0, movestogo=None, on_info=None, use_book=None):
        moves = list(moves)
        use_book = self.use_book if use_book is None else use_book
        if use_book and len(moves) < 40:
            bm = self._book_move(fen, moves)
            if bm:
                return {"move": bm, "source": "book", "score": None, "depth": 0, "pv": [bm], "nodes": 0}
        if self.use_tablebase:
            tb = self._tablebase(fen, moves)
            if tb:
                return {"move": tb[0], "source": "tablebase", "score": None, "wdl": tb[1], "depth": 0,
                        "pv": [tb[0]], "nodes": 0}
        if getattr(self, "rank_all", False) and movetime:
            rk = rank_moves(self, fen, moves, min(movetime, MAX_TURN_MS))
            if not rk["ranked"]:
                return {"move": None, "source": "none"}
            top = rk["ranked"][0]
            return {"move": top["move"], "source": "search", "score": top["score"], "depth": rk["depth"],
                    "pv": [top["move"]], "nodes": rk["nodes"], "legal_moves": rk["legal_moves"]}
        pos = Position(fen, moves)
        legal = pos.legal()
        if not legal:
            return {"move": None, "source": "none"}
        if movetime is None and depth is None and nodes is None:
            if wtime is not None or btime is not None:
                left = (wtime if pos.st[0] == 1 else btime) or 1000
                inc = (winc if pos.st[0] == 1 else binc) or 0
                mtg = movestogo or 30
                movetime = max(30, min(left / mtg + inc * 0.8, left * 0.4))
            else:
                movetime = 2000
        if movetime is None:
            movetime = 10 ** 9 if depth or nodes else MAX_TURN_MS
        movetime = min(movetime, MAX_TURN_MS)
        depth = depth or MAXPLY - 4
        start = time.perf_counter()
        self.tm[0] = start
        self.tm[1] = start + movetime / 1000.0
        self.info[:] = 0
        self.info[3] = nodes or 0
        self.kil[:] = 0
        self.hh[:core.H_CM] //= 4
        reset_plies(self)
        best = legal[0]
        best_score = 0
        result = {"move": move_uci(best), "source": "search", "score": 0, "depth": 0, "pv": [move_uci(best)]}
        if len(legal) == 1:
            depth = min(depth, 4)
        prev = 0
        helpers = []
        if self.threads > 1 and len(legal) > 1:
            while len(self.workers) < self.threads - 1:
                self.workers.append(_Worker())
            for k, w in enumerate(self.workers[:self.threads - 1]):
                w.tm[:] = self.tm
                w.info[:] = 0
                w.info[3] = 0
                w.hh[:core.H_CM] //= 4
                th = threading.Thread(target=_helper_loop, args=(self, w, fen, moves, depth, k), daemon=True)
                th.start()
                helpers.append((th, w))
        for d in range(1, depth + 1):
            alpha, beta = -INF, INF
            window = 35
            if d >= 4:
                alpha, beta = prev - window, prev + window
            while True:
                s = core.search(pos.b, pos.st, pos.hist, pos.und, self.mvs, self.scs, self.kil, self.hh,
                                self.ttk, self.ttm, self.ttd, self.ttf, self.tts, self.info, self.tm,
                                self.P, self.scr, d, alpha, beta, 0, True, self.cfg)
                if self.info[1]:
                    break
                if s <= alpha:
                    alpha = max(-INF, alpha - window * 3)
                    window *= 3
                elif s >= beta:
                    beta = min(INF, beta + window * 3)
                    window *= 3
                else:
                    break
            if self.info[1]:
                # partial iteration: keep a root move only if it was fully searched as better
                if self.info[4] and self.info[4] != best and d > 1 and self.info[5] > best_score:
                    best = int(self.info[4])
                    best_score = int(self.info[5])
                    result.update(move=move_uci(best), score=best_score)
                break
            best = int(self.info[4]) if self.info[4] else best
            best_score = int(s)
            prev = best_score
            el = time.perf_counter() - start
            result = {
                "move": move_uci(best), "source": "search", "score": best_score, "depth": d,
                "seldepth": int(self.info[2]), "nodes": int(self.info[0]),
                "time_ms": int(el * 1000), "nps": int(self.info[0] / max(el, 1e-6)),
                "pv": self.pv_line(pos, best),
            }
            if abs(best_score) > MATE_BOUND:
                plies = MATE - abs(best_score)
                result["mate"] = (plies + 1) // 2 * (1 if best_score > 0 else -1)
            if on_info:
                on_info(result)
            if abs(best_score) > MATE_BOUND and d > (MATE - abs(best_score)) + 2:
                break
            # do not start an iteration that will probably not finish
            if movetime < 10 ** 8 and el > movetime / 1000.0 * 0.55:
                break
        for th, w in helpers:
            w.tm[1] = 0.0  # stop the helpers at their next time check
        for th, w in helpers:
            th.join()
        result["nodes"] = int(self.info[0]) + sum(int(w.info[0]) for _, w in helpers)
        result["time_ms"] = int((time.perf_counter() - start) * 1000)
        if helpers:
            result["threads"] = len(helpers) + 1
            result["nps"] = int(result["nodes"] / max(result["time_ms"], 1) * 1000)
        return result


def reset_plies(engine):
    engine.scs[:, core.S_EXCL] = 0
    engine.scs[:, core.S_MOVE] = -1


def rank_moves(engine, fen=chess.STARTING_FEN, moves=(), movetime=3000, max_depth=MAXPLY - 4):
    """Score EVERY legal move with a full-window search at each depth (side to
    move's view). Returns legal-move count, the ranked list and the depth reached."""
    movetime = min(movetime, MAX_TURN_MS)
    pos = Position(fen, list(moves))
    legal = pos.legal()
    start = time.perf_counter()
    engine.tm[0] = start
    engine.tm[1] = start + movetime / 1000.0
    engine.info[:] = 0
    engine.kil[:] = 0
    reset_plies(engine)
    ranked = [(m, 0) for m in legal]
    reached = 0
    for d in range(1, max_depth + 1):
        cur = []
        for m, _ in ranked:  # previous order first: better moves fill the TT early
            core.make_move(pos.b, pos.st, pos.hist, pos.und, m)
            s = -core.search(pos.b, pos.st, pos.hist, pos.und, engine.mvs, engine.scs, engine.kil, engine.hh,
                             engine.ttk, engine.ttm, engine.ttd, engine.ttf, engine.tts, engine.info, engine.tm,
                             engine.P, engine.scr, d - 1, -INF, INF, 1, True, engine.cfg)
            core.unmake_move(pos.b, pos.st, pos.hist, pos.und)
            if engine.info[1]:
                break
            cur.append((m, int(s)))
        if engine.info[1]:
            break
        ranked = sorted(cur, key=lambda x: -x[1])
        reached = d
        if time.perf_counter() - start > movetime / 1000.0 * 0.5:
            break
    board = chess.Board(fen)
    for u in moves:
        board.push_uci(u)
    out = []
    for m, s in ranked:
        u = move_uci(m)
        out.append({"move": u, "san": board.san(chess.Move.from_uci(u)), "score": s})
    return {"legal_moves": len(legal), "depth": reached, "ranked": out,
            "time_ms": int((time.perf_counter() - start) * 1000), "nodes": int(engine.info[0])}
