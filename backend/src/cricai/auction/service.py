import hashlib
import secrets
from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from cricai.auction.domain import (
    AuctionError,
    AuctionState,
    Command,
    Player,
    RuleConfig,
    Team,
    execute,
    recover,
    require,
    tick,
    validate_setup,
)
from cricai.db import (
    AuctionRow,
    DataSnapshot,
    EventRow,
    ParticipantRow,
    PurchaseRow,
    RequestRow,
    SnapshotPlayer,
)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def database_time(session: Session) -> datetime:
    return session.execute(select(func.clock_timestamp())).scalar_one()  # type: ignore[no-any-return]


class AuctionService:
    def __init__(self, engine: Engine, allow_test_data: bool = False):
        self.engine = engine
        self.allow_test_data = allow_test_data

    def create(self, snapshot_id: str, franchises: list[str], rules: RuleConfig) -> dict[str, Any]:
        with Session(self.engine) as session, session.begin():
            snapshot = session.get(DataSnapshot, snapshot_id)
            require(snapshot is not None, "snapshot_not_found")
            assert snapshot is not None
            require(
                self.allow_test_data or not snapshot.manifest["test_data"], "test_data_disabled"
            )
            players = [
                Player.model_validate(row.data)
                for row in session.scalars(
                    select(SnapshotPlayer)
                    .where(SnapshotPlayer.snapshot_id == snapshot_id)
                    .order_by(SnapshotPlayer.position)
                )
            ]
            available = {player.franchise for player in players}
            require(all(name in available for name in franchises), "unknown_franchise")
            if not snapshot.manifest["test_data"]:
                require(len(franchises) == 10, "standard_requires_ten_franchises")
                require(rules == RuleConfig(), "standard_rules_fixed")
            state = AuctionState(
                id=str(uuid4()),
                snapshot_id=snapshot_id,
                season=snapshot.manifest["season"],
                test_data=snapshot.manifest["test_data"],
                rules=rules,
                players=players,
                teams=[Team(id=str(uuid4()), name=name, purse=rules.purse) for name in franchises],
            )
            validate_setup(state)
            row = AuctionRow(
                id=state.id,
                snapshot_id=snapshot_id,
                state=state.model_dump(mode="json"),
                version=0,
                phase=state.phase,
                deadline=None,
            )
            session.add(row)
            session.flush()
            credentials = []
            for index, team in enumerate(state.teams):
                token = secrets.token_urlsafe(32)
                session.add(
                    ParticipantRow(
                        auction_id=state.id,
                        team_id=team.id,
                        token_hash=digest(token),
                        host=index == 0,
                        purse=team.purse,
                    )
                )
                credentials.append(
                    {"team_id": team.id, "name": team.name, "host": index == 0, "token": token}
                )
            return {"auction_id": state.id, "participants": credentials}

    def participant(self, session: Session, auction_id: str, token: str) -> ParticipantRow:
        actor = session.scalar(
            select(ParticipantRow).where(
                ParticipantRow.auction_id == auction_id, ParticipantRow.token_hash == digest(token)
            )
        )
        if actor is None:
            raise AuctionError("unauthorized")
        return actor

    def snapshot(self, auction_id: str, token: str) -> dict[str, Any]:
        with Session(self.engine) as session:
            actor = self.participant(session, auction_id, token)
            row = session.get(AuctionRow, auction_id)
            assert row is not None
            state = AuctionState.model_validate(row.state)
            require(self.allow_test_data or not state.test_data, "test_data_disabled")
            return self.envelope(state, database_time(session), actor)

    @staticmethod
    def envelope(state: AuctionState, now: datetime, actor: ParticipantRow) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "server_now": now.isoformat(),
            "state": state.model_dump(mode="json"),
            "next_bid": state.next_bid,
            "team_id": actor.team_id,
            "host": actor.host,
        }

    def command(
        self, auction_id: str, token: str, request_id: str, command: Command
    ) -> dict[str, Any]:
        with Session(self.engine) as session, session.begin():
            actor = self.participant(session, auction_id, token)
            row = session.scalar(
                select(AuctionRow).where(AuctionRow.id == auction_id).with_for_update()
            )
            assert row is not None
            payload_hash = digest(command.model_dump_json())
            previous = session.get(RequestRow, (auction_id, actor.team_id, request_id))
            if previous is not None:
                require(previous.payload_hash == payload_hash, "request_id_reused")
                return previous.result
            state = AuctionState.model_validate(row.state)
            require(self.allow_test_data or not state.test_data, "test_data_disabled")
            now = database_time(session)
            updated = execute(state, command, actor.team_id, actor.host, now)
            self.persist(session, row, state, updated, command.kind, actor.team_id, now)
            result = self.envelope(updated, now, actor)
            session.add(
                RequestRow(
                    auction_id=auction_id,
                    actor=actor.team_id,
                    request_id=request_id,
                    payload_hash=payload_hash,
                    result=result,
                )
            )
            return result

    @staticmethod
    def persist(
        session: Session,
        row: AuctionRow,
        before: AuctionState,
        after: AuctionState,
        kind: str,
        actor: str | None,
        now: datetime,
    ) -> None:
        row.state = after.model_dump(mode="json")
        row.version = after.version
        row.phase = after.phase
        row.deadline = after.deadline
        for purchase in after.purchases[len(before.purchases) :]:
            session.add(PurchaseRow(auction_id=after.id, **purchase.model_dump()))
        for team in after.teams:
            participant = session.get(ParticipantRow, (after.id, team.id))
            assert participant is not None
            participant.purse = team.purse
        player = after.current_player
        session.add(
            EventRow(
                auction_id=after.id,
                version=after.version,
                kind=kind,
                actor=actor,
                at=now,
                data={
                    "phase": after.phase,
                    "player_id": player.id if player else None,
                    "amount": after.current_bid,
                    "leading_team_id": after.leading_team_id,
                    "deadline": after.deadline.isoformat() if after.deadline else None,
                },
            )
        )

    def advance(self, recovering: bool = False) -> int:
        changed = 0
        with Session(self.engine) as session, session.begin():
            query = select(AuctionRow).where(AuctionRow.deadline.is_not(None))
            if not recovering:
                query = query.where(AuctionRow.deadline <= func.clock_timestamp())
            rows = session.scalars(
                query.order_by(AuctionRow.id).with_for_update(skip_locked=True).limit(100)
            )
            for row in rows:
                before = AuctionState.model_validate(row.state)
                now = database_time(session)
                after = recover(before, now) if recovering else tick(before, now)
                if after.version != before.version:
                    self.persist(
                        session,
                        row,
                        before,
                        after,
                        "recovery" if recovering else "timer",
                        None,
                        now,
                    )
                    changed += 1
        return changed

    def history(self, auction_id: str, token: str, after_version: int) -> list[dict[str, Any]]:
        with Session(self.engine) as session:
            self.participant(session, auction_id, token)
            rows = session.scalars(
                select(EventRow)
                .where(EventRow.auction_id == auction_id, EventRow.version > after_version)
                .order_by(EventRow.version)
                .limit(200)
            )
            return [
                {
                    "version": row.version,
                    "kind": row.kind,
                    "actor": row.actor,
                    "at": row.at.isoformat(),
                    **row.data,
                }
                for row in rows
            ]
