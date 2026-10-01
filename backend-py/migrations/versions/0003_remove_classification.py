"""Remove ML prediction and review fields from tickets.

Revision ID: 0003_remove_classification
Revises: 0002_ticket_classification
Create Date: 2026-10-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_remove_classification"
down_revision: Union[str, None] = "0002_ticket_classification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("tickets", "category_corrected_at")
    op.drop_column("tickets", "category_reviewed_at")
    op.drop_column("tickets", "prediction_confidence")
    op.drop_column("tickets", "predicted_category")


def downgrade() -> None:
    op.add_column("tickets", sa.Column("predicted_category", sa.String(length=40), nullable=True))
    op.add_column("tickets", sa.Column("prediction_confidence", sa.Float(), nullable=True))
    op.add_column(
        "tickets",
        sa.Column("category_reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("category_corrected_at", sa.DateTime(timezone=True), nullable=True),
    )