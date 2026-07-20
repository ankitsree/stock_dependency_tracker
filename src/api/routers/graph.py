"""Blocking route (builds on CorrelationService per anchor): plain `def`,
not `async def` — see src/api/routers/prices.py's note.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from src.api import deps
from src.api.schemas.graph import GraphResponse, RelatednessResponse
from src.config import Config
from src.services.graph_service import GraphService

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("", response_model=GraphResponse)
def get_graph(
    anchors: list[str] | None = Query(default=None),
    top_n: int | None = Query(default=None, gt=0),
    threshold: float | None = Query(default=None, ge=0, le=1),
    force_refresh: bool = Query(default=False),
    graph_service: GraphService = Depends(deps.get_graph_service),
    config: Config = Depends(deps.get_config),
) -> GraphResponse:
    resolved_anchors = [a.upper() for a in anchors] if anchors else config.anchors
    data = graph_service.get_graph_json(resolved_anchors, top_n=top_n, threshold=threshold, force_refresh=force_refresh)
    return GraphResponse(**data)


@router.get("/relatedness", response_model=RelatednessResponse)
def get_relatedness(
    anchors: list[str] | None = Query(default=None),
    top_n: int | None = Query(default=None, gt=0),
    threshold: float | None = Query(default=None, ge=0, le=1),
    force_refresh: bool = Query(default=False),
    graph_service: GraphService = Depends(deps.get_graph_service),
    config: Config = Depends(deps.get_config),
) -> RelatednessResponse:
    resolved_anchors = [a.upper() for a in anchors] if anchors else config.anchors
    matrix = graph_service.get_relatedness_matrix(
        resolved_anchors, top_n=top_n, threshold=threshold, force_refresh=force_refresh
    )
    return RelatednessResponse(anchors=list(matrix.index), matrix=matrix.values.tolist())
