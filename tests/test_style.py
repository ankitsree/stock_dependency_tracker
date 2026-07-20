from src.visualisation import style


def test_sector_group_maps_known_sectors():
    assert style.sector_group("Semiconductor Equipment") == "Semiconductor Equipment"
    assert style.sector_group("Semiconductor IP") == "Chip IP, Materials & Memory"
    assert style.sector_group("Memory/Hardware") == "Chip IP, Materials & Memory"
    assert style.sector_group("Optical Networking") == "Photonics & Optical"


def test_sector_group_unknown_sector_falls_back_to_other():
    assert style.sector_group("Some New Sector") == "Other Components"


def test_sector_color_differs_by_mode():
    light = style.sector_color("Semiconductor Equipment", mode="light")
    dark = style.sector_color("Semiconductor Equipment", mode="dark")
    assert light != dark
    assert light == "#2a78d6"
    assert dark == "#3987e5"


def test_sector_color_never_uses_reserved_edge_red():
    all_sector_hues = {c for colors in style.SECTOR_GROUP_COLORS.values() for c in colors.values()}
    # positive edge color intentionally reuses slot 1 (blue) for both nodes and edges,
    # so only the negative (red) pole must stay exclusive to edges.
    assert style.NEGATIVE_EDGE_COLOR["light"] not in all_sector_hues
    assert style.NEGATIVE_EDGE_COLOR["dark"] not in all_sector_hues


def test_edge_color_positive_vs_negative():
    assert style.edge_color(0.7, mode="light") == style.POSITIVE_EDGE_COLOR["light"]
    assert style.edge_color(-0.7, mode="light") == style.NEGATIVE_EDGE_COLOR["light"]
    assert style.edge_color(0.0, mode="dark") == style.POSITIVE_EDGE_COLOR["dark"]


def test_edge_width_scales_with_magnitude():
    assert style.edge_width(0.5) < style.edge_width(0.9)
    assert style.edge_width(-0.9) == style.edge_width(0.9)  # sign doesn't affect width


def test_edge_opacity_floors_at_minimum():
    assert style.edge_opacity(0.0) == style.MIN_EDGE_OPACITY
    assert style.edge_opacity(1.0) == 1.0
    assert style.edge_opacity(0.5) == 0.5


def test_edge_opacity_missing_stability_is_fully_opaque():
    assert style.edge_opacity(None) == 1.0
    assert style.edge_opacity(float("nan")) == 1.0


def test_satellite_size_scales_with_log_market_cap():
    small = style.satellite_size(2e8)
    large = style.satellite_size(2e11)
    assert small < large
    assert style.MIN_NODE_SIZE <= small <= style.MAX_NODE_SIZE
    assert style.MIN_NODE_SIZE <= large <= style.MAX_NODE_SIZE


def test_satellite_size_clamped_at_extremes():
    assert style.satellite_size(1) == style.MIN_NODE_SIZE
    assert style.satellite_size(1e20) == style.MAX_NODE_SIZE


def test_satellite_size_missing_market_cap_uses_default():
    assert style.satellite_size(None) == style.DEFAULT_SATELLITE_SIZE
    assert style.satellite_size(float("nan")) == style.DEFAULT_SATELLITE_SIZE


def test_anchor_color_differs_by_mode_and_is_never_a_sector_color():
    light = style.anchor_color("light")
    dark = style.anchor_color("dark")
    assert light != dark
    all_sector_hues = {c for colors in style.SECTOR_GROUP_COLORS.values() for c in colors.values()}
    assert light not in all_sector_hues
    assert dark not in all_sector_hues
