# ADR 0001: Local, authoritative modular monolith

Status: accepted for Phase 1.

Flutter/Riverpod handles presentation, not rule authority. FastAPI/Pydantic and
SQLAlchemy/Alembic/PostgreSQL are the fixed backend architecture. Integer rupees,
transactional aggregate locking, immutable data/rules and accepted-event history
make outcomes explainable and recoverable. No second offline auction engine.

One API worker with PostgreSQL-backed timers/state streaming is enough locally;
distributed fanout belongs to multiplayer. Database checks are still necessary
even with one worker. No SQLite fallback for concurrency tests.

Phase 1 rival commands are manually controlled through a trusted developer
harness, explicitly selected by the user. No strategic bot code, friend-room UX,
email auth or score placeholders. Participant capabilities prevent arbitrary
team impersonation without bringing account workflows into Phase 1.

Real-data acceptance is separate from functionality. Authorized CSV import can
bridge unavailable APIs but cannot bypass licensing. No automatic official season
selection, logo reuse or fictional real-player metrics. Test fixtures stay labeled
and isolated. Runtime/data/visual blockers prevent claiming Phase 1 complete.