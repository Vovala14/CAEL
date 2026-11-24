"""CAEL chess core: a non-neural alpha-beta engine compiled with numba.

Board: 10x12 mailbox (a1 = 21, h8 = 98). Pieces: +1..+6 white P N B R Q K,
-1..-6 black, 0 empty, 99 off-board. Everything here is plain search plus a
hand-written evaluation whose weights are fitted to master games (tune.py).
"""
import math
import time

import numpy as np
from numba import njit, objmode

OFF = 99
MAXPLY = 128
MAXMOVES = 256
HISTLEN = 4096
INF = 32000
MATE = 31000
MATE_BOUND = 30000

N_DIRS = np.array([-21, -19, -12, -8, 8, 12, 19, 21], dtype=np.int64)
B_DIRS = np.array([-11, -9, 9, 11], dtype=np.int64)
R_DIRS = np.array([-10, -1, 1, 10], dtype=np.int64)
K_DIRS = np.array([-11, -10, -9, -1, 1, 9, 10, 11], dtype=np.int64)

SQ64 = np.full(120, -1, dtype=np.int64)
SQ120 = np.zeros(64, dtype=np.int64)
for _r in range(8):
    for _f in range(8):
        SQ64[21 + _f + 10 * _r] = _r * 8 + _f
        SQ120[_r * 8 + _f] = 21 + _f + 10 * _r

CASTLE_MASK = np.full(120, 15, dtype=np.int64)
CASTLE_MASK[25] = 15 & ~3
CASTLE_MASK[28] = 15 & ~1
CASTLE_MASK[21] = 15 & ~2
CASTLE_MASK[95] = 15 & ~12
CASTLE_MASK[98] = 15 & ~4
CASTLE_MASK[91] = 15 & ~8

_rng = np.random.default_rng(20261123)
ZOB = _rng.integers(0, 2**64 - 1, size=(13, 120), dtype=np.uint64, endpoint=True)
ZOB_CASTLE = _rng.integers(0, 2**64 - 1, size=16, dtype=np.uint64, endpoint=True)
ZOB_EP = _rng.integers(0, 2**64 - 1, size=120, dtype=np.uint64, endpoint=True)
ZOB_SIDE = np.uint64(_rng.integers(0, 2**63 - 1))
# pawn-structure key (st[7]) for correction history: pawns only
_prng = np.random.default_rng(20261124)
PZOB = np.zeros((13, 120), dtype=np.int64)
PZOB[5] = _prng.integers(1, 2**62, size=120)
PZOB[7] = _prng.integers(1, 2**62, size=120)

# history tables, one flat int64 array (hh):
H_BUT = 0                      # butterfly [side][from120][to120]
H_CM = 2 * 120 * 120           # countermove [prev piece-to 832] -> move
H_CONT = H_CM + 832            # continuation [prev piece-to 832][piece-to 832]
H_CORR = H_CONT + 832 * 832    # eval correction [side][pawn key & 16383]
CORR_N = 16384
HH_LEN = H_CORR + 2 * CORR_N
HIST_MAX = 16384
# per-ply slots at the end of each scs row
S_STATIC = MAXMOVES - 1        # static eval of this node
S_MOVE = MAXMOVES - 2          # piece-to index of the move made from this node (-1 none)
S_EXCL = MAXMOVES - 3          # move excluded by a singular-extension search
NCFG = 16

VAL = np.array([0, 100, 320, 330, 500, 900, 20000], dtype=np.int64)
PHASE_INC = np.array([0, 0, 1, 1, 2, 4, 0], dtype=np.int64)

LMR = np.zeros((64, 64), dtype=np.int64)
for _d in range(1, 64):
    for _m in range(1, 64):
        LMR[_d, _m] = int(0.75 + math.log(_d) * math.log(_m) / 2.25)

# ---------------------------------------------------------------- parameters
PST_MG = 0
PST_EG = 384
EXT = 768
FEATURES = [
    "bishop_pair", "doubled_pawn", "isolated_pawn",
    "passed_r2", "passed_r3", "passed_r4", "passed_r5", "passed_r6", "passed_r7",
    "rook_open_file", "rook_semi_open", "knight_mob", "bishop_mob", "rook_mob",
    "queen_mob", "king_shield", "tempo", "king_open_file", "rook_7th",
    # extended terms (computed only when one of their weights is non-zero)
    "king_attack", "pawn_threat", "hanging", "passed_free", "passer_king_dist", "knight_outpost",
    # richer evaluation (2026-11-24): pawn structure, king danger, threats, space, piece terms
    "backward_pawn", "connected_pawn", "connected_rank", "passed_blocked", "king_danger_sq",
    "king_zone_weak", "safe_check_knight", "safe_check_line", "threat_minor_on_major", "threat_rook_on_queen",
    "space", "bishop_pawns", "minor_behind_pawn", "king_pawn_dist",
] + [f"mob_n_{i}" for i in range(9)] + [f"mob_b_{i}" for i in range(14)] + \
    [f"mob_r_{i}" for i in range(15)] + [f"mob_q_{i}" for i in range(28)]
NBASIC = 19
F_BACKWARD = 25
F_CONN = 26
F_CONNR = 27
F_PBLOCK = 28
F_KD2 = 29
F_KZW = 30
F_SCN = 31
F_SCL = 32
F_TMIN = 33
F_TROOK = 34
F_SPACE = 35
F_BPAWNS = 36
F_MBEHIND = 37
F_KPDIST = 38
F_MOBN = 39
F_MOBB = 48
F_MOBR = 62
F_MOBQ = 77
ATT_W = np.array([0, 0, 2, 2, 3, 5, 0], dtype=np.int64)
NFEAT = len(FEATURES)
NPARAM = EXT + 2 * NFEAT
FOFF = 2048  # feature record: scr[FOFF .. FOFF + NFEAT)

# --- move encoding: from | to<<7 | promo<<14 | flag<<17 (flag 1 double, 2 ep, 3 castle)


@njit(cache=True, inline="always")
def mfrom(m):
    return m & 127


@njit(cache=True, inline="always")
def mto(m):
    return (m >> 7) & 127


@njit(cache=True, inline="always")
def mpromo(m):
    return (m >> 14) & 7


@njit(cache=True, inline="always")
def mflag(m):
    return (m >> 17) & 3


@njit(cache=True, inline="always")
def enc(fr, to, pr, fl):
    return fr | (to << 7) | (pr << 14) | (fl << 17)


# ---------------------------------------------------------------- board ops
@njit(cache=True)
def compute_hash(b, st):
    h = np.uint64(0)
    for s in range(21, 99):
        p = b[s]
        if p != 0 and p != OFF:
            h ^= ZOB[p + 6, s]
    h ^= ZOB_CASTLE[st[1]]
    if st[2] != 0:
        h ^= ZOB_EP[st[2]]
    if st[0] == -1:
        h ^= ZOB_SIDE
    return h


@njit(cache=True)
def compute_pawn_key(b):
    k = np.int64(0)
    for s in range(21, 99):
        p = b[s]
        if p == 1 or p == -1:
            k ^= PZOB[p + 6, s]
    return k


@njit(cache=True)
def attacked(b, sq, by):
    if by == 1:
        if b[sq - 9] == 1 or b[sq - 11] == 1:
            return True
    else:
        if b[sq + 9] == -1 or b[sq + 11] == -1:
            return True
    kn = 2 * by
    for d in N_DIRS:
        if b[sq + d] == kn:
            return True
    kg = 6 * by
    for d in K_DIRS:
        if b[sq + d] == kg:
            return True
    bi = 3 * by
    qu = 5 * by
    for d in B_DIRS:
        t = sq + d
        while b[t] == 0:
            t += d
        if b[t] == bi or b[t] == qu:
            return True
    ro = 4 * by
    for d in R_DIRS:
        t = sq + d
        while b[t] == 0:
            t += d
        if b[t] == ro or b[t] == qu:
            return True
    return False


