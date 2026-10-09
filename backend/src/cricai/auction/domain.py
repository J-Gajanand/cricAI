from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator

Money = Annotated[StrictInt, Field(ge=0, le=10**12)]
PositiveMoney = Annotated[StrictInt, Field(gt=0, le=10**12)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RuleConfig(Model):
    version: str = "foundation-v1"
    purse: PositiveMoney = 1_000_000_000
    increment: PositiveMoney = 1_000_000
    interval_seconds: Annotated[StrictInt, Field(ge=1, le=120)] = 15
    presentation_seconds: Annotated[StrictInt, Field(ge=1, le=30)] = 2
    squad_limit: Annotated[StrictInt, Field(ge=1, le=25)] = 12
    minimum_squad: Annotated[StrictInt, Field(ge=0, le=25)] = 11
    overseas_limit: Annotated[StrictInt, Field(ge=0, le=25)] = 4
    max_teams: Annotated[StrictInt, Field(ge=2, le=10)] = 10

    @model_validator(mode="after")
    def compatible_limits(self) -> "RuleConfig":
        if self.minimum_squad > self.squad_limit or self.overseas_limit > self.squad_limit:
            raise ValueError("Composition limits must fit the squad limit")
        return self


class Statistics(Model):
    matches: Annotated[StrictInt, Field(ge=0)] | None = None
    runs: Annotated[StrictInt, Field(ge=0)] | None = None
    wickets: Annotated[StrictInt, Field(ge=0)] | None = None
    coverage: str = "not_available"


class Player(Model):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=120)
    role: Literal["batter", "bowler", "all_rounder", "wicketkeeper"]
    nationality: str = Field(min_length=2, max_length=80)
    overseas: StrictBool
    eligible: StrictBool = True
    base_price: PositiveMoney = 2_000_000
    price_basis: Literal["game_configured", "verified_official"] = "game_configured"
    franchise: str = Field(min_length=1, max_length=100)
    statistics: Statistics = Field(default_factory=Statistics)


class Team(Model):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    purse: Money


class Purchase(Model):
    player_id: str
    team_id: str
    amount: PositiveMoney


class Phase(StrEnum):
    LOBBY = "lobby"
    MARQUEE = "marquee_selection"
    INITIALIZING = "initializing"
    PRESENTATION = "presentation"
    BIDDING = "bidding"
    SOLD = "sold"
    UNSOLD = "unsold"
    UNSOLD_ROUND = "unsold_round"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AuctionState(Model):
    id: str
    snapshot_id: str
    season: str
    test_data: bool = False
    rules: RuleConfig
    teams: list[Team]
    players: list[Player]
    phase: Phase = Phase.LOBBY
    version: int = 0
    lot_index: int = 0
    round_number: int = 1
    deadline: datetime | None = None
    leading_team_id: str | None = None
    current_bid: Money = 0
    purchases: list[Purchase] = Field(default_factory=list)
    unsold: list[str] = Field(default_factory=list)
    previous_phase: Phase | None = None
    remaining_seconds: float | None = None

    @property
    def current_player(self) -> Player | None:
        if self.lot_index >= len(self.players) or self.phase in (Phase.COMPLETED, Phase.CANCELLED):
            return None
        return self.players[self.lot_index]

    @property
    def next_bid(self) -> int | None:
        player = self.current_player
        if player is None:
            return None
        return (
            player.base_price
            if self.leading_team_id is None
            else (self.current_bid + self.rules.increment)
        )


class Command(Model):
    kind: Literal["start", "bid", "pause", "resume", "cancel"]
    expected_version: Annotated[StrictInt, Field(ge=0)]
    player_id: str | None = None
    amount: PositiveMoney | None = None


class AuctionError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def require(condition: bool, code: str) -> None:
    if not condition:
        raise AuctionError(code)


def validate_setup(state: AuctionState) -> None:
    rules = state.rules
    require(2 <= len(state.teams) <= rules.max_teams, "invalid_team_count")
    require(len({team.id for team in state.teams}) == len(state.teams), "duplicate_team")
    require(len({team.name for team in state.teams}) == len(state.teams), "duplicate_franchise")
    require(all(team.purse == rules.purse for team in state.teams), "invalid_initial_purse")
    require(bool(state.players), "empty_pool")
    require(len({player.id for player in state.players}) == len(state.players), "duplicate_player")
    require(all(player.eligible for player in state.players), "ineligible_pool")
    require(all(player.base_price <= rules.purse for player in state.players), "unaffordable_pool")
    require(len(state.players) >= len(state.teams) * rules.minimum_squad, "insufficient_pool")
    domestic_needed = max(0, rules.minimum_squad - rules.overseas_limit) * len(state.teams)
    require(
        sum(not player.overseas for player in state.players) >= domestic_needed,
        "insufficient_domestic_pool",
    )
    if rules.minimum_squad >= 11:
        require(
            sum(player.role == "wicketkeeper" for player in state.players) >= len(state.teams),
            "insufficient_keepers",
        )


