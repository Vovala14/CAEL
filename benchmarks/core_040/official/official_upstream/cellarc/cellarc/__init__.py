"""cellarc package: tools for generating and solving few-shot cellular automata tasks."""

from importlib import import_module
from typing import Any, Dict, List

from ._version import __version__
from .data import (
    EpisodeDataLoader,
    EpisodeDataset,
    available_remote_datasets,
    available_remote_splits,
    augment_episode,
    download_benchmark,
    load_manifest,
    random_palette_mapping,
)
from .signatures import batch_signatures, compute_signature, signatures_as_rows
from .solver import LearnedLocalMap, learn_from_record, learn_local_map_from_pairs
from .utils import choose_r_t_for_W, de_bruijn_cycle, window_size

_OPTIONAL_EXPORTS: Dict[str, tuple[str, str]] = {
    "generate_dataset_jsonl": ("cellarc.generation.dataset", "generate_dataset_jsonl"),
    "sample_task": ("cellarc.generation.sampling", "sample_task"),
}

__all__ = [
    "EpisodeDataLoader",
    "EpisodeDataset",
    "available_remote_datasets",
    "available_remote_splits",
    "augment_episode",
    "download_benchmark",
    "load_manifest",
    "random_palette_mapping",
    "generate_dataset_jsonl",
    "sample_task",
    "LearnedLocalMap",
    "learn_from_record",
    "learn_local_map_from_pairs",
    "de_bruijn_cycle",
    "choose_r_t_for_W",
    "window_size",
    "compute_signature",
    "batch_signatures",
    "signatures_as_rows",
    "__version__",
]


def __getattr__(name: str) -> Any:
    optional = _OPTIONAL_EXPORTS.get(name)
    if optional:
        module_name, attr_name = optional
        try:
            module = import_module(module_name)
        except ImportError as exc:  # pragma: no cover - optional import guard
            raise ImportError(
                f"'{name}' requires optional simulation dependencies. "
                "Install with `pip install cellarc[all]` to enable generation utilities."
            ) from exc
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module 'cellarc' has no attribute '{name}'")


def __dir__() -> List[str]:
    return sorted(set(globals()) | set(_OPTIONAL_EXPORTS))
