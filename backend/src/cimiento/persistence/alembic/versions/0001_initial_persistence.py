"""Initial persistence schema.

Revision ID: 0001_initial_persistence
Revises:
Create Date: 2026-04-20
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial_persistence"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_projects_name", "projects", ["name"])

    op.create_table(
        "project_versions",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("solar_data", sa.JSON(), nullable=False),
        sa.Column("program_data", sa.JSON(), nullable=False),
        sa.Column("solution_data", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "version_number", name="uq_project_version_number"),
    )
    op.create_index("ix_project_versions_project_id", "project_versions", ["project_id"])

    op.create_table(
        "generated_outputs",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("project_version_id", sa.String(length=36), nullable=False),
        sa.Column("output_type", sa.String(length=50), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("media_type", sa.String(length=255), nullable=True),
        sa.Column("output_metadata", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["project_version_id"],
            ["project_versions.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_generated_outputs_project_version_id",
        "generated_outputs",
        ["project_version_id"],
    )
    op.create_index("ix_generated_outputs_output_type", "generated_outputs", ["output_type"])


def downgrade() -> None:
    op.drop_index("ix_generated_outputs_output_type", table_name="generated_outputs")
    op.drop_index("ix_generated_outputs_project_version_id", table_name="generated_outputs")
    op.drop_table("generated_outputs")

    op.drop_index("ix_project_versions_project_id", table_name="project_versions")
    op.drop_table("project_versions")

    op.drop_index("ix_projects_name", table_name="projects")
    op.drop_table("projects")