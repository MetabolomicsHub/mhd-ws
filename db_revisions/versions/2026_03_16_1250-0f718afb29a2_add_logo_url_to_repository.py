"""add logo_url to repository

Revision ID: 0f718afb29a2
Revises: 9940b74caeda
Create Date: 2026-03-16 12:50:39.990378

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0f718afb29a2"
down_revision: Union[str, None] = "9940b74caeda"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("repository", sa.Column("logo_url", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("repository", "logo_url")
