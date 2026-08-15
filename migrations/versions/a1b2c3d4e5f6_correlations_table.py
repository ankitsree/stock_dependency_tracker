"""correlations table

Adds the `correlations` table written by the daily correlation-recompute
job (Track A Phase 1). `/api/graph` reads from this table instead of running
the full analytic stack on every request.

Revision ID: a1b2c3d4e5f6
Revises: ecf9be0d7993
Create Date: 2026-08-15 14:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "ecf9be0d7993"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "correlations",
        sa.Column("anchor", sa.String(), nullable=False),
        sa.Column("satellite", sa.String(), nullable=False),
        sa.Column("lookback_days", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("spearman_correlation", sa.Float(), nullable=True),
        sa.Column("pearson_correlation", sa.Float(), nullable=True),
        sa.Column("partial_correlation", sa.Float(), nullable=True),
        sa.Column("sector_relative_correlation", sa.Float(), nullable=True),
        sa.Column("stability_score", sa.Float(), nullable=True),
        sa.Column("best_lag", sa.Integer(), nullable=True),
        sa.Column("best_lag_correlation", sa.Float(), nullable=True),
        sa.Column("regime_break", sa.Boolean(), nullable=True),
        sa.Column("regime_drift", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("anchor", "satellite", "lookback_days", "computed_at", name="pk_correlations"),
    )
    # "Latest snapshot per anchor" is the hottest read path — the graph
    # endpoint runs it once per anchor. `computed_at DESC` puts newest rows
    # first so the query is a single index scan with LIMIT.
    op.create_index(
        "ix_correlations_anchor_computed_at",
        "correlations",
        ["anchor", sa.text("computed_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_correlations_anchor_computed_at", table_name="correlations")
    op.drop_table("correlations")
