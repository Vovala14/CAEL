"""Shared evaluation data structures and helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple, Union


@dataclass
class EpisodeRecord:
    """Container for a raw dataset record plus provenance metadata."""

    record: Dict[str, Any]
    source: Path
    manifest: Optional[Path] = None


@dataclass
class EpisodeData:
    """Normalized fields required for evaluation."""

    train_pairs: List[Tuple[List[int], List[int]]]
    query: List[int]
    solution: List[int]
    meta: Dict[str, Any]
    window: int
    wrap: bool
    alphabet_size: Optional[int]
    windows_total: Optional[int]


def _iter_jsonl(path: Path) -> Iterator[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def _load_meta_lookup(paths: Sequence[Path]) -> Dict[str, Dict[str, Any]]:
    lookup: Dict[str, Dict[str, Any]] = {}
    for meta_path in paths:
        if not meta_path.exists():
            continue
        with meta_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                fp = payload.get("fingerprint")
                if not fp:
                    continue
                lookup[str(fp)] = payload
    return lookup


def _merge_meta(record: Dict[str, Any], meta_lookup: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    if not meta_lookup:
        return record
    meta = record.get("meta", {}) or {}
    fp = meta.get("fingerprint")
    if not fp:
        return record
    extra = meta_lookup.get(str(fp))
    if not extra:
        return record
    merged_meta = dict(extra.get("meta", {}))
    merged_meta.update(meta)
    record["meta"] = merged_meta
    for key, value in extra.items():
        if key in {"fingerprint", "meta"}:
            continue
        record[key] = value
    return record


def _iter_manifest(path: Path) -> Iterator[EpisodeRecord]:
    with path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    base = path.parent
    artifacts = manifest.get("artifacts", {}) or {}
    jsonl_paths = artifacts.get("jsonl", [])
    if not jsonl_paths:
        raise ValueError(f"Manifest {path} does not contain any JSONL artifacts.")
    meta_paths = artifacts.get("meta_jsonl", []) or []
    meta_lookup = _load_meta_lookup(
        [Path(p) if Path(p).is_absolute() else base / p for p in meta_paths]
    )
    for rel in jsonl_paths:
        json_path = Path(rel)
        if not json_path.is_absolute():
            json_path = base / json_path
        for record in _iter_jsonl(json_path):
            merged = _merge_meta(record, meta_lookup)
            yield EpisodeRecord(record=merged, source=json_path, manifest=path)


def load_records(sources: Sequence[Union[str, Path]]) -> Iterator[EpisodeRecord]:
    """Yield dataset records from a collection of JSONL files or manifests."""

    if not sources:
        raise ValueError("No sources provided to load_records.")

    for src in sources:
        path = Path(src)
        if not path.exists():
            raise FileNotFoundError(f"Input source does not exist: {path}")
        if path.is_dir():
            raise ValueError(f"Directories are not supported as inputs: {path}")
        suffix = path.suffix.lower()
        if suffix == ".jsonl":
            meta_candidate = path.with_name(f"{path.stem}_meta.jsonl")
            meta_lookup = _load_meta_lookup([meta_candidate]) if meta_candidate.exists() else {}
            for record in _iter_jsonl(path):
                merged = _merge_meta(record, meta_lookup)
                yield EpisodeRecord(record=merged, source=path)
        elif suffix == ".json" and path.name.endswith("_manifest.json"):
            yield from _iter_manifest(path)
        else:
            raise ValueError(
                f"Unsupported input type for {path}. Expected *.jsonl or *_manifest.json"
            )


def prepare_episode(record: Dict[str, Any]) -> EpisodeData:
    """Normalize an ARC episode dictionary into a typed structure."""

    if not isinstance(record, dict):
        raise TypeError("Episode record must be a dictionary.")

    try:
        train_pairs = record["train"]
        query = record["query"]
        solution = record["solution"]
        meta = record["meta"]
    except KeyError as exc:  # pragma: no cover - defensive
        raise KeyError(f"Episode record missing required key: {exc}") from exc

    if not isinstance(train_pairs, list) or not train_pairs:
        raise ValueError("Episode train field must be a non-empty list.")

    window = int(meta["window"])
    wrap = bool(meta.get("wrap", True))
    alphabet_size = meta.get("alphabet_size")
    windows_total = meta.get("windows_total")

    normalized_pairs: List[Tuple[List[int], List[int]]] = []
    for pair in train_pairs:
        try:
            inp = list(pair["input"])
            out = list(pair["output"])
        except KeyError as exc:
            raise KeyError(f"Training pair missing key: {exc}") from exc
        if len(inp) != len(out):
            raise ValueError("Training input/output lengths must match.")
        normalized_pairs.append((inp, out))

    return EpisodeData(
        train_pairs=normalized_pairs,
        query=list(query),
        solution=list(solution),
        meta=dict(meta),
        window=window,
        wrap=wrap,
        alphabet_size=int(alphabet_size) if alphabet_size is not None else None,
        windows_total=int(windows_total) if windows_total is not None else None,
    )


def centered_window(seq: Sequence[int], index: int, width: int, wrap: bool) -> Tuple[int, ...]:
    """Return the centered window around index."""

    half = width // 2
    n = len(seq)
    window: List[int] = []
    for offset in range(-half, half + 1):
        j = index + offset
        if wrap:
            window.append(seq[j % n])
        else:
            if 0 <= j < n:
                window.append(seq[j])
            else:
                window.append(0)
    return tuple(window)


def training_windows(
    episode: EpisodeData,
    *,
    wrap_training: bool = True,
) -> Tuple[List[Tuple[int, ...]], List[int]]:
    """Extract sliding windows from training pairs along with targets."""

    W = episode.window
    half = W // 2
    windows: List[Tuple[int, ...]] = []
    targets: List[int] = []
    for inp, out in episode.train_pairs:
        n = len(inp)
        for i in range(half, n - half):
            win = centered_window(inp, i, W, wrap=True if wrap_training else episode.wrap)
            windows.append(win)
            targets.append(int(out[i]))
    if not windows:
        raise ValueError("No training windows extracted; check window size/context.")
    return windows, targets


def query_windows(episode: EpisodeData) -> List[Tuple[int, ...]]:
    """Return all centered windows for the query sequence."""

    return [
        centered_window(episode.query, i, episode.window, episode.wrap)
        for i in range(len(episode.query))
    ]


def compute_query_coverage(
    mapping: Dict[Tuple[int, ...], int],
    q_windows: Sequence[Tuple[int, ...]],
) -> float:
    """Compute the share of query windows observed during training."""

    if not q_windows:
        return 0.0
    observed = sum(1 for win in q_windows if win in mapping)
    return observed / len(q_windows)


def compute_accuracy(pred: Sequence[int], target: Sequence[int]) -> float:
    if len(pred) != len(target):
        raise ValueError("Prediction and target lengths must match for accuracy.")
    if not target:
        return 0.0
    correct = sum(1 for a, b in zip(pred, target) if a == b)
    return correct / len(target)


def infer_alphabet_size(episode: EpisodeData) -> int:
    """Infer the alphabet size from metadata or observed symbols."""

    if episode.alphabet_size is not None and episode.alphabet_size > 0:
        return episode.alphabet_size

    max_symbol = 0
    for seq in [episode.query, episode.solution]:
        if seq:
            max_symbol = max(max_symbol, max(seq))
    for inp, out in episode.train_pairs:
        if inp:
            max_symbol = max(max_symbol, max(inp))
        if out:
            max_symbol = max(max_symbol, max(out))
    return max_symbol + 1
