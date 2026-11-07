#!/usr/bin/env python3
"""Per-episode visualization tools with styled task layouts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import gridspec
from matplotlib.patches import FancyArrowPatch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:  # pragma: no cover
    sys.path.insert(0, str(PROJECT_ROOT))

from cellarc.eval import prepare_episode, load_records, EpisodeRecord
from cellarc.visualization.ca_rollout_viz import _ensure_rule_table
from cellarc.visualization.palette import BG_COLOR, CMAP_HEX, PALETTE


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "inputs",
        nargs="+",
        help="Dataset JSONL or manifest inputs.",
    )
    parser.add_argument(
        "--fingerprint",
        type=str,
        help="Fingerprint to visualize (optional).",
    )
    parser.add_argument(
        "--index",
        type=int,
        help="Episode index to visualize (0-based).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("episode_viz"),
        help="Directory to write plots (default: episode_viz).",
    )
    return parser.parse_args(argv)


def find_episode(args: argparse.Namespace) -> EpisodeRecord:
    for idx, entry in enumerate(load_records(args.inputs)):
        if args.index is not None and idx != args.index:
            continue
        meta = entry.record.get("meta", {}) or {}
        if args.fingerprint and str(meta.get("fingerprint")) != args.fingerprint:
            continue
        _ensure_rule_table(entry)
        if args.index is None and args.fingerprint is None:
            return entry
        if args.index == idx or (args.fingerprint and str(meta.get("fingerprint")) == args.fingerprint):
            return entry
    raise ValueError("Episode not found with the provided filters.")


def _normalize_grid(grid: Sequence[int]) -> np.ndarray:
    arr = np.asarray(grid, dtype=int)
    if arr.ndim == 1:
        arr = arr[np.newaxis, :]
    return arr


def draw_grid(
    grid: Sequence[Sequence[int]] | Sequence[int],
    xmax: float = 10,
    ymax: float = 10,
    padding: float = 0.5,
    extra_bottom_padding: float = 0.5,
    group: bool = False,
    add_size: bool = True,
    label: str = "",
    bordercol: str = "#111111ff",
    ax=None,
):
    """Render a grid with cellular-automata styling using matplotlib."""

    data = _normalize_grid(grid)
    height, width = data.shape
    scale = min(xmax / max(width, 1), ymax / max(height, 1))

    created_fig = False
    if ax is None:
        fig_width = max(width * scale + padding, 1.0)
        fig_height = max(height * scale + padding + extra_bottom_padding, 1.0)
        fig, ax = plt.subplots(figsize=(fig_width, fig_height))
        created_fig = True
    else:
        fig = ax.figure

    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.imshow(
        data,
        cmap=PALETTE,
        vmin=0,
        vmax=len(CMAP_HEX) - 1,
        interpolation="nearest",
        aspect="equal",
    )
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    # Draw border manually for crisper edges.
    rect = plt.Rectangle(
        (-0.5, -0.5),
        width,
        height,
        linewidth=2,
        edgecolor=bordercol,
        facecolor="none",
    )
    ax.add_patch(rect)

    fontsize = 10
    if add_size:
        ax.text(
            0.98,
            1.02,
            f"{width}x{height}",
            transform=ax.transAxes,
            ha="right",
            va="bottom",
            fontsize=fontsize,
            fontweight="600",
            color="#1c1c1c",
        )
    if label:
        ax.text(
            0.02,
            1.02,
            label,
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=fontsize,
            fontweight="600",
            color="#1c1c1c",
        )

    ax.set_xlim(-0.5 - padding / 2, width - 0.5 + padding / 2)
    ax.set_ylim(height - 0.5 + (padding + extra_bottom_padding) / 2, -0.5 - padding / 2)

    if created_fig:
        fig.tight_layout()
        if group:
            return fig, ax
        return fig
    return ax


def _connect_axes_with_arrow(fig: plt.Figure, ax_from, ax_to) -> None:
    bbox_from = ax_from.get_position()
    bbox_to = ax_to.get_position()
    start = (
        bbox_from.x0 + bbox_from.width / 2,
        bbox_from.y0 - 0.01,
    )
    end = (
        bbox_to.x0 + bbox_to.width / 2,
        bbox_to.y1 + 0.01,
    )
    arrow = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=12,
        linewidth=1.2,
        color="#888888",
        transform=fig.transFigure,
    )
    fig.add_artist(arrow)


def draw_task(
    episode_data,
    width: float = 12,
    row_height: float = 2.4,
    include_test: bool = True,
    label: bool = True,
    bordercols: Sequence[str] = ("#111111ff", "#111111ff"),
    shortdesc: bool = False,
) -> plt.Figure:
    """Compose a two-column episode visualization with outputs beneath inputs."""

    train_pairs = episode_data.train_pairs
    if not train_pairs:
        raise ValueError("Episode has no training examples.")

    def _height_ratio(seq):
        arr = _normalize_grid(seq)
        h, w = arr.shape
        return max(h / max(w, 1), 1.0)

    columns = 1 if len(train_pairs) == 1 else min(2, len(train_pairs))
    pairs_per_column = int(np.ceil(len(train_pairs) / columns))
    base_rows = 2 * pairs_per_column
    total_rows = base_rows + (2 if include_test else 0)

    height_ratios = [0.0] * total_rows
    for idx, (inp, out) in enumerate(train_pairs):
        within_col = idx % pairs_per_column
        row_in = 2 * within_col
        row_out = row_in + 1
        height_ratios[row_in] = max(height_ratios[row_in], _height_ratio(inp))
        height_ratios[row_out] = max(height_ratios[row_out], _height_ratio(out))

    if include_test:
        query_ratio = _height_ratio(episode_data.query)
        solution_ratio = _height_ratio(episode_data.solution) if episode_data.solution else 1.0
        height_ratios[base_rows] = max(height_ratios[base_rows], query_ratio)
        height_ratios[base_rows + 1] = max(height_ratios[base_rows + 1], solution_ratio)

    height_ratios = [hr if hr > 0 else 1.0 for hr in height_ratios]
    fig_height = max(row_height * sum(height_ratios), row_height * total_rows)

    fig = plt.figure(figsize=(width, fig_height))
    fig.patch.set_facecolor(BG_COLOR)

    gs = gridspec.GridSpec(
        total_rows,
        columns,
        figure=fig,
        height_ratios=height_ratios,
        width_ratios=[1.0] * columns,
        hspace=0.25,
        wspace=0.5,
    )

    border_in, border_out = bordercols
    for idx, (inp, out) in enumerate(train_pairs):
        col = min(idx // pairs_per_column, columns - 1)
        within_col = idx % pairs_per_column
        row_in = 2 * within_col
        row_out = row_in + 1

        ax_in = fig.add_subplot(gs[row_in, col])
        draw_grid(
            inp,
            label=f"Input {idx + 1}" if label and not shortdesc else "",
            bordercol=border_in,
            ax=ax_in,
        )

        ax_out = fig.add_subplot(gs[row_out, col])
        draw_grid(
            out,
            label=f"Output {idx + 1}" if label and not shortdesc else "",
            bordercol=border_out,
            ax=ax_out,
        )
        _connect_axes_with_arrow(fig, ax_in, ax_out)

    if include_test:
        row_query = base_rows
        row_solution = base_rows + 1

        ax_query = fig.add_subplot(gs[row_query, :])
        draw_grid(
            episode_data.query,
            label="Test Query" if label else "",
            bordercol=border_in,
            ax=ax_query,
        )

        ax_solution = fig.add_subplot(gs[row_solution, :])
        if episode_data.solution:
            draw_grid(
                episode_data.solution,
                label="Test Output" if label else "",
                bordercol=border_out,
                ax=ax_solution,
            )
        else:
            ax_solution.axis("off")
            ax_solution.set_facecolor(BG_COLOR)
            ax_solution.text(
                0.5,
                0.5,
                "?",
                ha="center",
                va="center",
                fontsize=16,
                fontweight="600",
                color="#444444",
                transform=ax_solution.transAxes,
            )
        _connect_axes_with_arrow(fig, ax_query, ax_solution)

    return fig


def print_grid(grid: Sequence[Sequence[int]] | Sequence[int]) -> None:
    """Print a grid using ANSI background colors."""

    data = _normalize_grid(grid)
    reset = "\033[0m"
    for row in data:
        line = []
        for value in row:
            try:
                color = CMAP_HEX[int(value)]
            except (ValueError, IndexError):
                color = "#FFFFFF"
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            line.append(f"\033[48;2;{r};{g};{b}m  {reset}")
        print("".join(line))


def plot_episode_task(episode_data, output_path: Path) -> None:
    fig = draw_task(episode_data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200, bbox_inches="tight", facecolor=BG_COLOR)
    plt.close(fig)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    entry = find_episode(args)
    episode = prepare_episode(entry.record)

    fingerprint = episode.meta.get("fingerprint") or f"idx{args.index if args.index is not None else 0}"
    args.output_dir.mkdir(parents=True, exist_ok=True)

    plot_episode_task(episode, args.output_dir / f"space_time_{fingerprint}.png")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
