"""Episode sampling logic for the cellular automata ARC benchmark."""

from __future__ import annotations

import math
import random
from typing import Dict, List, Optional, Tuple

from .cax_runner import AutomatonRunner

from ..utils import choose_r_t_for_W, de_bruijn_cycle
from .constants import SCHEMA_VERSION
from .fingerprints import induced_tstep_fingerprint, rule_fingerprint
from .helpers import ring_slice
from .metrics import average_cell_entropy, average_mutual_information
from .morphology import quick_morphology_features
from .rules import (
    rule_table_cyclic_excitable,
    rule_table_linear_mod_k,
    rule_table_outer_inner_totalistic,
    rule_table_outer_totalistic,
    rule_table_permuted_totalistic,
    rule_table_random_lambda,
    rule_table_threshold,
    rule_table_totalistic,
)
from .serialization import serialize_rule_table


def lambda_bin(lam: float) -> str:
    return "ordered" if lam < 0.20 else "edge" if lam < 0.50 else "chaotic"


def entropy_bin(H: float) -> str:
    return "low" if H < 0.25 else "mid" if H < 0.6 else "high"


def sample_task(
    rng: random.Random,
    *,
    k_range=(2, 6),
    max_radius=3,
    max_steps=5,
    train_examples=4,
    target_avg_train_len=48,
    family_mix: Optional[Dict[str, float]] = None,
    lambda_for_random: Tuple[float, float] = (0.2, 0.7),
    unique_by: str = "tstep",
    complexity_rollout=(30, 256),
    coverage_fraction: float = 1.0,
    coverage_mode: str = "chunked",
    compute_complexity: bool = True,
    annotate_morphology: bool = True,
    query_within_coverage: bool = False,
    construction: str = "cycle",
    unroll_tau_max: int = 24,
    schema_version: str = SCHEMA_VERSION,
    dataset_version: Optional[str] = None,
    include_rule_table: bool = True,
    episode_seed: Optional[int] = None,
):
    """Generate a single training episode with metadata and fingerprints."""
    if episode_seed is None:
        episode_seed = rng.randrange(1 << 62)
    episode_rng = random.Random(episode_seed)

    k_lo, k_hi = k_range
    alphabet_choices = list(range(k_lo, k_hi + 1))
    weights = [1.0 / (idx + 1) for idx in range(len(alphabet_choices))]
    k = episode_rng.choices(alphabet_choices, weights=weights, k=1)[0]

    total_budget = max(1, train_examples * target_avg_train_len)
    W_by_budget = int(math.floor(math.log(max(1, total_budget), k))) if k >= 2 else 1
    if W_by_budget % 2 == 0:
        W_by_budget -= 1
    W_by_budget = max(W_by_budget, 3)
    W_cap = 2 * max_radius * max_steps + 1
    W = min(W_by_budget, W_cap)

    while True:
        try:
            r, t = choose_r_t_for_W(
                W,
                max_radius=max_radius,
                max_steps=max_steps,
                strategy="uniform",
                rng=episode_rng,
            )
            break
        except ValueError:
            W -= 2
            if W < 3:
                raise RuntimeError(
                    "Failed to find feasible (r,t) for the given budget/caps."
                )

    construction = construction.lower()
    if construction not in {"cycle", "unrolled", "hybrid"}:
        raise ValueError("construction must be 'cycle', 'unrolled', or 'hybrid'.")

    fam_mix = family_mix or {
        "random": 0.35,
        "totalistic": 0.15,
        "outer_totalistic": 0.15,
        "outer_inner_totalistic": 0.10,
        "threshold": 0.10,
        "linear_mod_k": 0.10,
        "cyclic_excitable": 0.05,
        "permuted_totalistic": 0.0,
    }
    items = [(name, w) for name, w in fam_mix.items() if w > 0]
    total_w = sum(w for _, w in items)
    u = episode_rng.random() * total_w
    acc = 0.0
    family = items[-1][0]
    for name, weight in items:
        acc += weight
        if u <= acc:
            family = name
            break

    def _unwrap(result):
        if isinstance(result, tuple) and len(result) == 4:
            table, lam_actual, qstate, extra = result
        else:
            table, lam_actual, qstate = result
            extra = {}
        return table, lam_actual, qstate, extra

    family_params: Dict[str, object] = {}

    if family == "random":
        lam_target = episode_rng.uniform(*lambda_for_random)
        table, lam_actual, qstate = rule_table_random_lambda(
            k, r, episode_rng, lambda_val=lam_target, quiescent_state=0
        )
        family_params = {"lambda_target": float(lam_target), "quiescent_state": 0}
    elif family == "totalistic":
        table, lam_actual, qstate = rule_table_totalistic(k, r, episode_rng)
    elif family == "outer_totalistic":
        lam_target = episode_rng.uniform(*lambda_for_random)
        table, lam_actual, qstate, extra = _unwrap(
            rule_table_outer_totalistic(
                k, r, episode_rng, lambda_val=lam_target, qstate=0
            )
        )
        family_params = extra
    elif family == "outer_inner_totalistic":
        lam_target = episode_rng.uniform(*lambda_for_random)
        table, lam_actual, qstate, extra = _unwrap(
            rule_table_outer_inner_totalistic(
                k, r, episode_rng, lambda_val=lam_target, qstate=0
            )
        )
        family_params = extra
    elif family == "threshold":
        table, lam_actual, qstate, extra = _unwrap(
            rule_table_threshold(k, r, episode_rng, qstate=0)
        )
        family_params = extra
    elif family == "linear_mod_k":
        sparsity_choice = episode_rng.choice([1, 2, 3])
        table, lam_actual, qstate, extra = _unwrap(
            rule_table_linear_mod_k(
                k, r, episode_rng, sparsity=sparsity_choice, bias_prob=0.3
            )
        )
        family_params = extra
    elif family == "cyclic_excitable":
        trig = 1 if k >= 3 else 1
        min_trig = 1 if r == 1 else episode_rng.choice([1, 2])
        table, lam_actual, qstate, extra = _unwrap(
            rule_table_cyclic_excitable(
                k, r, episode_rng, trigger_state=trig, min_triggers=min_trig
            )
        )
        family_params = extra
    elif family == "permuted_totalistic":
        table, lam_actual, qstate, extra = _unwrap(
            rule_table_permuted_totalistic(k, r, episode_rng)
        )
        family_params = extra
    else:
        raise ValueError(f"Unknown family: {family}")

    cycle = de_bruijn_cycle(k, W)
    length = len(cycle)
    half = (W - 1) // 2

    runner = AutomatonRunner(
        alphabet_size=k,
        radius=r,
        table=table,
        rng_seed=episode_rng.randrange(1 << 30),
    )
    if construction == "cycle":
        S_t_row = runner.evolve(cycle, timesteps=t + 1).tolist()
        space_time: Optional[List[List[int]]] = None
        tau_max = 0
    else:
        tau_max = max(0, min(unroll_tau_max, 256 - t))
        history = runner.evolve(
            cycle,
            timesteps=tau_max + t + 1,
            return_history=True,
        )
        space_time = history.tolist()
        S_t_row = list(space_time[t])

    episode_count = max(1, train_examples)
    if query_within_coverage:
        seg_len = max(W, math.ceil(length / episode_count))
        lengths = [seg_len] * episode_count
        offset = episode_rng.randrange(length)
        starts: List[int] = []
        acc = offset
        for _ in lengths:
            starts.append(acc % length)
            acc += seg_len
        windows_revealed = min(length, seg_len * episode_count)
        coverage_fraction_effective = min(1.0, windows_revealed / length)
        coverage_mode_effective = "full_cycle_partition"
    else:
        if not (0 < coverage_fraction <= 1.0):
            raise ValueError("coverage_fraction must lie in (0, 1].")
        target_windows = int(round(coverage_fraction * length))
        target_windows = max(W, episode_count, target_windows)
        target_windows = min(length, target_windows)
        seg_len = max(W, math.ceil(target_windows / episode_count))
        lengths = [seg_len] * episode_count

        if coverage_mode == "uniform":
            starts = [int((i * length) / episode_count) % length for i in range(episode_count)]
            jitter = max(1, length // max(4 * episode_count, 1))
            starts = [(s + episode_rng.randrange(0, jitter)) % length for s in starts]
        elif coverage_mode == "chunked":
            starts = [episode_rng.randrange(0, length) for _ in range(episode_count)]
        else:
            raise ValueError("coverage_mode must be 'chunked' or 'uniform'")

        windows_revealed = min(length, seg_len * episode_count)
        coverage_fraction_effective = float(min(1.0, windows_revealed / length))
        coverage_mode_effective = coverage_mode

    train_pairs: List[Tuple[List[int], List[int]]] = []
    train_spans: List[Dict[str, int]] = []
    if construction == "cycle":
        taus = [0] * len(lengths)
    elif construction == "unrolled":
        assert space_time is not None
        max_tau_choice = tau_max
        taus = [
            episode_rng.randrange(0, max_tau_choice + 1) for _ in lengths
        ]
    else:  # construction == "hybrid"
        assert space_time is not None
        max_tau_choice = tau_max
        taus = []
        for idx, _ in enumerate(lengths):
            if idx == 0 or max_tau_choice < 1:
                taus.append(0)
            else:
                taus.append(episode_rng.randrange(1, max_tau_choice + 1))

    for start, seg_len, tau in zip(starts, lengths, taus):
        if construction == "cycle":
            x = ring_slice(cycle, start - half, seg_len + 2 * half)
            y = ring_slice(S_t_row, start - half, seg_len + 2 * half)
        else:
            assert space_time is not None
            S_tau = space_time[tau]
            S_tau_t = space_time[tau + t]
            x = ring_slice(S_tau, start - half, seg_len + 2 * half)
            y = ring_slice(S_tau_t, start - half, seg_len + 2 * half)
        train_pairs.append((x, y))
        train_spans.append(
            {"start": int(start), "length": int(seg_len), "time": int(tau)}
        )

    query_span: Optional[Dict[str, int]] = None
    if lengths:
        full_width = lengths[0] + 2 * half
    else:
        full_width = W + 2 * half
    q_len = full_width
    if construction == "cycle":
        query = [episode_rng.randrange(k) for _ in range(q_len)]
        solution = runner.evolve(query, timesteps=t + 1).tolist()
        query_time = 0
    else:
        assert space_time is not None
        query_time = episode_rng.choice(taus) if taus else 0
        S_tau = space_time[query_time]
        q_start = episode_rng.randrange(0, len(S_tau))
        query = ring_slice(S_tau, q_start, q_len)
        S_tau_t = space_time[query_time + t]
        solution = ring_slice(S_tau_t, q_start, q_len)
        core_length = lengths[0] if lengths else W
        query_span = {
            "start": int(q_start),
            "length": int(core_length),
            "time": int(query_time),
        }

    def _observed_windows_count(window: int, pairs: List[Tuple[List[int], List[int]]]) -> int:
        half_w = window // 2
        seen = set()
        for x, _ in pairs:
            if len(x) < window:
                continue
            for idx in range(half_w, len(x) - half_w):
                seen.add(tuple(x[idx - half_w : idx + half_w + 1]))
        return len(seen)

    observed_windows = _observed_windows_count(W, train_pairs)
    observed_fraction = observed_windows / max(1, k ** W)

    width, horizon = complexity_rollout
    if compute_complexity:
        random_init = [episode_rng.randrange(k) for _ in range(width)]
        ca_roll = runner.evolve(random_init, timesteps=horizon, return_history=True)
        avg_cell_entropy = float(average_cell_entropy(ca_roll))
        ami_1 = float(average_mutual_information(ca_roll, temporal_distance=1))
    else:
        avg_cell_entropy = None
        ami_1 = None

    morphology = (
        quick_morphology_features(
            table,
            k,
            r,
            t,
            width=width,
            horizon=horizon,
            rng=episode_rng,
        )
        if annotate_morphology
        else None
    )

    if unique_by == "tstep":
        fp = induced_tstep_fingerprint(table, k, r, t)
    elif unique_by == "rule":
        fp = rule_fingerprint(table, k, r)
    else:
        raise ValueError("unique_by must be 'rule' or 'tstep'")

    probe_fp = rule_fingerprint(table, k, r)

    if include_rule_table:
        rule_table_payload = serialize_rule_table(
            table, alphabet_size=k, radius=r, quiescent_state=qstate
        )
    else:
        rule_table_payload = None

    record = {
        "train": [{"input": x, "output": y} for x, y in train_pairs],
        "query": query,
        "solution": solution,
        "meta": {
            "schema_version": schema_version,
            "dataset_version": dataset_version,
            "alphabet_size": k,
            "radius": r,
            "steps": t,
            "window": W,
            "windows_total": k ** W,
            "train_context": half,
            "train_core_lengths": lengths,
            "train_spans": train_spans,
            **({"query_span": query_span} if query_span is not None else {}),
            "construction": construction,
            "family": family,
            "family_params": family_params,
            "lambda": float(lam_actual),
            "lambda_bin": lambda_bin(lam_actual),
            "avg_cell_entropy": avg_cell_entropy,
            "entropy_bin": entropy_bin(avg_cell_entropy)
            if avg_cell_entropy is not None
            else None,
            "avg_mutual_information_d1": ami_1,
            "fingerprint": fp,
            "probe_fingerprint": probe_fp,
            "unique_by": unique_by,
            "wrap": True,
            "episode_seed": int(episode_seed),
            "coverage": {
                "scheme": "de_bruijn_subcover",
                "fraction": coverage_fraction_effective,
                "windows": int(windows_revealed),
                "segments": int(len(lengths)),
                "mode": coverage_mode_effective,
                "query_within_coverage": bool(query_within_coverage),
                "cycle_length": int(length),
                "observed_windows": int(observed_windows),
                "observed_fraction": float(observed_fraction),
            },
            "morphology": morphology,
            "query_time": int(query_time),
        },
    }
    if include_rule_table:
        record["rule_table"] = rule_table_payload
    return record


__all__ = ["entropy_bin", "lambda_bin", "sample_task"]
