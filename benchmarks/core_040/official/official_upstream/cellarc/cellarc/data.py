"""Dataset loading, augmentation, and remote download utilities."""

from __future__ import annotations

import copy
import json
import os
import random
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Union

try:  # pragma: no cover - optional dependency
    from datasets import Dataset, load_dataset
except ImportError:  # pragma: no cover - fallback when datasets is not installed
    Dataset = None  # type: ignore
    load_dataset = None  # type: ignore

try:  # pragma: no cover - optional dependency
    from huggingface_hub import snapshot_download
except ImportError:  # pragma: no cover - fallback when hub is not installed
    snapshot_download = None  # type: ignore

Episode = Dict[str, object]

_PACKAGE_DIR = Path(__file__).resolve().parent
_CELLARC_SPLIT_FILES: Dict[str, Dict[str, List[str]]] = {
    "train": {
        "jsonl": ["data/train.jsonl"],
        "parquet": ["data/train.parquet"],
    },
    "train_100": {
        "jsonl": ["data/train_100.jsonl"],
        "parquet": ["data/train_100.parquet"],
    },
    "val": {
        "jsonl": ["data/val.jsonl"],
        "parquet": ["data/val.parquet"],
    },
    "val_100": {
        "jsonl": ["data/val_100.jsonl"],
        "parquet": ["data/val_100.parquet"],
    },
    "test_interpolation": {
        "jsonl": ["data/test_interpolation.jsonl"],
        "parquet": ["data/test_interpolation.parquet"],
    },
    "test_interpolation_100": {
        "jsonl": ["data/test_interpolation_100.jsonl"],
        "parquet": ["data/test_interpolation_100.parquet"],
    },
    "test_extrapolation": {
        "jsonl": ["data/test_extrapolation.jsonl"],
        "parquet": ["data/test_extrapolation.parquet"],
    },
    "test_extrapolation_100": {
        "jsonl": ["data/test_extrapolation_100.jsonl"],
        "parquet": ["data/test_extrapolation_100.parquet"],
    },
}

_REMOTE_BENCHMARKS: Dict[str, Dict[str, object]] = {
    "cellarc_100k": {
        "repo_id": "mireklzicar/cellarc_100k",
        "meta_repo_id": "mireklzicar/cellarc_100k_meta",
        "local_dir": "hf-cellarc_100k",
        "meta_dir": "hf-cellarc_100k_meta",
        "split_files": _CELLARC_SPLIT_FILES,
        "split_aliases": {
            "validation": "val",
            "test": "test_interpolation",
            "test_interp": "test_interpolation",
            "test_extrap": "test_extrapolation",
            # convenient subset aliases
            "train100": "train_100",
            "val100": "val_100",
            "test_interpolation_100": "test_interpolation_100",
            "test_interpolation100": "test_interpolation_100",
            "test_interp_100": "test_interpolation_100",
            "test_interp100": "test_interpolation_100",
            "test_extrapolation_100": "test_extrapolation_100",
            "test_extrapolation100": "test_extrapolation_100",
            "test_extrap_100": "test_extrapolation_100",
            "test_extrap100": "test_extrapolation_100",
        },
    },
}


