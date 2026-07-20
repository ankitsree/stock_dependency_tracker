from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless rendering, no display server needed
import matplotlib.pyplot as plt
import networkx as nx


def plot_graph(graph: nx.Graph, output_path: Path, title: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    n_nodes = graph.number_of_nodes()
    # Bigger, more spread-out layout as the multi-anchor graph grows, so
    # labels stay legible instead of clumping in the center.
    k = max(0.6, 0.9 / (n_nodes**0.5)) if n_nodes > 20 else 0.6
    pos = nx.spring_layout(graph, seed=42, k=k)
    anchors = [n for n, d in graph.nodes(data=True) if d["kind"] == "anchor"]
    satellites = [n for n, d in graph.nodes(data=True) if d["kind"] == "satellite"]
    weights = [graph[u][v]["weight"] for u, v in graph.edges()]

    side = max(10, min(20, n_nodes * 0.6))
    fig, ax = plt.subplots(figsize=(side, side * 0.8))

    nx.draw_networkx_edges(
        graph,
        pos,
        ax=ax,
        width=[abs(w) * 6 for w in weights],
        edge_color=["#2ca02c" if w >= 0 else "#d62728" for w in weights],
        alpha=0.6,
    )
    nx.draw_networkx_nodes(graph, pos, nodelist=anchors, node_color="#1f77b4", node_size=1600, ax=ax)
    nx.draw_networkx_nodes(graph, pos, nodelist=satellites, node_color="#ff7f0e", node_size=700, ax=ax)
    nx.draw_networkx_labels(graph, pos, ax=ax, font_size=9, font_weight="bold")

    edge_labels = {(u, v): f"{graph[u][v]['weight']:.2f}" for u, v in graph.edges()}
    nx.draw_networkx_edge_labels(graph, pos, edge_labels=edge_labels, ax=ax, font_size=7)

    ax.set_title(title)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
