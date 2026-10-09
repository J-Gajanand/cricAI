import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from pydantic import AwareDatetime, Field, HttpUrl, model_validator
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from cricai.auction.domain import Model, Player, Statistics, require
from cricai.db import DataSnapshot, PlayerIdentity, SnapshotPlayer


class Manifest(Model):
    season: str = Field(min_length=1, max_length=80)
    source_url: HttpUrl
    license: str = Field(min_length=1, max_length=200)
    permission_basis: str = Field(min_length=10, max_length=2000)
    retrieved_at: AwareDatetime
    coverage: str = Field(min_length=1, max_length=1000)
    test_data: bool = False
    redistribution_reviewed: bool = False
    roster_verified: bool = False


class PlayerImport(Model):
    manifest: Manifest
    players: list[Player] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_records(self) -> "PlayerImport":
        if len({player.id for player in self.players}) != len(self.players):
            raise ValueError("Duplicate player identity; do not merge by name")
        if self.manifest.retrieved_at > datetime.now(UTC):
            raise ValueError("Retrieval date cannot be in the future")
        if not self.manifest.test_data:
            if not (self.manifest.redistribution_reviewed and self.manifest.roster_verified):
                raise ValueError("Production imports require reviewed rights and verified rosters")
            if any(
                player.statistics.matches is None or player.statistics.coverage == "not_available"
                for player in self.players
            ):
                raise ValueError("Production player statistics need documented coverage")
        return self


class PlayerDataProvider(Protocol):
    def load(self) -> PlayerImport: ...


class CsvProvider:
    def __init__(self, csv_path: Path, manifest_path: Path):
        self.csv_path = csv_path
        self.manifest_path = manifest_path

    def load(self) -> PlayerImport:
        manifest = Manifest.model_validate_json(self.manifest_path.read_text(encoding="utf-8"))
        players = []
        with self.csv_path.open(encoding="utf-8-sig", newline="") as source:
            for number, row in enumerate(csv.DictReader(source), start=2):
                try:
                    if row["overseas"] not in ("true", "false"):
                        raise ValueError("overseas must be true or false")
                    stats = Statistics(
                        matches=int(row["matches"]) if row.get("matches") else None,
                        runs=int(row["runs"]) if row.get("runs") else None,
                        wickets=int(row["wickets"]) if row.get("wickets") else None,
                        coverage=row.get("statistics_coverage") or "not_available",
                    )
                    players.append(
                        Player.model_validate(
                            {
                                "id": row["id"],
                                "name": row["name"],
                                "role": row["role"],
                                "nationality": row["nationality"],
                                "overseas": row["overseas"] == "true",
                                "franchise": row["franchise"],
                                "base_price": int(row["base_price"]),
                                "price_basis": row["price_basis"],
                                "statistics": stats,
                            }
                        )
                    )
                except (KeyError, ValueError) as error:
                    raise ValueError(f"CSV row {number}: {error}") from error
        return PlayerImport(manifest=manifest, players=players)


def publish(session: Session, imported: PlayerImport, allow_test_data: bool) -> str:
    require(allow_test_data or not imported.manifest.test_data, "test_data_disabled")
    encoded = json.dumps(imported.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    snapshot_id = hashlib.sha256(encoded.encode()).hexdigest()
    session.execute(
        insert(DataSnapshot)
        .values(
            id=snapshot_id,
            manifest=imported.manifest.model_dump(mode="json"),
            created_at=datetime.now(UTC),
        )
        .on_conflict_do_nothing()
    )
    for position, player in enumerate(imported.players):
        session.execute(insert(PlayerIdentity).values(id=player.id).on_conflict_do_nothing())
        session.execute(
            insert(SnapshotPlayer)
            .values(
                snapshot_id=snapshot_id,
                player_id=player.id,
                position=position,
                data=player.model_dump(mode="json"),
            )
            .on_conflict_do_nothing()
        )
    return snapshot_id
