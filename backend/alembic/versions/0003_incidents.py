"""Phase 2 tables: incident_categories (seeded), incidents, incident_locations.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The 9 categories and their suggested department. This fixed lookup is a design
# assumption of the prototype (documented in docs/architecture.md), not an official mapping.
CATEGORIES = [
    ("theft", "Theft", "Police"),
    ("harassment", "Harassment", "Police"),
    ("medical_emergency", "Medical emergency", "Medical"),
    ("accident", "Accident", "Medical"),
    ("lost_person", "Lost person", "Police"),
    ("suspicious_activity", "Suspicious activity", "Police"),
    ("natural_disaster", "Natural disaster", "Disaster Management"),
    ("fire", "Fire", "Fire"),
    ("other", "Other", "Tourist Helpdesk"),
]


def upgrade() -> None:
    categories = op.create_table(
        "incident_categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("department", sa.String(length=40), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incident_categories")),
        sa.UniqueConstraint("code", name=op.f("uq_incident_categories_code")),
    )
    op.bulk_insert(
        categories,
        [{"code": c, "name": n, "department": d} for c, n, d in CATEGORIES],
    )

    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reporter_user_id", sa.Integer(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=10), nullable=False),
        sa.Column("severity", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=15), nullable=False),
        sa.Column("is_sos", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name=op.f("ck_incidents_severity"),
        ),
        sa.CheckConstraint(
            "status IN ('NEW', 'ACKNOWLEDGED', 'ASSIGNED', 'EN_ROUTE', 'RESOLVED', 'CLOSED')",
            name=op.f("ck_incidents_status"),
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name=op.f("ck_incidents_confidence_range"),
        ),
        sa.ForeignKeyConstraint(
            ["reporter_user_id"],
            ["users.id"],
            name=op.f("fk_incidents_reporter_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["incident_categories.id"],
            name=op.f("fk_incidents_category_id_incident_categories"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incidents")),
    )
    op.create_index(op.f("ix_incidents_reporter_user_id"), "incidents", ["reporter_user_id"])
    op.create_index(op.f("ix_incidents_status"), "incidents", ["status"])
    op.create_index(op.f("ix_incidents_created_at"), "incidents", ["created_at"])

    op.create_table(
        "incident_locations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column(
            "geom",
            Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("accuracy_m", sa.Float(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            name=op.f("fk_incident_locations_incident_id_incidents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incident_locations")),
    )
    op.create_index(
        op.f("ix_incident_locations_incident_id"), "incident_locations", ["incident_id"]
    )
    op.create_index(op.f("ix_incident_locations_expires_at"), "incident_locations", ["expires_at"])
    op.create_index(
        "ix_incident_locations_geom", "incident_locations", ["geom"], postgresql_using="gist"
    )


def downgrade() -> None:
    op.drop_index("ix_incident_locations_geom", table_name="incident_locations")
    op.drop_index(op.f("ix_incident_locations_expires_at"), table_name="incident_locations")
    op.drop_index(op.f("ix_incident_locations_incident_id"), table_name="incident_locations")
    op.drop_table("incident_locations")
    op.drop_index(op.f("ix_incidents_created_at"), table_name="incidents")
    op.drop_index(op.f("ix_incidents_status"), table_name="incidents")
    op.drop_index(op.f("ix_incidents_reporter_user_id"), table_name="incidents")
    op.drop_table("incidents")
    op.drop_table("incident_categories")
