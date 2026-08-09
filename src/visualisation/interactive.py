"""Interactive HTML graph rendering (pyvis/vis.js), per roadmap Phase 3.

Encoding rules (colors, sizes, opacity) live in style.py and are documented in
.claude/skills/network-graph-style/SKILL.md — this module just wires them into
a pyvis Network and post-processes the generated HTML for light/dark support
and a companion summary table.
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path

import networkx as nx
from pyvis.network import Network

from src.visualisation import style


def build_interactive_graph(graph: nx.Graph, output_path: Path, title: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    net = Network(
        height="800px",
        width="100%",
        bgcolor=style.LIGHT_SURFACE,
        font_color=style.anchor_color("light"),
        directed=False,
        # pyvis's own template renders {{heading}} twice (a bug in the library,
        # not intentional) — leave it blank and inject a single <h1> ourselves.
        heading="",
        cdn_resources="in_line",  # embed vis-network JS/CSS so the file works offline
    )
    # pyvis mutates the graph it's given (renames the "weight" edge attribute
    # to "width" in place), so hand it a copy — the caller's graph, and our
    # own attribute lookups below, must stay intact.
    net.from_nx(graph.copy())
    net.toggle_physics(True)

    node_theme = {}
    for node in net.nodes:
        data = graph.nodes[node["id"]]
        if data.get("kind") == "anchor":
            node["shape"] = "star"
            node["size"] = style.ANCHOR_SIZE
            light, dark = style.anchor_color("light"), style.anchor_color("dark")
        else:
            node["shape"] = "dot"
            node["size"] = style.satellite_size(data.get("market_cap"))
            light = style.sector_color(data.get("sector", ""), mode="light")
            dark = style.sector_color(data.get("sector", ""), mode="dark")
        node["color"] = light
        node["font"] = {"color": style.anchor_color("light")}
        node["title"] = _node_tooltip(node["id"], data)
        node_theme[node["id"]] = {"light": light, "dark": dark}

    edge_theme = {}
    for edge in net.edges:
        u, v = edge["from"], edge["to"]
        data = graph[u][v]
        weight = data["weight"]
        stability = data.get("stability")
        edge_id = f"{u}__{v}"
        edge["id"] = edge_id
        edge["width"] = style.edge_width(weight)
        opacity = style.edge_opacity(stability)
        light, dark = style.edge_color(weight, "light"), style.edge_color(weight, "dark")
        edge["color"] = {"color": light, "opacity": opacity}
        edge["title"] = _edge_tooltip(u, v, weight, stability, data)
        edge_theme[edge_id] = {"light": light, "dark": dark, "opacity": opacity}

    html_doc = net.generate_html(notebook=False)
    heading_html = f'<center><h1 id="page-heading">{escape(title)}</h1></center>'
    html_doc = html_doc.replace("<body>", "<body>" + heading_html, 1)
    # Table must be inserted before the theme script runs, since the script
    # looks it up by id synchronously on load — reversed, getElementById
    # would return null and the table would never pick up the theme.
    html_doc = html_doc.replace("</body>", _summary_table(graph) + _theme_script(node_theme, edge_theme) + "</body>")
    output_path.write_text(html_doc)


def _node_tooltip(ticker: str, data: dict) -> str:
    if data.get("kind") == "anchor":
        return f"<b>{escape(ticker)}</b><br>Anchor"

    lines = [
        f"<b>{escape(str(data.get('name', ticker)))}</b> ({escape(ticker)})",
        f"Sector: {escape(str(data.get('sector', 'Unknown')))}",
    ]
    if data.get("market_cap"):
        lines.append(f"Market cap: ${data['market_cap']:,.0f}")
    if data.get("avg_volume"):
        lines.append(f"Avg volume: {data['avg_volume']:,.0f}")
    return "<br>".join(lines)


def _edge_tooltip(anchor: str, satellite: str, weight: float, stability: float | None, data: dict) -> str:
    lines = [f"{escape(anchor)} &harr; {escape(satellite)}", f"Correlation (Spearman): {weight:.2f}"]
    if stability is not None:
        lines.append(f"Stability: {stability:.2f}")
    if data.get("pearson_correlation") is not None:
        lines.append(f"Correlation (Pearson): {data['pearson_correlation']:.2f}")
    if data.get("partial_correlation") is not None:
        lines.append(f"Partial (market-adjusted): {data['partial_correlation']:.2f}")
    if data.get("sector_relative_correlation") is not None:
        lines.append(f"Sector-relative: {data['sector_relative_correlation']:.2f}")
    if data.get("best_lag") is not None:
        lines.append(f"Best lag: {data['best_lag']}d (r={data['best_lag_correlation']:.2f})")
    if data.get("regime_break"):
        lines.append(f"&#9888; Regime break (drift={data.get('regime_drift', 0):.2f})")
    return "<br>".join(lines)


def _theme_script(node_theme: dict, edge_theme: dict) -> str:
    return f"""
