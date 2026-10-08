"""Phase 7: risk_zones.kind and the risk_predictions table.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "risk_zones",
        sa.Column("kind", sa.String(length=10), server_default="area", nullable=False),
    )
    op.create_check_constraint(op.f("ck_risk_zones_kind"), "risk_zones", "kind IN ('area', 'grid')")

    op.create_table(
        "risk_predictions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("zone_id", sa.Integer(), nullable=False),
        sa.Column("time_bin", sa.DateTime(timezone=True), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("level", sa.String(length=10), nullable=False),
        sa.Column("model_version", sa.String(length=40), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "level IN ('LOW', 'MODERATE', 'HIGH', 'CRITICAL')",
            name=op.f("ck_risk_predictions_level"),
        ),
        sa.CheckConstraint(
            "score >= 0 AND score <= 1", name=op.f("ck_risk_predictions_score_range")
        ),
        sa.ForeignKeyConstraint(
            ["zone_id"],
            ["risk_zones.id"],
            name=op.f("fk_risk_predictions_zone_id_risk_zones"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risk_predictions")),
        sa.UniqueConstraint(
            "zone_id",
            "time_bin",
            "model_version",
            name=op.f("uq_risk_predictions_zone_id"),
        ),
    )
    op.create_index(op.f("ix_risk_predictions_zone_id"), "risk_predictions", ["zone_id"])
    op.create_index(op.f("ix_risk_predictions_time_bin"), "risk_predictions", ["time_bin"])


def downgrade() -> None:
    op.drop_index(op.f("ix_risk_predictions_time_bin"), table_name="risk_predictions")
    op.drop_index(op.f("ix_risk_predictions_zone_id"), table_name="risk_predictions")
    op.drop_table("risk_predictions")
    op.drop_constraint(op.f("ck_risk_zones_kind"), "risk_zones", type_="check")
    op.drop_column("risk_zones", "kind")
