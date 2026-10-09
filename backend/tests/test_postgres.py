from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_domain import fixture_state

from cricai.auction.domain import AuctionError, AuctionState, Command, Phase, RuleConfig
from cricai.auction.service import AuctionService
from cricai.db import AuctionRow, EventRow, ParticipantRow, PurchaseRow
from cricai.players.ingestion import Manifest, PlayerImport, publish

pytestmark = pytest.mark.postgres


def provision(database: Engine) -> tuple[AuctionService, str, list[dict[str, str]]]:
    fixture = fixture_state()
    with Session(database) as session, session.begin():
        snapshot = publish(
            session,
            PlayerImport(
                manifest=Manifest(
                    season="TEST ONLY",
                    source_url="https://example.invalid/tests",
                    license="Synthetic fixtures",
                    permission_basis="Original test data only",
                    retrieved_at=datetime.now(UTC),
                    coverage="synthetic",
                    test_data=True,
                ),
                players=fixture.players,
            ),
            allow_test_data=True,
        )
    service = AuctionService(database, allow_test_data=True)
    created = service.create(snapshot, ["Test Alpha", "Test Beta"], RuleConfig(minimum_squad=0))
    return service, created["auction_id"], created["participants"]


def activate(database: Engine, auction_id: str) -> None:
    with Session(database) as session, session.begin():
        row = session.get(AuctionRow, auction_id)
        state = AuctionState.model_validate(row.state)
        state.phase = Phase.BIDDING
        state.deadline = datetime.now(UTC) + timedelta(seconds=15)
        row.state = state.model_dump(mode="json")
        row.phase = state.phase
        row.deadline = state.deadline


def expire(database: Engine, auction_id: str) -> None:
    with Session(database) as session, session.begin():
        row = session.get(AuctionRow, auction_id)
        state = AuctionState.model_validate(row.state)
        state.deadline = datetime.now(UTC) - timedelta(seconds=1)
        row.deadline = state.deadline
        row.state = state.model_dump(mode="json")


def test_conflicting_bids_and_duplicate_sale(database: Engine) -> None:
    service, auction_id, actors = provision(database)
    activate(database, auction_id)
    command = Command(kind="bid", expected_version=0, player_id="test-one", amount=2_000_000)

    def compete(token: str) -> str:
        try:
            service.command(auction_id, token, str(uuid4()), command)
            return "accepted"
        except AuctionError as error:
            return error.code

    with ThreadPoolExecutor(2) as executor:
        results = list(executor.map(compete, [actor["token"] for actor in actors]))
    assert sorted(results) == ["accepted", "stale_version"]
    expire(database, auction_id)
    with ThreadPoolExecutor(2) as executor:
        list(executor.map(lambda _: service.advance(), range(2)))
    with Session(database) as session:
        assert session.scalar(select(func.count()).select_from(PurchaseRow)) == 1
        purses = list(session.scalars(select(ParticipantRow.purse)))
        assert sum(purses) == 2_000_000_000 - 2_000_000
        assert min(purses) >= 0
        assert session.scalar(select(func.count()).select_from(EventRow)) == 2


def test_idempotent_bid_and_altered_retry(database: Engine) -> None:
    service, auction_id, actors = provision(database)
    activate(database, auction_id)
    request_id = str(uuid4())
    command = Command(kind="bid", expected_version=0, player_id="test-one", amount=2_000_000)
    first = service.command(auction_id, actors[0]["token"], request_id, command)
    second = service.command(auction_id, actors[0]["token"], request_id, command)
    assert first == second
    altered = command.model_copy(update={"amount": 3_000_000})
    with pytest.raises(AuctionError, match="request_id_reused"):
        service.command(auction_id, actors[0]["token"], request_id, altered)
    assert service.snapshot(auction_id, actors[0]["token"])["state"]["version"] == 1


def test_capability_bound_to_auction_and_purse_constraint(database: Engine) -> None:
    service, auction_id, actors = provision(database)
    with pytest.raises(AuctionError, match="unauthorized"):
        service.snapshot(auction_id, "not-a-capability")
    with pytest.raises(IntegrityError), Session(database) as session, session.begin():
        actor = session.get(ParticipantRow, (auction_id, actors[0]["team_id"]))
        actor.purse = -1
        session.flush()


def test_restart_retains_bid_and_recovery_pauses(database: Engine) -> None:
    service, auction_id, actors = provision(database)
    activate(database, auction_id)
    service.command(
        auction_id,
        actors[0]["token"],
        str(uuid4()),
        Command(kind="bid", expected_version=0, player_id="test-one", amount=2_000_000),
    )
    restarted = AuctionService(database, allow_test_data=True)
    assert restarted.advance(recovering=True) == 1
    recovered = restarted.snapshot(auction_id, actors[0]["token"])["state"]
    assert recovered["phase"] == "paused"
    assert recovered["current_bid"] == 2_000_000
    assert recovered["deadline"] is None


def test_production_service_rejects_test_snapshot(database: Engine) -> None:
    service, auction_id, actors = provision(database)
    snapshot = service.snapshot(auction_id, actors[0]["token"])["state"]["snapshot_id"]
    with pytest.raises(AuctionError, match="test_data_disabled"):
        AuctionService(database).create(
            snapshot, ["Test Alpha", "Test Beta"], RuleConfig(minimum_squad=0)
        )