@njit(cache=True)
def king_sq(st, side):
    return st[4] if side == 1 else st[5]


@njit(cache=True)
def in_check(b, st):
    side = st[0]
    return attacked(b, king_sq(st, side), -side)


@njit(cache=True)
def make_move(b, st, hist, und, m):
    fr = mfrom(m)
    to = mto(m)
    pr = mpromo(m)
    fl = mflag(m)
    side = st[0]
    i = st[6]
    h = hist[i]
    p = b[fr]
    cap = b[to]
    und[i, 0] = cap
    und[i, 1] = st[1]
    und[i, 2] = st[2]
    und[i, 3] = st[3]
    und[i, 4] = m
    und[i, 5] = st[7]
    pk = st[7]
    if st[2] != 0:
        h ^= ZOB_EP[st[2]]
    h ^= ZOB_CASTLE[st[1]]
    h ^= ZOB[p + 6, fr]
    pk ^= PZOB[p + 6, fr]
    b[fr] = 0
    if cap != 0:
        h ^= ZOB[cap + 6, to]
        pk ^= PZOB[cap + 6, to]
    if fl == 2:
        capsq = to - 10 * side
        h ^= ZOB[-side + 6, capsq]
        pk ^= PZOB[-side + 6, capsq]
        b[capsq] = 0
    np_ = p
    if pr != 0:
        np_ = pr * side
    b[to] = np_
    h ^= ZOB[np_ + 6, to]
    pk ^= PZOB[np_ + 6, to]
    st[7] = pk
    if fl == 3:
        rf = 0
        rt = 0
        if to == 27:
            rf, rt = 28, 26
        elif to == 23:
            rf, rt = 21, 24
        elif to == 97:
            rf, rt = 98, 96
        else:
            rf, rt = 91, 94
        rk = b[rf]
        b[rf] = 0
        b[rt] = rk
        h ^= ZOB[rk + 6, rf]
        h ^= ZOB[rk + 6, rt]
    if p == 6:
        st[4] = to
    elif p == -6:
        st[5] = to
    st[1] = st[1] & CASTLE_MASK[fr] & CASTLE_MASK[to]
    h ^= ZOB_CASTLE[st[1]]
    st[2] = 0
    if fl == 1:
        st[2] = fr + 10 * side
        h ^= ZOB_EP[st[2]]
    if p == 1 or p == -1 or cap != 0:
        st[3] = 0
    else:
        st[3] += 1
    st[0] = -side
    h ^= ZOB_SIDE
    st[6] = i + 1
    hist[i + 1] = h


@njit(cache=True)
def unmake_move(b, st, hist, und):
    i = st[6] - 1
    m = und[i, 4]
    fr = mfrom(m)
    to = mto(m)
    pr = mpromo(m)
    fl = mflag(m)
    st[0] = -st[0]
    side = st[0]
    p = b[to]
    if pr != 0:
        p = side
    b[fr] = p
    b[to] = und[i, 0]
    if fl == 2:
        b[to - 10 * side] = -side
    if fl == 3:
        rf = 0
        rt = 0
        if to == 27:
            rf, rt = 28, 26
        elif to == 23:
            rf, rt = 21, 24
        elif to == 97:
            rf, rt = 98, 96
        else:
            rf, rt = 91, 94
        b[rf] = b[rt]
        b[rt] = 0
    if p == 6:
        st[4] = fr
    elif p == -6:
        st[5] = fr
    st[1] = und[i, 1]
    st[2] = und[i, 2]
    st[3] = und[i, 3]
    st[7] = und[i, 5]
    st[6] = i


@njit(cache=True)
def make_null(st, hist, und):
    i = st[6]
    h = hist[i]
    und[i, 5] = st[7]
    und[i, 0] = 0
    und[i, 1] = st[1]
    und[i, 2] = st[2]
    und[i, 3] = st[3]
    und[i, 4] = 0
    if st[2] != 0:
        h ^= ZOB_EP[st[2]]
    st[2] = 0
    st[3] += 1
    st[0] = -st[0]
    h ^= ZOB_SIDE
    st[6] = i + 1
    hist[i + 1] = h


@njit(cache=True)
def unmake_null(st, hist, und):
    i = st[6] - 1
    st[0] = -st[0]
    st[2] = und[i, 2]
    st[3] = und[i, 3]
    st[6] = i


@njit(cache=True)
def _add_pawn_moves(out, n, fr, to, promo_rank, fl, caps):
    if promo_rank:
        out[n] = enc(fr, to, 5, 0)
        n += 1
        if not caps:
            out[n] = enc(fr, to, 2, 0)
            out[n + 1] = enc(fr, to, 4, 0)
            out[n + 2] = enc(fr, to, 3, 0)
            n += 3
    else:
        out[n] = enc(fr, to, 0, fl)
        n += 1
    return n


@njit(cache=True)
def gen_moves(b, st, out, caps):
    """Pseudo-legal moves into out; returns count. caps=True: captures + queen promos."""
    side = st[0]
    n = 0
    for s in range(21, 99):
        p = b[s]
        if p == 0 or p == OFF or p * side < 0:
            continue
        a = p * side
        if a == 1:
            fwd = 10 * side
            t = s + fwd
            promo = (t >= 91) if side == 1 else (t <= 28)
            if b[t] == 0:
                if promo or not caps:
                    n = _add_pawn_moves(out, n, s, t, promo, 0, caps)
                if not promo and not caps:
                    start = (31 <= s <= 38) if side == 1 else (81 <= s <= 88)
                    if start and b[t + fwd] == 0:
                        out[n] = enc(s, t + fwd, 0, 1)
                        n += 1
            for c in (fwd - 1, fwd + 1):
                t = s + c
                q = b[t]
                if q != OFF and q * side < 0:
                    n = _add_pawn_moves(out, n, s, t, promo, 0, caps)
                elif st[2] != 0 and t == st[2]:
                    out[n] = enc(s, t, 0, 2)
                    n += 1
        elif a == 2:
            for d in N_DIRS:
                t = s + d
                q = b[t]
                if q == OFF:
                    continue
                if q == 0:
                    if not caps:
                        out[n] = enc(s, t, 0, 0)
                        n += 1
                elif q * side < 0:
                    out[n] = enc(s, t, 0, 0)
                    n += 1
        elif a == 6:
            for d in K_DIRS:
                t = s + d
                q = b[t]
                if q == OFF:
                    continue
                if q == 0:
                    if not caps:
                        out[n] = enc(s, t, 0, 0)
                        n += 1
                elif q * side < 0:
                    out[n] = enc(s, t, 0, 0)
                    n += 1
        else:
            for k in range(8):
                if k < 4:
                    if a == 4:
                        continue
                    d = B_DIRS[k]
                else:
                    if a == 3:
                        continue
                    d = R_DIRS[k - 4]
                t = s + d
                while True:
                    q = b[t]
                    if q == OFF:
                        break
                    if q == 0:
                        if not caps:
                            out[n] = enc(s, t, 0, 0)
                            n += 1
                    else:
                        if q * side < 0:
                            out[n] = enc(s, t, 0, 0)
                            n += 1
                        break
                    t += d
    if not caps:
        cr = st[1]
        if side == 1:
            if (cr & 1) and b[26] == 0 and b[27] == 0 and b[28] == 4 and b[25] == 6:
                if not attacked(b, 25, -1) and not attacked(b, 26, -1) and not attacked(b, 27, -1):
                    out[n] = enc(25, 27, 0, 3)
                    n += 1
            if (cr & 2) and b[22] == 0 and b[23] == 0 and b[24] == 0 and b[21] == 4 and b[25] == 6:
                if not attacked(b, 25, -1) and not attacked(b, 24, -1) and not attacked(b, 23, -1):
                    out[n] = enc(25, 23, 0, 3)
                    n += 1
        else:
            if (cr & 4) and b[96] == 0 and b[97] == 0 and b[98] == -4 and b[95] == -6:
                if not attacked(b, 95, 1) and not attacked(b, 96, 1) and not attacked(b, 97, 1):
                    out[n] = enc(95, 97, 0, 3)
                    n += 1
            if (cr & 8) and b[92] == 0 and b[93] == 0 and b[94] == 0 and b[91] == -4 and b[95] == -6:
                if not attacked(b, 95, 1) and not attacked(b, 94, 1) and not attacked(b, 93, 1):
                    out[n] = enc(95, 93, 0, 3)
                    n += 1
    return n


