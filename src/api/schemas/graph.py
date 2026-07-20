from __future__ import annotations

from pydantic import BaseModel

from src.domain.models import GraphEdge, GraphNode


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class RelatednessResponse(BaseModel):
    anchors: list[str]
    matrix: list[list[float]]
