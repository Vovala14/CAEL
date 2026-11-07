from __future__ import annotations

import random
from typing import List, Optional, Tuple

Word = List[int]


def window_size(radius: int, steps: int) -> int:
    return 2 * radius * steps + 1


def de_bruijn_cycle(k: int, n: int) -> Word:
    """
    Return a cyclic de Bruijn sequence B(k, n) as a linear list of length k**n.
    Each length-n window on the cycle appears exactly once.
    """
    if k < 2 or n < 1:
        raise ValueError("k>=2 and n>=1 required")
    a = [0] * (k * n)
    seq: List[int] = []

    def db(t: int, p: int) -> None:
        if t > n:
            if n % p == 0:
                seq.extend(a[1 : p + 1])
        else:
            a[t] = a[t - p]
            db(t + 1, p)
            for j in range(a[t - p] + 1, k):
                a[t] = j
                db(t + 1, t)

    db(1, 1)
    return seq  # length == k**n


def split_cycle(cycle: Word, parts: int) -> List[Word]:
    """
    Cut the cyclic sequence into `parts` contiguous segments.
    Each segment will be treated as wrap=True when used as a CA input.
    """
    L = len(cycle)
    if parts <= 0 or parts > L:
        raise ValueError("parts must be in [1, len(cycle)]")
    base = L // parts
    rem = L % parts
    cuts = []
    start = 0
    for i in range(parts):
        seg_len = base + (1 if i < rem else 0)
        cuts.append(cycle[start : start + seg_len])
        start += seg_len
    return cuts


def choose_r_t_options(W: int, max_radius: int = 3, max_steps: int | None = None) -> List[Tuple[int, int]]:
    """
    Enumerate feasible (r, t) pairs satisfying 2*r*t+1 == W with caps on radius/steps.
    """
    if W < 3 or W % 2 == 0:
        raise ValueError("W must be odd and >=3")
    opts: List[Tuple[int, int]] = []
    for r in range(1, max_radius + 1):
        t = (W - 1) // (2 * r)
        if 2 * r * t + 1 == W and (max_steps is None or 1 <= t <= max_steps):
            opts.append((r, t))
    return opts


def choose_r_t_for_W(
    W: int,
    max_radius: int = 3,
    max_steps: int | None = None,
    strategy: str = "min_r",
    rng: Optional[random.Random] = None,
) -> Tuple[int, int]:
    """
    Select an (r, t) pair for the given window size using the supplied strategy.

    Strategies:
      - min_r / max_r: pick the extreme radius option.
      - uniform: sample uniformly from valid pairs.
      - bias_steps: prefer larger t.
      - bias_radius: prefer larger r.
    """
    options = choose_r_t_options(W, max_radius=max_radius, max_steps=max_steps)
    if not options:
        raise ValueError("No (r,t) matching W under the given caps.")
    if strategy == "min_r":
        return options[0]
    if strategy == "max_r":
        return options[-1]

    picker = rng if rng is not None else random
    if strategy == "uniform":
        return picker.choice(options)
    if strategy == "bias_steps":
        weights = [t for (_, t) in options]
        return picker.choices(options, weights=weights, k=1)[0]
    if strategy == "bias_radius":
        weights = [r for (r, _) in options]
        return picker.choices(options, weights=weights, k=1)[0]
    return options[0]