@njit(cache=True)
def legal_moves(b, st, hist, und, out):
    tmp = np.zeros(MAXMOVES, dtype=np.int64)
    n = gen_moves(b, st, tmp, False)
    k = 0
    side = st[0]
    for i in range(n):
        make_move(b, st, hist, und, tmp[i])
        if not attacked(b, king_sq(st, side), -side):
            out[k] = tmp[i]
            k += 1
        unmake_move(b, st, hist, und)
    return k


@njit(cache=True)
def perft(b, st, hist, und, depth):
    if depth == 0:
        return 1
    mv = np.zeros(MAXMOVES, dtype=np.int64)
    n = gen_moves(b, st, mv, False)
    side = st[0]
    total = 0
    for i in range(n):
        make_move(b, st, hist, und, mv[i])
        if not attacked(b, king_sq(st, side), -side):
            total += perft(b, st, hist, und, depth - 1)
        unmake_move(b, st, hist, und)
    return total


# ---------------------------------------------------------------- evaluation
def _zone_py(ks, sq, up):
    k64 = SQ64[ks]
    s64 = SQ64[sq]
    if k64 < 0 or s64 < 0:
        return False
    df = abs((k64 & 7) - (s64 & 7))
    dr = (s64 >> 3) - (k64 >> 3)
    if df <= 1 and abs(dr) <= 1:
        return True
    return df <= 1 and dr == 2 * up


# lookup tables for the richer terms
DIST = np.zeros((120, 120), dtype=np.int64)   # king (Chebyshev) distance
SQCOL = np.zeros(120, dtype=np.int64)          # square colour
for _a in range(120):
    if SQ64[_a] >= 0:
        SQCOL[_a] = ((SQ64[_a] & 7) + (SQ64[_a] >> 3)) & 1
    for _b in range(120):
        if SQ64[_a] >= 0 and SQ64[_b] >= 0:
            DIST[_a, _b] = max(abs((SQ64[_a] & 7) - (SQ64[_b] & 7)), abs((SQ64[_a] >> 3) - (SQ64[_b] >> 3)))
KREL = np.zeros(240, dtype=np.bool_)           # a knight jump apart (index delta + 120)
for _d in N_DIRS:
    KREL[_d + 120] = True
SPACE_SQ = np.zeros((2, 12), dtype=np.int64)   # files c-f, ranks 2-4 (white) / 7-5 (black)
for _w in range(2):
    _j = 0
    for _rk in (1, 2, 3):
        _r = _rk if _w == 0 else 7 - _rk
        for _f in range(2, 6):
            SPACE_SQ[_w, _j] = SQ120[_r * 8 + _f]
            _j += 1


# ZONE[0, ks, sq]: sq in the zone of a white king on ks (up = +1); ZONE[1]: black king (up = -1)
ZONE = np.zeros((2, 120, 120), dtype=np.bool_)
for _k in range(120):
    for _s in range(120):
        ZONE[0, _k, _s] = _zone_py(_k, _s, 1)
        ZONE[1, _k, _s] = _zone_py(_k, _s, -1)


@njit(cache=True)
def _zone(ks, sq, up):
    """sq is in the zone of king ks: around it, or two ranks in front."""
    k64 = SQ64[ks]
    s64 = SQ64[sq]
    df = abs((k64 & 7) - (s64 & 7))
    dr = (s64 >> 3) - (k64 >> 3)
    if df <= 1 and abs(dr) <= 1:
        return True
    return df <= 1 and dr == 2 * up


@njit(cache=True)
def _ext_finish(b, scr, wk, bk, nsq, units_w, units_b, natt_w, natt_b):
    """Extended terms; the attack maps (scr[128..375]) are already filled."""
    ka = 0
    if natt_w >= 2:
        ka += units_w
    if natt_b >= 2:
        ka -= units_b
    scr[FOFF + NBASIC + 0] = ka
    threat = 0
    hang = 0
    pfree = 0
    pkd = 0
    outpost = 0
    for qi in range(nsq):
        s = scr[440 + qi]
        p = b[s]
        t = p if p > 0 else -p
        sgn = 1 if p > 0 else -1
        own_map = 128 if p > 0 else 256
        opp_map = 256 if p > 0 else 128
        if 2 <= t <= 5:
            # attacked by an enemy pawn: a threat against this side
            if b[s + 9 * sgn] == -sgn or b[s + 11 * sgn] == -sgn:
                threat -= sgn
            if scr[opp_map + s] > 0 and scr[own_map + s] == 0:
                hang -= sgn
        if t == 1:
            s64 = SQ64[s]
            f = s64 & 7
            r = s64 >> 3
            passed = True
            for ff in range(max(f - 1, 0), min(f + 1, 7) + 1):
                if p > 0:
                    if scr[424 + ff] > r:
                        passed = False
                else:
                    if scr[416 + ff] < r:
                        passed = False
            if passed:
                rr = r if p > 0 else 7 - r
                stop = s + 10 * sgn
                if b[stop] == 0 and scr[opp_map + stop] == 0:
                    pfree += sgn * rr
                ok = wk if p > 0 else bk
                ek = bk if p > 0 else wk
                if ok != 0 and ek != 0:
                    st64 = SQ64[stop] if b[stop] != OFF else SQ64[s]
                    o64 = SQ64[ok]
                    e64 = SQ64[ek]
                    do = max(abs((o64 & 7) - (st64 & 7)), abs((o64 >> 3) - (st64 >> 3)))
                    de = max(abs((e64 & 7) - (st64 & 7)), abs((e64 >> 3) - (st64 >> 3)))
                    pkd += sgn * (de - do) * rr
        elif t == 2:
            s64 = SQ64[s]
            f = s64 & 7
            r = s64 >> 3
            rr = r if p > 0 else 7 - r
            if 3 <= rr <= 5 and (b[s - 9 * sgn] == sgn or b[s - 11 * sgn] == sgn):
                safe = True
                for ff in (f - 1, f + 1):
                    if 0 <= ff <= 7:
                        if p > 0 and scr[424 + ff] > r:
                            safe = False
                        if p < 0 and scr[416 + ff] < r:
                            safe = False
                if safe:
                    outpost += sgn
    scr[FOFF + NBASIC + 1] = threat
    scr[FOFF + NBASIC + 2] = hang
    scr[FOFF + NBASIC + 3] = pfree
    scr[FOFF + NBASIC + 4] = pkd
    scr[FOFF + NBASIC + 5] = outpost


