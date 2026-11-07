"""Signature extraction utilities for Cellular Automata episodes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

import numpy as np


@dataclass
class Signature:
    fingerprint: str
    features: Dict[str, float]
    meta: Dict[str, object]


def _nonzero_fraction(seq: Sequence[int]) -> float:
    if not seq:
        return 0.0
    arr = np.asarray(seq, dtype=int)
    return float(np.count_nonzero(arr) / arr.size)


def _mean_symbol(seq: Sequence[int]) -> float:
    if not seq:
        return 0.0
    arr = np.asarray(seq, dtype=float)
    return float(arr.mean())


def _std_symbol(seq: Sequence[int]) -> float:
    if not seq:
        return 0.0
    arr = np.asarray(seq, dtype=float)
    return float(arr.std())


def compute_signature(record: Mapping[str, object]) -> Signature:
    """Compute a lightweight signature vector summarizing an ARC CA episode."""

    meta = record.get("meta", {}) or {}
    coverage = meta.get("coverage", {}) or {}
    morphology = meta.get("morphology", {}) or {}

    fingerprint = str(meta.get("fingerprint", ""))
    alphabet = int(meta.get("alphabet_size", 0) or 0)
    window = int(meta.get("window", 0) or 0)
    lambda_val = float(meta.get("lambda", 0.0) or 0.0)
    entropy = float(meta.get("avg_cell_entropy", 0.0) or 0.0)
    rho = float(coverage.get("fraction", 0.0) or 0.0)

    train_pairs = record.get("train", []) or []
    train_lengths = [len(pair.get("input", [])) for pair in train_pairs]
    train_nonzero = [_nonzero_fraction(pair.get("output", [])) for pair in train_pairs]
    train_symbol_mean = [
        _mean_symbol(pair.get("output", [])) for pair in train_pairs if pair.get("output")
    ]
    train_symbol_std = [
        _std_symbol(pair.get("output", [])) for pair in train_pairs if pair.get("output")
    ]

    solution = record.get("solution", []) or []
    query = record.get("query", []) or []

    features: Dict[str, float] = {
        "lambda": lambda_val,
        "entropy": entropy,
        "rho": rho,
        "alphabet_size": float(alphabet),
        "window": float(window),
        "train_examples": float(len(train_pairs)),
        "train_length_mean": float(np.mean(train_lengths)) if train_lengths else 0.0,
        "train_length_std": float(np.std(train_lengths)) if train_lengths else 0.0,
        "train_density_mean": float(np.mean(train_nonzero)) if train_nonzero else 0.0,
        "train_density_std": float(np.std(train_nonzero)) if train_nonzero else 0.0,
        "train_symbol_mean": float(np.mean(train_symbol_mean)) if train_symbol_mean else 0.0,
        "train_symbol_std": float(np.mean(train_symbol_std)) if train_symbol_std else 0.0,
        "solution_density": _nonzero_fraction(solution),
        "solution_symbol_mean": _mean_symbol(solution),
        "solution_symbol_std": _std_symbol(solution),
        "query_length": float(len(query)),
        "coverage_windows": float(coverage.get("windows", 0) or 0),
        "coverage_segments": float((coverage.get("segments") or 0)),
        "absorb_flag": 1.0 if morphology.get("absorbing") else 0.0,
        "period_estimate": float(morphology.get("period_estimate", 0.0) or 0.0),
        "density_mean": float(morphology.get("density_mean", 0.0) or 0.0),
        "density_var": float(morphology.get("density_var", 0.0) or 0.0),
        "derrida_like": float(morphology.get("derrida_like", 0.0) or 0.0),
        "spatial_corr_length": float(morphology.get("spatial_corr_length", 0.0) or 0.0),
        "train_context": float(meta.get("train_context", 0) or 0),
    }

    meta_out = {
        "fingerprint": fingerprint,
        "lambda_bin": meta.get("lambda_bin"),
        "entropy_bin": meta.get("entropy_bin"),
        "family": meta.get("family"),
        "coverage_mode": coverage.get("mode"),
    }

    return Signature(
        fingerprint=fingerprint,
        features=features,
        meta=meta_out,
    )


def batch_signatures(records: Iterable[Mapping[str, object]]) -> List[Signature]:
    return [compute_signature(rec) for rec in records]


def signatures_as_rows(signatures: Sequence[Signature]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for sig in signatures:
        row: Dict[str, object] = {"fingerprint": sig.fingerprint}
        row.update(sig.features)
        row.update({f"meta_{k}": v for k, v in sig.meta.items()})
        rows.append(row)
    return rows
