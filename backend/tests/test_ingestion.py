from pathlib import Path

import pytest
from pydantic import ValidationError

from cricai.dev.__main__ import demo
from cricai.players.ingestion import CsvProvider, PlayerImport


def test_synthetic_fixture_is_explicit_and_statistics_absent() -> None:
    imported = demo()
    assert imported.manifest.test_data
    assert all(player.statistics.matches is None for player in imported.players)
    assert "SYNTHETIC" in imported.manifest.season


def test_production_rejects_missing_rights_and_stats() -> None:
    payload = demo().model_dump(mode="json")
    payload["manifest"]["test_data"] = False
    with pytest.raises(ValidationError, match="reviewed rights"):
        PlayerImport.model_validate(payload)
    payload["manifest"].update(redistribution_reviewed=True, roster_verified=True)
    with pytest.raises(ValidationError, match="statistics need"):
        PlayerImport.model_validate(payload)


def test_duplicate_identity_is_not_merged() -> None:
    payload = demo().model_dump(mode="json")
    payload["players"].append(payload["players"][0])
    with pytest.raises(ValidationError, match="Duplicate player"):
        PlayerImport.model_validate(payload)


def test_csv_validates_boolean_and_reports_row(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text(demo().manifest.model_dump_json(), encoding="utf-8")
    data = tmp_path / "players.csv"
    data.write_text(
        "id,name,role,nationality,overseas,franchise,base_price,price_basis\n"
        "test,Test Player,batter,Test country,unknown,Test Alpha,2000000,game_configured\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="CSV row 2: overseas must"):
        CsvProvider(data, manifest).load()
    data.write_text(data.read_text().replace(",unknown,", ",false,"), encoding="utf-8")
    imported = CsvProvider(data, manifest).load()
    assert imported.players[0].overseas is False
    assert imported.players[0].statistics.runs is None
