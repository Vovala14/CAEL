"""Families of cellular automata rule generators."""

from __future__ import annotations

import random
from array import array
from typing import Dict, List, Optional, Tuple

from .helpers import neighborhood_index
from .rule_table import DenseRuleTable, _typecode_for_alphabet


def _empty_values(
    k: int, r: int, fill: int = 0
) -> Tuple[array, List[Tuple[int, ...]], Dict[Tuple[int, int], List[Tuple[int, ...]]], Dict[Tuple[int, int], List[Tuple[int, ...]]], str]:
    neighborhoods, by_center_outer, by_center_total = neighborhood_index(k, r)
    typecode = _typecode_for_alphabet(k)
    size = len(neighborhoods)
    values = array(typecode)
    if size:
        values = array(typecode, [fill]) * size
    return values, neighborhoods, by_center_outer, by_center_total, typecode


def rule_table_random_lambda(
    k: int,
    r: int,
    rng: random.Random,
    lambda_val: float = 0.5,
    quiescent_state: int = 0,
) -> Tuple[DenseRuleTable, float, int]:
    """Langton-style random table over k symbols with target λ."""
    arity = 2 * r + 1
    size = k ** arity
    typecode = _typecode_for_alphabet(k)
    values = array(typecode)
    if size:
        values = array(typecode, [quiescent_state]) * size
    non_q = [s for s in range(k) if s != quiescent_state]
    non_q_count = 0
    for idx in range(size):
        if rng.random() < lambda_val and non_q:
            val = rng.choice(non_q)
            non_q_count += 1
        else:
            val = quiescent_state
        values[idx] = val
    lam_actual = non_q_count / size if size else 0.0
    return DenseRuleTable(k, r, values=values, typecode=typecode), lam_actual, quiescent_state


def rule_table_totalistic(
    k: int,
    r: int,
    rng: random.Random,
) -> Tuple[DenseRuleTable, float, int]:
    """Totalistic: output depends only on sum of neighborhood entries."""
    values, neighborhoods, _, _, typecode = _empty_values(k, r, fill=0)
    arity = 2 * r + 1
    max_sum = (k - 1) * arity
    sum_lookup = [rng.randrange(k) for _ in range(max_sum + 1)]
    non_q = 0
    for idx, nb in enumerate(neighborhoods):
        val = sum_lookup[sum(nb)]
        values[idx] = val
        if val != 0:
            non_q += 1
    lam = non_q / len(neighborhoods) if neighborhoods else 0.0
    return DenseRuleTable(k, r, values=values, typecode=typecode), lam, 0


def rule_table_outer_totalistic(
    k: int,
    r: int,
    rng: random.Random,
    lambda_val: float = 0.5,
    qstate: int = 0,
) -> Tuple[DenseRuleTable, float, int, Dict[str, object]]:
    """Outer-totalistic: depends on total neighborhood sum with separate center."""
    values, neighborhoods, _, by_center_total, typecode = _empty_values(k, r, fill=qstate)
    index_map = {nb: idx for idx, nb in enumerate(neighborhoods)}
    non_q = [s for s in range(k) if s != qstate]
    non_q_count = 0
    for (_, _total_sum), combos in by_center_total.items():
        if rng.random() < lambda_val and non_q:
            val = rng.choice(non_q)
        else:
            val = qstate
        if val != qstate:
            non_q_count += len(combos)
        for nb in combos:
            values[index_map[nb]] = val
    lam = non_q_count / len(neighborhoods) if neighborhoods else 0.0
    table = DenseRuleTable(k, r, values=values, typecode=typecode)
    return table, lam, qstate, {
        "lambda_target": float(lambda_val),
        "quiescent_state": int(qstate),
    }


def rule_table_outer_inner_totalistic(
    k: int,
    r: int,
    rng: random.Random,
    lambda_val: float = 0.5,
    qstate: int = 0,
) -> Tuple[DenseRuleTable, float, int, Dict[str, object]]:
    """Outer-inner totalistic: center tracked separately, depends on neighbors sum."""
    values, neighborhoods, by_center_outer, _, typecode = _empty_values(k, r, fill=qstate)
    index_map = {nb: idx for idx, nb in enumerate(neighborhoods)}
    non_q = [s for s in range(k) if s != qstate]
    non_q_count = 0
    for (_, _outer_sum), combos in by_center_outer.items():
        if rng.random() < lambda_val and non_q:
            val = rng.choice(non_q)
        else:
            val = qstate
        if val != qstate:
            non_q_count += len(combos)
        for nb in combos:
            values[index_map[nb]] = val
    lam = non_q_count / len(neighborhoods) if neighborhoods else 0.0
    table = DenseRuleTable(k, r, values=values, typecode=typecode)
    return table, lam, qstate, {
        "lambda_target": float(lambda_val),
        "quiescent_state": int(qstate),
    }


