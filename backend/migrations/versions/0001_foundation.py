"""Immutable data snapshots and authoritative auction persistence."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_snapshots",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("manifest", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table("player_identities", sa.Column("id", sa.String(100), primary_key=True))
    op.create_table(
        "snapshot_players",
        sa.Column(
            "snapshot_id", sa.String(64), sa.ForeignKey("data_snapshots.id"), primary_key=True
        ),
        sa.Column(
            "player_id", sa.String(100), sa.ForeignKey("player_identities.id"), primary_key=True
        ),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("data", JSONB, nullable=False),
        sa.UniqueConstraint("snapshot_id", "position"),
    )
    op.create_table(
        "auctions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("snapshot_id", sa.String(64), sa.ForeignKey("data_snapshots.id"), nullable=False),
        sa.Column("state", JSONB, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("phase", sa.String(30), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True)),
        sa.CheckConstraint("version >= 0"),
    )
    op.create_index("ix_auctions_deadline", "auctions", ["deadline"])
    op.create_table(
        "participants",
        sa.Column("auction_id", sa.String(36), sa.ForeignKey("auctions.id"), primary_key=True),
        sa.Column("team_id", sa.String(100), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("host", sa.Boolean, nullable=False),
        sa.Column("purse", sa.BigInteger, nullable=False),
        sa.CheckConstraint("purse >= 0"),
    )
    op.create_table(
        "purchases",
        sa.Column("auction_id", sa.String(36), sa.ForeignKey("auctions.id"), primary_key=True),
        sa.Column(
            "player_id", sa.String(100), sa.ForeignKey("player_identities.id"), primary_key=True
        ),
        sa.Column("team_id", sa.String(100), nullable=False),
        sa.Column("amount", sa.BigInteger, nullable=False),
        sa.ForeignKeyConstraint(
            ["auction_id", "team_id"], ["participants.auction_id", "participants.team_id"]
        ),
        sa.CheckConstraint("amount > 0"),
    )
    op.create_table(
        "auction_events",
        sa.Column("auction_id", sa.String(36), sa.ForeignKey("auctions.id"), primary_key=True),
        sa.Column("version", sa.Integer, primary_key=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("actor", sa.String(100)),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data", JSONB, nullable=False),
    )
    op.create_table(
        "command_requests",
        sa.Column("auction_id", sa.String(36), sa.ForeignKey("auctions.id"), primary_key=True),
        sa.Column("actor", sa.String(100), primary_key=True),
        sa.Column("request_id", sa.String(36), primary_key=True),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("result", JSONB, nullable=False),
    )


def downgrade() -> None:
    for table in (
        "command_requests",
        "auction_events",
        "purchases",
        "participants",
        "auctions",
        "snapshot_players",
        "player_identities",
        "data_snapshots",
    ):
        op.drop_table(table)
