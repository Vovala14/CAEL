"""Utilities for evolving one-dimensional cellular automata with CAX."""

from __future__ import annotations

import contextlib
import os
import warnings
from dataclasses import dataclass
from typing import Iterator, Mapping, Sequence, Tuple, Union

import jax
import jax.numpy as jnp
import numpy as np
from flax import nnx

try:  # JaxRuntimeError only exists on newer JAX releases.
    from jax.errors import JaxRuntimeError  # type: ignore
except ImportError:  # pragma: no cover - fallback for older wheels
    class JaxRuntimeError(RuntimeError):
        """Fallback when `jax.errors.JaxRuntimeError` is missing."""

        pass

from cax.core import ComplexSystem, Input, State
from cax.core.perceive import ConvPerceive
from cax.core.update import Update

from .rule_table import DenseRuleTable, ensure_dense_rule_table

def _env_flag(name: str, *, default: bool) -> bool:
    """Parse an environment boolean flag with a sensible default."""
    value = os.environ.get(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


_FORCE_CPU = _env_flag("CELLARC_FORCE_CPU", default=True)
_GPU_PROBE_FAILED = False
_CUDA_INVALID_IMAGE_MARKERS = (
    "CUDA_ERROR_INVALID_IMAGE",
    "Failed to load in-memory CUBIN",
)


@contextlib.contextmanager
def _cpu_device_scope() -> Iterator[None]:
    """Temporarily pin JAX array placement to the first CPU device."""
    cpu_devices = jax.devices("cpu")
    if not cpu_devices:
        yield
        return
    with jax.default_device(cpu_devices[0]):
        yield


def _is_cuda_invalid_image(error: Exception) -> bool:
    """Return True if the error looks like a CUDA invalid image failure."""
    msg = str(error)
    return any(marker in msg for marker in _CUDA_INVALID_IMAGE_MARKERS)


def _to_column_state(state: Sequence[int] | np.ndarray | jnp.ndarray) -> jnp.ndarray:
    """Normalise input states to a (width, 1) column vector."""
    arr = np.asarray(state, dtype=np.int32).reshape(-1, 1)
    return jnp.asarray(arr, dtype=jnp.float32)


def _transition_arrays(
    table: DenseRuleTable,
    *,
    alphabet_size: int,
    radius: int,
) -> tuple[jnp.ndarray, jnp.ndarray]:
    """Return transition lookup and base powers for the provided rule table."""
    arity = 2 * radius + 1
    transitions = np.asarray(table.values_view(), dtype=np.int32)
    base_pows = np.asarray(
        [alphabet_size ** (arity - 1 - i) for i in range(arity)], dtype=np.int32
    )
    return jnp.asarray(transitions, dtype=jnp.float32), jnp.asarray(base_pows)


class NeighborhoodPerceive(ConvPerceive):
    """Extract radius-r neighbourhoods via grouped convolutions."""

    def __init__(self, *, radius: int, rngs: nnx.Rngs):
        arity = 2 * radius + 1
        super().__init__(
            channel_size=1,
            perception_size=arity,
            kernel_size=(arity,),
            padding="CIRCULAR",
            feature_group_count=1,
            use_bias=False,
            activation_fn=None,
            rngs=rngs,
        )
        kernel = jnp.eye(arity, dtype=jnp.float32)[:, None, :]
        self.conv.kernel.value = kernel


class RuleTableUpdate(Update):
    """Apply a deterministic rule-table lookup to each neighbourhood."""

    def __init__(
        self,
        *,
        transitions: jnp.ndarray,
        base_pows: jnp.ndarray,
        alphabet_size: int,
    ):
        self.transitions = transitions
        self.base_pows = base_pows
        self.alphabet_size = alphabet_size

    def __call__(self, state: State, perception, input: Input | None = None) -> State:  # type: ignore[override]
        neighbourhood = jnp.clip(perception, 0.0, float(self.alphabet_size - 1))
        neighbourhood = jnp.rint(neighbourhood).astype(jnp.int32)
        indices = jnp.tensordot(neighbourhood, self.base_pows, axes=([-1], [0]))
        values = self.transitions[indices].astype(jnp.float32)
        return values[..., None]


class RuleTableAutomaton(ComplexSystem):
    """A one-dimensional cellular automaton driven by a rule table."""

    def __init__(
        self,
        *,
        radius: int,
        transitions: jnp.ndarray,
        base_pows: jnp.ndarray,
        alphabet_size: int,
        rngs: nnx.Rngs,
    ):
        self.perceive = NeighborhoodPerceive(radius=radius, rngs=rngs)
        self.update = RuleTableUpdate(
            transitions=transitions,
            base_pows=base_pows,
            alphabet_size=alphabet_size,
        )

    def _step(self, state: State, input: Input | None = None, *, sow: bool = False) -> State:  # type: ignore[override]
        perception = self.perceive(state)
        next_state = self.update(state, perception, input)
        if sow:
            self.sow(nnx.Intermediate, "state", next_state)
        return next_state

    def render(self, state: State) -> jnp.ndarray:  # type: ignore[override]
        return jnp.repeat(state, 3, axis=-1)


@dataclass
class AutomatonRunner:
    """Convenience wrapper around a deterministic rule-table automaton."""

    alphabet_size: int
    radius: int
    table: Union[DenseRuleTable, Mapping[Tuple[int, ...], int]]
    rng_seed: int = 0

    def __post_init__(self) -> None:
        dense_table = ensure_dense_rule_table(
            self.table,
            alphabet_size=self.alphabet_size,
            radius=self.radius,
        )
        self.table = dense_table

        def _construct() -> tuple[nnx.Rngs, RuleTableAutomaton]:
            transitions, base_pows = _transition_arrays(
                dense_table,
                alphabet_size=self.alphabet_size,
                radius=self.radius,
            )
            rngs = nnx.Rngs(self.rng_seed)
            automaton = RuleTableAutomaton(
                radius=self.radius,
                transitions=transitions,
                base_pows=base_pows,
                alphabet_size=self.alphabet_size,
                rngs=rngs,
            )
            return rngs, automaton

        global _GPU_PROBE_FAILED
        self._prefer_cpu = _FORCE_CPU or _GPU_PROBE_FAILED
        if self._prefer_cpu:
            with _cpu_device_scope():
                self._rngs, self._automaton = _construct()
            return

        try:
            self._rngs, self._automaton = _construct()
        except JaxRuntimeError as err:
            if not _is_cuda_invalid_image(err):
                raise
            _GPU_PROBE_FAILED = True
            self._prefer_cpu = True
            warnings.warn(
                "Falling back to CPU execution for AutomatonRunner due to CUDA kernel load failure. "
                "Set CELLARC_FORCE_CPU=0 to retry GPU execution.",
                RuntimeWarning,
                stacklevel=2,
            )
            with _cpu_device_scope():
                self._rngs, self._automaton = _construct()

    def evolve(
        self,
        init_state: Sequence[int] | np.ndarray | jnp.ndarray,
        *,
        timesteps: int,
        return_history: bool = False,
    ) -> np.ndarray:
        """Evolve the automaton for the requested number of time steps.

        Args:
            init_state: One-dimensional initial configuration.
            timesteps: Number of rows to return, matching the original backend semantics.
            return_history: Whether to return the full space-time diagram.

        Returns:
            The final state if ``return_history`` is False, otherwise an array
            containing the initial state followed by each successive step.
        """
        scope = _cpu_device_scope() if getattr(self, "_prefer_cpu", False) else contextlib.nullcontext()
        with scope:
            column_state = _to_column_state(init_state)
            steps = max(0, timesteps - 1)
            final_state = self._automaton(column_state, num_steps=steps, sow=return_history)
            if return_history:
                intermediates = nnx.pop(self._automaton, nnx.Intermediate)
                evolution = intermediates.state.value[0]
                trajectory = jnp.concatenate([column_state[None], evolution], axis=0)
                return np.asarray(jnp.squeeze(trajectory, axis=-1), dtype=np.int32)
            return np.asarray(jnp.squeeze(final_state, axis=-1), dtype=np.int32)


def evolve_rule_table(
    table: Union[DenseRuleTable, Mapping[Tuple[int, ...], int]],
    init_state: Sequence[int] | np.ndarray | jnp.ndarray,
    *,
    timesteps: int,
    alphabet_size: int,
    radius: int,
    return_history: bool = False,
    rng_seed: int = 0,
) -> np.ndarray:
    """Run a deterministic rule table using the CAX backend."""
    runner = AutomatonRunner(
        alphabet_size=alphabet_size,
        radius=radius,
        table=table,
        rng_seed=rng_seed,
    )
    return runner.evolve(init_state, timesteps=timesteps, return_history=return_history)


def random_state(width: int, *, alphabet_size: int, rng: np.random.Generator) -> np.ndarray:
    """Sample a random one-dimensional configuration."""
    return rng.integers(low=0, high=alphabet_size, size=width, dtype=np.int32)


__all__ = [
    "AutomatonRunner",
    "evolve_rule_table",
    "random_state",
]
