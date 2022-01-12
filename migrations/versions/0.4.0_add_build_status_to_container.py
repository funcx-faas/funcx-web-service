"""Add build status to container

Revision ID: 0.4.0
Revises: v0.2.0
Create Date: 2021-11-22 11:44:40.777670

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
from sqlalchemy import Column, String

revision = "0.4.0"
down_revision = "v0.2.0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("containers", Column("build_status", String(9)))
    op.execute("UPDATE containers SET build_status = 'provided'")


def downgrade():
    op.drop_column("containers", "build_status")