@njit(cache=True)
def _ext_more(b, scr, wk, bk, nsq, units_w, units_b, natt_w, natt_b, wpieces, bpieces):
    """Richer terms; needs the attack maps (white scr[128+sq], black scr[256+sq])."""
    kd = 0
    if natt_w >= 2:
        kd += units_w * units_w // 16
    if natt_b >= 2:
        kd -= units_b * units_b // 16
    scr[FOFF + F_KD2] = kd
    # one pass over the pieces: knight squares, bishop colour, shielded minors, king-pawn distance
    nwn = 0
    nbn = 0
    kdw = 99
    kdb = 99
    bp = 0
    mb = 0
    for qi in range(nsq):
        s = scr[440 + qi]
        p = b[s]
        if p == 1 or p == -1:
            if wk != 0:
                dd = DIST[wk, s]
                if dd < kdw:
                    kdw = dd
            if bk != 0:
                dd = DIST[bk, s]
                if dd < kdb:
                    kdb = dd
        elif p == 2:
            scr[480 + nwn] = s
            nwn += 1
            if b[s + 10] == 1:
                mb += 1
        elif p == -2:
            scr[490 + nbn] = s
            nbn += 1
            if b[s - 10] == -1:
                mb -= 1
        elif p == 3:
            bp += scr[432 + SQCOL[s]]
            if b[s + 10] == 1:
                mb += 1
        elif p == -3:
            bp -= scr[434 + SQCOL[s]]
            if b[s - 10] == -1:
                mb -= 1
    scr[FOFF + F_BPAWNS] = bp
    scr[FOFF + F_MBEHIND] = mb
    if kdw < 99 and kdb < 99:
        scr[FOFF + F_KPDIST] = kdw - kdb
    for who in range(2):
        sgn = 1 if who == 0 else -1
        ek = bk if who == 0 else wk
        if ek == 0:
            continue
        mine = 128 if who == 0 else 256
        theirs = 256 if who == 0 else 128
        # weak squares in the enemy king zone: we attack, they defend at most once
        weak = 0
        front = -20 * sgn  # two ranks in front of the enemy king
        for j in range(12):
            if j < 9:
                u = ek + (j // 3 - 1) * 10 + (j % 3 - 1)
            else:
                u = ek + front + (j - 10)
            if u < 0 or u >= 120 or b[u] == OFF:
                continue
            if scr[mine + u] > 0 and scr[theirs + u] <= 1:
                weak += 1
        # safe knight checks
        nchk = 0
        nk = nwn if who == 0 else nbn
        if nk > 0:
            kb = 480 if who == 0 else 490
            for d in N_DIRS:
                u = ek + d
                q = b[u]
                if q == OFF or q * sgn > 0 or scr[theirs + u] > 0:
                    continue
                for j in range(nk):
                    if KREL[u - scr[kb + j] + 120]:
                        nchk += 1
                        break
        # safe squares we attack on the enemy king's lines
        lchk = 0
        for k in range(8):
            d = B_DIRS[k] if k < 4 else R_DIRS[k - 4]
            u = ek + d
            while b[u] == 0:
                if scr[mine + u] > 0 and scr[theirs + u] == 0:
                    lchk += 1
                u += d
        scr[FOFF + F_KZW] += sgn * weak
        scr[FOFF + F_SCN] += sgn * nchk
        scr[FOFF + F_SCL] += sgn * lchk
    # space: safe central squares on our side of the board, extra when behind our pawns
    for who in range(2):
        sgn = 1 if who == 0 else -1
        npcs = wpieces if who == 0 else bpieces
        if npcs == 0:
            continue
        cnt = 0
        for j in range(12):
            u = SPACE_SQ[who, j]
            if b[u] == sgn or b[u + 9 * sgn] == -sgn or b[u + 11 * sgn] == -sgn:
                continue
            cnt += 1
            v = u + 10 * sgn
            for k in range(3):
                if b[v] == sgn:
                    cnt += 1
                    break
                if b[v] == OFF:
                    break
                v += 10 * sgn
        scr[FOFF + F_SPACE] += sgn * (cnt * npcs // 4)


@njit(cache=True)
def evaluate(b, side, P, scr, rec):
    """Score from the side to move's view. With rec, the linear feature record
    goes into scr: [0]=n pieces, [1..32]=signed PST index+1, [40]=phase,
    [41..41+NFEAT)=feature counts (white minus black)."""
    for i in range(400, 432):
        scr[i] = 0
    for i in range(416, 424):
        scr[i] = 8
    for i in range(424, 432):
        scr[i] = -1
    for i in range(432, 436):
        scr[i] = 0  # pawns on light / dark squares: white 432, 433; black 434, 435
    for k in range(NFEAT):
        scr[FOFF + k] = 0
    mg = 0
    eg = 0
    phase = 0
    npc = 0
    wb = 0
    bb = 0
    wmat = 0
    bmat = 0
    wminor = 0
    bminor = 0
    wmajor = 0
    bmajor = 0
    wpawns = 0
    bpawns = 0
    wk = 0
    bk = 0
    nsq = 0
    for s in range(21, 99):
        p = b[s]
        if p == 0 or p == OFF:
            continue
        scr[440 + nsq] = s  # piece list for the second pass
        nsq += 1
        t = p if p > 0 else -p
        s64 = SQ64[s]
        sgn = 1
        if p > 0:
            idx = (t - 1) * 64 + s64
        else:
            idx = (t - 1) * 64 + (s64 ^ 56)
            sgn = -1
        mg += sgn * P[PST_MG + idx]
        eg += sgn * P[PST_EG + idx]
        phase += PHASE_INC[t]
        if rec:
            npc += 1
            scr[npc] = sgn * (idx + 1)
        f = s64 & 7
        r = s64 >> 3
        if t == 1:
            scr[(432 if p > 0 else 434) + ((f + r) & 1)] += 1
            if p > 0:
                scr[400 + f] += 1
                wpawns += 1
                if r < scr[416 + f]:
                    scr[416 + f] = r
            else:
                scr[408 + f] += 1
                bpawns += 1
                if r > scr[424 + f]:
                    scr[424 + f] = r
            continue
        if t == 6:
            if p > 0:
                wk = s
            else:
                bk = s
            continue
        if p > 0:
            wmat += VAL[t]
        else:
            bmat += VAL[t]
        if t == 2 or t == 3:
            if p > 0:
                wminor += 1
            else:
                bminor += 1
        else:
            if p > 0:
                wmajor += 1
            else:
                bmajor += 1
        if t == 3:
            if p > 0:
                wb += 1
            else:
                bb += 1
    ext_on = rec
    if not ext_on:
        for k in range(2 * NBASIC, 2 * NFEAT):
            if P[EXT + k] != 0:
                ext_on = True
                break
    # the richer terms (index >= F_BACKWARD) cost time: only when one of their weights is set
    ext2_on = rec
    if ext_on and not ext2_on:
        for k in range(2 * F_BACKWARD, 2 * NFEAT):
            if P[EXT + k] != 0:
                ext2_on = True
                break
    # mobility, and (for the extended terms) attack maps and king-zone hits, in one ray walk
    if ext_on:
        for i in range(128, 376):
            scr[i] = 0
    units_w = 0
    units_b = 0
    natt_w = 0
    natt_b = 0
    for qi in range(nsq):
        s = scr[440 + qi]
        p = b[s]
        t = p if p > 0 else -p
        sgn = 1 if p > 0 else -1
        base = 128 if p > 0 else 256
        if t == 1:
            if ext_on:
                for c in (9, 11):
                    u = s + c * sgn
                    if b[u] != OFF:
                        scr[base + u] += 1
            continue
        if t == 6:
            if ext_on:
                for d in K_DIRS:
                    u = s + d
                    if b[u] != OFF:
                        scr[base + u] += 1
            continue
        eks = bk if p > 0 else wk
        zi = 1 if p > 0 else 0
        mob = 0
        smob = 0
        hits = 0
        if t == 2:
            for d in N_DIRS:
                u = s + d
                q = b[u]
                if q != OFF:
                    if q == 0 or q * sgn < 0:
                        mob += 1
                        if ext2_on and b[u + 9 * sgn] != -sgn and b[u + 11 * sgn] != -sgn:
                            smob += 1
                    if ext_on:
                        scr[base + u] += 1
                        if eks != 0 and ZONE[zi, eks, u]:
                            hits += 1
                        if ext2_on and q * sgn < 0 and (q == -4 * sgn or q == -5 * sgn):
                            scr[FOFF + F_TMIN] += sgn
            scr[FOFF + 11] += sgn * mob
            if ext2_on:
                scr[FOFF + F_MOBN + (smob if smob < 8 else 8)] += sgn
        else:
            for k in range(8):
                if k < 4:
                    if t == 4:
                        continue
                    d = B_DIRS[k]
                else:
                    if t == 3:
                        continue
                    d = R_DIRS[k - 4]
                u = s + d
                while True:
                    q = b[u]
                    if q == OFF:
                        break
                    if ext_on:
                        scr[base + u] += 1
                        if eks != 0 and ZONE[zi, eks, u]:
                            hits += 1
                    if q == 0:
                        mob += 1
                        if ext2_on and b[u + 9 * sgn] != -sgn and b[u + 11 * sgn] != -sgn:
                            smob += 1
                        u += d
                        continue
                    if q * sgn < 0:
                        mob += 1
                        if ext2_on:
                            if b[u + 9 * sgn] != -sgn and b[u + 11 * sgn] != -sgn:
                                smob += 1
                            if t == 3 and (q == -4 * sgn or q == -5 * sgn):
                                scr[FOFF + F_TMIN] += sgn
                            elif t == 4 and q == -5 * sgn:
                                scr[FOFF + F_TROOK] += sgn
                    break
            if t == 3:
                scr[FOFF + 12] += sgn * mob
                if ext2_on:
                    scr[FOFF + F_MOBB + (smob if smob < 13 else 13)] += sgn
            elif t == 4:
                scr[FOFF + 13] += sgn * mob
                if ext2_on:
                    scr[FOFF + F_MOBR + (smob if smob < 14 else 14)] += sgn
            else:
                scr[FOFF + 14] += sgn * mob
                if ext2_on:
                    scr[FOFF + F_MOBQ + (smob if smob < 27 else 27)] += sgn
        if hits > 0:
            if p > 0:
                units_w += ATT_W[t] * hits
                natt_w += 1
            else:
                units_b += ATT_W[t] * hits
                natt_b += 1
    if phase > 24:
        phase = 24
    # insufficient material
    if wpawns == 0 and bpawns == 0 and wmajor == 0 and bmajor == 0 and wminor <= 1 and bminor <= 1:
        if rec:
            scr[0] = npc
            scr[40] = phase
        return 0
    if wb >= 2:
        scr[FOFF + 0] += 1
    if bb >= 2:
        scr[FOFF + 0] -= 1
    # pawns and rooks (only the squares that hold pieces)
    for qi in range(nsq):
        s = scr[440 + qi]
        p = b[s]
        s64 = SQ64[s]
        f = s64 & 7
        r = s64 >> 3
        if p == 1 or p == -1:
            own = 400 if p > 0 else 408
            sgn = 1 if p > 0 else -1
            left = scr[own + f - 1] if f > 0 else 0
            right = scr[own + f + 1] if f < 7 else 0
            if left == 0 and right == 0:
                scr[FOFF + 2] += sgn
            rrel = r if p > 0 else 7 - r
            if b[s - 1] == p or b[s + 1] == p or b[s - 9 * sgn] == p or b[s - 11 * sgn] == p:
                scr[FOFF + F_CONN] += sgn
                scr[FOFF + F_CONNR] += sgn * rrel
            elif left != 0 or right != 0:
                # backward: no own pawn beside or behind on the adjacent files, stop square hit by a pawn
                sup = False
                for ff in (f - 1, f + 1):
                    if 0 <= ff <= 7:
                        if p > 0 and scr[416 + ff] <= r:
                            sup = True
                        if p < 0 and scr[424 + ff] >= r:
                            sup = True
                stop = s + 10 * sgn
                if not sup and (b[stop + 9 * sgn] == -sgn or b[stop + 11 * sgn] == -sgn):
                    scr[FOFF + F_BACKWARD] += sgn
            passed = True
            for ff in range(max(f - 1, 0), min(f + 1, 7) + 1):
                if p > 0:
                    if scr[424 + ff] > r:
                        passed = False
                else:
                    if scr[416 + ff] < r:
                        passed = False
            if passed:
                rr = r if p > 0 else 7 - r
                if 1 <= rr <= 6:
                    scr[FOFF + 3 + rr - 1] += sgn
                q = b[s + 10 * sgn]
                if q != 0 and q != OFF:
                    scr[FOFF + F_PBLOCK] += sgn
        elif p == 4 or p == -4:
            sgn = 1 if p > 0 else -1
            own = scr[400 + f] if p > 0 else scr[408 + f]
            opp = scr[408 + f] if p > 0 else scr[400 + f]
            if own == 0:
                if opp == 0:
                    scr[FOFF + 9] += sgn
                else:
                    scr[FOFF + 10] += sgn
            if (p > 0 and r == 6) or (p < 0 and r == 1):
                scr[FOFF + 18] += sgn
    for f in range(8):
        if scr[400 + f] > 1:
            scr[FOFF + 1] += scr[400 + f] - 1
        if scr[408 + f] > 1:
            scr[FOFF + 1] -= scr[408 + f] - 1
    # king safety
    for who in range(2):
        ks = wk if who == 0 else bk
        if ks == 0:
            continue
        sgn = 1 if who == 0 else -1
        k64 = SQ64[ks]
        kf = k64 & 7
        kr = k64 >> 3
        shield = 0
        openf = 0
        for ff in range(max(kf - 1, 0), min(kf + 1, 7) + 1):
            for dr in (1, 2):
                rr = kr + sgn * dr
                if 0 <= rr <= 7 and b[SQ120[rr * 8 + ff]] == sgn:
                    shield += 1
            if (scr[400 + ff] if who == 0 else scr[408 + ff]) == 0:
                openf += 1
        scr[FOFF + 15] += sgn * shield
        scr[FOFF + 17] += sgn * openf
    scr[FOFF + 16] = side
    if ext_on:
        _ext_finish(b, scr, wk, bk, nsq, units_w, units_b, natt_w, natt_b)
        if ext2_on:
            _ext_more(b, scr, wk, bk, nsq, units_w, units_b, natt_w, natt_b, wminor + wmajor, bminor + bmajor)
    nf = NFEAT if ext2_on else (F_BACKWARD if ext_on else NBASIC)
    for k in range(nf):
        c = scr[FOFF + k]
        if c != 0:
            mg += c * P[EXT + 2 * k]
            eg += c * P[EXT + 2 * k + 1]
    num = mg * phase + eg * (24 - phase)
    score = num // 24 if num >= 0 else -((-num) // 24)
    if rec:
        scr[0] = npc
        scr[40] = phase
    # mop-up: drive a bare king to the edge
    if bpawns == 0 and bmat == 0 and wmat >= 500 and bk != 0:
        score += _mopup(wk, bk)
    elif wpawns == 0 and wmat == 0 and bmat >= 500 and wk != 0:
        score -= _mopup(bk, wk)
    return score * side


EVC_OFF = 4096
EVC_SIZE = 65536
SCR_LEN = EVC_OFF + 2 * EVC_SIZE


@njit(cache=True)
def eval_cached(b, st, hist, P, scr, cfg):
    """Static evaluation with a small hash-indexed cache kept in scr."""
    if not cfg[7] or scr.shape[0] < SCR_LEN:
        return evaluate(b, st[0], P, scr, False)
    h = hist[st[6]]
    slot = EVC_OFF + 2 * np.int64(h & np.uint64(EVC_SIZE - 1))
    key = np.int64(h >> np.uint64(1))
    if scr[slot] == key:
        return scr[slot + 1]
    v = evaluate(b, st[0], P, scr, False)
    scr[slot] = key
    scr[slot + 1] = v
    return v


@njit(cache=True)
def _mopup(win_k, lose_k):
    l64 = SQ64[lose_k]
    w64 = SQ64[win_k]
    lf = l64 & 7
    lr = l64 >> 3
    cd = max(3 - lf, lf - 4) + max(3 - lr, lr - 4)
    kd = abs(lf - (w64 & 7)) + abs(lr - (w64 >> 3))
    return 300 + 20 * cd + 6 * (14 - kd)


# ---------------------------------------------------------------- search
@njit(cache=True)
def is_repetition(st, hist):
    i = st[6]
    h = hist[i]
    lo = i - st[3]
    if lo < 0:
        lo = 0
    k = i - 2
    while k >= lo:
        if hist[k] == h:
            return True
        k -= 2
    return False


@njit(cache=True)
def has_pieces(b, side):
    for s in range(21, 99):
        p = b[s] * side
        if 2 <= p <= 5 and b[s] != OFF:
            return True
    return False


@njit(cache=False)
def _time_up(info, tm):
    info[0] += 1
    if (info[0] & 2047) == 0:
        with objmode(now="float64"):
            now = time.perf_counter()
        if now >= tm[1] or (info[3] > 0 and info[0] >= info[3]):
            info[1] = 1
    return info[1] != 0


@njit(cache=True, inline="always")
def _pt(b, m):
    """piece-to index (0..831) of a move on the board before it is made."""
    return (b[mfrom(m)] + 6) * 64 + SQ64[mto(m)]


@njit(cache=True)
def _prev(scs, ply, back):
    if ply < back:
        return -1
    v = scs[ply - back, S_MOVE]
    return v if 0 <= v < 832 else -1


@njit(cache=True)
def _quiet_hist(b, hh, m, hi, p1, p2):
    pt = _pt(b, m)
    h = hh[H_BUT + hi * 14400 + mfrom(m) * 120 + mto(m)]
    if p1 >= 0:
        h += hh[H_CONT + p1 * 832 + pt]
    if p2 >= 0:
        h += hh[H_CONT + p2 * 832 + pt]
    return h


@njit(cache=True, inline="always")
def _grav(hh, i, bonus):
    hh[i] += bonus - hh[i] * abs(bonus) // HIST_MAX


@njit(cache=True)
def _score_moves(b, mv, sc, n, ttmove, kil, hh, ply, side, scs, cfg):
    hi = 0 if side == 1 else 1
    if cfg[8]:
        p1 = _prev(scs, ply, 1)
        p2 = _prev(scs, ply, 2)
        cm = hh[H_CM + p1] if p1 >= 0 else 0
        for i in range(n):
            m = mv[i]
            if m == ttmove:
                sc[i] = 10_000_000
                continue
            to = mto(m)
            cap = b[to]
            pr = mpromo(m)
            if cap != 0 or mflag(m) == 2 or pr != 0:
                victim = VAL[abs(cap)] if cap != 0 else 100
                attacker = VAL[abs(b[mfrom(m)])]
                sc[i] = 1_000_000 + 10 * victim - attacker // 10 + (VAL[pr] if pr else 0)
            elif m == kil[ply, 0]:
                sc[i] = 900_000
            elif m == kil[ply, 1]:
                sc[i] = 800_000
            elif m == cm:
                sc[i] = 700_000
            else:
                sc[i] = _quiet_hist(b, hh, m, hi, p1, p2)
        return
    for i in range(n):
        m = mv[i]
        if m == ttmove:
            sc[i] = 10_000_000
            continue
        to = mto(m)
        cap = b[to]
        pr = mpromo(m)
        if cap != 0 or mflag(m) == 2 or pr != 0:
            victim = VAL[abs(cap)] if cap != 0 else 100
            attacker = VAL[abs(b[mfrom(m)])]
            sc[i] = 1_000_000 + 10 * victim - attacker // 10 + (VAL[pr] if pr else 0)
        elif m == kil[ply, 0]:
            sc[i] = 900_000
        elif m == kil[ply, 1]:
            sc[i] = 800_000
        else:
            sc[i] = hh[H_BUT + hi * 14400 + mfrom(m) * 120 + to]


@njit(cache=True)
def _pick(mv, sc, i, n):
    best = i
    for j in range(i + 1, n):
        if sc[j] > sc[best]:
            best = j
    if best != i:
        t = mv[i]
        mv[i] = mv[best]
        mv[best] = t
        t = sc[i]
        sc[i] = sc[best]
        sc[best] = t


@njit(cache=True)
def least_attacker(b, sq, side):
    if side == 1:
        if b[sq - 9] == 1:
            return sq - 9
        if b[sq - 11] == 1:
            return sq - 11
    else:
        if b[sq + 9] == -1:
            return sq + 9
        if b[sq + 11] == -1:
            return sq + 11
    for d in N_DIRS:
        if b[sq + d] == 2 * side:
            return sq + d
    best = 0
    bestv = 99
    for d in B_DIRS:
        t = sq + d
        while b[t] == 0:
            t += d
        p = b[t] * side
        if b[t] != OFF and (p == 3 or p == 5) and p < bestv:
            best = t
            bestv = p
    for d in R_DIRS:
        t = sq + d
        while b[t] == 0:
            t += d
        p = b[t] * side
        if b[t] != OFF and (p == 4 or p == 5) and p < bestv:
            best = t
            bestv = p
    if best != 0:
        return best
    for d in K_DIRS:
        if b[sq + d] == 6 * side:
            return sq + d
    return 0


@njit(cache=True)
def see(b, fr, to):
    """Static exchange evaluation of the capture fr->to (material balance for the mover)."""
    gain = np.zeros(40, dtype=np.int64)
    rsq = np.zeros(40, dtype=np.int64)
    rpc = np.zeros(40, dtype=np.int64)
    nrem = 0
    side = 1 if b[fr] > 0 else -1
    gain[0] = VAL[abs(b[to])]
    att_val = VAL[abs(b[fr])]
    rsq[nrem] = fr
    rpc[nrem] = b[fr]
    nrem += 1
    b[fr] = 0
    stm = -side
    d = 0
    while d < 38:
        a = least_attacker(b, to, stm)
        if a == 0:
            break
        d += 1
        gain[d] = att_val - gain[d - 1]
        if max(-gain[d - 1], gain[d]) < 0:
            break
        att_val = VAL[abs(b[a])]
        rsq[nrem] = a
        rpc[nrem] = b[a]
        nrem += 1
        b[a] = 0
        stm = -stm
    for k in range(nrem):
        b[rsq[k]] = rpc[k]
    while d > 0:
        g = gain[d - 1]
        gain[d - 1] = -max(-g, gain[d])
        d -= 1
    return gain[0]


@njit(cache=False, nogil=True)
def qsearch(b, st, hist, und, mvs, scs, kil, hh, ttk, ttm, ttd, ttf, tts, info, tm, P, scr,
            alpha, beta, ply, cfg):
    if _time_up(info, tm):
        return 0
    key = hist[st[6]]
    qidx = np.int64(key & np.uint64(ttk.shape[0] - 1))
    if cfg[5] and beta - alpha == 1 and ttk[qidx] == key:
        s = tts[qidx]
        if s > MATE_BOUND:
            s -= ply
        elif s < -MATE_BOUND:
            s += ply
        f = ttf[qidx]
        if f == 0 or (f == 1 and s >= beta) or (f == 2 and s <= alpha):
            return s
    orig_alpha = alpha
    stand = eval_cached(b, st, hist, P, scr, cfg)
    if ply >= MAXPLY - 1:
        return stand
    if stand >= beta:
        if cfg[5] and ttk[qidx] != key:
            ttk[qidx] = key
            ttm[qidx] = 0
            ttd[qidx] = 0
            ttf[qidx] = 1
            tts[qidx] = stand
        return stand
    if stand > alpha:
        alpha = stand
    mv = mvs[ply]
    sc = scs[ply]
    n = gen_moves(b, st, mv, True)
    _score_moves(b, mv, sc, n, 0, kil, hh, ply, st[0], scs, cfg)
    side = st[0]
    for i in range(n):
        _pick(mv, sc, i, n)
        m = mv[i]
        cap = b[mto(m)]
        if mpromo(m) == 0:
            gain = VAL[abs(cap)] if cap != 0 else 100
            if stand + gain + 200 < alpha:
                continue
            if cfg[0] and cap != 0 and VAL[abs(b[mfrom(m)])] > VAL[abs(cap)] and see(b, mfrom(m), mto(m)) < 0:
                continue
        make_move(b, st, hist, und, m)
        if attacked(b, king_sq(st, side), -side):
            unmake_move(b, st, hist, und)
            continue
        s = -qsearch(b, st, hist, und, mvs, scs, kil, hh, ttk, ttm, ttd, ttf, tts, info, tm, P, scr,
                     -beta, -alpha, ply + 1, cfg)
        unmake_move(b, st, hist, und)
        if info[1] != 0:
            return 0
        if s >= beta:
            if cfg[5] and (ttk[qidx] != key or ttd[qidx] <= 0) and abs(s) < MATE_BOUND:
                ttk[qidx] = key
                ttm[qidx] = m
                ttd[qidx] = 0
                ttf[qidx] = 1
                tts[qidx] = s
            return s
        if s > alpha:
            alpha = s
    if cfg[5] and (ttk[qidx] != key or ttd[qidx] <= 0) and abs(alpha) < MATE_BOUND:
        if ttk[qidx] != key:
            ttm[qidx] = 0
        ttk[qidx] = key
        ttd[qidx] = 0
        ttf[qidx] = 0 if alpha > orig_alpha else 2
        tts[qidx] = alpha
    return alpha


@njit(cache=False, nogil=True)
def search(b, st, hist, und, mvs, scs, kil, hh, ttk, ttm, ttd, ttf, tts, info, tm, P, scr,
           depth, alpha, beta, ply, do_null, cfg):
    side = st[0]
    pv_node = beta - alpha > 1
    excl = scs[ply, S_EXCL]
    if ply > 0:
        if st[3] >= 100 or is_repetition(st, hist):
            return 0
        # mate distance pruning
        ma = -MATE + ply
        if alpha < ma:
            alpha = ma
        mb = MATE - ply - 1
        if beta > mb:
            beta = mb
        if alpha >= beta:
            return alpha
    chk = attacked(b, king_sq(st, side), -side)
    if chk:
        depth += 1
    if depth <= 0:
        return qsearch(b, st, hist, und, mvs, scs, kil, hh, ttk, ttm, ttd, ttf, tts, info, tm, P, scr,
                       alpha, beta, ply, cfg)
    if _time_up(info, tm):
        return 0
    if ply >= MAXPLY - 1:
        return eval_cached(b, st, hist, P, scr, cfg)
    if ply > info[2]:
        info[2] = ply
    key = hist[st[6]]
    idx = np.int64(key & np.uint64(ttk.shape[0] - 1))
    ttmove = 0
    tthit = ttk[idx] == key
    if tthit:
        ttmove = ttm[idx]
        if ply > 0 and not pv_node and excl == 0 and ttd[idx] >= depth:
            s = tts[idx]
            if s > MATE_BOUND:
                s -= ply
            elif s < -MATE_BOUND:
                s += ply
            f = ttf[idx]
            if f == 0 or (f == 1 and s >= beta) or (f == 2 and s <= alpha):
                return s
    hi = 0 if side == 1 else 1
    raw = eval_cached(b, st, hist, P, scr, cfg)
    static = raw
    cidx = H_CORR + hi * CORR_N + (st[7] & (CORR_N - 1))
    if cfg[11] and not chk:
        static = raw + hh[cidx] // 256
        if static > MATE_BOUND - 1:
            static = MATE_BOUND - 1
        elif static < -MATE_BOUND + 1:
            static = -MATE_BOUND + 1
    scs[ply, S_STATIC] = static if not chk else -INF
    scs[ply, S_MOVE] = -1
    imp = 1
    if cfg[4]:
        imp = 1 if (not chk and ply >= 2 and static > scs[ply - 2, S_STATIC]) else 0
    if excl == 0:
        if cfg[3] and not pv_node and not chk and depth <= 2 and static + 250 * depth < alpha:
            q = qsearch(b, st, hist, und, mvs, scs, kil, hh, ttk, ttm, ttd, ttf, tts, info, tm, P, scr,
                        alpha, alpha + 1, ply, cfg)
            if q <= alpha:
                return q
        if not pv_node and not chk:
            # reverse futility
            if depth <= 4 and abs(beta) < MATE_BOUND and static - 90 * (depth - (imp if cfg[4] else 0)) >= beta:
                return static
            # null move
            if do_null and depth >= 3 and static >= beta and has_pieces(b, side):
                R = 3 + depth // 6
                make_null(st, hist, und)
                s = -search(b, st, hist, und, mvs, scs, kil, hh, ttk, ttm, ttd, ttf, tts, info, tm, P, scr,
                            depth - 1 - R, -beta, -beta + 1, ply + 1, False, cfg)
                unmake_null(st, hist, und)
                if info[1] != 0:
                    return 0
                if s >= beta:
                    if s > MATE_BOUND:
                        s = beta
                    return s
            # ProbCut: a good capture that beats beta by a margin at reduced depth
            if cfg[10] and depth >= 5 and abs(beta) < MATE_BOUND:
                rbeta = beta + 200
                mv = mvs[ply]
                sc = scs[ply]
                n = gen_moves(b, st, mv, True)
                _score_moves(b, mv, sc, n, ttmove, kil, hh, ply, side, scs, cfg)
                for i in range(n):
                    _pick(mv, sc, i, n)
                    m = mv[i]
                    cap = b[mto(m)]
                    if cap == 0:
                        continue
                    if see(b, mfrom(m), mto(m)) < rbeta - static:
                        continue
                    pt = _pt(b, m)
                    make_move(b, st, hist, und, m)
                    if attacked(b, king_sq(st, side), -side):
                        unmake_move(b, st, hist, und)
                        continue
                    scs[ply, S_MOVE] = pt
                    s = -qsearch(b, st, hist, und, mvs, scs, kil, hh, ttk, ttm, ttd, ttf, tts, info, tm, P, scr,
                                 -rbeta, -rbeta + 1, ply + 1, cfg)
                    if s >= rbeta:
                        s = -search(b, st, hist, und, mvs, scs, kil, hh, ttk, ttm, ttd, ttf, tts, info, tm, P,
                                    scr, depth - 4, -rbeta, -rbeta + 1, ply + 1, True, cfg)
                    unmake_move(b, st, hist, und)
                    if info[1] != 0:
                        return 0
                    if s >= rbeta:
                        return s
                scs[ply, S_MOVE] = -1
    # internal iterative reduction
    if ttmove == 0 and depth >= 5 and pv_node:
        depth -= 1
    # singular extension: is the hash move much better than every alternative?
    sing = 0
    if (cfg[9] and ply > 0 and excl == 0 and ttmove != 0 and depth >= 7 and ply < MAXPLY // 2 and tthit
            and ttd[idx] >= depth - 3 and ttf[idx] != 2 and abs(tts[idx]) < MATE_BOUND):
        sbeta = tts[idx] - 2 * depth
        scs[ply, S_EXCL] = ttmove
        s = search(b, st, hist, und, mvs, scs, kil, hh, ttk, ttm, ttd, ttf, tts, info, tm, P, scr,
                   (depth - 1) // 2, sbeta - 1, sbeta, ply, False, cfg)
        scs[ply, S_EXCL] = 0
        if info[1] != 0:
            return 0
        if s < sbeta:
            sing = 1
        elif sbeta >= beta:
            return sbeta  # multi-cut: several moves beat beta
        scs[ply, S_STATIC] = static if not chk else -INF
    mv = mvs[ply]
    sc = scs[ply]
    n = gen_moves(b, st, mv, False)
    _score_moves(b, mv, sc, n, ttmove, kil, hh, ply, side, scs, cfg)
    if cfg[1]:
        for i in range(n):
            m = mv[i]
            c = b[mto(m)]
            if m != ttmove and c != 0 and mpromo(m) == 0 and VAL[abs(b[mfrom(m)])] > VAL[abs(c)]:
                if see(b, mfrom(m), mto(m)) < 0:
                    sc[i] = -1_000_000 + VAL[abs(c)]
    p1 = _prev(scs, ply, 1)
    p2 = _prev(scs, ply, 2)
    best = -INF
    bestmove = 0
    legal = 0
    orig_alpha = alpha
    quiets_tried = 0
    for i in range(n):
        _pick(mv, sc, i, n)
        m = mv[i]
        if m == excl:
            continue
        cap = b[mto(m)]
        quiet = cap == 0 and mflag(m) != 2 and mpromo(m) == 0
        pt = _pt(b, m)
        qh = 0
        if quiet and cfg[12]:
            qh = _quiet_hist(b, hh, m, hi, p1, p2)
        make_move(b, st, hist, und, m)
        if attacked(b, king_sq(st, side), -side):
            unmake_move(b, st, hist, und)
            continue
        legal += 1
        gives = attacked(b, king_sq(st, -side), side)
        if cfg[6] and not pv_node and not chk and not gives and legal > 1 and best > -MATE_BOUND and depth <= 4 \
                and mpromo(m) == 0:
            # SEE on the board after the move: is the moved piece now lost?
            unmake_move(b, st, hist, und)
            sv = see(b, mfrom(m), mto(m))
            make_move(b, st, hist, und, m)
            if (quiet and sv < -50 * depth) or (not quiet and sv < -100 * depth):
                unmake_move(b, st, hist, und)
                continue
        if quiet and not pv_node and not chk and not gives and legal > 1 and best > -MATE_BOUND:
            # futility and late-move pruning
            if depth <= 2 and static + 120 * depth <= alpha:
                unmake_move(b, st, hist, und)
                continue
            if depth <= 3 and quiets_tried >= (4 + 4 * depth * depth if imp else 3 + 2 * depth * depth):
                unmake_move(b, st, hist, und)
                continue
        if quiet:
            quiets_tried += 1
        scs[ply, S_MOVE] = pt
        ext = 1 if (sing and m == ttmove) else 0
        nd = depth - 1 + ext
        if legal == 1:
            s = -search(b, st, hist, und, mvs, scs, kil, hh, ttk, ttm, ttd, ttf, tts, info, tm, P, scr,
                        nd, -beta, -alpha, ply + 1, True, cfg)
        else:
            r = 0
            if depth >= 3 and legal > 3 and quiet and not chk and not gives:
                r = LMR[min(depth, 63), min(legal, 63)]
                if pv_node:
                    r -= 1
                if m == kil[ply, 0] or m == kil[ply, 1]:
                    r -= 1
                if cfg[2]:
                    hv = hh[H_BUT + hi * 14400 + mfrom(m) * 120 + mto(m)]
                    if hv > 2000:
                        r -= 1
                    elif hv == 0 and legal > 8:
                        r += 1
                if cfg[12]:
                    r -= qh // 12000
                if cfg[12] and not imp:
                    r += 1
                if r < 0:
                    r = 0
                if r > nd - 1:
                    r = nd - 1
                if r < 0:
                    r = 0
            s = -search(b, st, hist, und, mvs, scs, kil, hh, ttk, ttm, ttd, ttf, tts, info, tm, P, scr,
                        nd - r, -alpha - 1, -alpha, ply + 1, True, cfg)
            if s > alpha and r > 0:
                s = -search(b, st, hist, und, mvs, scs, kil, hh, ttk, ttm, ttd, ttf, tts, info, tm, P, scr,
                            nd, -alpha - 1, -alpha, ply + 1, True, cfg)
            if s > alpha and s < beta:
                s = -search(b, st, hist, und, mvs, scs, kil, hh, ttk, ttm, ttd, ttf, tts, info, tm, P, scr,
                            nd, -beta, -alpha, ply + 1, True, cfg)
        unmake_move(b, st, hist, und)
        if info[1] != 0:
            return 0
        if s > best:
            best = s
            bestmove = m
            if ply == 0:
                info[4] = m
                info[5] = s
            if s > alpha:
                alpha = s
                if s >= beta:
                    if quiet:
                        if kil[ply, 0] != m:
                            kil[ply, 1] = kil[ply, 0]
                            kil[ply, 0] = m
                        if cfg[8]:
                            bonus = 4000 if depth > 13 else 20 * depth * depth + 100 * depth - 80
                            _grav(hh, H_BUT + hi * 14400 + mfrom(m) * 120 + mto(m), bonus)
                            if p1 >= 0:
                                _grav(hh, H_CONT + p1 * 832 + pt, bonus)
                                hh[H_CM + p1] = m
                            if p2 >= 0:
                                _grav(hh, H_CONT + p2 * 832 + pt, bonus)
                            # the quiet moves tried before it failed: lower their history
                            for j in range(i):
                                q = mv[j]
                                if q == excl or b[mto(q)] != 0 or mflag(q) == 2 or mpromo(q) != 0:
                                    continue
                                _grav(hh, H_BUT + hi * 14400 + mfrom(q) * 120 + mto(q), -bonus)
                                qt = _pt(b, q)
                                if p1 >= 0:
                                    _grav(hh, H_CONT + p1 * 832 + qt, -bonus)
                                if p2 >= 0:
                                    _grav(hh, H_CONT + p2 * 832 + qt, -bonus)
                        else:
                            hb = H_BUT + hi * 14400
                            hh[hb + mfrom(m) * 120 + mto(m)] += depth * depth
                            if hh[hb + mfrom(m) * 120 + mto(m)] > 400_000:
                                for x in range(14400):
                                    hh[hb + x] //= 2
                    break
    if legal == 0:
        if excl != 0:
            return alpha
        return -MATE + ply if chk else 0
    flag = 1 if best >= beta else (0 if best > orig_alpha else 2)
    if excl != 0:
        return best
    # correction history: learn how far the static eval was from the search result
    if cfg[11] and not chk and abs(best) < MATE_BOUND and (bestmove == 0 or (b[mto(bestmove)] == 0 and
                                                                           mpromo(bestmove) == 0)):
        if not (flag == 1 and best <= static) and not (flag == 2 and best >= static):
            w = depth + 1 if depth < 15 else 16
            tgt = (best - raw) * 256
            if tgt > 256 * 64:
                tgt = 256 * 64
            elif tgt < -256 * 64:
                tgt = -256 * 64
            hh[cidx] = (hh[cidx] * (256 - w) + tgt * w) // 256
    store = best
    if store > MATE_BOUND:
        store += ply
    elif store < -MATE_BOUND:
        store -= ply
    if ttk[idx] != key or depth >= ttd[idx] or flag == 0:
        ttk[idx] = key
        ttm[idx] = bestmove
        ttd[idx] = depth
        ttf[idx] = flag
        tts[idx] = store
    return best
