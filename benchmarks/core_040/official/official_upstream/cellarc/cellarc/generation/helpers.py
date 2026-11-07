"""Utility helpers for working with one-dimensional cellular automata neighborhoods."""

from __future__ import annotations

from functools import lru_cache
from typing import Dict, Iterator, List, Sequence, Tuple

import numpy as np


def as_init(seq: Sequence[int]) -> np.ndarray:
    """Convert a 1-D configuration into a single-row array."""
    return np.array([list(seq)], dtype=int)


def enumerate_neighborhoods(k: int, r: int) -> Iterator[Tuple[int, ...]]:
    """Yield all radius-r neighborhoods over an alphabet of size k."""
    arity = 2 * r + 1
    for idx in range(k ** arity):
        x = idx
        digits: List[int] = []
        for _ in range(arity):
            digits.append(x % k)
            x //= k
        yield tuple(reversed(digits))


@lru_cache(maxsize=128)
def neighborhood_index(
    k: int, r: int
) -> Tuple[
    List[Tuple[int, ...]],
    Dict[Tuple[int, int], List[Tuple[int, ...]]],
    Dict[Tuple[int, int], List[Tuple[int, ...]]],
]:
    """Group neighborhoods by useful statistics for rule construction."""
    neighborhoods = list(enumerate_neighborhoods(k, r))
    by_center_outer_sum: Dict[Tuple[int, int], List[Tuple[int, ...]]] = {}
    by_center_total_sum: Dict[Tuple[int, int], List[Tuple[int, ...]]] = {}
    for nb in neighborhoods:
        center = nb[r]
        total = sum(nb)
        outer = total - center
        by_center_outer_sum.setdefault((center, outer), []).append(nb)
        by_center_total_sum.setdefault((center, total), []).append(nb)
    return neighborhoods, by_center_outer_sum, by_center_total_sum


def ring_slice(seq: Sequence[int], start: int, count: int) -> List[int]:
    """Return `count` elements from the cyclic sequence starting at `start`."""
    n = len(seq)
    return [seq[(start + j) % n] for j in range(count)]


__all__ = ["as_init", "enumerate_neighborhoods", "neighborhood_index", "ring_slice"]
