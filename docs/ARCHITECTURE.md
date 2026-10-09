# Architecture

## Boundaries

`mobile/` owns Flutter presentation, application state, typed transport and secure
capability storage. `backend/src/cricai/` owns domain rules, services, PostgreSQL
repositories, REST/WebSocket transport and data imports. `docs/` records contracts.
One modular monolith, one API worker initially; no Redis or external LLM needed.

Pure auction decisions accept explicit UTC time and return a new state/event.
Widgets, bots and HTTP handlers do not compute authoritative outcomes.
Money is integral INR rupees. Pydantic validates all external commands; negative,
fractional, boolean and out-of-range monetary inputs are rejected.

## Transactions and synchronization

Lock the auction row before reading current state and authoritative database time
(`clock_timestamp()`, not transaction-start `now()`). Check actor, request ID,
payload hash, expected version, lot ID, state, deadline, budget and composition.
Serialize timer and bid mutations through the same lock. Accept only before the
deadline; queued requests evaluated after it are late.

Persist state, accepted event, ownership/purse projections and idempotent response
atomically. Uniqueness and CHECK constraints defend purchases and purses. Deliver
only committed state. Every update includes monotonic version, server time and
deadline. Clients deduplicate and resnapshot after gaps or reconnect; animated
countdowns are estimates, never authority. Invalid and duplicate bids do not reset
deadlines. An accepted bid resets to acceptance time plus configured interval.

Phase 1 uses durable snapshots/events with polling-based WebSocket delivery, not
a lossy in-memory event bus. Reconnect always fetches a complete current snapshot.
Database events remain an audit record, not a claim of full event sourcing.

## Persistence and recovery

Normalized player identities, season/data snapshots, auction state, participants,
bid/transition events and purchases retain historical inputs. Updates create new
snapshots; completed auctions never follow mutable current statistics.
Purses debit on sale, not when an offer leads. Cancellation preserves purchases
and prior history. Pause stores remaining interval and state; resume rebases it.
Startup recovery pauses interrupted open auctions; elapsed deadlines retain zero
time and must settle before another bid can win. No invented downtime bids.

## Local security

No email accounts yet. A trusted PC-only development token provisions auctions
and participant capabilities. Actor capabilities are hashed at rest, checked on
all commands and never accepted as arbitrary submitted team IDs. The Android app
must not receive the developer token. No public deployment of this development
API. Secrets are excluded from source control and logs. WebSocket authentication
uses an initial message, never a query-string secret. Cleartext is debug-only.

## Extensibility

Providers map to stable internal IDs, source manifests and statistics snapshots.
Future bots consume visible state and submit ordinary commands. Future scoring
uses fixed data/rule/model/scenario inputs; future users claim authorized local
sessions without replacing financial persistence. Custom rules require new
validated versions, not runtime mutation of an ongoing auction.