def execute(
    state: AuctionState, command: Command, team_id: str, host: bool, now: datetime
) -> AuctionState:
    require(now.tzinfo is not None, "timezone_required")
    require(any(team.id == team_id for team in state.teams), "unknown_participant")
    require(command.expected_version == state.version, "stale_version")
    require(state.phase not in (Phase.COMPLETED, Phase.CANCELLED), "auction_finished")
    updated = state.model_copy(deep=True)
    if command.kind == "bid":
        place_bid(updated, command, team_id, now)
    else:
        require(host, "host_required")
        if command.kind == "start":
            require(state.phase == Phase.LOBBY, "invalid_transition")
            validate_setup(state)
            updated.phase = Phase.PRESENTATION
            updated.deadline = now + timedelta(seconds=state.rules.presentation_seconds)
        elif command.kind == "pause":
            require(
                state.phase in (Phase.PRESENTATION, Phase.BIDDING, Phase.SOLD, Phase.UNSOLD),
                "invalid_transition",
            )
            require(state.deadline is not None and now < state.deadline, "lot_expired")
            assert state.deadline is not None
            updated.previous_phase = state.phase
            updated.remaining_seconds = (state.deadline - now).total_seconds()
            updated.phase = Phase.PAUSED
            updated.deadline = None
        elif command.kind == "resume":
            require(
                state.phase == Phase.PAUSED and state.previous_phase is not None,
                "invalid_transition",
            )
            assert state.previous_phase is not None
            updated.phase = state.previous_phase
            updated.deadline = now + timedelta(seconds=state.remaining_seconds or 0)
            updated.previous_phase = None
            updated.remaining_seconds = None
        elif command.kind == "cancel":
            updated.phase = Phase.CANCELLED
            updated.deadline = None
            updated.leading_team_id = None
            updated.current_bid = 0
    updated.version += 1
    return updated


def place_bid(state: AuctionState, command: Command, team_id: str, now: datetime) -> None:
    require(state.phase == Phase.BIDDING, "bidding_closed")
    require(state.deadline is not None and now < state.deadline, "lot_expired")
    player = state.current_player
    require(player is not None and command.player_id == player.id, "stale_player")
    assert player is not None
    require(player.eligible, "ineligible_player")
    require(not any(item.player_id == player.id for item in state.purchases), "already_owned")
    require(state.leading_team_id != team_id, "already_leading")
    require(command.amount == state.next_bid, "invalid_increment")
    assert command.amount is not None
    team = next(team for team in state.teams if team.id == team_id)
    squad_ids = {item.player_id for item in state.purchases if item.team_id == team_id}
    require(len(squad_ids) < state.rules.squad_limit, "squad_full")
    overseas = sum(member.overseas for member in state.players if member.id in squad_ids)
    require(not player.overseas or overseas < state.rules.overseas_limit, "overseas_limit")
    remaining_slots = max(0, state.rules.minimum_squad - len(squad_ids) - 1)
    reserve = remaining_slots * min(member.base_price for member in state.players)
    require(command.amount + reserve <= team.purse, "insufficient_purse")
    state.current_bid = command.amount
    state.leading_team_id = team_id
    state.deadline = now + timedelta(seconds=state.rules.interval_seconds)


def tick(state: AuctionState, now: datetime) -> AuctionState:
    require(now.tzinfo is not None, "timezone_required")
    if state.deadline is None or now < state.deadline:
        return state
    updated = state.model_copy(deep=True)
    if state.phase == Phase.PRESENTATION:
        updated.phase = Phase.BIDDING
        updated.deadline = now + timedelta(seconds=state.rules.interval_seconds)
    elif state.phase == Phase.BIDDING:
        player = state.current_player
        assert player is not None
        if state.leading_team_id is None:
            updated.unsold.append(player.id)
            updated.phase = Phase.UNSOLD
        else:
            require(
                not any(item.player_id == player.id for item in state.purchases), "already_owned"
            )
            team = next(team for team in updated.teams if team.id == state.leading_team_id)
            require(team.purse >= state.current_bid, "insufficient_purse")
            team.purse -= state.current_bid
            updated.purchases.append(
                Purchase(player_id=player.id, team_id=team.id, amount=state.current_bid)
            )
            updated.phase = Phase.SOLD
        updated.deadline = now + timedelta(seconds=state.rules.presentation_seconds)
    elif state.phase in (Phase.SOLD, Phase.UNSOLD):
        updated.lot_index += 1
        updated.current_bid = 0
        updated.leading_team_id = None
        full = all(
            sum(item.team_id == team.id for item in state.purchases) >= state.rules.squad_limit
            for team in state.teams
        )
        updated.phase = (
            Phase.COMPLETED
            if full or updated.lot_index >= len(state.players)
            else (Phase.PRESENTATION)
        )
        updated.deadline = (
            None
            if updated.phase == Phase.COMPLETED
            else (now + timedelta(seconds=state.rules.presentation_seconds))
        )
    else:
        return state
    updated.version += 1
    return updated


def recover(state: AuctionState, now: datetime) -> AuctionState:
    if state.deadline is None:
        return state
    updated = state.model_copy(deep=True)
    updated.previous_phase = state.phase
    updated.remaining_seconds = max(0, (state.deadline - now).total_seconds())
    updated.phase = Phase.PAUSED
    updated.deadline = None
    updated.version += 1
    return updated