def _default_cache_dir() -> Path:
    override = os.getenv("CELLARC_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".cache" / "cellarc"


def _resolve_split_spec(name: str, split: str) -> Dict[str, List[str]]:
    config = _REMOTE_BENCHMARKS.get(name)
    if not config:
        raise KeyError(f"Unknown remote benchmark: {name}")
    split_aliases: Dict[str, str] = config.get("split_aliases", {})  # type: ignore[assignment]
    split_files: Dict[str, Dict[str, List[str]]] = config.get("split_files", {})  # type: ignore[assignment]
    key = _normalize_split_name(split)
    canonical = split_aliases.get(key, key)
    spec = split_files.get(canonical)
    if not spec:
        available = ", ".join(sorted(split_files.keys())) or "<none>"
        raise KeyError(
            f"Split '{split}' is not defined for benchmark '{name}'. Available: {available}"
        )
    return spec


def available_remote_datasets() -> List[str]:
    """Return the list of remote benchmark names known to the loader."""

    return sorted(_REMOTE_BENCHMARKS.keys())


def available_remote_splits(name: str = "cellarc_100k") -> List[str]:
    """Return the supported split identifiers for a remote benchmark."""

    config = _REMOTE_BENCHMARKS.get(name)
    if not config:
        raise KeyError(f"Unknown remote benchmark: {name}")
    split_files: Dict[str, Dict[str, List[str]]] = config.get("split_files", {})  # type: ignore[assignment]
    return sorted(split_files.keys())


def _require_snapshot_download() -> None:
    if snapshot_download is None:  # pragma: no cover - optional dependency guard
        raise RuntimeError(
            "The 'huggingface_hub' package is required for downloading benchmarks. "
            "Install it with `pip install huggingface_hub`."
        )


def _normalize_split_name(split: str) -> str:
    normalized = "_".join(part for part in split.lower().replace("/", "_").split())
    return normalized.replace("-", "_")


def _resolve_artifact_path(base_dir: Path, entry: Union[str, Path]) -> Path:
    path = Path(entry)
    if path.is_absolute():
        return path
    for candidate_root in (base_dir, *base_dir.parents):
        candidate = candidate_root / path
        if candidate.exists():
            return candidate
    return base_dir / path


def download_benchmark(
    *,
    name: str = "cellarc_100k",
    include_metadata: bool = True,
    root: Optional[Union[str, Path]] = None,
    force_download: bool = False,
    revision: Optional[str] = None,
    meta_revision: Optional[str] = None,
    token: Optional[str] = None,
    allow_patterns: Optional[Sequence[str]] = None,
    ignore_patterns: Optional[Sequence[str]] = None,
) -> Path:
    """Download a benchmark snapshot from the Hugging Face Hub.

    Parameters
    ----------
    name:
        Registered benchmark name. Currently supports ``cellarc_100k``.
    include_metadata:
        If ``True`` download the companion repository with per-episode metadata
        (the ``cellarc_100k_meta`` dataset). When ``False`` the lighter
        supervision-only dataset is retrieved instead.
    root:
        Directory where the snapshot should be materialised. Defaults to
        ``CELLARC_HOME`` or ``~/.cache/cellarc``.
    force_download:
        If ``True`` redownload all files even if they are present locally.
    revision / meta_revision:
        Optional git revision (tag, branch, or commit) to pin the dataset or its
        metadata variant.
    token:
        Optional Hugging Face token for private artifacts.
    allow_patterns / ignore_patterns:
        Optional filename patterns forwarded to ``snapshot_download``.
    
    Existing local checkouts in ``root`` short-circuit the download step unless
    ``force_download`` is set.

    Returns
    -------
    pathlib.Path
        Location of the downloaded snapshot.
    """

    config = _REMOTE_BENCHMARKS.get(name)
    if not config:
        raise KeyError(f"Unknown remote benchmark: {name}")

    use_meta = include_metadata and config.get("meta_repo_id")
    repo_id = config["meta_repo_id" if use_meta else "repo_id"]
    local_dir_name = config["meta_dir" if use_meta else "local_dir"]
    base_root = Path(root).expanduser() if root else _default_cache_dir()
    target_dir = base_root / local_dir_name

    if not force_download:
        if target_dir.exists():
            return target_dir

    _require_snapshot_download()

    target_dir.parent.mkdir(parents=True, exist_ok=True)

    resolved_revision = meta_revision if use_meta and meta_revision else revision

    snapshot_download(  # type: ignore[misc]
        repo_id=repo_id,
        repo_type="dataset",
        revision=resolved_revision,
        local_dir=str(target_dir),
        force_download=force_download,
        token=token,
        allow_patterns=list(allow_patterns) if allow_patterns else None,
        ignore_patterns=list(ignore_patterns) if ignore_patterns else None,
    )

    return target_dir


def _ensure_datasets_available() -> None:
    if Dataset is None or load_dataset is None:
        raise RuntimeError(
            "The 'datasets' package is required for dataset loading. Install it with "
            "`pip install datasets pyarrow`."
        )


def _infer_format(path: Path) -> str:
    if path.is_dir():
        if (path / "dataset_info.json").exists() or any(path.glob("*.arrow")):
            return "hf_dataset"
        if list(path.glob("*.jsonl")):
            return "jsonl"
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return "jsonl"
    if suffix == ".parquet":
        return "parquet"
    raise ValueError(f"Unable to infer dataset format for path: {path}")


def _iter_jsonl(paths: Sequence[Path]) -> Iterator[Episode]:
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)


def _load_meta_lookup(paths: Sequence[Path]) -> Dict[str, Dict[str, object]]:
    lookup: Dict[str, Dict[str, object]] = {}
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


def load_manifest(path: Union[str, Path]) -> Dict[str, object]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _select_artifact(manifest: Dict[str, object], prefer: Sequence[str]) -> tuple[str, List[Path]]:
    artifacts = manifest.get("artifacts", {}) or {}
    for key in prefer:
        if key == "jsonl" and artifacts.get("jsonl"):
            paths = [Path(p) for p in artifacts["jsonl"]]
            if paths:
                return "jsonl", paths
        if key == "parquet" and artifacts.get("parquet"):
            return "parquet", [Path(artifacts["parquet"])]
        if key == "hf_dataset" and artifacts.get("hf_dataset"):
            return "hf_dataset", [Path(artifacts["hf_dataset"])]
    raise ValueError("Manifest does not contain any supported artifact paths.")


