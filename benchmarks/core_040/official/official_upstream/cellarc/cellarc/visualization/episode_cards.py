"""Episode card visualisations for the Cell ARC dataset."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import numpy as np

from cellarc.eval import EpisodeRecord
from cellarc.generation.cax_runner import AutomatonRunner
from cellarc.generation.reconstruction import (
    infer_dataset_config,
    reconstruct_rule_table_payload,
)
from cellarc.generation.serialization import deserialize_rule_table
from cellarc.utils import de_bruijn_cycle
from cellarc.visualization.palette import BG_COLOR, PALETTE


def _ensure_rule_table(entry: EpisodeRecord) -> Dict[str, object]:
    """Guarantee that an episode record has an associated rule-table payload."""

    record = entry.record
    rule_table = record.get("rule_table")
    if isinstance(rule_table, dict):
        return rule_table

    meta = record.get("meta") or {}
    config = infer_dataset_config(meta)
    if config is None:
        raise ValueError(
            "Episode is missing a rule_table and cannot be reconstructed from metadata."
        )

    payload = reconstruct_rule_table_payload(meta, config=config)
    record["rule_table"] = payload
    return payload


def runner_from_record(rec: Dict[str, Any], *, rng_seed: int = 0) -> AutomatonRunner:
    """Instantiate an AutomatonRunner for the serialized rule table."""
    if "rule_table" not in rec or not isinstance(rec.get("rule_table"), dict):
        entry = EpisodeRecord(record=rec, source=Path("<episode_cards>"))
        payload = _ensure_rule_table(entry)
    else:
        payload = rec["rule_table"]
    if not isinstance(payload, dict):
        raise ValueError("Episode record is missing a valid rule_table payload.")
    table = deserialize_rule_table(payload)
    alphabet_size = int(payload["alphabet_size"])
    radius = int(payload["radius"])
    return AutomatonRunner(
        alphabet_size=alphabet_size,
        radius=radius,
        table=table,
        rng_seed=rng_seed,
    )


def space_time_from_record(
    rec: Dict[str, Any],
    *,
    tau_max: Optional[int] = None,
    rng_seed: int = 0,
) -> np.ndarray:
    """Reconstruct the space–time diagram implied by a dataset record."""
    meta = rec["meta"]
    alphabet_size = int(meta["alphabet_size"])
    window = int(meta["window"])
    steps = int(meta["steps"])
    cycle = de_bruijn_cycle(alphabet_size, window)
    depth = tau_max if tau_max is not None else max(4, min(24, steps + 8))
    depth = max(0, depth)
    runner = runner_from_record(rec, rng_seed=rng_seed)
    history = runner.evolve(
        cycle,
        timesteps=depth + steps + 1,
        return_history=True,
    )
    return history


def show_episode_card(
    rec: Dict[str, Any],
    *,
    palette=None,
    tau_max: Optional[int] = None,
    rng_seed: int = 0,
    show_core: bool = True,
    show_metadata: bool = False,
    metadata_fields: Optional[Sequence[str]] = None,
    metadata_formatter: Optional[Callable[[Dict[str, Any]], str]] = None,
) -> Figure:
    """
    Render an ARC-style card with train I/O bands and an unrolled CA view.

    Args:
        rec: Serialized episode record containing train/query I/O and metadata.
        palette: Optional matplotlib colormap override.
        tau_max: Optional rollout depth override when reconstructing the CA.
        rng_seed: Seed used when reconstructing stochastic automata.
        show_core: Insert masked spacer rows between samples when True.
        show_metadata: When True, render a summary of metadata beneath the plots.
        metadata_fields: Explicit list of metadata keys to display.
        metadata_formatter: Callable returning a custom metadata string.
    """
    space_time = space_time_from_record(rec, tau_max=tau_max, rng_seed=rng_seed)
    meta = rec["meta"]
    window = int(meta["window"])
    half = (window - 1) // 2
    spans = meta.get("train_spans", [])
    steps = int(meta["steps"])

    cmap = palette or PALETTE

    fig = plt.figure(figsize=(11, 6.2), facecolor=BG_COLOR)
    grid = fig.add_gridspec(2, 1, height_ratios=(3.2, 1.4), hspace=0.35)

    # Top panel: space–time diagram with training spans highlighted.
    ax_right = fig.add_subplot(grid[0, 0])
    ax_right.set_facecolor(BG_COLOR)
    space_width = space_time.shape[1] if space_time.ndim > 1 else 0
    ax_right.imshow(
        space_time, aspect="equal", interpolation="nearest", cmap=cmap, zorder=0
    )
    ax_right.set_title("Unrolled CA")
    if space_width:
        ax_right.set_xlim(-0.5, space_width - 0.5)
    ax_right.set_xticks([])
    ax_right.set_yticks([])
    for spine in ax_right.spines.values():
        spine.set_visible(False)

    def _draw_outline(x: float, y: float, width: float, height: float, *, dashed: bool):
        shadow = plt.Rectangle(
            (x, y),
            width,
            height,
            fill=False,
            linewidth=2.4,
            edgecolor="black",
            alpha=0.6,
            zorder=3,
        )
        ax_right.add_patch(shadow)
        ax_right.add_patch(
            plt.Rectangle(
                (x, y),
                width,
                height,
                fill=False,
                linewidth=1.2,
                edgecolor="white",
                linestyle="--" if dashed else "solid",
                zorder=4,
            )
        )

    def _draw_wrapped(start: int, width: int, tau: int, *, dashed: bool) -> None:
        if space_width <= 0 or width <= 0:
            return
        start_mod = start % space_width
        remaining = width
        segments = []
        first = min(remaining, space_width - start_mod)
        segments.append((start_mod, first))
        remaining -= first
        while remaining > 0:
            seg_width = min(remaining, space_width)
            segments.append((0, seg_width))
            remaining -= seg_width
        for x0, w0 in segments:
            _draw_outline(x0, tau, w0, 1, dashed=dashed)

    for span in spans:
        start = int(span.get("start", 0))
        length = int(span.get("length", 0))
        tau = int(span.get("time", 0))
        width = length + 2 * half
        _draw_wrapped(start - half, width, tau, dashed=False)
        _draw_wrapped(start - half, width, tau + steps, dashed=False)
    query_span = meta.get("query_span")
    if query_span:
        q_start = int(query_span.get("start", 0))
        q_len = int(query_span.get("length", 0))
        q_tau = int(query_span.get("time", 0))
        highlight_width = q_len + 2 * half
        _draw_wrapped(q_start - half, highlight_width, q_tau, dashed=True)
        _draw_wrapped(q_start - half, highlight_width, q_tau + steps, dashed=True)

    # Bottom panel: horizontally arranged I/O samples.
    columns: List[List[tuple[Optional[str], Optional[np.ndarray]]]] = []

    for pair in rec.get("train", []):
        inp = np.asarray(pair["input"], dtype=int)[None, :]
        out = np.asarray(pair["output"], dtype=int)[None, :]
        columns.append([("I", inp), ("O", out)])
        if show_core:
            columns.append([(None, None), (None, None)])
    query = rec.get("query")
    solution = rec.get("solution")
    if query is not None and solution is not None:
        q_arr = np.asarray(query, dtype=int)[None, :]
        s_arr = np.asarray(solution, dtype=int)[None, :]
        columns.append([("Q", q_arr), ("S", s_arr)])

    if columns and all(entry[0] is None for entry in columns[-1]):
        columns.pop()

    if columns:
        width_ratios: List[float] = []
        for column in columns:
            widths = [tile.shape[1] for _, tile in column if tile is not None]
            width_ratios.append(float(max(widths)) if widths else 0.5)
        bottom_spec = grid[1, 0].subgridspec(
            2,
            len(columns),
            wspace=0.1,
            hspace=0.05,
            width_ratios=width_ratios,
        )
        for col_idx, column in enumerate(columns):
            for row_idx, (label, tile) in enumerate(column):
                ax_tile = fig.add_subplot(bottom_spec[row_idx, col_idx])
                ax_tile.set_facecolor(BG_COLOR)
                if tile is None:
                    ax_tile.axis("off")
                    continue
                ax_tile.imshow(tile, aspect="equal", interpolation="nearest", cmap=cmap)
                ax_tile.set_xticks([])
                ax_tile.set_yticks([])
                for spine in ax_tile.spines.values():
                    spine.set_visible(False)
                if label:
                    ax_tile.text(
                        0.5,
                        1.08,
                        label,
                        transform=ax_tile.transAxes,
                        ha="center",
                        va="bottom",
                        fontsize=9,
                        color="#222222",
                    )

    metadata_text: Optional[str] = None
    if metadata_formatter is not None:
        metadata_text = metadata_formatter(meta)
    else:
        fields: Optional[Sequence[str]] = metadata_fields
        if fields is None and show_metadata:
            fields = ("split", "family", "alphabet_size", "radius", "steps", "lambda")
        if fields:
            parts: List[str] = []
            for key in fields:
                value = meta.get(key)
                if value is None:
                    continue
                label = "lambda" if key == "lambda" else key.replace("_", " ")
                if isinstance(value, float):
                    value_str = f"{value:.3f}"
                else:
                    value_str = str(value)
                parts.append(f"{label}: {value_str}")
            if parts:
                metadata_text = " | ".join(parts)

    bottom_margin = 0.22 if metadata_text else 0.12
    top_margin = 0.88 if metadata_text else 0.9
    fig.subplots_adjust(
        left=0.06,
        right=0.98,
        top=top_margin,
        bottom=bottom_margin,
        hspace=0.35,
    )
    if metadata_text:
        fig.text(
            0.5,
            0.035,
            metadata_text,
            ha="center",
            va="center",
            fontsize=9,
            color="#222222",
        )
    return fig


__all__ = [
    "runner_from_record",
    "space_time_from_record",
    "show_episode_card",
]
