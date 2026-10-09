from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DataSnapshot(Base):
    __tablename__ = "data_snapshots"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PlayerIdentity(Base):
    __tablename__ = "player_identities"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)


class SnapshotPlayer(Base):
    __tablename__ = "snapshot_players"
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("data_snapshots.id"), primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("player_identities.id"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    __table_args__ = (UniqueConstraint("snapshot_id", "position"),)


class AuctionRow(Base):
    __tablename__ = "auctions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("data_snapshots.id"))
    state: Mapped[dict[str, Any]] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(Integer)
    phase: Mapped[str] = mapped_column(String(30))
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    __table_args__ = (CheckConstraint("version >= 0"),)


class ParticipantRow(Base):
    __tablename__ = "participants"
    auction_id: Mapped[str] = mapped_column(ForeignKey("auctions.id"), primary_key=True)
    team_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    host: Mapped[bool] = mapped_column(Boolean)
    purse: Mapped[int] = mapped_column(BigInteger)
    __table_args__ = (CheckConstraint("purse >= 0"),)


class PurchaseRow(Base):
    __tablename__ = "purchases"
    auction_id: Mapped[str] = mapped_column(ForeignKey("auctions.id"), primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("player_identities.id"), primary_key=True)
    team_id: Mapped[str] = mapped_column(String(100))
    amount: Mapped[int] = mapped_column(BigInteger)
    __table_args__ = (
        ForeignKeyConstraint(
            ["auction_id", "team_id"], ["participants.auction_id", "participants.team_id"]
        ),
        CheckConstraint("amount > 0"),
    )


class EventRow(Base):
    __tablename__ = "auction_events"
    auction_id: Mapped[str] = mapped_column(ForeignKey("auctions.id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(40))
    actor: Mapped[str | None] = mapped_column(String(100))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)


class RequestRow(Base):
    __tablename__ = "command_requests"
    auction_id: Mapped[str] = mapped_column(ForeignKey("auctions.id"), primary_key=True)
    actor: Mapped[str] = mapped_column(String(100), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    result: Mapped[dict[str, Any]] = mapped_column(JSONB)


def make_engine(url: str) -> Engine:
    if not url.startswith("postgresql+psycopg://"):
        raise ValueError("Configure CRICAI_DATABASE_URL with postgresql+psycopg://")
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 5})
