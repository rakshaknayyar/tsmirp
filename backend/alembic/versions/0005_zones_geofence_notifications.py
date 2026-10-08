"""Phase 4: risk_zones, notifications, and latest-location columns on tourist_profiles.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "risk_zones",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "geom",
            Geometry(geometry_type="POLYGON", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("base_level", sa.String(length=10), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "base_level IN ('LOW', 'MODERATE', 'HIGH', 'CRITICAL')",
            name=op.f("ck_risk_zones_base_level"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_risk_zones")),
        sa.UniqueConstraint("name", name=op.f("uq_risk_zones_name")),
    )
    op.create_index("ix_risk_zones_geom", "risk_zones", ["geom"], postgresql_using="gist")

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("recipient", sa.String(length=254), nullable=True),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=True),
        sa.Column("zone_id", sa.Integer(), nullable=True),
        sa.Column("simulated", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "channel IN ('in_app', 'sms_sandbox', 'email_sandbox')",
            name=op.f("ck_notifications_channel"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notifications_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            name=op.f("fk_notifications_incident_id_incidents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["zone_id"],
            ["risk_zones.id"],
            name=op.f("fk_notifications_zone_id_risk_zones"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"])
    op.create_index(op.f("ix_notifications_incident_id"), "notifications", ["incident_id"])

    op.add_column(
        "tourist_profiles",
        sa.Column(
            "last_location",
            Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=True,
        ),
    )
    op.add_column(
        "tourist_profiles", sa.Column("last_location_accuracy_m", sa.Float(), nullable=True)
    )
    op.add_column(
        "tourist_profiles",
        sa.Column("last_location_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tourist_profiles",
        sa.Column("last_location_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tourist_profiles",
        sa.Column(
            "geofence_state",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("tourist_profiles", "geofence_state")
    op.drop_column("tourist_profiles", "last_location_expires_at")
    op.drop_column("tourist_profiles", "last_location_at")
    op.drop_column("tourist_profiles", "last_location_accuracy_m")
    op.drop_column("tourist_profiles", "last_location")
    op.drop_index(op.f("ix_notifications_incident_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_user_id"), table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_risk_zones_geom", table_name="risk_zones")
    op.drop_table("risk_zones")