def random_palette_mapping(
    alphabet_size: int,
    palette: Sequence[int] = tuple(range(10)),
    rng: Optional[random.Random] = None,
) -> Dict[int, int]:
    rng = rng or random
    if alphabet_size < 1:
        raise ValueError("alphabet_size must be >= 1")
    palette = list(dict.fromkeys(palette))  # preserve order, ensure uniqueness
    if 0 not in palette:
        palette.insert(0, 0)
    available = [c for c in palette if c != 0]
    if len(available) < max(0, alphabet_size - 1):
        raise ValueError("Palette does not have enough non-zero symbols for the alphabet size.")
    rng.shuffle(available)
    mapping = {0: 0}
    for idx in range(1, alphabet_size):
        mapping[idx] = available[idx - 1]
    return mapping


def augment_episode(
    episode: Episode,
    *,
    rng: Optional[random.Random] = None,
    palette: Sequence[int] = tuple(range(10)),
    reverse_prob: float = 0.5,
) -> Episode:
    rng_local = rng or random.Random()
    augmented = copy.deepcopy(episode)

    meta = augmented.setdefault("meta", {})
    alphabet_size = int(meta.get("alphabet_size", 10))
    mapping = random_palette_mapping(alphabet_size, palette=palette, rng=rng_local)
    reverse = rng_local.random() < reverse_prob

    def transform(seq: Iterable[int]) -> List[int]:
        mapped = [mapping[int(v)] for v in seq]
        return list(reversed(mapped)) if reverse else mapped

    augmented["train"] = [
        {
            "input": transform(pair["input"]),
            "output": transform(pair["output"]),
        }
        for pair in augmented.get("train", [])
    ]
    augmented["query"] = transform(augmented.get("query", []))
    augmented["solution"] = transform(augmented.get("solution", []))

    augmentation_meta = {
        "palette_mapping": mapping,
        "reverse_applied": reverse,
    }
    meta["augmentation"] = augmentation_meta
    return augmented


