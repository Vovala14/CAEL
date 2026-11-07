"""Reconstruction utilities for recovering rule tables from metadata."""

from __future__ import annotations

import random
from typing import Dict, Optional, Tuple

from cellarc.utils import choose_r_t_for_W

from .fingerprints import induced_tstep_fingerprint, rule_fingerprint
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

DEFAULT_LAMBDA_RANGE: Tuple[float, float] = (0.2, 0.7)

POOL_V1_CONFIG = {
    "k_range": (2, 6),
    "max_radius": 3,
    "max_steps": 5,
    "query_within_coverage": False,
    "unroll_tau_max": 32,
}


def infer_dataset_config(meta: Dict[str, object]) -> Optional[Dict[str, object]]:
    """Return reconstruction hyperparameters for known dataset versions."""
    dataset_version = meta.get("dataset_version")
    if dataset_version == "pool_v1":
        return POOL_V1_CONFIG
    return None


def reconstruct_rule_table_payload(
    meta: Dict[str, object],
    *,
    config: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """Rebuild the serialized rule table payload from episode metadata."""
    if config is None:
        config = infer_dataset_config(meta)
    if config is None:
        raise ValueError(
            f"No reconstruction config available for dataset_version={meta.get('dataset_version')!r}."
        )

    episode_seed = meta.get("episode_seed")
    if episode_seed is None:
        raise ValueError("Episode metadata missing 'episode_seed'; cannot reconstruct rule table.")

    k_lo, k_hi = config["k_range"]
    max_radius = config["max_radius"]
    max_steps = config["max_steps"]
    lambda_for_random = config.get("lambda_for_random", DEFAULT_LAMBDA_RANGE)

    alphabet_size = int(meta.get("alphabet_size"))
    radius = int(meta.get("radius"))
    steps = int(meta.get("steps"))
    window = int(meta.get("window"))
    family = meta.get("family")
    probe_fp_expected = meta.get("probe_fingerprint")

    episode_rng = random.Random(int(episode_seed))

    alphabet_choices = list(range(int(k_lo), int(k_hi) + 1))
    weights = [1.0 / (idx + 1) for idx in range(len(alphabet_choices))]
    k_draw = episode_rng.choices(alphabet_choices, weights=weights, k=1)[0]
    if int(k_draw) != alphabet_size:
        raise ValueError(
            f"alphabet_size mismatch during reconstruction (expected {alphabet_size}, drew {k_draw}). "
            "Update reconstruction configuration."
        )

    r_draw, t_draw = choose_r_t_for_W(
        window,
        max_radius=max_radius,
        max_steps=max_steps,
        strategy="uniform",
        rng=episode_rng,
    )
    if int(r_draw) != radius or int(t_draw) != steps:
        raise ValueError(
            "radius/steps mismatch during reconstruction; adjust reconstruction caps."
        )

    episode_rng.random()  # consume the draw used for family selection

    def _unwrap(result):
        if isinstance(result, tuple) and len(result) == 4:
            table, lam_actual, qstate, extra = result
        else:
            table, lam_actual, qstate = result
            extra = {}
        return table, lam_actual, qstate, extra

    if family == "random":
        lam_target = episode_rng.uniform(*lambda_for_random)
        table, lam_actual, qstate = rule_table_random_lambda(
            alphabet_size, radius, episode_rng, lambda_val=lam_target, quiescent_state=0
        )
    elif family == "totalistic":
        table, lam_actual, qstate = rule_table_totalistic(alphabet_size, radius, episode_rng)
    elif family == "outer_totalistic":
        lam_target = episode_rng.uniform(*lambda_for_random)
        table, lam_actual, qstate, _ = _unwrap(
            rule_table_outer_totalistic(
                alphabet_size, radius, episode_rng, lambda_val=lam_target, qstate=0
            )
        )
    elif family == "outer_inner_totalistic":
        lam_target = episode_rng.uniform(*lambda_for_random)
        table, lam_actual, qstate, _ = _unwrap(
            rule_table_outer_inner_totalistic(
                alphabet_size, radius, episode_rng, lambda_val=lam_target, qstate=0
            )
        )
    elif family == "threshold":
        table, lam_actual, qstate, _ = _unwrap(
            rule_table_threshold(alphabet_size, radius, episode_rng, qstate=0)
        )
    elif family == "linear_mod_k":
        sparsity_choice = episode_rng.choice([1, 2, 3])
        table, lam_actual, qstate, _ = _unwrap(
            rule_table_linear_mod_k(
                alphabet_size, radius, episode_rng, sparsity=sparsity_choice, bias_prob=0.3
            )
        )
    elif family == "cyclic_excitable":
        trig = 1 if alphabet_size >= 3 else 1
        min_trig = 1 if radius == 1 else episode_rng.choice([1, 2])
        table, lam_actual, qstate, _ = _unwrap(
            rule_table_cyclic_excitable(
                alphabet_size, radius, episode_rng, trigger_state=trig, min_triggers=min_trig
            )
        )
    elif family == "permuted_totalistic":
        table, lam_actual, qstate, _ = _unwrap(
            rule_table_permuted_totalistic(alphabet_size, radius, episode_rng)
        )
    else:
        raise ValueError(f"Unknown family '{family}' encountered; cannot reconstruct rule table.")

    fp_actual = rule_fingerprint(table, alphabet_size, radius)
    if probe_fp_expected and fp_actual != probe_fp_expected:
        raise ValueError("Reconstructed rule table fingerprint does not match metadata.")

    tstep_fp_expected = meta.get("fingerprint")
    if tstep_fp_expected:
        tstep_fp_actual = induced_tstep_fingerprint(table, alphabet_size, radius, steps)
        if tstep_fp_actual != tstep_fp_expected:
            raise ValueError("Reconstructed CA t-step fingerprint does not match metadata.")

    payload = serialize_rule_table(
        table,
        alphabet_size=alphabet_size,
        radius=radius,
        quiescent_state=qstate,
    )
    return payload


__all__ = [
    "DEFAULT_LAMBDA_RANGE",
    "POOL_V1_CONFIG",
    "infer_dataset_config",
    "reconstruct_rule_table_payload",
]
