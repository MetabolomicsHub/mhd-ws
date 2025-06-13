"""initial revision

Revision ID: 1a8c5681a323
Revises:
Create Date: 2025-04-15 17:15:04.335356

"""

import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import MetaData, Table
from sqlalchemy.schema import CreateSequence

# revision identifiers, used by Alembic.
revision: str = "1a8c5681a323"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    unique_identifier_seq = sa.schema.Sequence("unique_identifier_seq")
    op.execute(CreateSequence(unique_identifier_seq))
    create_identifier_table(unique_identifier_seq)
    create_repository_table(unique_identifier_seq)
    create_api_token_table(unique_identifier_seq)
    create_dataset_table(unique_identifier_seq)
    create_annoucement_file_table(unique_identifier_seq)
    create_dataset_revision_table(unique_identifier_seq)


def downgrade() -> None:
    """Downgrade schema."""
    e_identifier_seq = Sequence("unique_identifier_seq")
    op.drop_table("dataset_revision", if_exists=True)
    op.drop_table("annoucement_file", if_exists=True)
    op.drop_table("dataset", if_exists=True)
    op.drop_table("api_token", if_exists=True)
    op.drop_table("repository", if_exists=True)
    op.drop_table("identifier", if_exists=True)
    op.execute(sa.schema.DropSequence(e_identifier_seq))


def create_repository_table(unique_identifier_seq: sa.schema.Sequence):
    op.create_table(
        "repository",
        sa.Column(
            "id",
            sa.Integer,
            unique_identifier_seq,
            primary_key=True,
            unique=True,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("short_name", sa.String(255), nullable=False, index=True),
        sa.Column("description", sa.String(512), nullable=False),
        sa.Column(
            "join_datetime",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("status", sa.Integer, nullable=False, default=0),
        sa.Column("public_key", sa.String(2028), unique=False, nullable=True),
        if_not_exists=True,
    )

    meta = MetaData()
    repository = Table("repository", meta, autoload_with=op.get_bind())

    op.bulk_insert(
        repository,
        [
            {
                "id": 1,
                "name": "MetaboLights",
                "short_name": "mtbls",
                "description": "MetaboLights",
                "join_datetime": datetime.datetime.fromisoformat(
                    "2025-06-10T00:00:00Z"
                ),
                "status": 1,
            },
            {
                "id": 2,
                "name": "Metabolomics Workbench",
                "short_name": "mw",
                "description": "Metabolomics Workbench",
                "join_datetime": datetime.datetime.fromisoformat(
                    "2025-06-10T00:00:00Z"
                ),
                "status": 1,
            },
            {
                "id": 3,
                "name": "GNPS",
                "short_name": "gnps",
                "description": "GNPS",
                "join_datetime": datetime.datetime.fromisoformat(
                    "2025-06-10T00:00:00Z"
                ),
                "status": 1,
            },
        ],
        multiinsert=False,
    )


def create_api_token_table(unique_identifier_seq: sa.schema.Sequence):
    op.create_table(
        "api_token",
        sa.Column(
            "id",
            sa.Integer,
            unique_identifier_seq,
            primary_key=True,
            unique=True,
            index=True,
        ),
        sa.Column(
            "repository_id",
            sa.Integer(),
            sa.ForeignKey("repository.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False, unique=False),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column("token_hash", sa.String(512), unique=True, nullable=False),
        sa.Column("expiration_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Integer, nullable=False, default=0),
        sa.UniqueConstraint("name", "repository_id", name="uq_api_token_name"),
        if_not_exists=True,
    )


def create_identifier_table(unique_identifier_seq: sa.schema.Sequence):
    op.create_table(
        "identifier",
        sa.Column(
            "id",
            sa.Integer,
            unique_identifier_seq,
            primary_key=True,
            unique=True,
            index=True,
        ),
        sa.Column("prefix", sa.String(255), nullable=False, unique=True),
        sa.Column("last_identifier", sa.Integer, nullable=False, default=1),
        if_not_exists=True,
    )

    meta = MetaData()
    identifier = Table("identifier", meta, autoload_with=op.get_bind())

    op.bulk_insert(
        identifier,
        [
            {"id": 1, "prefix": "mhd", "last_identifier": 0},
            {"id": 2, "prefix": "mhd_test", "last_identifier": 0},
        ],
        multiinsert=False,
    )


def create_dataset_table(unique_identifier_seq: sa.schema.Sequence):
    op.create_table(
        "dataset",
        sa.Column(
            "id",
            sa.Integer,
            unique_identifier_seq,
            primary_key=True,
            unique=True,
        ),
        sa.Column("accession", sa.String(255), nullable=False, unique=True, index=True),
        sa.Column("dataset_repository_identifier", sa.String(255), nullable=False),
        sa.Column(
            "repository_id",
            sa.Integer,
            sa.ForeignKey("repository.id", name="dataset_repository_id_fkey"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer, nullable=True),
        sa.Column("revision_datetime", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Integer, nullable=False, default=0),
        sa.UniqueConstraint(
            "repository_id",
            "dataset_repository_identifier",
            name="uq_dataset_repository_identifier",
        ),
        if_not_exists=True,
    )


def create_annoucement_file_table(unique_identifier_seq: sa.schema.Sequence):
    op.create_table(
        "announcement_file",
        sa.Column(
            "id",
            sa.Integer,
            unique_identifier_seq,
            primary_key=True,
            unique=True,
            index=True,
        ),
        sa.Column(
            "dataset_id", sa.Integer, sa.ForeignKey("dataset.id"), nullable=False
        ),
        sa.Column("file", sa.JSON, nullable=False),
        sa.Column("hash_sha256", sa.String(512), nullable=False),
        sa.Column("schema_uri", sa.String(2048), nullable=False),
        sa.Column("profile_uri", sa.String(2048), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        if_not_exists=True,
    )


def create_dataset_revision_table(unique_identifier_seq: sa.schema.Sequence):

    op.create_table(
        "dataset_revision",
        sa.Column(
            "id",
            sa.Integer,
            unique_identifier_seq,
            primary_key=True,
            unique=True,
            index=True,
        ),
        sa.Column(
            "dataset_id", sa.Integer, sa.ForeignKey("dataset.id"), nullable=False
        ),
        sa.Column("task_id", sa.String(512), nullable=False),
        sa.Column("revision", sa.Integer, nullable=False, default=1),
        sa.Column(
            "revision_datetime", sa.DateTime(timezone=True), nullable=False, default=1
        ),
        sa.Column("repository_revision", sa.Integer, nullable=True),
        sa.Column(
            "repository_revision_datetime", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("status", sa.Integer, nullable=False, default=0),
        sa.Column("description", sa.String(512), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "file_id", sa.Integer, sa.ForeignKey("announcement_file.id"), nullable=False
        ),
        sa.UniqueConstraint(
            "dataset_id",
            "revision",
            name="uq_dataset_id_revision",
        ),
        if_not_exists=True,
    )
