from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from cricai.auction.domain import (
    AuctionError,
    AuctionState,
    Command,
    Phase,
    Player,
    RuleConfig,
    Team,
    execute,
    recover,
    tick,
    validate_setup,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def fixture_state() -> AuctionState:
    return AuctionState(
        id="synthetic-auction",
        snapshot_id="synthetic-snapshot",
        season="TEST ONLY",
        test_data=True,
        rules=RuleConfig(minimum_squad=0),
        teams=[
            Team(id="alpha", name="Test Alpha", purse=1_000_000_000),
            Team(id="beta", name="Test Beta", purse=1_000_000_000),
        ],
        players=[
            Player(
                id="test-one",
                name="Synthetic Player One",
                role="batter",
                nationality="Test country",
                overseas=False,
                franchise="Test Alpha",
            ),
            Player(
                id="test-two",
                name="Synthetic Player Two",
                role="bowler",
                nationality="Test country",
                overseas=True,
                franchise="Test Beta",
            ),
        ],
    )


def active() -> AuctionState:
    state = fixture_state()
    state = execute(state, Command(kind="start", expected_version=0), "alpha", True, NOW)
    return tick(state, NOW + timedelta(seconds=2))


def bid(
    state: AuctionState, actor: str = "alpha", seconds: float = 5, **overrides: object
) -> AuctionState:
    payload = {
        "kind": "bid",
        "expected_version": state.version,
        "player_id": "test-one",
        "amount": state.next_bid,
        **overrides,
    }
    return execute(
        state, Command.model_validate(payload), actor, False, NOW + timedelta(seconds=seconds)
    )


def test_bid_resets_and_sale_debits_once() -> None:
    state = active()
    updated = bid(state)
    assert state.current_bid == 0
    assert updated.deadline == NOW + timedelta(seconds=20)
    assert updated.teams[0].purse == 1_000_000_000
    sold = tick(updated, NOW + timedelta(seconds=20))
    assert sold.phase == Phase.SOLD
    assert sold.teams[0].purse == 998_000_000
    assert len(sold.purchases) == 1
    assert tick(sold, NOW + timedelta(seconds=20)) is sold
    next_lot = tick(sold, NOW + timedelta(seconds=22))
    assert next_lot.current_player.id == "test-two"
    assert len(next_lot.purchases) == 1


@pytest.mark.parametrize("seconds", [17, 17.001, 100])
def test_at_and_after_deadline_is_rejected(seconds: float) -> None:
    with pytest.raises(AuctionError, match="lot_expired"):
        bid(active(), seconds=seconds)


@pytest.mark.parametrize(
    "payload,code",
    [
        ({"amount": 2_000_001}, "invalid_increment"),
        ({"expected_version": 0}, "stale_version"),
        ({"player_id": "test-two"}, "stale_player"),
    ],
)
def test_bad_bid_cannot_mutate_state(payload: dict[str, object], code: str) -> None:
    state = active()
    before = state.model_dump_json()
    with pytest.raises(AuctionError, match=code):
        bid(state, **payload)
    assert state.model_dump_json() == before


def test_repeated_leader_cannot_bid() -> None:
    with pytest.raises(AuctionError, match="already_leading"):
        bid(bid(active()), seconds=6)


def test_over_budget_and_overseas_rejected() -> None:
    state = active()
    state.teams[0].purse = 1
    with pytest.raises(AuctionError, match="insufficient_purse"):
        bid(state)
    state.teams[0].purse = 1_000_000_000
    state.players[0].overseas = True
    state.rules.overseas_limit = 0
    with pytest.raises(AuctionError, match="overseas_limit"):
        bid(state)


def test_pause_resume_and_recovery_preserve_interval() -> None:
    state = bid(active())
    paused = execute(
        state,
        Command(kind="pause", expected_version=state.version),
        "alpha",
        True,
        NOW + timedelta(seconds=10),
    )
    assert paused.remaining_seconds == 10
    assert tick(paused, NOW + timedelta(days=1)) is paused
    resumed = execute(
        paused,
        Command(kind="resume", expected_version=paused.version),
        "alpha",
        True,
        NOW + timedelta(seconds=100),
    )
    assert resumed.deadline == NOW + timedelta(seconds=110)
    recovered = recover(resumed, NOW + timedelta(seconds=200))
    assert recovered.phase == Phase.PAUSED
    assert recovered.remaining_seconds == 0
    resumed = execute(
        recovered,
        Command(kind="resume", expected_version=recovered.version),
        "alpha",
        True,
        NOW + timedelta(seconds=201),
    )
    with pytest.raises(AuctionError, match="lot_expired"):
        bid(resumed, "beta", seconds=201)
    assert tick(resumed, NOW + timedelta(seconds=201)).phase == Phase.SOLD


def test_unsold_pool_completes_without_invented_squad() -> None:
    state = active()
    for seconds in [17, 19, 21, 36, 38]:
        state = tick(state, NOW + timedelta(seconds=seconds))
    assert state.phase == Phase.COMPLETED
    assert state.unsold == ["test-one", "test-two"]
    assert state.purchases == []


def test_cancellation_and_host_authorization() -> None:
    state = active()
    with pytest.raises(AuctionError, match="host_required"):
        execute(state, Command(kind="cancel", expected_version=state.version), "beta", False, NOW)
    cancelled = execute(
        state, Command(kind="cancel", expected_version=state.version), "alpha", True, NOW
    )
    with pytest.raises(AuctionError, match="auction_finished"):
        bid(cancelled)


@pytest.mark.parametrize("amount", [-1, 0, 1.5, True, "2000000", 10**13])
def test_money_is_strict_positive_integer(amount: object) -> None:
    with pytest.raises(ValidationError):
        Command.model_validate({"kind": "bid", "expected_version": 0, "amount": amount})


def test_pool_validation() -> None:
    state = fixture_state()
    state.players.append(state.players[0])
    with pytest.raises(AuctionError, match="duplicate_player"):
        validate_setup(state)
    state = fixture_state()
    state.rules.minimum_squad = 11
    with pytest.raises(AuctionError, match="insufficient_pool"):
        validate_setup(state)
