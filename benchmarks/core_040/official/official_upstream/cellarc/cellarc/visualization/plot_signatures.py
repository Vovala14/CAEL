#!/usr/bin/env python3
"""Compute and visualize CA signatures using t-SNE or UMAP embeddings."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import colors as mcolors
from matplotlib.lines import Line2D

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:  # pragma: no cover
    sys.path.insert(0, str(PROJECT_ROOT))

from cellarc.eval import EpisodeRecord, load_records
from cellarc.signatures import Signature, compute_signature, signatures_as_rows

try:  # optional dependency for parquet IO
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:  # pragma: no cover
    pa = None
    pq = None


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "inputs",
        nargs="*",
        help="Dataset JSONL or manifest inputs. Ignored if --from-parquet is provided.",
    )
    parser.add_argument(
        "--from-parquet",
        type=Path,
        help="Existing signatures parquet to load instead of recomputing.",
    )
    parser.add_argument(
        "--save-parquet",
        type=Path,
        help="Optional path to write signatures.parquet after computation.",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        help="Limit the number of episodes to include (random order preserved).",
    )
    parser.add_argument(
        "--method",
        choices=["tsne", "umap"],
        default="tsne",
        help="Embedding method to use (default: tsne).",
    )
    parser.add_argument(
        "--perplexity",
        type=float,
        default=30.0,
        help="t-SNE perplexity (default: 30).",
    )
    parser.add_argument(
        "--n-neighbors",
        type=int,
        default=15,
        help="UMAP n_neighbors (default: 15).",
    )
    parser.add_argument(
        "--min-dist",
        type=float,
        default=0.1,
        help="UMAP min_dist (default: 0.1).",
    )
    parser.add_argument(
        "--color-by",
        nargs="+",
        choices=["meta_lambda_bin", "meta_entropy_bin", "meta_family"],
        default=["meta_lambda_bin"],
        help="Metadata fields to color points by (default: meta_lambda_bin).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("signature_viz"),
        help="Directory to write plots (default: signature_viz).",
    )
    parser.add_argument(
        "--fig-format",
        type=str,
        default="png",
        help="Image format for plots (default: png).",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=200,
        help="Image DPI (default: 200).",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=12345,
        help="Random seed for embeddings (default: 12345).",
    )
    parser.add_argument(
        "--summary-json",
        type=Path,
        help="Optional path to dump embedding metadata as JSON.",
    )
    return parser.parse_args(argv)


def load_signatures_from_parquet(path: Path) -> List[Dict[str, object]]:
    if pq is None:
        raise RuntimeError("pyarrow is required to read parquet files. Install pyarrow.")
    table = pq.read_table(path)
    return table.to_pylist()


def write_signatures_parquet(rows: List[Dict[str, object]], path: Path) -> None:
    if pq is None:
        raise RuntimeError("pyarrow is required to write parquet files. Install pyarrow.")
    table = pa.Table.from_pylist(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


def load_signatures_from_inputs(inputs: Sequence[str], max_records: Optional[int]) -> List[Signature]:
    signatures: List[Signature] = []
    for idx, entry in enumerate(load_records(inputs)):
        if max_records is not None and idx >= max_records:
            break
        signatures.append(compute_signature(entry.record))
    return signatures


def prepare_feature_matrix(signatures: Sequence[Signature]) -> Tuple[np.ndarray, List[str]]:
    if not signatures:
        raise ValueError("No signatures available for embedding.")
    feature_names = sorted(signatures[0].features.keys())
    matrix = np.array([[sig.features[name] for name in feature_names] for sig in signatures], dtype=float)
    # Replace nan with column means
    col_means = np.nanmean(matrix, axis=0)
    col_means = np.nan_to_num(col_means, nan=0.0)
    inds = np.where(np.isnan(matrix))
    matrix[inds] = np.take(col_means, inds[1])
    # Standardize
    col_std = matrix.std(axis=0)
    col_std[col_std == 0.0] = 1.0
    matrix = (matrix - matrix.mean(axis=0)) / col_std
    return matrix, feature_names


def compute_embedding(
    matrix: np.ndarray,
    method: str,
    *,
    perplexity: float,
    n_neighbors: int,
    min_dist: float,
    random_state: int,
) -> np.ndarray:
    if method == "tsne":
        try:
            from sklearn.manifold import TSNE
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("scikit-learn is required for t-SNE embeddings.") from exc
        max_perp = max(2.0, (matrix.shape[0] - 1) / 3)
        perplexity = min(perplexity, max_perp, matrix.shape[0] - 1e-3)
        tsne = TSNE(
            n_components=2,
            perplexity=perplexity,
            metric="euclidean",
            random_state=random_state,
            init="random",
        )
        return tsne.fit_transform(matrix)
    if method == "umap":
        try:
            import umap
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("umap-learn is required for UMAP embeddings.") from exc
        reducer = umap.UMAP(
            n_neighbors=n_neighbors,
            min_dist=min_dist,
            random_state=random_state,
        )
        return reducer.fit_transform(matrix)
    raise ValueError(f"Unknown method: {method}")


def color_mapping(values: Sequence[object]) -> Tuple[List[str], Dict[object, str]]:
    categories = sorted({val if val is not None else "unknown" for val in values})
    cmap = plt.colormaps.get_cmap("tab20" if len(categories) > 10 else "tab10")
    colors: Dict[object, str] = {}
    for idx, cat in enumerate(categories):
        color = cmap(idx / max(1, len(categories) - 1))
        colors[cat] = mcolors.to_hex(color)
    mapped = [colors[val if val is not None else "unknown"] for val in values]
    return mapped, colors


def plot_embedding(
    embedding: np.ndarray,
    signatures: Sequence[Signature],
    *,
    color_key: str,
    output_dir: Path,
    fmt: str,
    dpi: int,
) -> Dict[str, object]:
    values = [sig.meta.get(color_key.replace("meta_", "")) if color_key.startswith("meta_") else sig.meta.get(color_key) for sig in signatures]
    colors, legend_map = color_mapping(values)
    plt.figure()
    plt.scatter(embedding[:, 0], embedding[:, 1], c=colors, s=20, alpha=0.8, edgecolors="none")
    plt.xlabel("dim 1")
    plt.ylabel("dim 2")
    plt.title(f"Signature embedding colored by {color_key}")
    handles = []
    for label, color in legend_map.items():
        handles.append(Line2D([0], [0], marker="o", color="w", label=str(label), markerfacecolor=color, markersize=6))
    plt.legend(handles=handles, loc="best", fontsize=8)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"embedding_{color_key}.{fmt}"
    plt.tight_layout()
    plt.savefig(path, dpi=dpi)
    plt.close()
    return {
        "color_key": color_key,
        "legend": {str(k): v for k, v in legend_map.items()},
        "path": str(path),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    if args.from_parquet:
        rows = load_signatures_from_parquet(args.from_parquet)
        signatures = []
        for row in rows:
            fingerprint = str(row.get("fingerprint", ""))
            features = {k: float(row[k]) for k in row if k not in {"fingerprint"} and not str(k).startswith("meta_")}
            meta = {k.replace("meta_", ""): row[k] for k in row if str(k).startswith("meta_")}
            signatures.append(Signature(fingerprint=fingerprint, features=features, meta=meta))
    else:
        if not args.inputs:
            raise SystemExit("Provide dataset inputs or --from-parquet.")
        signatures = load_signatures_from_inputs(args.inputs, args.max_records)
        if args.save_parquet:
            rows = signatures_as_rows(signatures)
            write_signatures_parquet(rows, args.save_parquet)

    matrix, feature_names = prepare_feature_matrix(signatures)
    embedding = compute_embedding(
        matrix,
        args.method,
        perplexity=args.perplexity,
        n_neighbors=args.n_neighbors,
        min_dist=args.min_dist,
        random_state=args.random_state,
    )

    summary = {
        "method": args.method,
        "count": len(signatures),
        "features": feature_names,
        "color_by": args.color_by,
    }

    outputs = []
    for color_key in args.color_by:
        outputs.append(
            plot_embedding(
                embedding,
                signatures,
                color_key=color_key,
                output_dir=args.output_dir,
                fmt=args.fig_format,
                dpi=args.dpi,
            )
        )
    summary["plots"] = outputs

    if args.summary_json:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        with args.summary_json.open("w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2)
            handle.write("\n")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