<script>
(function() {{
  const nodeTheme = {json.dumps(node_theme)};
  const edgeTheme = {json.dumps(edge_theme)};
  function applyTheme(isDark) {{
    const mode = isDark ? "dark" : "light";
    const inkColor = isDark ? "{style.anchor_color("dark")}" : "{style.anchor_color("light")}";
    nodes.update(Object.entries(nodeTheme).map(([id, c]) => ({{id: id, color: c[mode], font: {{color: inkColor}}}})));
    edges.update(Object.entries(edgeTheme).map(([id, c]) => ({{id: id, color: {{color: c[mode], opacity: c.opacity}}}})));
    const net = document.getElementById("mynetwork");
    if (net) net.style.backgroundColor = isDark ? "{style.DARK_SURFACE}" : "{style.LIGHT_SURFACE}";
    document.body.style.backgroundColor = isDark ? "#0d0d0d" : "#f9f9f7";
    document.body.style.color = inkColor;
    const table = document.getElementById("summary-table-container");
    if (table) {{
      table.style.backgroundColor = isDark ? "{style.DARK_SURFACE}" : "{style.LIGHT_SURFACE}";
      table.style.color = inkColor;
    }}
  }}
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  applyTheme(mq.matches);
  mq.addEventListener("change", (e) => applyTheme(e.matches));
}})();
</script>
"""


def _summary_table(graph: nx.Graph) -> str:
    rows = []
    for anchor, satellite, data in graph.edges(data=True):
        # nx.Graph edges are undirected/unordered — figure out which endpoint is the anchor.
        anchor_node, satellite_node = (
            (anchor, satellite) if graph.nodes[anchor]["kind"] == "anchor" else (satellite, anchor)
        )
        sat_data = graph.nodes[satellite_node]
        stability = data.get("stability")
        rows.append(
            {
                "anchor": anchor_node,
                "ticker": satellite_node,
                "name": sat_data.get("name", satellite_node),
                "sector": sat_data.get("sector", ""),
                "correlation": data["weight"],
                "stability": stability,
                "market_cap": sat_data.get("market_cap"),
                "pearson_correlation": data.get("pearson_correlation"),
                "partial_correlation": data.get("partial_correlation"),
                "sector_relative_correlation": data.get("sector_relative_correlation"),
                "best_lag": data.get("best_lag"),
                "best_lag_correlation": data.get("best_lag_correlation"),
                "regime_break": data.get("regime_break"),
            }
        )
    rows.sort(key=lambda r: (r["anchor"], -abs(r["correlation"])))

    has_phase4_columns = any(r["pearson_correlation"] is not None for r in rows)
    header_cells = ["Anchor", "Ticker", "Name", "Sector", "Correlation (Spearman)", "Stability", "Market Cap"]
    if has_phase4_columns:
        header_cells += ["Pearson", "Partial", "Sector-Rel", "Lag", "Regime"]
    header = "<tr>" + "".join(f"<th>{cell}</th>" for cell in header_cells) + "</tr>"

    def _fmt(value: float | None) -> str:
        return f"{value:.2f}" if value is not None else "&mdash;"

    body = ""
    for r in rows:
        stability_cell = f"{r['stability']:.2f}" if r["stability"] is not None else "&mdash;"
        market_cap_cell = f"${r['market_cap']:,.0f}" if r["market_cap"] else "&mdash;"
        cells = (
            f"<td>{escape(r['anchor'])}</td>"
            f"<td>{escape(r['ticker'])}</td>"
            f"<td>{escape(str(r['name']))}</td>"
            f"<td>{escape(str(r['sector']))}</td>"
            f"<td>{r['correlation']:.2f}</td>"
            f"<td>{stability_cell}</td>"
            f"<td>{market_cap_cell}</td>"
        )
        if has_phase4_columns:
            lag_cell = (
                f"{r['best_lag']}d ({_fmt(r['best_lag_correlation'])})" if r["best_lag"] is not None else "&mdash;"
            )
            regime_cell = "&#9888;" if r["regime_break"] else "&mdash;"
            cells += (
                f"<td>{_fmt(r['pearson_correlation'])}</td>"
                f"<td>{_fmt(r['partial_correlation'])}</td>"
                f"<td>{_fmt(r['sector_relative_correlation'])}</td>"
                f"<td>{lag_cell}</td>"
                f"<td>{regime_cell}</td>"
            )
        body += f"<tr>{cells}</tr>"

    return f"""
<div id="summary-table-container" style="max-width:100%; overflow-x:auto; margin:16px auto; padding:16px; font-family:system-ui,-apple-system,sans-serif; background:{style.LIGHT_SURFACE};">
  <h3>Satellite summary</h3>
  <table style="border-collapse:collapse; width:100%;">
    <thead>{header}</thead>
    <tbody>{body}</tbody>
  </table>
</div>
<style>
  #summary-table-container table, #summary-table-container th, #summary-table-container td {{
    border: 1px solid rgba(128,128,128,0.3);
    padding: 6px 10px;
    text-align: left;
    font-size: 14px;
  }}
  #summary-table-container th {{ font-weight: 600; }}
</style>
"""
