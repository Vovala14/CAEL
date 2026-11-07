"""Shared colour palettes for Cell ARC visualisations."""

from __future__ import annotations

from matplotlib.colors import ListedColormap

CMAP_HEX = [
    '#252525', # black
    '#0074D9', # blue
    '#FF4136', # red
    '#37D449', #2ECC40', # green
    '#FFDC00', # yellow
    '#E6E6E6', # grey
    '#F012BE', # pink
    '#FF871E', # orange
    '#54D2EB', #7FDBFF', # light blue
    '#8D1D2C', #870C25', # brown
    '#FFFFFF'
]

BG_COLOR = "#EEEFF6"

PALETTE = ListedColormap(CMAP_HEX)
PALETTE.set_bad(color=BG_COLOR)


__all__ = ["CMAP_HEX", "BG_COLOR", "PALETTE"]
