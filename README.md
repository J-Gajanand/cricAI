# cricAI

Cricket Auction Intelligence. An independent, unofficial cricket auction game;
not affiliated with or endorsed by the IPL, BCCI, or any franchise.

## Development status

Phase 0 and Phase 1 are in progress. Phase 1 uses **developer-controlled rival
bidders**, not bots. No accounts, strategic opponents, scoring reports, private
rooms, paid services, or deployments are included. See
[build progress](docs/BUILD_PROGRESS.md) for verified results and blockers.

## Architecture

Flutter Android client; Python FastAPI modular monolith; PostgreSQL with SQLAlchemy
and Alembic. The backend alone validates bids and determines winners. Prices use
integer INR rupees. See [architecture](docs/ARCHITECTURE.md) and
[requirements](docs/PRODUCT_REQUIREMENTS.md).

## Local setup

Python 3.12-3.14 and uv are required. From `backend` run `uv sync --locked`.
Flutter and an Android SDK/device are separate requirements; no SDK is bundled.
The PostgreSQL Docker image requires a running, appropriately licensed Docker
installation. Native PostgreSQL 17 is also supported; SQLite is not a substitute.

Configure root `.env` using `.env.example`. Set a private local database password,
`CRICAI_DATABASE_URL=postgresql+psycopg://cricai:<url-encoded-password>@localhost:5432/cricai`,
and a cryptographically random `CRICAI_DEV_TOKEN` of at least 32 characters.
Never put these values in tracked files, screenshots, or chat. Keep
`CRICAI_ALLOW_TEST_DATA=false` for real datasets.

From the root: `docker compose up -d db`. From `backend`:
`uv run alembic upgrade head`, then
`uv run uvicorn cricai.main:app --host 127.0.0.1 --port 8000`.
These commands require implementation/runtime gates listed in build progress.

## Android connectivity

The Android emulator reaches the PC at `http://10.0.2.2:8000`. A physical phone
uses the PC's private LAN IP, not the phone's localhost. For trusted private Wi-Fi
only, bind Uvicorn to `0.0.0.0` and permit TCP 8000 on Windows' private firewall
profile. Do not disable the firewall or forward a router port.

Enable Android Developer options and Wireless debugging. Use
`adb pair <phone-ip>:<pairing-port>` and enter the code directly in the terminal,
then `adb connect <phone-ip>:<debugging-port>`. Ports may differ. Check
`adb devices -l` and `flutter devices`. Wireless ADB does not itself expose the API.
An alternative after connecting ADB is `adb reverse tcp:8000 tcp:8000`, with
`http://127.0.0.1:8000` as the device API URL. Use only debug builds for HTTP;
release connectivity must use HTTPS.

## Quality gates

From `backend`: `uv run pytest`, `uv run ruff check .`,
`uv run ruff format --check .`, `uv run mypy src`.
PostgreSQL integration tests require a dedicated test database and must not run
against user data. Flutter analyze, widget tests, Android build and actual screen
review are independent gates; none is implied by Python tests passing.

## Data

No production player pool is bundled. Data needs documented provenance, usage
rights, season coverage, and eligibility. Synthetic test fixtures must never be
represented as real players. See [data sources](docs/DATA_SOURCES.md).