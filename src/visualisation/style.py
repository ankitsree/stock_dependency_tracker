"""Visual encoding rules shared by every graph renderer (static and interactive).

Concrete color/size/opacity decisions are documented and justified in
.claude/skills/network-graph-style/SKILL.md — this module just implements them.
Kept as pure functions (no pyvis/matplotlib imports) so the encoding logic is
testable without rendering anything.
"""

from __future__ import annotations

import math

LIGHT_SURFACE = "#fcfcfb"
DARK_SURFACE = "#1a1a19"

ANCHOR_COLOR = {"light": "#0b0b0b", "dark": "#ffffff"}

POSITIVE_EDGE_COLOR = {"light": "#2a78d6", "dark": "#3987e5"}
NEGATIVE_EDGE_COLOR = {"light": "#e34948", "dark": "#e66767"}

# Sector -> color group. Anything not listed here falls into "Other Components".
_SECTOR_TO_GROUP = {
    "Semiconductor Equipment": "Semiconductor Equipment",
    "Semiconductors": "Semiconductors",
    "Semiconductor IP": "Chip IP, Materials & Memory",
    "Semiconductor Materials": "Chip IP, Materials & Memory",
    "Memory": "Chip IP, Materials & Memory",
    "Memory/Hardware": "Chip IP, Materials & Memory",
    "Laser/Photonics": "Photonics & Optical",
    "Optical Networking": "Photonics & Optical",
    "Test & Measurement": "Photonics & Optical",
    "Contract Manufacturing": "Contract Manufacturing",
    "Networking Hardware": "Networking & Systems",
    "Electronic Systems": "Networking & Systems",
}
_OTHER_GROUP = "Other Components"

# 7 of the dataviz skill's 8 categorical slots, in fixed order, skipping red
# (slot 6) so red stays reserved for negative-correlation edges.
SECTOR_GROUP_COLORS = {
    "Semiconductor Equipment": {"light": "#2a78d6", "dark": "#3987e5"},
    "Semiconductors": {"light": "#1baf7a", "dark": "#199e70"},
    "Chip IP, Materials & Memory": {"light": "#eda100", "dark": "#c98500"},
    "Photonics & Optical": {"light": "#008300", "dark": "#008300"},
    "Contract Manufacturing": {"light": "#4a3aa7", "dark": "#9085e9"},
    "Networking & Systems": {"light": "#e87ba4", "dark": "#d55181"},
    _OTHER_GROUP: {"light": "#eb6834", "dark": "#d95926"},
}

MIN_NODE_SIZE = 12
MAX_NODE_SIZE = 40
DEFAULT_SATELLITE_SIZE = 18
ANCHOR_SIZE = 40

MIN_EDGE_WIDTH_BASE = 1
EDGE_WIDTH_SCALE = 6

MIN_EDGE_OPACITY = 0.25


def sector_group(sector: str) -> str:
    """Map a fine-grained sector label onto one of the 7 color groups."""
    return _SECTOR_TO_GROUP.get(sector, _OTHER_GROUP)


def sector_color(sector: str, mode: str = "light") -> str:
    group = sector_group(sector)
    return SECTOR_GROUP_COLORS[group][mode]


def anchor_color(mode: str = "light") -> str:
    return ANCHOR_COLOR[mode]


def edge_color(weight: float, mode: str = "light") -> str:
    palette = POSITIVE_EDGE_COLOR if weight >= 0 else NEGATIVE_EDGE_COLOR
    return palette[mode]


def edge_width(weight: float) -> float:
    return MIN_EDGE_WIDTH_BASE + abs(weight) * EDGE_WIDTH_SCALE


def edge_opacity(stability: float | None) -> float:
    """Stability (0-1) becomes edge opacity, floored so edges never vanish.

    Missing stability (Phase 1 graphs predate the metric) renders fully opaque
    rather than guessing at reliability.
    """
    if stability is None or (isinstance(stability, float) and math.isnan(stability)):
        return 1.0
    return max(MIN_EDGE_OPACITY, min(1.0, stability))


def satellite_size(market_cap: float | None) -> float:
    """Log-scaled node size — market caps span orders of magnitude, so linear
    sizing would make everything but the one or two largest names invisible.
    """
    if market_cap is None or market_cap <= 0 or (isinstance(market_cap, float) and math.isnan(market_cap)):
        return DEFAULT_SATELLITE_SIZE
    size = 12 + 6 * math.log10(market_cap / 1e8)
    return max(MIN_NODE_SIZE, min(MAX_NODE_SIZE, size))
