"""Add accession_type column to dataset table

Revision ID: 9940b74caeda
Revises: 1a8c5681a323
Create Date: 2026-01-23 21:51:52.620605

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9940b74caeda"
down_revision: Union[str, None] = "1a8c5681a323"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "dataset",
        sa.Column("accession_type", sa.String(), nullable=False, server_default="mhd"),
    )
    op.execute(
        "UPDATE dataset SET accession_type = 'test' WHERE accession LIKE 'MHDT%'"
    )
    op.execute("UPDATE dataset SET accession_type = 'dev' WHERE accession LIKE 'MHDD%'")
    op.execute(
        "UPDATE dataset SET accession_type = 'legacy' WHERE accession NOT LIKE 'MHD%'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("dataset", "accession_type")
