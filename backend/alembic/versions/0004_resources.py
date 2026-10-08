"""Phase 3 tables: response_resources, response_assignments.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "response_resources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("resource_type", sa.String(length=20), nullable=False),
        sa.Column(
            "geog",
            Geography(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("source_ref", sa.String(length=40), nullable=True),
        sa.Column("capabilities", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("availability_sim", sa.String(length=10), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "resource_type IN ('police_station', 'hospital', 'fire_station')",
            name=op.f("ck_response_resources_resource_type"),
        ),
        sa.CheckConstraint(
            "availability_sim IN ('AVAILABLE', 'BUSY', 'OFFLINE')",
            name=op.f("ck_response_resources_availability_sim"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_response_resources")),
        sa.UniqueConstraint("source_ref", name=op.f("uq_response_resources_source_ref")),
    )
    op.create_index(
        op.f("ix_response_resources_resource_type"), "response_resources", ["resource_type"]
    )
    op.create_index(
        "ix_response_resources_geog", "response_resources", ["geog"], postgresql_using="gist"
    )

    op.create_table(
        "response_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.Column("assigned_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("distance_m", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'RELEASED')", name=op.f("ck_response_assignments_status")
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            name=op.f("fk_response_assignments_incident_id_incidents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["resource_id"],
            ["response_resources.id"],
            name=op.f("fk_response_assignments_resource_id_response_resources"),
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by_user_id"],
            ["users.id"],
            name=op.f("fk_response_assignments_assigned_by_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_response_assignments")),
    )
    op.create_index(
        op.f("ix_response_assignments_incident_id"), "response_assignments", ["incident_id"]
    )
    op.create_index(
        op.f("ix_response_assignments_resource_id"), "response_assignments", ["resource_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_response_assignments_resource_id"), table_name="response_assignments")
    op.drop_index(op.f("ix_response_assignments_incident_id"), table_name="response_assignments")
    op.drop_table("response_assignments")
    op.drop_index("ix_response_resources_geog", table_name="response_resources")
    op.drop_index(op.f("ix_response_resources_resource_type"), table_name="response_resources")
    op.drop_table("response_resources")
