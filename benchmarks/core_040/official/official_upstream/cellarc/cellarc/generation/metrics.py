"""Utility metrics for analysing cellular automata trajectories."""

from __future__ import annotations

import math
from collections import Counter
from typing import Sequence

import numpy as np


def _sequence_to_string(sequence: Sequence[int] | np.ndarray) -> str:
    return "".join(str(int(x)) for x in sequence)


def shannon_entropy(sequence: Sequence[int] | np.ndarray) -> float:
    """Shannon entropy, mirroring our original implementation semantics."""
    string = _sequence_to_string(sequence)
    if not string:
        return 0.0
    counts = Counter(string)
    total = float(len(string))
    entropy = -sum((count / total) * math.log(count / total, 2.0) for count in counts.values())
    return float(entropy + 0.0)


def joint_shannon_entropy(
    sequence_x: Sequence[int] | np.ndarray,
    sequence_y: Sequence[int] | np.ndarray,
) -> float:
    """Joint Shannon entropy between two sequences."""
    string_x = _sequence_to_string(sequence_x)
    string_y = _sequence_to_string(sequence_y)
    if len(string_x) != len(string_y):
        raise ValueError("Sequences must be of equal length.")
    if not string_x:
        return 0.0
    counts = Counter(zip(string_x, string_y))
    total = float(len(string_x))
    entropy = -sum((count / total) * math.log(count / total, 2.0) for count in counts.values())
    return float(entropy)


def mutual_information(
    sequence_x: Sequence[int] | np.ndarray,
    sequence_y: Sequence[int] | np.ndarray,
) -> float:
    """Mutual information between two sequences."""
    return float(
        shannon_entropy(sequence_x)
        + shannon_entropy(sequence_y)
        - joint_shannon_entropy(sequence_x, sequence_y)
    )


def average_cell_entropy(space_time: np.ndarray) -> float:
    """Average Shannon entropy per cell over time."""
    arr = np.asarray(space_time)
    if arr.ndim != 2:
        raise ValueError("Expected a 2-D space-time diagram.")
    entropies = [shannon_entropy(arr[:, idx]) for idx in range(arr.shape[1])]
    return float(np.mean(entropies))


def average_mutual_information(space_time: np.ndarray, *, temporal_distance: int = 1) -> float:
    """Average mutual information between successive states of each cell."""
    if temporal_distance <= 0:
        raise ValueError("Temporal distance must be positive.")
    arr = np.asarray(space_time)
    if arr.ndim != 2:
        raise ValueError("Expected a 2-D space-time diagram.")
    if temporal_distance >= arr.shape[0]:
        raise ValueError("Temporal distance must be less than the number of time steps.")
    mi_values = [
        mutual_information(arr[:-temporal_distance, idx], arr[temporal_distance:, idx])
        for idx in range(arr.shape[1])
    ]
    return float(np.mean(mi_values))


__all__ = [
    "shannon_entropy",
    "joint_shannon_entropy",
    "mutual_information",
    "average_cell_entropy",
    "average_mutual_information",
]
