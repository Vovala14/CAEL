"""Fingerprints and reusable evaluation helpers for cellular automata rules."""

from __future__ import annotations

import hashlib
from typing import Dict, Mapping, Tuple, Union

from ..utils import de_bruijn_cycle
from .cax_runner import evolve_rule_table
from .helpers import neighborhood_index
from .rule_table import DenseRuleTable, ensure_dense_rule_table

RuleTableLike = Union[DenseRuleTable, Mapping[Tuple[int, ...], int]]


def apply_rule_from_table(table: RuleTableLike):
    """Return a callable that applies the provided rule table."""
    return lambda n, c, t: table[tuple(int(x) for x in n)]


def induced_tstep_fingerprint(table: RuleTableLike, k: int, r: int, t: int) -> str:
    """Hash the induced t-step map over all windows to enforce uniqueness."""
    dense = ensure_dense_rule_table(table, alphabet_size=k, radius=r)
    width = 2 * r * t + 1
    cycle = de_bruijn_cycle(k, width)
    half = (width - 1) // 2
    evolved = evolve_rule_table(
        dense,
        cycle,
        timesteps=t + 1,
        alphabet_size=k,
        radius=r,
    ).tolist()
    length = len(cycle)
    mapping: Dict[Tuple[int, ...], int] = {}
    for i in range(length):
        window = tuple(cycle[(i - half + j) % length] for j in range(width))
        mapping[window] = evolved[i]
    h = hashlib.sha256()
    h.update(f"k={k};r={r};t={t};W={width};".encode())
    for window in sorted(mapping.keys()):
        h.update(bytes(window))
        h.update(bytes([mapping[window]]))
    return h.hexdigest()


def rule_fingerprint(table: RuleTableLike, k: int, r: int) -> str:
    """Hash the one-step local rule table."""
    dense = ensure_dense_rule_table(table, alphabet_size=k, radius=r)
    neighborhoods, _, _ = neighborhood_index(k, r)
    values = dense.values_view()
    h = hashlib.sha256()
    h.update(f"k={k};r={r};".encode())
    for nb, val in zip(neighborhoods, values):
        h.update(bytes(nb))
        h.update(bytes([int(val)]))
    return h.hexdigest()


__all__ = ["apply_rule_from_table", "induced_tstep_fingerprint", "rule_fingerprint"]