class EpisodeDataset:
    """Iterates over benchmark episodes with optional augmentation."""

    def __init__(
        self,
        *,
        manifest: Optional[Union[str, Path]] = None,
        paths: Optional[Sequence[Union[str, Path]]] = None,
        meta_paths: Optional[Sequence[Union[str, Path]]] = None,
        prefer: Sequence[str] = ("hf_dataset", "parquet", "jsonl"),
        fmt: Optional[str] = None,
        augment: bool = False,
        reverse_prob: float = 0.5,
        palette: Sequence[int] = tuple(range(10)),
        seed: Optional[int] = None,
    ) -> None:
        if manifest is None and paths is None:
            raise ValueError("Provide either a manifest path or explicit paths to dataset files.")

        self.augment = augment
        self.reverse_prob = reverse_prob
        self.palette = palette
        self.seed = seed

        self.meta_lookup: Dict[str, Dict[str, object]] = {}

        if manifest is not None:
            manifest_data = load_manifest(manifest)
            fmt, resolved_paths = _select_artifact(manifest_data, prefer)
            artifacts = manifest_data.get("artifacts", {}) or {}
            meta_entries = artifacts.get("meta_jsonl") or []
            base_dir = Path(manifest).parent
            resolved_paths = [_resolve_artifact_path(base_dir, entry) for entry in resolved_paths]
            meta_resolved = [_resolve_artifact_path(base_dir, entry) for entry in meta_entries]
            self.meta_lookup = _load_meta_lookup(meta_resolved)
        else:
            resolved_paths = [Path(p) for p in (paths or [])]
            fmt = fmt or _infer_format(resolved_paths[0])
            if meta_paths:
                meta_resolved = [Path(p) for p in meta_paths]
                self.meta_lookup = _load_meta_lookup(meta_resolved)
            else:
                auto_meta = []
                for data_path in resolved_paths:
                    candidate = data_path.with_name(f"{data_path.stem}_meta.jsonl")
                    if candidate.exists():
                        auto_meta.append(candidate)
                if auto_meta:
                    self.meta_lookup = _load_meta_lookup(auto_meta)

        self.format = fmt
        self.paths = [Path(p) for p in resolved_paths]

    @classmethod
    def from_huggingface(
        cls,
        split: str,
        *,
        name: str = "cellarc_100k",
        include_metadata: bool = True,
        root: Optional[Union[str, Path]] = None,
        force_download: bool = False,
        revision: Optional[str] = None,
        meta_revision: Optional[str] = None,
        token: Optional[str] = None,
        allow_patterns: Optional[Sequence[str]] = None,
        ignore_patterns: Optional[Sequence[str]] = None,
        **kwargs: Any,
    ) -> "EpisodeDataset":
        """Instantiate a dataset after downloading a snapshot from the Hub.

        The helper understands the new ``cellarc_100k`` layout where each split is
        stored as ``data/<split>.{jsonl,parquet}``. Metadata-enriched variants are
        served by pointing ``include_metadata`` at the ``cellarc_100k_meta``
        repository.
        """

        repository_path = download_benchmark(
            name=name,
            include_metadata=include_metadata,
            root=root,
            force_download=force_download,
            revision=revision,
            meta_revision=meta_revision,
            token=token,
            allow_patterns=allow_patterns,
            ignore_patterns=ignore_patterns,
        )

        split_spec = _resolve_split_spec(name, split)

        fmt_override = kwargs.pop("fmt", None)
        prefer_order = kwargs.pop("prefer", None)
        if fmt_override is not None:
            search_order: Sequence[str] = (fmt_override,)
        else:
            if prefer_order is None:
                prefer_order = ("jsonl", "parquet")
            search_order = tuple(prefer_order)

        resolved_paths: List[Path] = []
        chosen_fmt: Optional[str] = None
        for candidate in search_order:
            entries = split_spec.get(candidate)
            if not entries:
                continue
            chosen_fmt = candidate
            resolved_paths = [(repository_path / Path(entry)).resolve() for entry in entries]
            break

        if chosen_fmt is None:
            available = ", ".join(split_spec.keys()) or "<none>"
            raise ValueError(
                f"Split '{split}' does not provide any of the requested formats {search_order}. "
                f"Available formats: {available}"
            )

        kwargs["fmt"] = fmt_override or chosen_fmt
        return cls(paths=resolved_paths, **kwargs)

    def __iter__(self) -> Iterator[Episode]:
        rng = random.Random(self.seed)
        for episode in self._iter_raw():
            if self.augment:
                yield augment_episode(
                    episode,
                    rng=rng,
                    palette=self.palette,
                    reverse_prob=self.reverse_prob,
                )
            else:
                yield episode

    def _iter_raw(self) -> Iterator[Episode]:
        if self.format == "jsonl":
            for record in _iter_jsonl(self.paths):
                if self.meta_lookup:
                    record = self._merge_meta(record)
                yield record
        elif self.format == "parquet":
            _ensure_datasets_available()
            dataset = Dataset.from_parquet(str(self.paths[0]))
            for record in dataset:
                if self.meta_lookup:
                    record = self._merge_meta(record)
                yield record
        elif self.format == "hf_dataset":
            _ensure_datasets_available()
            dataset = Dataset.load_from_disk(str(self.paths[0]))
            for record in dataset:
                if self.meta_lookup:
                    record = self._merge_meta(record)
                yield record
        else:
            raise ValueError(f"Unsupported dataset format: {self.format}")

    def _merge_meta(self, record: Episode) -> Episode:
        meta = record.get("meta", {}) or {}
        fp = meta.get("fingerprint")
        if not fp:
            return record
        extra = self.meta_lookup.get(str(fp))
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

    def __len__(self) -> int:
        if self.format == "jsonl":
            return sum(1 for _ in self._iter_raw())
        _ensure_datasets_available()
        if self.format == "parquet":
            return Dataset.from_parquet(str(self.paths[0])).num_rows
        if self.format == "hf_dataset":
            return Dataset.load_from_disk(str(self.paths[0])).num_rows
        raise ValueError(f"Unsupported dataset format: {self.format}")


class EpisodeDataLoader:
    """Simple iterable wrapper that batches episodes from an ``EpisodeDataset``."""

    def __init__(
        self,
        dataset: EpisodeDataset,
        *,
        batch_size: int = 1,
        shuffle: bool = False,
        drop_last: bool = False,
        seed: Optional[int] = None,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        self.dataset = dataset
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.drop_last = drop_last
        self.seed = seed

    def __iter__(self) -> Iterator[List[Episode]]:
        if self.shuffle:
            buffer = list(self.dataset)
            rng = random.Random(self.seed)
            rng.shuffle(buffer)
            iterator: Iterable[Episode] = buffer
        else:
            iterator = self.dataset

        batch: List[Episode] = []
        for episode in iterator:
            batch.append(episode)
            if len(batch) == self.batch_size:
                yield batch
                batch = []
        if batch and not self.drop_last:
            yield batch

    def __len__(self) -> int:
        total = len(self.dataset)
        if self.drop_last:
            return total // self.batch_size
        return (total + self.batch_size - 1) // self.batch_size


__all__ = [
    "EpisodeDataset",
    "EpisodeDataLoader",
    "available_remote_datasets",
    "available_remote_splits",
    "download_benchmark",
    "augment_episode",
    "load_manifest",
    "random_palette_mapping",
]
