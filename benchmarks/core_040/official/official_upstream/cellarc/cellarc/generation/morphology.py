"""Lightweight morphology metrics for generated cellular automata."""

from __future__ import annotations

import math
import random
from typing import Dict, List, Optional, Union

import numpy as np

from .cax_runner import evolve_rule_table


def quick_morphology_features(
    table,
    k: int,
    r: int,
    t: int,
    *,
    width: int = 30,
    horizon: int = 256,
    rng: Optional[random.Random] = None,
) -> Dict[str, Union[bool, float, int]]:
    """
    Lightweight CA morphology summary for annotation: absorbing behaviour,
    density stats, temporal period estimate, spatial correlation length,
    and a Derrida-like sensitivity proxy.
    """
    rng = rng or random

    seed = rng.randrange(1 << 30)
    rng_np = np.random.default_rng(seed)
    init = rng_np.integers(low=0, high=k, size=width, dtype=int)
    steps = max(t + 1, horizon)
    A = evolve_rule_table(
        table,
        init,
        timesteps=steps,
        alphabet_size=k,
        radius=r,
        return_history=True,
        rng_seed=seed,
    ).astype(int)
    if A.size == 0:
        return {
            "absorbing": True,
            "density_mean": 0.0,
            "density_var": 0.0,
            "period_estimate": 1,
            "spatial_corr_length": 0,
            "derrida_like": 0.0,
        }

    last = A[-1]
    tail = A[-min(10, len(A)) :]
    absorbing = bool(np.all(tail == tail[-1]))

    dens = A.mean(axis=1).astype(float)
    density_mean = float(dens.mean())
    density_var = float(dens.var())

    max_lag = min(128, len(A) - 1)
    period_estimate = 1
    if max_lag >= 1:
        base = A[-1].astype(float)
        base_c = base - base.mean()
        cors: List[float] = []
        for lag in range(1, max_lag + 1):
            other = A[-1 - lag].astype(float)
            other_c = other - other.mean()
            denom = math.sqrt(
                float(np.dot(base_c, base_c)) * float(np.dot(other_c, other_c))
            )
            if denom <= 0:
                cors.append(0.0)
            else:
                cors.append(float(np.clip(np.dot(base_c, other_c) / denom, -1.0, 1.0)))
        if cors:
            period_estimate = int(1 + int(np.argmax(cors)))

    last_centered = last.astype(float) - float(last.mean())
    if np.allclose(last_centered, 0):
        spatial_corr_length = 0
    else:
        ac = np.correlate(last_centered, last_centered, mode="full")
        ac = ac[len(ac) // 2 :]
        max_ac = ac[0] if ac[0] != 0 else 1.0
        ac = ac / max_ac
        below = np.where(ac < 1 / math.e)[0]
        spatial_corr_length = int(below[0]) if below.size else int(len(ac))

    perturb_steps = 50
    last_row = last.copy()
    perturbed = last_row.copy()
    flip_count = max(1, len(perturbed) // 100)
    rng_np = np.random.default_rng(seed + 1)
    flip_indices = rng_np.choice(len(perturbed), size=flip_count, replace=False)
    perturbed[flip_indices] = (perturbed[flip_indices] + 1) % k
    evo1 = evolve_rule_table(
        table,
        last_row,
        timesteps=perturb_steps,
        alphabet_size=k,
        radius=r,
        return_history=True,
        rng_seed=seed + 2,
    )
    evo2 = evolve_rule_table(
        table,
        perturbed,
        timesteps=perturb_steps,
        alphabet_size=k,
        radius=r,
        return_history=True,
        rng_seed=seed + 3,
    )
    diffs = [float(np.mean(frame1 != frame2)) for frame1, frame2 in zip(evo1, evo2)]
    if len(diffs) <= 1:
        derrida_like = 0.0
    else:
        derrida_like = float((diffs[-1] - diffs[0]) / max(1, len(diffs) - 1))

    return {
        "absorbing": absorbing,
        "density_mean": density_mean,
        "density_var": density_var,
        "period_estimate": period_estimate,
        "spatial_corr_length": spatial_corr_length,
        "derrida_like": derrida_like,
    }


__all__ = ["quick_morphology_features"]