def rule_table_threshold(
    k: int,
    r: int,
    rng: random.Random,
    qstate: int = 0,
) -> Tuple[DenseRuleTable, float, int, Dict[str, object]]:
    """Piecewise threshold family with per-state randomised behaviour."""
    values, neighborhoods, by_center_outer, _, typecode = _empty_values(k, r, fill=qstate)
    index_map = {nb: idx for idx, nb in enumerate(neighborhoods)}
    theta = {c: float(rng.uniform(0.25 * (k - 1), 0.75 * (k - 1))) for c in range(k)}
    pairs: Dict[int, Tuple[int, int]] = {}
    pair_modes: Dict[int, str] = {}
    for c in range(k):
        if rng.random() < 0.5:
            pairs[c] = (qstate, c)
            pair_modes[c] = "majority_like"
        else:
            lo = rng.randrange(k)
            hi = rng.randrange(k)
            pairs[c] = (lo, hi)
            pair_modes[c] = "random_pairs"

    non_q = 0
    total = len(neighborhoods)
    denom = max(1, 2 * r)
    for (center, outer_sum), combos in by_center_outer.items():
        lo, hi = pairs[center]
        avg = outer_sum / denom
        val = hi if avg >= theta[center] else lo
        if val != qstate:
            non_q += len(combos)
        for nb in combos:
            values[index_map[nb]] = val
    lam = non_q / total if total else 0.0
    table = DenseRuleTable(k, r, values=values, typecode=typecode)
    return table, lam, qstate, {
        "theta": theta,
        "pair_modes": pair_modes,
        "theta_range": [0.25 * (k - 1), 0.75 * (k - 1)],
    }


def rule_table_linear_mod_k(
    k: int,
    r: int,
    rng: random.Random,
    sparsity: int = 2,
    bias_prob: float = 0.3,
) -> Tuple[DenseRuleTable, float, int, Dict[str, object]]:
    """Affine linear rule modulo k with sparse coefficients."""
    values, neighborhoods, _, _, typecode = _empty_values(k, r, fill=0)
    width = 2 * r + 1
    idxs = list(range(width))
    active_count = min(max(1, sparsity), width)
    active = rng.sample(idxs, k=active_count)
    alpha = [0] * width
    for idx in active:
        alpha[idx] = rng.randrange(k)
    if all(alpha[idx] == 0 for idx in range(width) if idx != r):
        alpha[r] = (alpha[r] + 1) % k
    bias = rng.randrange(k) if rng.random() < bias_prob else 0
    non_q = 0
    for idx, nb in enumerate(neighborhoods):
        val = (sum(alpha[j] * nb[j] for j in range(width)) + bias) % k
        values[idx] = val
        if val != 0:
            non_q += 1
    lam = non_q / len(neighborhoods) if neighborhoods else 0.0
    table = DenseRuleTable(k, r, values=values, typecode=typecode)
    return table, lam, 0, {
        "sparsity": int(active_count),
        "active_indices": active,
        "coefficients": alpha,
        "bias": int(bias),
    }


def rule_table_cyclic_excitable(
    k: int,
    r: int,
    rng: random.Random,
    trigger_state: Optional[int] = None,
    min_triggers: int = 1,
) -> Tuple[DenseRuleTable, float, int, Dict[str, int]]:
    """Simple cyclic excitable rule family."""
    values, neighborhoods, _, _, typecode = _empty_values(k, r, fill=0)
    trigger_state = trigger_state if trigger_state is not None else 1
    non_q = 0
    for idx, nb in enumerate(neighborhoods):
        center = nb[r]
        neighbours = nb[:r] + nb[r + 1 :]
        triggers = sum(
            1 for v in neighbours if (v == trigger_state if k >= 3 else v != 0)
        )
        if center == 0 and triggers >= min_triggers:
            val = 1 % k
        elif center != 0:
            val = (center + 1) % k
        else:
            val = 0
        values[idx] = val
        if val != 0:
            non_q += 1
    lam = non_q / len(neighborhoods) if neighborhoods else 0.0
    table = DenseRuleTable(k, r, values=values, typecode=typecode)
    return table, lam, 0, {
        "trigger_state": int(trigger_state),
        "min_triggers": int(min_triggers),
    }


def rule_table_permuted_totalistic(
    k: int,
    r: int,
    rng: random.Random,
) -> Tuple[DenseRuleTable, float, int, Dict[str, List[int]]]:
    """Totalistic outputs followed by a random permutation of states."""
    values, neighborhoods, _, _, typecode = _empty_values(k, r, fill=0)
    arity = 2 * r + 1
    max_sum = (k - 1) * arity
    sum_lookup = [rng.randrange(k) for _ in range(max_sum + 1)]
    perm = list(range(k))
    rng.shuffle(perm)
    non_q = 0
    for idx, nb in enumerate(neighborhoods):
        val = perm[sum_lookup[sum(nb)]]
        values[idx] = val
        if val != 0:
            non_q += 1
    lam = non_q / len(neighborhoods) if neighborhoods else 0.0
    table = DenseRuleTable(k, r, values=values, typecode=typecode)
    return table, lam, 0, {
        "permutation": perm,
    }


__all__ = [
    "rule_table_random_lambda",
    "rule_table_totalistic",
    "rule_table_outer_totalistic",
    "rule_table_outer_inner_totalistic",
    "rule_table_threshold",
    "rule_table_linear_mod_k",
    "rule_table_cyclic_excitable",
    "rule_table_permuted_totalistic",
]
