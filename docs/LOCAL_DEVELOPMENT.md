# Local development and manual bidders

## Backend

From `backend`, run `uv sync --locked` then `uv run python -m cricai.dev init`.
Initialization creates a root ignored `.env` with random local credentials and
port 55432; an existing file is never overwritten. Never display its secrets in
chat, source control or diagnostic output. Start `docker compose up -d --wait db`
from the root. From `backend`, `uv run alembic upgrade head` applies migrations.
Run `uv run uvicorn cricai.main:app --host 127.0.0.1 --port 8000` (one worker).
Check `/health` and `/ready`; the latter requires the schema and database.

## Explicit synthetic test mode

No real dataset is bundled. Synthetic records are for local development only.
In each participating PowerShell terminal, set `$env:CRICAI_ALLOW_TEST_DATA='true'`.
Start the backend with that opt-in, then run `uv run python -m cricai.dev demo`.
The private participant file is written under root `.local/`. Do not share it;
each participant should receive only their own capability, never the dev token.
In Android, connect with auction ID and one participant capability. Credentials
are stored using OS-backed secure storage. Team index 0 is the local host.

From `backend`, manually control a participant (replace the session filename):

```powershell
uv run python -m cricai.dev command --session ../.local/<auction-id>.json --team 0 --kind start
uv run python -m cricai.dev command --session ../.local/<auction-id>.json --team 1 --kind bid
uv run python -m cricai.dev command --session ../.local/<auction-id>.json --team 0 --kind pause
uv run python -m cricai.dev command --session ../.local/<auction-id>.json --team 0 --kind resume
```

Commands fetch the current version and submit through the same authenticated
HTTP route used by the app. A racing command may be rejected as stale. Nothing
automatically bids. Use `--kind state` to inspect non-secret current state.
There is no production solo or private-room multiplayer experience yet.

## Authorized player import

`uv run python -m cricai.dev import <players.csv> <manifest.json>` validates and
publishes an immutable snapshot, then creates a local auction from its franchise
names. Required CSV columns:

`id,name,role,nationality,overseas,franchise,base_price,price_basis`

Optional stats columns: `matches,runs,wickets,statistics_coverage`.
Roles: `batter`, `bowler`, `all_rounder`, `wicketkeeper`. Overseas is strictly
`true` or `false`. Prices are integer rupees; price basis is `game_configured`
or `verified_official`. Empty optional numbers remain unknown.

Manifest fields: `season`, `source_url`, `license`, `permission_basis`,
`retrieved_at` (UTC ISO timestamp), `coverage`, `test_data`,
`redistribution_reviewed`, `roster_verified`. Real imports need reviewed rights,
verified roster/eligibility and documented statistics coverage. Assertions must
be backed by retained source evidence; the importer cannot independently prove
that a claimed license is true. Mixed-source packages require a documented
manifest URL covering every contributing source. No private/paid/unlicensed data
is committed. Ten franchises and default rules are required for non-test auctions.

## Tests and shutdown

`uv run pytest` runs domain, import, API and real PostgreSQL tests. Integration
tests create randomly named temporary schemas and drop only those schemas; no
production tables are reset. Missing database configuration skips integration
tests explicitly; a configured but unavailable database fails them.
`uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src` are gates.

Stop Uvicorn with Ctrl+C. `docker compose stop db` preserves the data volume.
Do not use `down -v` on a database containing sessions you wish to preserve.