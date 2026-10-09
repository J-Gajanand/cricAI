import argparse
import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from pydantic import HttpUrl
from sqlalchemy.orm import Session

from cricai.auction.domain import Player, RuleConfig
from cricai.auction.service import AuctionService
from cricai.config import ROOT, Settings
from cricai.db import make_engine
from cricai.players.ingestion import CsvProvider, Manifest, PlayerImport, publish


def initialize() -> None:
    target = ROOT / ".env"
    password = secrets.token_urlsafe(32)
    token = secrets.token_urlsafe(32)
    with target.open("x", encoding="utf-8") as destination:
        destination.write(
            f"POSTGRES_USER=cricai\nPOSTGRES_DB=cricai\nPOSTGRES_PASSWORD={password}\n"
            "POSTGRES_PORT=55432\n"
            f"CRICAI_DATABASE_URL=postgresql+psycopg://cricai:{password}@localhost:55432/cricai\n"
            f"CRICAI_DEV_TOKEN={token}\nCRICAI_ALLOW_TEST_DATA=false\n"
        )
    print("Created private .env with random local credentials; test data remains disabled.")


def demo() -> PlayerImport:
    return PlayerImport(
        manifest=Manifest(
            season="SYNTHETIC TEST DATA",
            source_url=HttpUrl("https://example.invalid/cricai-fixtures"),
            license="Original synthetic test fixtures",
            permission_basis="Project-authored test data",
            retrieved_at=datetime.now(UTC),
            coverage="No real player statistics",
            test_data=True,
        ),
        players=[
            Player(
                id="synthetic-" + str(index),
                name="Synthetic Player " + str(index),
                role="batter" if index % 2 else "bowler",
                nationality="Test country",
                overseas=index % 3 == 0,
                franchise="Test Alpha" if index % 2 else "Test Beta",
            )
            for index in range(1, 7)
        ],
    )


def provision(imported: PlayerImport) -> None:
    settings = Settings()
    if imported.manifest.test_data and not settings.allow_test_data:
        raise SystemExit("Test data disabled. Opt in explicitly with CRICAI_ALLOW_TEST_DATA=true.")
    engine = make_engine(settings.database_url)
    try:
        with Session(engine) as session, session.begin():
            snapshot = publish(session, imported, settings.allow_test_data)
        franchises = sorted({player.franchise for player in imported.players})
        rules = RuleConfig(minimum_squad=0) if imported.manifest.test_data else RuleConfig()
        created = AuctionService(engine, settings.allow_test_data).create(
            snapshot, franchises, rules
        )
        private = ROOT / ".local"
        private.mkdir(exist_ok=True)
        destination = private / (created["auction_id"] + ".json")
        with destination.open("x", encoding="utf-8") as output:
            json.dump(created, output, indent=2)
        print(f"Created auction {created['auction_id']}; private capabilities: {destination}")
        print("Treat that file as a credential. Enter only your participant token in the app.")
    finally:
        engine.dispose()


def send_command(args: argparse.Namespace) -> None:
    saved = json.loads(Path(args.session).read_text(encoding="utf-8"))
    participant = saved["participants"][args.team]
    endpoint = args.api.rstrip("/") + "/v1/auctions/" + saved["auction_id"]
    headers = {"Authorization": "Bearer " + participant["token"]}
    with urlopen(Request(endpoint, headers=headers), timeout=10) as response:
        current = json.load(response)
    if args.kind == "state":
        state = current["state"]
        print(
            json.dumps(
                {
                    "phase": state["phase"],
                    "version": state["version"],
                    "next_bid": current["next_bid"],
                    "deadline": state["deadline"],
                }
            )
        )
        return
    payload = {"kind": args.kind, "expected_version": current["state"]["version"]}
    if args.kind == "bid":
        state = current["state"]
        payload.update(
            player_id=state["players"][state["lot_index"]]["id"], amount=current["next_bid"]
        )
    headers.update({"Content-Type": "application/json", "Idempotency-Key": str(uuid4())})
    try:
        with urlopen(
            Request(
                endpoint + "/commands",
                data=json.dumps(payload).encode(),
                headers=headers,
                method="POST",
            ),
            timeout=10,
        ) as response:
            result = json.load(response)
            print(
                json.dumps(
                    {
                        "phase": result["state"]["phase"],
                        "version": result["state"]["version"],
                        "actor": participant["name"],
                    }
                )
            )
    except HTTPError as error:
        print(error.read().decode())
        raise SystemExit(1) from error


def main() -> None:
    parser = argparse.ArgumentParser(description="cricAI local developer tools")
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("init")
    commands.add_parser("demo", help="Explicit synthetic test auction; no bots")
    importer = commands.add_parser(
        "import", help="Validate authorized CSV and create local auction"
    )
    importer.add_argument("csv", type=Path)
    importer.add_argument("manifest", type=Path)
    sender = commands.add_parser("command", help="Manually control one local participant")
    sender.add_argument("--session", required=True, type=Path)
    sender.add_argument("--team", type=int, default=0, help="Zero-based local participant index")
    sender.add_argument("--api", default="http://127.0.0.1:8000")
    sender.add_argument(
        "--kind", choices=["state", "start", "bid", "pause", "resume", "cancel"], required=True
    )
    args = parser.parse_args()
    if args.action == "init":
        try:
            initialize()
        except FileExistsError:
            print("Existing .env preserved; configure it locally.")
    elif args.action == "demo":
        provision(demo())
    elif args.action == "import":
        provision(CsvProvider(args.csv, args.manifest).load())
    else:
        send_command(args)


if __name__ == "__main__":
    main()
